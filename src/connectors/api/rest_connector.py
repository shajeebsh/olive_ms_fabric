from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import (
    fetch_all_pages,
    flatten_struct_cols,
    get_oauth2_token,
    is_circuit_open,
)
from src.config_loader import lakehouse_table
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


API_SOURCE_CONFIGS: dict[str, dict[str, Any]] = {
    "rest_api_lms": {
        "endpoint": "/enrolments",
        "auth_type": "bearer",
        "secret_key": "lms-api-token",
        "delta_param": "updated_since",
        "page_size": 500,
    },
    "rest_api_hr": {
        "endpoint": "/staff",
        "auth_type": "oauth2",
        "secret_key": "hr-client-secret",
        "client_id": "fabric_client",
        "token_url": "https://hr.example.org/oauth/token",
        "delta_param": "modified_after",
        "page_size": 200,
    },
}


class RestApiConnector(BaseConnector):
    connector_type = "rest_api"

    def __init__(
        self,
        source_system: str = "rest_api_lms",
        api_cfg: dict[str, Any] | None = None,
    ):
        super().__init__(source_system=source_system)
        self.api_cfg = api_cfg or {}

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        if is_circuit_open(self.source_system):
            print(
                f"Circuit open for {self.source_system}, skipping."
            )
            return None

        cfg = self.api_cfg
        secrets = get_secrets()
        control_watermark = lakehouse_table(
            config, "bronze", "control_watermark"
        )

        wm_row = spark.sql(
            f"SELECT last_run_ts FROM {control_watermark} "
            f"WHERE source_system = '{self.source_system}' "
            f"LIMIT 1"
        ).first()
        watermark_ts = (
            wm_row["last_run_ts"]
            if wm_row
            else datetime(1900, 1, 1, tzinfo=timezone.utc)
        )
        watermark_value = watermark_ts.isoformat()

        scope = config.get("secret_scope", "")
        if cfg.get("auth_type") == "oauth2":
            token = get_oauth2_token(secrets, self.source_system, {
                **cfg,
                "secret_scope": scope,
            })
        else:
            token = secrets.get(scope, cfg.get("secret_key", ""))

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {
            cfg.get("delta_param", "updated_since"): watermark_value,
            "page_size": cfg.get("page_size", 500),
        }

        records = fetch_all_pages(
            spark, config, self.source_system,
            {**cfg, "base_url": config.get("api_base_url", ""),
             "secret_scope": scope},
            headers, params, watermark_ts,
        )

        if not records:
            print(
                f"No new records for {self.source_system}."
            )
            return None

        df_api = spark.read.json(
            spark.sparkContext.parallelize(
                [json.dumps(r) for r in records]
            )
        )
        df_api = flatten_struct_cols(df_api)

        spark.sql(f"""
            UPDATE {control_watermark}
            SET last_run_ts = current_timestamp(),
                last_batch_id = '{batch_id}',
                last_row_count = {len(records)},
                status = 'SUCCESS',
                updated_at = current_timestamp()
            WHERE source_system = '{self.source_system}'
        """)
        print(
            f"Loaded {len(records)} records "
            f"for {self.source_system}."
        )

        return df_api


def register_connectors(registry, config=None):
    base_url = ""
    scope = ""
    if config:
        base_url = config.get("api_base_url", "")
        scope = config.get("secret_scope", "")

    for source_system, api_cfg in API_SOURCE_CONFIGS.items():
        full_cfg = {
            **api_cfg,
            "base_url": base_url,
            "secret_scope": scope,
        }
        registry.register(
            RestApiConnector(
                source_system=source_system,
                api_cfg=full_cfg,
            )
        )

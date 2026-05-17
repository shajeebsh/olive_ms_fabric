from __future__ import annotations

import json
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import flatten_struct_cols
from src.config_loader import lakehouse_table
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class GhostInspectorConnector(BaseConnector):
    connector_type = "ghost_inspector_api"
    source_system = "ghost_inspector"
    api_key_secret: str = "ghost-inspector-api-key"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        api_key = secrets.get(scope, self.api_key_secret)

        control_watermark = lakehouse_table(
            config, "bronze", "control_watermark"
        )
        wm_row = spark.sql(f"""
            SELECT last_run_ts FROM {control_watermark}
            WHERE source_system = '{self.source_system}'
            LIMIT 1
        """).first()
        since = (
            wm_row["last_run_ts"].isoformat()
            if wm_row else None
        )

        params = {"apiKey": api_key}
        if since:
            params["updatedAfter"] = since

        resp = requests.get(
            "https://api.ghostinspector.com/v1/suites/",
            params=params, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            return None

        rdd = spark.sparkContext.parallelize(
            [json.dumps(r) for r in data]
        )
        df = spark.read.json(rdd)
        df = flatten_struct_cols(df)

        spark.sql(f"""
            UPDATE {control_watermark}
            SET last_run_ts = current_timestamp(),
                last_batch_id = '{batch_id}',
                last_row_count = {len(data)},
                status = 'SUCCESS',
                updated_at = current_timestamp()
            WHERE source_system = '{self.source_system}'
        """)

        return df


def register_connectors(registry, config=None):
    registry.register(GhostInspectorConnector())

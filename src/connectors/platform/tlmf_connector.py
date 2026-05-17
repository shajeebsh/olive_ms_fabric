from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import flatten_struct_cols
from src.config_loader import lakehouse_table
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class TlmfConnector(BaseConnector):
    connector_type = "tlmf_api"
    source_system = "tlmf"
    base_url: str = (
        "https://portal.tlmf.university.ie/api"
    )
    endpoint: str = "/activity"
    secret_key: str = "tlmf-api-key"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        api_key = secrets.get(scope, self.secret_key)

        control_watermark = lakehouse_table(
            config, "bronze", "control_watermark"
        )
        wm_row = spark.sql(f"""
            SELECT last_run_ts FROM {control_watermark}
            WHERE source_system = '{self.source_system}'
            LIMIT 1
        """).first()
        since = (
            wm_row["last_run_ts"]
            if wm_row
            else datetime(1900, 1, 1, tzinfo=timezone.utc)
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        params = {
            "updated_after": since.isoformat(),
            "limit": 1000,
        }

        all_records, offset = [], 0
        while True:
            params["offset"] = offset
            resp = requests.get(
                f"{self.base_url}{self.endpoint}",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            batch = (
                data if isinstance(data, list)
                else data.get("data", [])
            )
            all_records.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

        if not all_records:
            return None

        spark.sql(f"""
            UPDATE {control_watermark}
            SET last_run_ts = current_timestamp(),
                last_batch_id = '{batch_id}',
                last_row_count = {len(all_records)},
                status = 'SUCCESS',
                updated_at = current_timestamp()
            WHERE source_system = '{self.source_system}'
        """)

        rdd = spark.sparkContext.parallelize(
            [json.dumps(r) for r in all_records]
        )
        df = spark.read.json(rdd)
        return flatten_struct_cols(df)


def register_connectors(registry, config=None):
    registry.register(TlmfConnector())

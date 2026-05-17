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


class QuercusConnector(BaseConnector):
    connector_type = "quercus_api"
    source_system = "quercus"
    base_url: str = "https://quercus.university.ie/api/v1"
    endpoint: str = "/students"
    secret_key: str = "quercus-api-key"

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
            "modified_since": since.isoformat(),
            "page_size": 500,
        }

        all_records, page = [], 1
        while True:
            params["page"] = page
            resp = requests.get(
                f"{self.base_url}{self.endpoint}",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results", [])
            all_records.extend(batch)
            if not batch or not data.get("next"):
                break
            page += 1

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
    registry.register(QuercusConnector())

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json, schema_of_json

from src.connectors.base import BaseConnector


class WebhookConnector(BaseConnector):
    connector_type = "webhook"
    source_system = "webhook"
    event_table: str = "Bronze_Lakehouse.bronze_webhook_events"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        df = spark.table(self.event_table).filter(
            col("_batch_id").isNull()
        )
        if df.rdd.isEmpty():
            return None

        sample = (
            df.select("payload").limit(1).first()["payload"]
        )
        schema = schema_of_json(sample)
        df = df.withColumn(
            "payload_parsed",
            from_json(col("payload"), schema),
        )
        for field_name in df.select("payload_parsed.*").columns:
            df = df.withColumn(
                field_name,
                col(f"payload_parsed.{field_name}"),
            )
        return df.drop("payload_parsed")


def register_connectors(registry, config=None):
    registry.register(WebhookConnector())

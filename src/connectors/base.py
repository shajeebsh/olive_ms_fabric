from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import current_timestamp, lit

from src.config_loader import lakehouse_table


@dataclass
class ConnectorResult:
    source_system: str
    batch_id: str
    rows_written: int
    status: str
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):

    connector_type: str = "base"
    source_system: str = "unknown"

    def __init__(self, source_system: str | None = None):
        if source_system is not None:
            self.source_system = source_system

    @abstractmethod
    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        ...

    def _add_audit_cols(
        self, df: DataFrame, batch_id: str
    ) -> DataFrame:
        return (
            df
            .withColumn("_ingested_at", current_timestamp())
            .withColumn("_source_system", lit(self.source_system))
            .withColumn("_connector_type", lit(self.connector_type))
            .withColumn("_batch_id", lit(batch_id))
            .withColumn("_schema_version", lit("1.0"))
        )

    def run(
        self,
        spark: SparkSession,
        config: dict[str, Any],
    ) -> ConnectorResult:
        batch_id = str(uuid.uuid4())
        target = lakehouse_table(
            config, "bronze", f"bronze_{self.source_system}"
        )
        try:
            df_raw = self.extract(spark, config, batch_id)
            if df_raw is None or df_raw.rdd.isEmpty():
                return ConnectorResult(
                    self.source_system, batch_id, 0, "SKIPPED"
                )
            df_bronze = self._add_audit_cols(df_raw, batch_id)
            df_bronze.write.format("delta").mode("append") \
                .option("mergeSchema", "true") \
                .saveAsTable(target)
            rows = df_bronze.count()
            return ConnectorResult(
                self.source_system, batch_id, rows, "SUCCESS"
            )
        except Exception as e:
            return ConnectorResult(
                self.source_system, batch_id, 0,
                "FAILED", error=str(e)
            )

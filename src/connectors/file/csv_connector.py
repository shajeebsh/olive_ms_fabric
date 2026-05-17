from __future__ import annotations

import re
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import input_file_name, lit

from src.connectors.base import BaseConnector
from src.file_ingestion import (
    md5_of_file,
    move_file,
    register_file,
    registry_action,
)
from src.filesystem import get_filesystem


FILE_PATTERN = re.compile(
    r"^[a-z_]+_\d{4}_(0[1-9]|1[0-2])\.csv$"
)


class CsvConnector(BaseConnector):
    connector_type = "file_csv"
    source_system = "csv_import"
    landing_path = "Files/landing/csv/"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        fs = get_filesystem()
        try:
            files = [f for f in fs.ls(self.landing_path)
                     if f.name.endswith(".csv")]
        except Exception:
            print(f"No landing folder found: {self.landing_path}")
            return None

        if not files:
            return None

        dfs = []
        for f in files:
            if not FILE_PATTERN.match(f.name):
                register_file(
                    spark, config, f.name, f.path, f.size,
                    "", self.source_system, "FAILED", batch_id,
                    error="Invalid filename",
                )
                move_file(fs, f.path, "rejected")
                continue

            file_hash = md5_of_file(fs, f.path)
            action = registry_action(
                spark, config, f.name, file_hash
            )

            if action == "DUPLICATE":
                register_file(
                    spark, config, f.name, f.path, f.size,
                    file_hash, self.source_system,
                    "DUPLICATE", batch_id,
                )
                move_file(fs, f.path, "rejected")
                continue

            df = (
                spark.read
                .option("header", "true")
                .option("inferSchema", "false")
                .option("sep", ",")
                .option("encoding", "UTF-8")
                .option("multiLine", "true")
                .option("escape", '"')
                .option("nullValue", "")
                .csv(f.path)
            )

            df_enriched = (
                df
                .withColumn("_source_file", input_file_name())
                .withColumn("_file_hash", lit(file_hash))
                .withColumn(
                    "_is_correction", lit(action == "CORRECTION")
                )
            )

            register_file(
                spark, config, f.name, f.path, f.size,
                file_hash, self.source_system, "SUCCESS",
                batch_id, df.count(),
            )
            move_file(fs, f.path, "processed")
            dfs.append(df_enriched)

        if not dfs:
            return None

        result = dfs[0]
        for d in dfs[1:]:
            result = result.unionByName(d, allowMissingColumns=True)
        return result


def register_connectors(registry, config=None):
    registry.register(CsvConnector())

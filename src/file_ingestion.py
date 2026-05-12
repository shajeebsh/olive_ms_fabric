from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, input_file_name, lit
from src.config_loader import lakehouse_table
from src.filesystem import FileInfo, FileSystem


def md5_of_file(fs: FileSystem, path: str) -> str:
    return fs.md5(path)


def registry_action(
    spark: SparkSession, config: dict, file_name: str, file_hash: str
) -> str:
    registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
    df_registry = spark.table(registry)

    existing_hash = df_registry.filter(
        (col("file_hash_md5") == file_hash) & (col("status") == "SUCCESS")
    ).select("file_name").limit(1)
    if existing_hash.count():
        return "DUPLICATE"

    existing_name = df_registry.filter(
        (col("file_name") == file_name) & (col("status") == "SUCCESS")
    ).select("file_name").limit(1)
    if existing_name.count():
        return "CORRECTION"

    failed_hash = df_registry.filter(
        (col("file_hash_md5") == file_hash) & (col("status") == "FAILED")
    ).select("file_id").limit(1)
    if failed_hash.count():
        return "RETRY"

    return "NEW"


def register_file(
    spark: SparkSession,
    config: dict,
    file_name: str,
    file_path: str,
    file_size: int,
    file_hash: str,
    source: str,
    status: str,
    batch_id: str,
    row_count: int = 0,
    error: Optional[str] = None,
) -> None:
    registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
    now = datetime.now(timezone.utc)
    rows = [
        (
            str(uuid.uuid4()),
            file_name,
            file_path,
            file_size,
            file_hash,
            source,
            now,
            now if status in ("SUCCESS", "DUPLICATE", "CORRECTION") else None,
            row_count,
            status,
            batch_id,
            error,
        )
    ]
    spark.createDataFrame(
        rows,
        "file_id STRING, file_name STRING, file_path STRING, file_size_bytes LONG, "
        "file_hash_md5 STRING, source_system STRING, detected_at TIMESTAMP, "
        "processed_at TIMESTAMP, row_count LONG, status STRING, batch_id STRING, error_message STRING",
    ).write.format("delta").mode("append").saveAsTable(registry)


def log_schema_drift(
    spark: SparkSession,
    config: dict,
    source_system: str,
    file_name: str,
    actual_columns: list[str],
    expected_columns: list[str],
    batch_id: str,
) -> int:
    if not expected_columns:
        return 0

    schema_log = lakehouse_table(config, "bronze", "schema_change_log")
    now = datetime.now(timezone.utc)
    changes = []
    for column_name in actual_columns:
        if column_name not in expected_columns:
            changes.append(
                (
                    str(uuid.uuid4()),
                    source_system,
                    file_name,
                    "NEW_COLUMN",
                    column_name,
                    None,
                    now,
                    batch_id,
                    False,
                )
            )
    for column_name in expected_columns:
        if column_name not in actual_columns:
            changes.append(
                (
                    str(uuid.uuid4()),
                    source_system,
                    file_name,
                    "REMOVED_COLUMN",
                    column_name,
                    column_name,
                    now,
                    batch_id,
                    False,
                )
            )

    if changes:
        spark.createDataFrame(
            changes,
            "change_id STRING, source_system STRING, file_name STRING, change_type STRING, "
            "column_name STRING, previous_value STRING, detected_at TIMESTAMP, batch_id STRING, resolved BOOLEAN",
        ).write.format("delta").mode("append").saveAsTable(schema_log)
    return len(changes)


def move_file(fs: FileSystem, src_path: str, zone: str) -> None:
    file_name = src_path.split("/")[-1]
    source_dir = src_path.split("/")[-2]
    dest = f"Files/{zone}/{source_dir}/{file_name}"
    fs.mkdirs(f"Files/{zone}/{source_dir}/")
    fs.mv(src_path, dest)

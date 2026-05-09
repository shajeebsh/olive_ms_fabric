# NB_01_Create_Control_Tables
# Layer: Setup
# Purpose: Create control tables, file registry, monitoring tables, and Files zones.

from pyspark.sql.functions import col, current_timestamp
from delta.tables import DeltaTable
from src.config_loader import load_config, lakehouse_name, lakehouse_table
from src.filesystem import get_filesystem

config = load_config("DEV")
fs = get_filesystem()

bronze_lh = lakehouse_name(config, "bronze")
silver_lh = lakehouse_name(config, "silver")

spark.sql(f"USE {bronze_lh}")

spark.sql("""
CREATE TABLE IF NOT EXISTS control_watermark (
    source_system STRING NOT NULL,
    last_run_ts TIMESTAMP,
    last_batch_id STRING,
    last_row_count LONG,
    status STRING,
    updated_at TIMESTAMP
) USING DELTA
COMMENT 'Tracks last successful ingest per source'
""")

sources = [
    ("excel_training", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_medical", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_hr", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_facilities", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("rest_api_lms", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("rest_api_hr", "1900-01-01 00:00:00", "INIT", 0, "READY"),
]

df_sources = spark.createDataFrame(
    sources,
    "source_system STRING, last_run_ts STRING, last_batch_id STRING, last_row_count LONG, status STRING",
).withColumn("last_run_ts", col("last_run_ts").cast("timestamp")).withColumn(
    "updated_at", current_timestamp()
)

DeltaTable.forName(spark, f"{bronze_lh}.control_watermark").alias("t").merge(
    df_sources.alias("s"), "t.source_system = s.source_system"
).whenNotMatchedInsertAll().execute()

spark.sql("""
CREATE TABLE IF NOT EXISTS control_pipeline_log (
    log_id STRING,
    pipeline_name STRING,
    source_system STRING,
    batch_id STRING,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    rows_read LONG,
    rows_written LONG,
    status STRING,
    error_message STRING
) USING DELTA
COMMENT 'Audit log for every pipeline and notebook run'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS file_ingestion_registry (
    file_id STRING,
    file_name STRING,
    file_path STRING,
    file_size_bytes LONG,
    file_hash_md5 STRING,
    source_system STRING,
    detected_at TIMESTAMP,
    processed_at TIMESTAMP,
    row_count LONG,
    status STRING,
    batch_id STRING,
    error_message STRING
) USING DELTA
COMMENT 'Registry of every file seen for duplicate detection'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS api_call_log (
    call_id STRING,
    api_name STRING,
    endpoint STRING,
    http_status INT,
    attempt_num INT,
    response_ms LONG,
    records_returned LONG,
    watermark_used TIMESTAMP,
    called_at TIMESTAMP,
    status STRING,
    error_message STRING
) USING DELTA
COMMENT 'Tracks every REST API call for retry, SLA, and failure monitoring'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS schema_change_log (
    change_id STRING,
    source_system STRING,
    file_name STRING,
    change_type STRING,
    column_name STRING,
    previous_value STRING,
    detected_at TIMESTAMP,
    batch_id STRING,
    resolved BOOLEAN
) USING DELTA
COMMENT 'Tracks Excel column header changes between loads'
""")

folders = [
    "Files/landing/training",
    "Files/landing/medical",
    "Files/landing/hr",
    "Files/landing/facilities",
    "Files/processed/training",
    "Files/processed/medical",
    "Files/processed/hr",
    "Files/processed/facilities",
    "Files/rejected/training",
    "Files/rejected/medical",
    "Files/rejected/hr",
    "Files/rejected/facilities",
    "Files/archive",
    "Files/profiling_reports",
    "Files/checkpoints",
    "Files/checkpoints/stream_bronze_to_silver_lms",
]

for folder in folders:
    fs.mkdirs(folder)

spark.sql(f"USE {silver_lh}")

spark.sql("""
CREATE TABLE IF NOT EXISTS control_silver_watermark (
    entity STRING NOT NULL,
    last_run_ts TIMESTAMP,
    rows_merged LONG,
    updated_at TIMESTAMP
) USING DELTA
COMMENT 'Silver transformation watermark per entity'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS dq_log (
    run_id STRING,
    entity STRING,
    check_name STRING,
    description STRING,
    total_rows LONG,
    failed_rows LONG,
    fail_pct DECIMAL(5,2),
    status STRING,
    severity STRING,
    run_ts TIMESTAMP
) USING DELTA
COMMENT 'Data quality check results'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS monitoring_alerts (
    alert_ts TIMESTAMP,
    alert_type STRING,
    entity STRING,
    severity STRING,
    message STRING,
    value DOUBLE,
    threshold DOUBLE,
    status STRING,
    run_ts TIMESTAMP
) USING DELTA
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS monitoring_metrics (
    snapshot_ts TIMESTAMP,
    entity STRING,
    metric_name STRING,
    value DOUBLE,
    threshold DOUBLE,
    unit STRING
) USING DELTA
""")

print("Control tables and folder structure are ready.")

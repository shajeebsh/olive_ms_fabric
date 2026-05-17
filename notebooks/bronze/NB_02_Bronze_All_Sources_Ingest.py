# NB_02_Bronze_All_Sources_Ingest
# Layer: Bronze
# Purpose: Unified ingestion for all source types using the ConnectorRegistry.
#          Replaces NB_02_Bronze_Excel_Ingest and NB_03_Bronze_REST_API_Ingest.
#          Auto-discovers all registered connectors and runs them.

import uuid

from pyspark.sql.functions import current_timestamp

from src.config_loader import load_config
from src.connectors import register_all
from src.connectors.registry import ConnectorRegistry

config = load_config()
registry = ConnectorRegistry()

register_all(registry, config)

enabled_sources = config.get("connectors", {}).get("enabled", None)

results = registry.run_all(spark, config, only=enabled_sources)

summary = registry.summary(results)
print(f"Ingestion complete: {summary}")

log_rows = [
    (
        str(uuid.uuid4()),
        "NB_02_All_Sources",
        r.source_system,
        r.batch_id,
        r.rows_written,
        r.status,
        r.error,
    )
    for r in results
]
spark.createDataFrame(
    log_rows,
    "log_id STRING, pipeline_name STRING, source_system STRING, "
    "batch_id STRING, rows_written LONG, status STRING, "
    "error_message STRING",
).withColumn("end_ts", current_timestamp()) \
 .write.format("delta").mode("append") \
 .saveAsTable("Bronze_Lakehouse.control_pipeline_log")

critical_failures = [
    r for r in results if r.status == "FAILED"
]
if critical_failures:
    names = [r.source_system for r in critical_failures]
    raise Exception(
        f"Connectors failed: {names}. See control_pipeline_log."
    )

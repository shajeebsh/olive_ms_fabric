# NB_08_Monitoring_and_Alerting
# Layer: Operations
# Purpose: Capture monitoring alerts for freshness and DQ failures.

from pyspark.sql.functions import current_timestamp

from src.config_loader import load_config, lakehouse_table

config = load_config("DEV")

control_watermark = lakehouse_table(config, "bronze", "control_watermark")
dq_log_table = lakehouse_table(config, "silver", "dq_log")
api_call_log = lakehouse_table(config, "bronze", "api_call_log")
file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
monitoring_alerts = lakehouse_table(config, "silver", "monitoring_alerts")

alerts = []

freshness = spark.sql(f"""
    SELECT source_system, last_run_ts
    FROM {control_watermark}
    WHERE last_run_ts < current_timestamp() - INTERVAL 26 HOURS
""")

for row in freshness.collect():
    alerts.append((
        "FRESHNESS",
        row["source_system"],
        "HIGH",
        f"No successful load within SLA for {row['source_system']}",
        26.0,
        26.0,
        "OPEN",
    ))

dq_failures = spark.sql(f"""
    SELECT entity, check_name, fail_pct
    FROM {dq_log_table}
    WHERE status = 'FAIL'
      AND run_ts >= current_timestamp() - INTERVAL 30 MINUTES
""")

for row in dq_failures.collect():
    alerts.append((
        "DQ_FAILURE",
        row["entity"],
        "HIGH",
        f"DQ check failed: {row['check_name']}",
        float(row["fail_pct"]),
        0.0,
        "OPEN",
    ))

api_health = spark.sql(f"""
    SELECT api_name,
           sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
           sum(CASE WHEN status = 'RATE_LIMITED' THEN 1 ELSE 0 END) AS rate_limits,
           round(avg(response_ms), 0) AS avg_response_ms
    FROM {api_call_log}
    WHERE called_at >= current_timestamp() - INTERVAL 24 HOURS
    GROUP BY api_name
""")

for row in api_health.collect():
    if row["failures"] and row["failures"] > 0:
        alerts.append((
            "API_FAILURE",
            row["api_name"],
            "HIGH",
            f"{row['failures']} API failures in the last 24h",
            float(row["failures"]),
            0.0,
            "OPEN",
        ))
    if row["rate_limits"] and row["rate_limits"] > 5:
        alerts.append((
            "API_RATE_LIMIT",
            row["api_name"],
            "MEDIUM",
            f"{row['rate_limits']} API rate-limit responses in the last 24h",
            float(row["rate_limits"]),
            5.0,
            "OPEN",
        ))
    if row["avg_response_ms"] and row["avg_response_ms"] > 5000:
        alerts.append((
            "API_SLOW",
            row["api_name"],
            "MEDIUM",
            f"Average response time is {row['avg_response_ms']}ms",
            float(row["avg_response_ms"]),
            5000.0,
            "OPEN",
        ))

file_health = spark.sql(f"""
    SELECT source_system, status, count(*) AS file_count
    FROM {file_ingestion_registry}
    WHERE cast(detected_at AS DATE) = current_date()
    GROUP BY source_system, status
""")

for row in file_health.collect():
    if row["status"] == "DUPLICATE":
        alerts.append((
            "DUPLICATE_FILE",
            row["source_system"],
            "MEDIUM",
            f"{row['file_count']} duplicate file(s) detected today",
            float(row["file_count"]),
            0.0,
            "OPEN",
        ))
    if row["status"] == "FAILED":
        alerts.append((
            "FILE_INGEST_FAILED",
            row["source_system"],
            "HIGH",
            f"{row['file_count']} file ingestion failure(s) today",
            float(row["file_count"]),
            0.0,
            "OPEN",
        ))

if alerts:
    alert_df = spark.createDataFrame(
        alerts,
        "alert_type STRING, entity STRING, severity STRING, message STRING, value DOUBLE, threshold DOUBLE, status STRING",
    ).withColumn("alert_ts", current_timestamp()).withColumn("run_ts", current_timestamp())
    alert_df.write.format("delta").mode("append").saveAsTable(monitoring_alerts)
    print(f"Raised {len(alerts)} alerts.")
else:
    print("No alerts raised.")

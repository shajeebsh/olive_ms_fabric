# NB_08_Monitoring_and_Alerting
# Layer: Operations
# Purpose: Capture monitoring alerts for freshness and DQ failures.

from pyspark.sql.functions import current_timestamp

alerts = []

freshness = spark.sql("""
    SELECT source_system, last_run_ts
    FROM Bronze_Lakehouse.control_watermark
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

dq_failures = spark.sql("""
    SELECT entity, check_name, fail_pct
    FROM Silver_Lakehouse.dq_log
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

if alerts:
    alert_df = spark.createDataFrame(
        alerts,
        "alert_type STRING, entity STRING, severity STRING, message STRING, value DOUBLE, threshold DOUBLE, status STRING",
    ).withColumn("alert_ts", current_timestamp()).withColumn("run_ts", current_timestamp())
    alert_df.write.format("delta").mode("append").saveAsTable("Silver_Lakehouse.monitoring_alerts")
    print(f"Raised {len(alerts)} alerts.")
else:
    print("No alerts raised.")


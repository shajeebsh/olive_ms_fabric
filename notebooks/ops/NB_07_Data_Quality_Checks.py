# NB_07_Data_Quality_Checks
# Layer: Silver
# Purpose: Log data quality results and fail fast on severe issues.

from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.data_quality import dq_check

config = load_config()
dq_log_table = lakehouse_table(config, "silver", "dq_log")

results = []

training = spark.table(lakehouse_table(config, "silver", "silver_training_enrolments"))

results.append(
    dq_check(training, "training_enrolments", "no_null_student_id", "Student id must not be null", col("student_id").isNull())
)
results.append(
    dq_check(training, "training_enrolments", "no_null_course_id", "Course id must not be null", col("course_id").isNull())
)
results.append(
    dq_check(
        training,
        "training_enrolments",
        "score_range_0_100",
        "Score must be between 0 and 100 when supplied",
        col("score_pct").isNotNull() & ((col("score_pct") < 0) | (col("score_pct") > 100)),
    )
)
results.append(
    dq_check(
        training,
        "training_enrolments",
        "enrolment_date_not_future",
        "Enrolment date must not be in the future",
        col("enrolment_date") > current_timestamp().cast("date"),
    )
)

import uuid
from datetime import datetime, timezone

dq_df = spark.createDataFrame(
    [
        (
            r["run_id"],
            r["entity"],
            r["check_name"],
            r["description"],
            r["total_rows"],
            r["failed_rows"],
            r["fail_pct"],
            r["status"],
            r["severity"],
        )
        for r in results
    ],
    "run_id STRING, entity STRING, check_name STRING, description STRING, total_rows LONG, "
    "failed_rows LONG, fail_pct DECIMAL(5,2), status STRING, severity STRING",
).withColumn("run_ts", current_timestamp())

dq_df.write.format("delta").mode("append").saveAsTable(dq_log_table)

if any(r["status"] == "FAIL" for r in results):
    raise Exception("DQ failure detected. Stop downstream Gold processing.")

print("DQ checks complete.")

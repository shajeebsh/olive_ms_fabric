# NB_07_Data_Quality_Checks
# Layer: Silver
# Purpose: Log data quality results and fail fast on severe issues.

import uuid
from pyspark.sql.functions import col, current_timestamp, lit

RUN_ID = str(uuid.uuid4())
results = []


def dq_check(entity, name, description, df, fail_condition, severity="HIGH"):
    total_rows = df.count()
    failed_rows = df.filter(fail_condition).count()
    fail_pct = round(failed_rows / total_rows * 100, 2) if total_rows else 0
    status = "PASS" if failed_rows == 0 else ("WARN" if severity != "HIGH" else "FAIL")
    results.append((RUN_ID, entity, name, description, total_rows, failed_rows, fail_pct, status, severity))
    print(f"{status}: {entity}.{name} failed {failed_rows}/{total_rows}")


training = spark.table("Silver_Lakehouse.silver_training_enrolments")

dq_check("training_enrolments", "no_null_student_id", "Student id must not be null", training, col("student_id").isNull())
dq_check("training_enrolments", "no_null_course_id", "Course id must not be null", training, col("course_id").isNull())
dq_check(
    "training_enrolments",
    "score_range_0_100",
    "Score must be between 0 and 100 when supplied",
    training,
    col("score_pct").isNotNull() & ((col("score_pct") < 0) | (col("score_pct") > 100)),
)
dq_check(
    "training_enrolments",
    "enrolment_date_not_future",
    "Enrolment date must not be in the future",
    training,
    col("enrolment_date") > current_timestamp().cast("date"),
)

dq_df = spark.createDataFrame(
    results,
    "run_id STRING, entity STRING, check_name STRING, description STRING, total_rows LONG, "
    "failed_rows LONG, fail_pct DECIMAL(5,2), status STRING, severity STRING",
).withColumn("run_ts", current_timestamp())

dq_df.write.format("delta").mode("append").saveAsTable("Silver_Lakehouse.dq_log")

if any(row[7] == "FAIL" for row in results):
    raise Exception("DQ failure detected. Stop downstream Gold processing.")

print("DQ checks complete.")


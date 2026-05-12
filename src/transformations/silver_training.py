from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    coalesce,
    col,
    concat_ws,
    current_timestamp,
    lit,
    md5,
    to_date,
    trim,
    upper,
    when,
)


def transform_training_enrolments(df: DataFrame) -> DataFrame:
    if "_source_system" not in df.columns:
        df = df.withColumn("_source_system", lit("unknown"))
    return (
        df.withColumn("student_id", upper(trim(col("StudentID"))))
        .withColumn("course_id", upper(trim(col("CourseCode"))))
        .withColumn("enrolment_date", to_date(col("EnrolDate"), "dd/MM/yyyy"))
        .withColumn("completion_date", to_date(col("CompletionDate"), "dd/MM/yyyy"))
        .withColumn("score_pct", col("Score").cast("decimal(5,2)"))
        .withColumn(
            "enrolment_status",
            when(col("Status") == "C", "Completed")
            .when(col("Status") == "A", "Active")
            .when(col("Status") == "D", "Dropped")
            .otherwise("Unknown"),
        )
        .withColumn("is_completed", col("enrolment_status") == "Completed")
        .withColumn("valid_from", current_timestamp())
        .withColumn("valid_to", lit(None).cast("timestamp"))
        .withColumn("is_current", col("student_id").isNotNull())
        .withColumn("_silver_created", current_timestamp())
        .withColumn("_silver_updated", current_timestamp())
        .withColumn(
            "row_hash",
            md5(
                concat_ws(
                    "|",
                    col("student_id"),
                    col("course_id"),
                    col("enrolment_status"),
                    col("score_pct"),
                )
            ),
        )
        .select(
            "student_id",
            "course_id",
            "enrolment_date",
            "completion_date",
            "score_pct",
            "enrolment_status",
            "is_completed",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "_silver_created",
            "_silver_updated",
            "_source_system",
        )
    )

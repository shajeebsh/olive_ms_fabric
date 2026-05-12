from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    abs as spark_abs, col, current_timestamp, hash as spark_hash, lit,
)


def build_dim_student(training: DataFrame) -> DataFrame:
    return (
        training.select("student_id")
        .dropDuplicates()
        .withColumn("student_key", spark_abs(spark_hash(col("student_id"))))
        .withColumn("is_current", lit(True))
        .withColumn("last_refreshed", current_timestamp())
    )


def build_dim_course(training: DataFrame) -> DataFrame:
    return (
        training.select("course_id")
        .dropDuplicates()
        .withColumn("course_key", spark_abs(spark_hash(col("course_id"))))
        .withColumn("is_current", lit(True))
        .withColumn("last_refreshed", current_timestamp())
    )


def build_fact_training_completion(
    training: DataFrame, dim_student: DataFrame, dim_course: DataFrame
) -> DataFrame:
    return (
        training.alias("f")
        .join(dim_student.alias("s"), "student_id", "left")
        .join(dim_course.alias("c"), "course_id", "left")
        .select(
            col("s.student_key"),
            col("c.course_key"),
            col("f.enrolment_date"),
            col("f.completion_date"),
            col("f.score_pct"),
            col("f.is_completed"),
            col("f.enrolment_status"),
        )
        .withColumn("last_refreshed", current_timestamp())
    )

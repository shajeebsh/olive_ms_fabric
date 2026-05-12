# NB_05_Bronze_to_Silver_Streaming
# Layer: Bronze to Silver
# Purpose: Micro-batch processing using Delta Change Data Feed.

from delta.tables import DeltaTable
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

from src.config_loader import load_config, lakehouse_table

config = load_config()
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_lms_enrolments")
SILVER_TABLE = lakehouse_table(config, "silver", "silver_lms_enrolments")


def transform_to_silver(batch_df, batch_id):
    # Only inserts and post-update images from CDF
    df_new = batch_df.filter(
        col("_change_type").isin("insert", "update_postimage")
    )
    if df_new.rdd.isEmpty():
        return

    # Drop CDF system columns before writing
    cdf_cols = [c for c in
                ["_change_type", "_commit_version", "_commit_timestamp"]
                if c in df_new.columns]
    df_new = df_new.drop(*cdf_cols)

    # Apply LMS-specific column mapping (API uses snake_case)
    df_silver = (
        df_new
        .withColumn("student_id",
                    upper(trim(col("student_id"))))
        .withColumn("course_id",
                    upper(trim(col("course_code"))))
        .withColumn("enrolment_date",
                    to_date(col("enrol_date"), "yyyy-MM-dd"))
        .withColumn("enrolment_status",
                    when(col("status") == "C", "Completed")
                    .when(col("status") == "A", "Active")
                    .when(col("status") == "D", "Dropped")
                    .otherwise("Unknown"))
        .withColumn("is_completed",
                    col("enrolment_status") == "Completed")
        .withColumn("is_current", lit(True))
        .withColumn("valid_from", current_timestamp())
        .withColumn("valid_to", lit(None).cast("timestamp"))
        .withColumn("_silver_ingested_at", current_timestamp())
        .withColumn("_stream_batch_id", lit(str(batch_id)))
        .withColumn("row_hash", md5(concat_ws("|",
                    coalesce(col("student_id"), lit("")),
                    coalesce(col("course_id"), lit("")),
                    coalesce(col("enrolment_status"), lit(""))
                                              )))
    )

    target = DeltaTable.forName(spark, SILVER_TABLE)
    target.alias("t").merge(
        df_silver.alias("s"),
        "t.student_id = s.student_id "
        "AND t.course_id = s.course_id "
        "AND t.is_current = true"
    ).whenMatchedUpdate(
        condition="t.row_hash <> s.row_hash",
        set={
            "enrolment_status": "s.enrolment_status",
            "is_completed": "s.is_completed",
            "row_hash": "s.row_hash",
            "_silver_ingested_at": "s._silver_ingested_at",
        }
    ).whenNotMatchedInsertAll().execute()


df_stream = (
    spark.readStream.format("delta")
    .option("readChangeFeed", "true")
    .option("startingVersion", "latest")
    .table(BRONZE_TABLE)
)

query = (
    df_stream.writeStream.foreachBatch(transform_to_silver)
    .option("checkpointLocation", "Files/checkpoints/bronze_to_silver_lms")
    .trigger(processingTime="15 minutes")
    .start()
)

query.awaitTermination(timeout=900)

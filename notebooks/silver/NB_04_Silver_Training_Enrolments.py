# NB_04_Silver_Training_Enrolments
# Layer: Silver
# Purpose: Clean and upsert training enrolments from Bronze to Silver.

from delta.tables import DeltaTable
from pyspark.sql.functions import col, concat_ws, current_timestamp, lit, md5, to_date, trim, upper, when

ENTITY = "training_enrolments"
TARGET_TABLE = "Silver_Lakehouse.silver_training_enrolments"

df_bronze = spark.sql(f"""
    SELECT *
    FROM Bronze_Lakehouse.bronze_training_enrolments
    WHERE _ingested_at > (
        SELECT coalesce(max(last_run_ts), timestamp('1900-01-01'))
        FROM Silver_Lakehouse.control_silver_watermark
        WHERE entity = '{ENTITY}'
    )
""")

df_silver = (
    df_bronze.withColumn("student_id", upper(trim(col("StudentID"))))
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
        md5(concat_ws("|", col("student_id"), col("course_id"), col("enrolment_status"), col("score_pct"))),
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

if not spark.catalog.tableExists(TARGET_TABLE):
    df_silver.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)
else:
    target = DeltaTable.forName(spark, TARGET_TABLE)
    target.alias("t").merge(
        df_silver.alias("s"),
        "t.student_id = s.student_id AND t.course_id = s.course_id AND t.is_current = true",
    ).whenMatchedUpdate(
        condition="t.row_hash <> s.row_hash",
        set={
            "valid_to": "current_timestamp()",
            "is_current": "false",
            "_silver_updated": "current_timestamp()",
        },
    ).whenNotMatchedInsertAll().execute()

rows_merged = df_silver.count()

spark.sql(f"""
    MERGE INTO Silver_Lakehouse.control_silver_watermark t
    USING (
        SELECT '{ENTITY}' AS entity,
               current_timestamp() AS last_run_ts,
               {rows_merged} AS rows_merged,
               current_timestamp() AS updated_at
    ) s
    ON t.entity = s.entity
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

print(f"Silver transformation complete for {ENTITY}: {rows_merged} rows considered.")

# NB_04_Silver_Training_Enrolments
# Layer: Silver
# Purpose: Clean and upsert training enrolments from Bronze to Silver.

from delta.tables import DeltaTable
from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.transformations.silver_training import transform_training_enrolments

config = load_config()

ENTITY = "training_enrolments"
TARGET_TABLE = lakehouse_table(config, "silver", "silver_training_enrolments")
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_training_enrolments")
SILVER_WATERMARK = lakehouse_table(config, "silver", "control_silver_watermark")

df_bronze = spark.sql(f"""
    SELECT *
    FROM {BRONZE_TABLE}
    WHERE _ingested_at > (
        SELECT coalesce(max(last_run_ts), timestamp('1900-01-01'))
        FROM {SILVER_WATERMARK}
        WHERE entity = '{ENTITY}'
    )
""")

df_silver = transform_training_enrolments(df_bronze)

if not spark.catalog.tableExists(TARGET_TABLE):
    df_silver.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)
else:
    target = DeltaTable.forName(spark, TARGET_TABLE)

    target.alias("t").merge(
        df_silver.alias("s"),
        "t.student_id = s.student_id "
        "AND t.course_id = s.course_id "
        "AND t.is_current = true "
        "AND t.row_hash <> s.row_hash",
    ).whenMatchedUpdate(set={
        "valid_to": "current_timestamp()",
        "is_current": "false",
        "_silver_updated": "current_timestamp()",
    }).execute()

    df_to_insert = df_silver.alias("s").join(
        spark.table(TARGET_TABLE).filter("is_current = true").alias("t"),
        (col("s.student_id") == col("t.student_id")) &
        (col("s.course_id") == col("t.course_id")),
        "left_anti"
    )
    df_to_insert.write.format("delta").mode("append").saveAsTable(TARGET_TABLE)

rows_merged = df_silver.count()

spark.sql(f"""
    MERGE INTO {SILVER_WATERMARK} t
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

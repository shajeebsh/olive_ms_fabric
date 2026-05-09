# NB_09_PowerBI_Semantic_Model_Prep
# Layer: Gold
# Purpose: Build Power BI-ready summary tables.

from pyspark.sql.functions import avg, col, count, current_timestamp, round as spark_round, sum as spark_sum, when

summary = spark.sql("""
    SELECT
        c.course_id,
        count(*) AS total_enrolments,
        sum(CASE WHEN f.is_completed THEN 1 ELSE 0 END) AS completed_count,
        round(avg(f.score_pct), 2) AS avg_score,
        round(sum(CASE WHEN f.is_completed THEN 1.0 ELSE 0 END) / count(*) * 100, 2) AS completion_rate_pct
    FROM Gold_Lakehouse.fact_training_completion f
    LEFT JOIN Gold_Lakehouse.dim_course c ON f.course_key = c.course_key
    GROUP BY c.course_id
""").withColumn("last_refreshed", current_timestamp())

summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "Gold_Lakehouse.vw_training_summary"
)

file_ingestion_summary = spark.sql("""
    SELECT
        cast(detected_at AS DATE) AS load_date,
        source_system,
        status,
        count(*) AS file_count,
        sum(row_count) AS total_rows,
        max(detected_at) AS last_seen
    FROM Bronze_Lakehouse.file_ingestion_registry
    WHERE cast(detected_at AS DATE) >= current_date() - 30
    GROUP BY cast(detected_at AS DATE), source_system, status
""")

file_ingestion_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "Gold_Lakehouse.vw_file_ingestion_summary"
)

required_tables = [
    "Gold_Lakehouse.dim_student",
    "Gold_Lakehouse.dim_course",
    "Gold_Lakehouse.fact_training_completion",
    "Gold_Lakehouse.vw_training_summary",
    "Gold_Lakehouse.vw_file_ingestion_summary",
]

for table_name in required_tables:
    rows = spark.table(table_name).count()
    print(f"{table_name}: {rows} rows")

print("Power BI semantic model prep complete.")

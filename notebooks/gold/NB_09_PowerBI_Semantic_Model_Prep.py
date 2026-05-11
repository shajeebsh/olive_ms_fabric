# NB_09_PowerBI_Semantic_Model_Prep
# Layer: Gold
# Purpose: Build Power BI-ready summary tables.

from pyspark.sql.functions import avg, col, count, current_timestamp, round as spark_round, sum as spark_sum, when

from src.config_loader import load_config, lakehouse_table

config = load_config()

fact_table = lakehouse_table(config, "gold", "fact_training_completion")
dim_course_table = lakehouse_table(config, "gold", "dim_course")
vw_summary = lakehouse_table(config, "gold", "vw_training_summary")
file_ingestion_summary_table = lakehouse_table(config, "gold", "vw_file_ingestion_summary")
file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")

summary = spark.sql(f"""
    SELECT
        c.course_id,
        count(*) AS total_enrolments,
        sum(CASE WHEN f.is_completed THEN 1 ELSE 0 END) AS completed_count,
        round(avg(f.score_pct), 2) AS avg_score,
        round(sum(CASE WHEN f.is_completed THEN 1.0 ELSE 0 END) / count(*) * 100, 2) AS completion_rate_pct
    FROM {fact_table} f
    LEFT JOIN {dim_course_table} c ON f.course_key = c.course_key
    GROUP BY c.course_id
""").withColumn("last_refreshed", current_timestamp())

summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(vw_summary)

file_ingestion_summary = spark.sql(f"""
    SELECT
        cast(detected_at AS DATE) AS load_date,
        source_system,
        status,
        count(*) AS file_count,
        sum(row_count) AS total_rows,
        max(detected_at) AS last_seen
    FROM {file_ingestion_registry}
    WHERE cast(detected_at AS DATE) >= current_date() - 30
    GROUP BY cast(detected_at AS DATE), source_system, status
""")

file_ingestion_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    file_ingestion_summary_table
)

required_tables = [
    lakehouse_table(config, "gold", "dim_student"),
    lakehouse_table(config, "gold", "dim_course"),
    lakehouse_table(config, "gold", "fact_training_completion"),
    vw_summary,
    file_ingestion_summary_table,
]

for table_name in required_tables:
    rows = spark.table(table_name).count()
    print(f"{table_name}: {rows} rows")

print("Power BI semantic model prep complete.")

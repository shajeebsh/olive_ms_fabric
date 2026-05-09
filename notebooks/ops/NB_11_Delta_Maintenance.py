# NB_11_Delta_Maintenance
# Layer: All
# Purpose: Weekly Delta housekeeping.

VACUUM_HOURS = 168

TABLES = [
    ("Bronze_Lakehouse.bronze_training_enrolments", None),
    ("Bronze_Lakehouse.bronze_lms_enrolments", None),
    ("Bronze_Lakehouse.file_ingestion_registry", ["source_system"]),
    ("Bronze_Lakehouse.api_call_log", ["api_name"]),
    ("Silver_Lakehouse.silver_training_enrolments", ["student_id", "course_id"]),
    ("Silver_Lakehouse.dq_log", ["entity"]),
    ("Gold_Lakehouse.fact_training_completion", ["student_key", "course_key"]),
    ("Gold_Lakehouse.dim_student", ["student_id"]),
    ("Gold_Lakehouse.dim_course", ["course_id"]),
]

for table_name, zorder_columns in TABLES:
    print(f"Maintaining {table_name}")
    spark.sql(f"VACUUM {table_name} RETAIN {VACUUM_HOURS} HOURS")
    if zorder_columns:
        zorder_sql = ", ".join(zorder_columns)
        spark.sql(f"OPTIMIZE {table_name} ZORDER BY ({zorder_sql})")
    spark.sql(f"ANALYZE TABLE {table_name} COMPUTE STATISTICS")

spark.sql("""
CREATE TABLE IF NOT EXISTS Bronze_Lakehouse.file_ingestion_registry_archive
USING DELTA AS
SELECT * FROM Bronze_Lakehouse.file_ingestion_registry WHERE 1 = 0
""")

archive_count = spark.sql("""
    SELECT count(*) AS row_count
    FROM Bronze_Lakehouse.file_ingestion_registry
    WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
""").first()["row_count"]

if archive_count:
    spark.sql("""
        INSERT INTO Bronze_Lakehouse.file_ingestion_registry_archive
        SELECT *
        FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    spark.sql("""
        DELETE FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    print(f"Archived {archive_count} file registry rows older than 90 days.")

print("Delta maintenance complete.")

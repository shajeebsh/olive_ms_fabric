# NB_11_Delta_Maintenance
# Layer: All
# Purpose: Weekly Delta housekeeping.

from src.config_loader import load_config, lakehouse_table

config = load_config("DEV")

VACUUM_HOURS = 168

TABLES = [
    (lakehouse_table(config, "bronze", "bronze_training_enrolments"), None),
    (lakehouse_table(config, "bronze", "bronze_lms_enrolments"), None),
    (lakehouse_table(config, "bronze", "file_ingestion_registry"), ["source_system"]),
    (lakehouse_table(config, "bronze", "api_call_log"), ["api_name"]),
    (lakehouse_table(config, "silver", "silver_training_enrolments"), ["student_id", "course_id"]),
    (lakehouse_table(config, "silver", "dq_log"), ["entity"]),
    (lakehouse_table(config, "gold", "fact_training_completion"), ["student_key", "course_key"]),
    (lakehouse_table(config, "gold", "dim_student"), ["student_id"]),
    (lakehouse_table(config, "gold", "dim_course"), ["course_id"]),
]

for table_name, zorder_columns in TABLES:
    print(f"Maintaining {table_name}")
    spark.sql(f"VACUUM {table_name} RETAIN {VACUUM_HOURS} HOURS")
    if zorder_columns:
        zorder_sql = ", ".join(zorder_columns)
        spark.sql(f"OPTIMIZE {table_name} ZORDER BY ({zorder_sql})")
    spark.sql(f"ANALYZE TABLE {table_name} COMPUTE STATISTICS")

file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
file_ingestion_registry_archive = lakehouse_table(config, "bronze", "file_ingestion_registry_archive")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {file_ingestion_registry_archive}
    USING DELTA AS
    SELECT * FROM {file_ingestion_registry} WHERE 1 = 0
""")

archive_count = spark.sql(f"""
    SELECT count(*) AS row_count
    FROM {file_ingestion_registry}
    WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
""").first()["row_count"]

if archive_count:
    spark.sql(f"""
        INSERT INTO {file_ingestion_registry_archive}
        SELECT *
        FROM {file_ingestion_registry}
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    spark.sql(f"""
        DELETE FROM {file_ingestion_registry}
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    print(f"Archived {archive_count} file registry rows older than 90 days.")

print("Delta maintenance complete.")

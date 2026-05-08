# NB_11_Delta_Maintenance
# Layer: All
# Purpose: Weekly Delta housekeeping.

VACUUM_HOURS = 168

TABLES = [
    ("Bronze_Lakehouse.bronze_training_enrolments", None),
    ("Bronze_Lakehouse.bronze_lms_enrolments", None),
    ("Silver_Lakehouse.silver_training_enrolments", ["student_id", "course_id"]),
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

print("Delta maintenance complete.")


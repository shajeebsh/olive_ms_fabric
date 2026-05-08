# NB_00_Data_Profiling
# Layer: Pre-Bronze
# Purpose: Profile source files before production ingestion is designed.

from pyspark.sql.functions import col, count, when, countDistinct
from pyspark.sql.types import StringType
import json

SOURCE_PATH = "Files/raw/profiling/"
REPORT_PATH = "Files/profiling_reports/"


def null_blank_rate(df):
    total = df.count()
    result = {}
    for column_name in df.columns:
        null_count = df.filter(
            col(column_name).isNull() | (col(column_name).cast(StringType()) == "")
        ).count()
        result[column_name] = {
            "null_count": null_count,
            "null_pct": round(null_count / total * 100, 2) if total else 0,
            "total_rows": total,
        }
    return result


def find_duplicates(df, key_columns):
    return (
        df.groupBy(key_columns)
        .count()
        .filter("count > 1")
        .orderBy("count", ascending=False)
    )


df_excel = (
    spark.read.format("com.crealytics.spark.excel")
    .option("header", "true")
    .option("inferSchema", "false")
    .option("dataAddress", "Sheet1!A1")
    .load(f"{SOURCE_PATH}training_enrolments_sample.xlsx")
)

print(f"Rows: {df_excel.count()}")
print(f"Columns: {df_excel.columns}")
df_excel.printSchema()

null_report = null_blank_rate(df_excel)
for column_name, stats in null_report.items():
    flag = " HIGH_NULL" if stats["null_pct"] > 10 else ""
    print(f"{column_name}: {stats['null_pct']}%{flag}")

find_duplicates(df_excel, ["StudentID", "CourseCode"]).show(20, truncate=False)
df_excel.groupBy("Status").count().orderBy("count", ascending=False).show()

report = {
    "training_excel": {
        "rows": df_excel.count(),
        "columns": len(df_excel.columns),
        "nulls": null_report,
    }
}

spark.sparkContext.parallelize([json.dumps(report, indent=2)]).saveAsTextFile(
    f"{REPORT_PATH}profile_{spark._sc.applicationId}"
)


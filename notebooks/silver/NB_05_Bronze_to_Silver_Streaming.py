# NB_05_Bronze_to_Silver_Streaming
# Layer: Bronze to Silver
# Purpose: Micro-batch processing using Delta Change Data Feed.

from delta.tables import DeltaTable
from pyspark.sql.functions import col, concat_ws, md5, to_date, trim, upper


def transform_to_silver(batch_df, batch_id):
    df_silver = (
        batch_df.filter(col("_change_type").isin("insert", "update_postimage"))
        .withColumn("student_id", upper(trim(col("student_id"))))
        .withColumn("course_id", upper(trim(col("course_code"))))
        .withColumn("enrolment_date", to_date(col("enrol_date"), "yyyy-MM-dd"))
        .withColumn("row_hash", md5(concat_ws("|", col("student_id"), col("course_id"), col("enrolment_date"))))
    )

    target = DeltaTable.forName(spark, "Silver_Lakehouse.silver_lms_enrolments")
    target.alias("t").merge(
        df_silver.alias("s"),
        "t.student_id = s.student_id AND t.course_id = s.course_id",
    ).whenMatchedUpdateAll(condition="t.row_hash <> s.row_hash").whenNotMatchedInsertAll().execute()


df_stream = (
    spark.readStream.format("delta")
    .option("readChangeFeed", "true")
    .option("startingVersion", "latest")
    .table("Bronze_Lakehouse.bronze_lms_enrolments")
)

query = (
    df_stream.writeStream.foreachBatch(transform_to_silver)
    .option("checkpointLocation", "Files/checkpoints/bronze_to_silver_lms")
    .trigger(processingTime="15 minutes")
    .start()
)

query.awaitTermination(timeout=900)


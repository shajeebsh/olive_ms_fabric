# NB_05_Bronze_to_Silver_Streaming
# Layer: Bronze to Silver
# Purpose: Micro-batch processing using Delta Change Data Feed.

from pyspark.sql.functions import col, current_timestamp, lit

from src.config_loader import load_config, lakehouse_table

config = load_config()
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_lms_enrolments")
SILVER_TABLE = lakehouse_table(config, "silver", "silver_lms_enrolments")


def transform_to_silver(batch_df, batch_id):
    df_silver = (
        batch_df.filter(col("_change_type").isin("insert", "update_postimage"))
        .withColumn("_silver_ingested_at", current_timestamp())
        .withColumn("_stream_batch_id", lit(batch_id))
        .drop("_change_type", "_commit_version", "_commit_timestamp")
    )
    df_silver.write.format("delta").mode("append").saveAsTable(SILVER_TABLE)


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

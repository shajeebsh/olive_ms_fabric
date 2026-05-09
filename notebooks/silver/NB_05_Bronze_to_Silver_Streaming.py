# NB_05_Bronze_to_Silver_Streaming
# Layer: Bronze to Silver
# Purpose: Micro-batch processing using Delta Change Data Feed.

from delta.tables import DeltaTable
from pyspark.sql.functions import col

from src.config_loader import load_config, lakehouse_table
from src.transformations.silver_training import transform_training_enrolments

config = load_config("DEV")
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_lms_enrolments")
SILVER_TABLE = lakehouse_table(config, "silver", "silver_lms_enrolments")


def transform_to_silver(batch_df, batch_id):
    df_silver = (
        batch_df.filter(col("_change_type").isin("insert", "update_postimage"))
    )
    df_transformed = transform_training_enrolments(df_silver)

    target = DeltaTable.forName(spark, SILVER_TABLE)
    target.alias("t").merge(
        df_transformed.alias("s"),
        "t.student_id = s.student_id AND t.course_id = s.course_id",
    ).whenMatchedUpdateAll(condition="t.row_hash <> s.row_hash").whenNotMatchedInsertAll().execute()


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

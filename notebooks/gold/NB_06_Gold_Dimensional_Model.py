# NB_06_Gold_Dimensional_Model
# Layer: Gold
# Purpose: Build starter Gold dimensions and facts.

from pyspark.sql.functions import col, current_timestamp, monotonically_increasing_id, year, month, dayofmonth, quarter, to_date

training = spark.table("Silver_Lakehouse.silver_training_enrolments").filter(col("is_current") == True)

dim_student = (
    training.select("student_id")
    .dropDuplicates()
    .withColumn("student_key", monotonically_increasing_id())
    .withColumn("is_current", col("student_id").isNotNull())
    .withColumn("last_refreshed", current_timestamp())
)
dim_student.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("Gold_Lakehouse.dim_student")

dim_course = (
    training.select("course_id")
    .dropDuplicates()
    .withColumn("course_key", monotonically_increasing_id())
    .withColumn("is_current", col("course_id").isNotNull())
    .withColumn("last_refreshed", current_timestamp())
)
dim_course.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("Gold_Lakehouse.dim_course")

fact_training_completion = (
    training.alias("f")
    .join(dim_student.alias("s"), "student_id", "left")
    .join(dim_course.alias("c"), "course_id", "left")
    .select(
        col("s.student_key"),
        col("c.course_key"),
        col("f.enrolment_date"),
        col("f.completion_date"),
        col("f.score_pct"),
        col("f.is_completed"),
        col("f.enrolment_status"),
    )
    .withColumn("last_refreshed", current_timestamp())
)
fact_training_completion.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "Gold_Lakehouse.fact_training_completion"
)

print("Gold starter model complete.")


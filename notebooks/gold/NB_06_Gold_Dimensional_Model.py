# NB_06_Gold_Dimensional_Model
# Layer: Gold
# Purpose: Build starter Gold dimensions and facts.

from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.gold_dimensional import build_dim_student, build_dim_course, build_fact_training_completion

config = load_config("DEV")

training = spark.table(lakehouse_table(config, "silver", "silver_training_enrolments")).filter(col("is_current") == True)

dim_student = build_dim_student(training)
dim_student.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "dim_student")
)

dim_course = build_dim_course(training)
dim_course.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "dim_course")
)

fact_training_completion = build_fact_training_completion(training, dim_student, dim_course)
fact_training_completion.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "fact_training_completion")
)

print("Gold starter model complete.")

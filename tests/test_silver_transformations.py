import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType

from src.transformations.silver_training import transform_training_enrolments


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder \
        .appName("unit-tests") \
        .master("local[*]") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()


class TestTransformTrainingEnrolments:

    def test_standard_case(self, spark):
        data = [("  S123  ", "C001", "01/01/2023", "01/02/2023", "85.5", "C")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["student_id"] == "S123"
        assert row["course_id"] == "C001"
        assert str(row["enrolment_date"]) == "2023-01-01"
        assert str(row["completion_date"]) == "2023-02-01"
        assert row["score_pct"] == 85.50
        assert row["enrolment_status"] == "Completed"
        assert row["is_completed"] is True
        assert row["row_hash"] is not None

    def test_trim_and_upper(self, spark):
        data = [("  abc123  ", "  XYZ  ", "01/01/2023", None, None, "A")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["student_id"] == "ABC123"
        assert row["course_id"] == "XYZ"

    def test_status_mapping(self, spark):
        data = [
            ("S1", "C1", "01/01/2023", None, None, "C"),
            ("S2", "C2", "01/01/2023", None, None, "A"),
            ("S3", "C3", "01/01/2023", None, None, "D"),
            ("S4", "C4", "01/01/2023", None, None, "X"),
        ]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        rows = {r["student_id"]: r for r in df_output.collect()}

        assert rows["S1"]["enrolment_status"] == "Completed"
        assert rows["S1"]["is_completed"] is True
        assert rows["S2"]["enrolment_status"] == "Active"
        assert rows["S2"]["is_completed"] is False
        assert rows["S3"]["enrolment_status"] == "Dropped"
        assert rows["S3"]["is_completed"] is False
        assert rows["S4"]["enrolment_status"] == "Unknown"
        assert rows["S4"]["is_completed"] is False

    def test_null_score_cast_to_zero(self, spark):
        data = [("S1", "C1", "01/01/2023", None, None, "C")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["score_pct"] == 0.0

    def test_empty_input_does_not_crash(self, spark):
        schema = StructType([
            StructField("StudentID", StringType()),
            StructField("CourseCode", StringType()),
            StructField("EnrolDate", StringType()),
            StructField("CompletionDate", StringType()),
            StructField("Score", StringType()),
            StructField("Status", StringType()),
        ])
        df_input = spark.createDataFrame([], schema)

        df_output = transform_training_enrolments(df_input)

        assert df_output.count() == 0

    def test_row_hash_changes_on_data_change(self, spark):
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        data_a = [("S1", "C1", "01/01/2023", None, "80", "C")]
        data_b = [("S1", "C1", "01/01/2023", None, "90", "C")]

        hash_a = transform_training_enrolments(spark.createDataFrame(data_a, schema)).collect()[0]["row_hash"]
        hash_b = transform_training_enrolments(spark.createDataFrame(data_b, schema)).collect()[0]["row_hash"]

        assert hash_a != hash_b

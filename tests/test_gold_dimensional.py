import pytest
from pyspark.sql import SparkSession

from src.gold_dimensional import build_dim_student, build_dim_course, build_fact_training_completion


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[*]").appName("test-gold").getOrCreate()


@pytest.fixture
def training(spark):
    return spark.createDataFrame([
        ("S001", "C001", "2023-01-01", "2023-02-01", 85.5, True, "Completed", "lms"),
        ("S001", "C002", "2023-03-01", None, None, False, "Active", "lms"),
        ("S002", "C001", "2023-01-15", "2023-03-01", 92.0, True, "Completed", "lms"),
    ], ["student_id", "course_id", "enrolment_date", "completion_date",
        "score_pct", "is_completed", "enrolment_status", "_source_system"])


class TestGoldDimensional:

    def test_build_dim_student_deduplicates(self, training):
        dim = build_dim_student(training)
        rows = dim.collect()
        assert len(rows) == 2
        ids = {r["student_id"] for r in rows}
        assert ids == {"S001", "S002"}

    def test_build_dim_student_has_key(self, training):
        dim = build_dim_student(training)
        assert "student_key" in dim.columns
        keys = [r["student_key"] for r in dim.collect()]
        assert all(k > 0 for k in keys)

    def test_build_dim_student_columns(self, training):
        dim = build_dim_student(training)
        cols = set(dim.columns)
        assert "student_id" in cols
        assert "student_key" in cols
        assert "is_current" in cols
        assert "last_refreshed" in cols

    def test_build_dim_course_deduplicates(self, training):
        dim = build_dim_course(training)
        rows = dim.collect()
        assert len(rows) == 2
        ids = {r["course_id"] for r in rows}
        assert ids == {"C001", "C002"}

    def test_build_dim_course_columns(self, training):
        dim = build_dim_course(training)
        cols = set(dim.columns)
        assert "course_id" in cols
        assert "course_key" in cols
        assert "is_current" in cols
        assert "last_refreshed" in cols

    def test_build_fact_joins_dims(self, training):
        dim_s = build_dim_student(training)
        dim_c = build_dim_course(training)
        fact = build_fact_training_completion(training, dim_s, dim_c)
        rows = fact.collect()
        assert len(rows) == 3
        cols = set(fact.columns)
        assert "student_key" in cols
        assert "course_key" in cols
        assert "enrolment_date" in cols
        assert "score_pct" in cols

    def test_fact_has_no_null_keys(self, training):
        dim_s = build_dim_student(training)
        dim_c = build_dim_course(training)
        fact = build_fact_training_completion(training, dim_s, dim_c)
        null_keys = fact.filter("student_key IS NULL OR course_key IS NULL").count()
        assert null_keys == 0

    def test_empty_training(self, spark):
        from pyspark.sql.types import StructType, StructField, StringType
        schema = StructType([
            StructField("student_id", StringType()),
            StructField("course_id", StringType()),
        ])
        df = spark.createDataFrame([], schema)
        dim = build_dim_student(df)
        assert dim.count() == 0

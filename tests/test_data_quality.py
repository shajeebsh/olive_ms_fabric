import pytest
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

from src.data_quality import dq_check


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[*]").appName("test-dq").getOrCreate()


class TestDqCheck:

    def test_pass_when_no_failures(self, spark):
        df = spark.createDataFrame([(1,), (2,), (3,)], ["id"])
        result = dq_check(df, "entity1", "null_check", "No nulls", col("id").isNull())
        assert result["status"] == "PASS"
        assert result["failed_rows"] == 0
        assert result["total_rows"] == 3
        assert result["fail_pct"] == 0.0

    def test_fail_when_failures_exist_high_severity(self, spark):
        df = spark.createDataFrame([(1,), (None,), (3,)], ["id"])
        result = dq_check(df, "entity1", "null_check", "Has nulls", col("id").isNull())
        assert result["status"] == "FAIL"
        assert result["failed_rows"] == 1
        assert result["total_rows"] == 3

    def test_warn_on_failure_with_low_severity(self, spark):
        df = spark.createDataFrame([(1,), (None,)], ["id"])
        result = dq_check(
            df, "entity1", "warn_check", "Warning only",
            col("id").isNull(), severity="LOW",
        )
        assert result["status"] == "WARN"
        assert result["severity"] == "LOW"

    def test_empty_dataframe(self, spark):
        from pyspark.sql.types import StructType, StructField, IntegerType
        schema = StructType([StructField("id", IntegerType())])
        df = spark.createDataFrame([], schema)
        result = dq_check(df, "empty", "check", "desc", col("id").isNull())
        assert result["status"] == "PASS"
        assert result["total_rows"] == 0
        assert result["fail_pct"] == 0.0

    def test_all_rows_fail(self, spark):
        from pyspark.sql.types import StructType, StructField, IntegerType
        schema = StructType([StructField("id", IntegerType())])
        df = spark.createDataFrame([(None,), (None,)], schema)
        result = dq_check(df, "all_null", "null_check", "All null", col("id").isNull())
        assert result["failed_rows"] == 2
        assert result["fail_pct"] == 100.0

    def test_result_has_expected_keys(self, spark):
        df = spark.createDataFrame([(1,)], ["id"])
        result = dq_check(df, "e", "c", "d", col("id").isNull())
        assert "run_id" in result
        assert "entity" in result
        assert "check_name" in result
        assert "description" in result
        assert result["entity"] == "e"
        assert result["check_name"] == "c"
        assert result["description"] == "d"

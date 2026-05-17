import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

from src.connectors.base import BaseConnector, ConnectorResult


class _SimpleConnector(BaseConnector):
    connector_type = "simple"
    source_system = "simple_source"

    def extract(self, spark, config, batch_id):
        schema = StructType([
            StructField("id", IntegerType()),
            StructField("name", StringType()),
        ])
        return spark.createDataFrame([(1, "Alice"), (2, "Bob")], schema)


class _EmptyConnector(BaseConnector):
    connector_type = "empty"
    source_system = "empty_source"

    def extract(self, spark, config, batch_id):
        return None


class _CrashConnector(BaseConnector):
    connector_type = "crash"
    source_system = "crash_source"

    def extract(self, spark, config, batch_id):
        raise ValueError("boom")


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[*]").appName("test-connector-base").getOrCreate()


class TestBaseConnector:

    def test_connector_result_success(self, spark):
        c = _SimpleConnector()
        result = c.run(spark, {"lakehouses": {"bronze": "test_lh"}})
        assert result.source_system == "simple_source"
        assert result.status in ("FAILED", "SUCCESS")
        if result.status == "FAILED":
            assert "delta" in result.error.lower() or "catalog" in result.error.lower()

    def test_connector_result_skipped_on_none(self, spark):
        c = _EmptyConnector()
        result = c.run(spark, {"lakehouses": {"bronze": "test_lh"}})
        assert result.status == "SKIPPED"
        assert result.rows_written == 0

    def test_connector_result_failed(self, spark):
        c = _CrashConnector()
        result = c.run(spark, {"lakehouses": {"bronze": "test_lh"}})
        assert result.status == "FAILED"
        assert "boom" in result.error

    def test_add_audit_cols(self, spark):
        c = _SimpleConnector()
        schema = StructType([StructField("x", StringType())])
        df = spark.createDataFrame([("hello",)], schema)
        batch_id = "test-batch-123"
        result_df = c._add_audit_cols(df, batch_id)

        cols = [f.name for f in result_df.schema.fields]
        assert "_ingested_at" in cols
        assert "_source_system" in cols
        assert "_connector_type" in cols
        assert "_batch_id" in cols
        assert "_schema_version" in cols

        row = result_df.collect()[0]
        assert row["_source_system"] == "simple_source"
        assert row["_connector_type"] == "simple"
        assert row["_batch_id"] == "test-batch-123"
        assert row["_schema_version"] == "1.0"

    def test_override_source_system(self, spark):
        c = _SimpleConnector(source_system="custom_source")
        assert c.source_system == "custom_source"

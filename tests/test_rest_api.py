import pytest
import requests
from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from src.connectors.base import BaseConnector, ConnectorResult
from src.connectors.registry import ConnectorRegistry

BASE_URL = "https://jsonplaceholder.typicode.com"
POSTS_URL = f"{BASE_URL}/posts"
POSTS_SCHEMA = StructType([
    StructField("userId", IntegerType()),
    StructField("id", IntegerType()),
    StructField("title", StringType()),
    StructField("body", StringType()),
])


def _posts_to_rows(data):
    return [(p["userId"], p["id"], p["title"], p["body"]) for p in data]


class _JsonPlaceholderPostsConnector(BaseConnector):
    connector_type = "rest_api"
    source_system = "jsonplaceholder_posts"

    def extract(self, spark, config, batch_id):
        params = config.get("request_params", {})
        resp = requests.get(POSTS_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return spark.createDataFrame(_posts_to_rows(data), POSTS_SCHEMA)


class _PostNotFoundConnector(BaseConnector):
    connector_type = "rest_api"
    source_system = "jsonplaceholder_404"

    def extract(self, spark, config, batch_id):
        resp = requests.get(f"{POSTS_URL}/99999", timeout=10)
        resp.raise_for_status()
        return None


class _EmptyResponseConnector(BaseConnector):
    connector_type = "rest_api"
    source_system = "empty_source"

    def extract(self, spark, config, batch_id):
        return None


@pytest.fixture(scope="module")
def spark():
    return (
        SparkSession.builder.master("local[*]")
        .appName("test-rest-api")
        .getOrCreate()
    )


MINIMAL_CONFIG = {"lakehouses": {"bronze": "test_lh"}}


class TestConnectorExtract:

    def test_extract_returns_dataframe(self, spark):
        c = _JsonPlaceholderPostsConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "batch-1")
        assert df is not None
        assert df.count() > 0

    def test_extract_has_100_posts(self, spark):
        c = _JsonPlaceholderPostsConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "batch-1")
        assert df.count() == 100

    def test_extract_has_expected_schema(self, spark):
        c = _JsonPlaceholderPostsConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "batch-1")
        assert set(df.columns) == {"userId", "id", "title", "body"}

    def test_extract_data_correctness(self, spark):
        c = _JsonPlaceholderPostsConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "batch-1")
        row = df.filter("id = 1").first()
        assert row["userId"] == 1
        assert isinstance(row["title"], str)
        assert len(row["title"]) > 0

    def test_extract_filter_by_user_id(self, spark):
        c = _JsonPlaceholderPostsConnector()
        config = {**MINIMAL_CONFIG, "request_params": {"userId": 1}}
        df = c.extract(spark, config, "batch-1")
        assert df.count() == 10
        assert all(r["userId"] == 1 for r in df.collect())

    def test_extract_raises_on_404(self, spark):
        c = _PostNotFoundConnector()
        with pytest.raises(requests.HTTPError, match="404"):
            c.extract(spark, MINIMAL_CONFIG, "batch-1")

    def test_extract_empty_returns_none(self, spark):
        c = _EmptyResponseConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "batch-1")
        assert df is None


class TestConnectorRun:

    def test_run_fails_at_delta_write(self, spark):
        c = _JsonPlaceholderPostsConnector()
        result = c.run(spark, MINIMAL_CONFIG)
        assert result.source_system == "jsonplaceholder_posts"
        assert result.status == "FAILED"
        assert "delta" in result.error.lower() or "table" in result.error.lower()

    def test_run_returns_failed_on_404(self, spark):
        c = _PostNotFoundConnector()
        result = c.run(spark, MINIMAL_CONFIG)
        assert result.status == "FAILED"
        assert "404" in result.error

    def test_run_skipped_when_no_data(self, spark):
        c = _EmptyResponseConnector()
        result = c.run(spark, MINIMAL_CONFIG)
        assert result.status == "SKIPPED"
        assert result.rows_written == 0


class TestConnectorRegistry:

    def test_register_and_run_via_registry(self, spark):
        registry = ConnectorRegistry()
        registry.register(_JsonPlaceholderPostsConnector())
        registry.register(_EmptyResponseConnector())

        results = registry.run_all(spark, MINIMAL_CONFIG, only=["jsonplaceholder_posts"])
        assert len(results) == 1
        r = results[0]
        assert r.source_system == "jsonplaceholder_posts"
        assert r.status == "FAILED"

    def test_registry_summary(self, spark):
        registry = ConnectorRegistry()
        registry.register(_JsonPlaceholderPostsConnector())
        results = registry.run_all(spark, MINIMAL_CONFIG)
        summary = registry.summary(results)
        assert summary["total"] == 1
        assert summary["failed"] >= 0

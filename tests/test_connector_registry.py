from src.connectors.registry import ConnectorRegistry
from src.connectors.base import BaseConnector, ConnectorResult


class _TestConnector(BaseConnector):
    connector_type = "test"
    source_system = "test_source"

    def extract(self, spark, config, batch_id):
        return None


class _FailingConnector(BaseConnector):
    connector_type = "test_fail"
    source_system = "fail_source"

    def extract(self, spark, config, batch_id):
        raise RuntimeError("extract failed")


class TestConnectorRegistry:

    def test_register_and_get(self):
        registry = ConnectorRegistry()
        c = _TestConnector()
        registry.register(c)
        assert registry.get("test_source") is c

    def test_get_missing_returns_none(self):
        registry = ConnectorRegistry()
        assert registry.get("nonexistent") is None

    def test_list_connectors(self):
        registry = ConnectorRegistry()
        registry.register(_TestConnector())
        registry.register(_FailingConnector())
        names = registry.list_connectors()
        assert "test_source" in names
        assert "fail_source" in names

    def test_list_empty(self):
        registry = ConnectorRegistry()
        assert registry.list_connectors() == []

    def test_run_all_filters_by_only(self):
        import pytest
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.master("local[*]").appName("test-registry").getOrCreate()
        registry = ConnectorRegistry()
        registry.register(_TestConnector())
        registry.register(_FailingConnector())
        results = registry.run_all(spark, {"lakehouses": {"bronze": "test_lh"}}, only=["test_source"])
        assert len(results) == 1
        assert results[0].source_system == "test_source"

    def test_run_all_with_no_filter_runs_all(self):
        import pytest
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.master("local[*]").appName("test-registry").getOrCreate()
        registry = ConnectorRegistry()
        registry.register(_TestConnector())
        registry.register(_FailingConnector())
        results = registry.run_all(spark, {"lakehouses": {"bronze": "test_lh"}}, only=None)
        assert len(results) == 2

    def test_summary_empty(self):
        summary = ConnectorRegistry().summary([])
        assert summary == {"total": 0, "success": 0, "failed": 0, "skipped": 0, "rows": 0}

    def test_summary_counts(self):
        results = [
            ConnectorResult("a", "b1", 10, "SUCCESS"),
            ConnectorResult("b", "b2", 0, "FAILED"),
            ConnectorResult("c", "b3", 0, "SKIPPED"),
            ConnectorResult("d", "b4", 20, "SUCCESS"),
        ]
        summary = ConnectorRegistry().summary(results)
        assert summary["total"] == 4
        assert summary["success"] == 2
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["rows"] == 30


class TestConnectorResult:

    def test_defaults(self):
        r = ConnectorResult("src", "b_id", 5, "SUCCESS")
        assert r.source_system == "src"
        assert r.batch_id == "b_id"
        assert r.rows_written == 5
        assert r.status == "SUCCESS"
        assert r.error is None
        assert r.metadata == {}

    def test_with_error_and_metadata(self):
        r = ConnectorResult("src", "b_id", 0, "FAILED", error="oops", metadata={"key": "val"})
        assert r.error == "oops"
        assert r.metadata == {"key": "val"}

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

from src.api_ingestion import (
    is_circuit_open,
    _record_failure,
    _reset_circuit,
    _circuit_state,
    _token_cache,
    flatten_struct_cols,
)
from src.connectors.base import BaseConnector


@pytest.fixture(autouse=True)
def clear_state():
    _circuit_state.clear()
    _token_cache.clear()


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[*]").appName("test-api").getOrCreate()


MINIMAL_CONFIG = {"lakehouses": {"bronze": "test_lh"}}


class _CircuitAwareConnector(BaseConnector):
    connector_type = "test_cb"

    def extract(self, spark, config, batch_id):
        if is_circuit_open(self.source_system):
            return None
        return spark.createDataFrame([("ok",)], ["col"])


class _NestedStructConnector(BaseConnector):
    connector_type = "test_nested"
    source_system = "nested_source"

    def extract(self, spark, config, batch_id):
        schema = StructType([
            StructField("id", IntegerType()),
            StructField("nested", StructType([
                StructField("a", StringType()),
                StructField("b", StringType()),
            ])),
        ])
        return spark.createDataFrame([(1, ("x", "y"))], schema)


class _MultiNestedConnector(BaseConnector):
    connector_type = "test_multi_nested"
    source_system = "multi_nested_source"

    def extract(self, spark, config, batch_id):
        inner1 = StructType([StructField("p", StringType())])
        inner2 = StructType([StructField("q", StringType())])
        schema = StructType([
            StructField("s1", inner1),
            StructField("s2", inner2),
        ])
        return spark.createDataFrame([(("a",), ("b",))], schema)


class _FlatDataConnector(BaseConnector):
    connector_type = "test_flat"
    source_system = "flat_source"

    def extract(self, spark, config, batch_id):
        return spark.createDataFrame([(1, "hello")], ["id", "name"])


class _MixedStructConnector(BaseConnector):
    connector_type = "test_mixed"
    source_system = "mixed_source"

    def extract(self, spark, config, batch_id):
        schema = StructType([
            StructField("id", IntegerType()),
            StructField("data", StructType([StructField("val", StringType())])),
            StructField("name", StringType()),
        ])
        return spark.createDataFrame([(1, ("inner",), "test")], schema)


class TestConnectorCircuitBreaker:

    def test_extract_returns_data_when_circuit_closed(self, spark):
        c = _CircuitAwareConnector(source_system="api_a")
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        assert df is not None
        assert df.collect()[0]["col"] == "ok"

    def test_extract_skipped_when_circuit_open(self, spark):
        c = _CircuitAwareConnector(source_system="api_open")
        for _ in range(5):
            _record_failure("api_open")
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        assert df is None

    def test_circuit_remains_closed_below_threshold(self, spark):
        c = _CircuitAwareConnector(source_system="api_below")
        for _ in range(3):
            _record_failure("api_below")
        assert is_circuit_open("api_below") is False
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        assert df is not None

    def test_reset_closes_circuit(self, spark):
        c = _CircuitAwareConnector(source_system="api_reset")
        for _ in range(5):
            _record_failure("api_reset")
        _reset_circuit("api_reset")
        assert is_circuit_open("api_reset") is False
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        assert df is not None

    def test_run_returns_skipped_when_circuit_open(self, spark):
        c = _CircuitAwareConnector(source_system="api_run_open")
        for _ in range(5):
            _record_failure("api_run_open")
        result = c.run(spark, MINIMAL_CONFIG)
        assert result.status == "SKIPPED"
        assert result.rows_written == 0

    def test_run_returns_failed_when_circuit_closed_but_delta_fails(self, spark):
        c = _CircuitAwareConnector(source_system="api_run_closed")
        result = c.run(spark, MINIMAL_CONFIG)
        assert result.status == "FAILED"

    def test_independent_per_api(self, spark):
        failing = _CircuitAwareConnector(source_system="failing_api")
        healthy = _CircuitAwareConnector(source_system="healthy_api")
        for _ in range(5):
            _record_failure("failing_api")
        assert failing.extract(spark, MINIMAL_CONFIG, "b1") is None
        assert healthy.extract(spark, MINIMAL_CONFIG, "b1") is not None


class TestConnectorFlattenStructCols:

    def test_flatten_single_struct(self, spark):
        c = _NestedStructConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        flat = flatten_struct_cols(df)
        assert "nested_a" in flat.columns
        assert "nested_b" in flat.columns
        assert "nested" not in flat.columns
        assert flat.collect()[0]["nested_a"] == "x"

    def test_flatten_multiple_structs(self, spark):
        c = _MultiNestedConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        flat = flatten_struct_cols(df)
        assert "s1_p" in flat.columns
        assert "s2_q" in flat.columns
        assert "s1" not in flat.columns
        assert "s2" not in flat.columns

    def test_no_struct_cols_unchanged(self, spark):
        c = _FlatDataConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        flat = flatten_struct_cols(df)
        assert flat.columns == ["id", "name"]

    def test_non_struct_types_untouched(self, spark):
        c = _MixedStructConnector()
        df = c.extract(spark, MINIMAL_CONFIG, "b1")
        flat = flatten_struct_cols(df)
        assert "data_val" in flat.columns
        assert "id" in flat.columns
        assert "name" in flat.columns


class TestFileIngestionMoveFile:

    def test_move_file_builds_dest_path(self):
        from src.file_ingestion import move_file
        from src.filesystem import LocalFileSystem
        import tempfile, os

        tmpdir = tempfile.mkdtemp()
        src_dir = os.path.join(tmpdir, "landing", "training")
        os.makedirs(src_dir)
        src = os.path.join(src_dir, "test.xlsx")
        with open(src, "w") as f:
            f.write("data")

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            fs = LocalFileSystem()
            move_file(fs, src, "processed")
            assert not os.path.exists(src)
            dest = os.path.join(tmpdir, "Files/processed/training/test.xlsx")
            assert os.path.exists(dest)
        finally:
            os.chdir(old_cwd)


class TestConnectorInit:

    def test_register_all_imports(self):
        from src.connectors import register_all
        from src.connectors.registry import ConnectorRegistry
        registry = ConnectorRegistry()
        register_all(registry, {})
        names = registry.list_connectors()
        assert "excel_training" in names
        assert "rest_api_lms" in names
        assert "csv_import" in names
        assert "quercus" in names
        assert len(names) >= 15

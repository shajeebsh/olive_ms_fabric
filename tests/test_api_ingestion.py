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


@pytest.fixture(autouse=True)
def clear_state():
    _circuit_state.clear()
    _token_cache.clear()


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[*]").appName("test-api").getOrCreate()


class TestCircuitBreaker:

    def test_circuit_starts_closed(self):
        assert is_circuit_open("api_a") is False

    def test_circuit_opens_after_threshold(self):
        for _ in range(5):
            _record_failure("api_a")
        assert is_circuit_open("api_a") is True

    def test_circuit_remains_below_threshold(self):
        for _ in range(3):
            _record_failure("api_b")
        assert is_circuit_open("api_b") is False

    def test_reset_closes_circuit(self):
        for _ in range(5):
            _record_failure("api_c")
        _reset_circuit("api_c")
        assert is_circuit_open("api_c") is False

    def test_independent_per_api(self):
        for _ in range(5):
            _record_failure("failing_api")
        assert is_circuit_open("failing_api") is True
        assert is_circuit_open("healthy_api") is False


class TestFlattenStructCols:

    def test_flatten_single_struct(self, spark):
        schema = StructType([
            StructField("id", IntegerType()),
            StructField("nested", StructType([
                StructField("a", StringType()),
                StructField("b", StringType()),
            ])),
        ])
        df = spark.createDataFrame([(1, ("x", "y"))], schema)
        flat = flatten_struct_cols(df)
        cols = flat.columns
        assert "nested_a" in cols
        assert "nested_b" in cols
        assert "nested" not in cols
        assert flat.collect()[0]["nested_a"] == "x"

    def test_flatten_multiple_structs(self, spark):
        inner1 = StructType([StructField("p", StringType())])
        inner2 = StructType([StructField("q", StringType())])
        schema = StructType([
            StructField("s1", inner1),
            StructField("s2", inner2),
        ])
        df = spark.createDataFrame([(("a",), ("b",))], schema)
        flat = flatten_struct_cols(df)
        assert "s1_p" in flat.columns
        assert "s2_q" in flat.columns
        assert "s1" not in flat.columns
        assert "s2" not in flat.columns

    def test_no_struct_cols_unchanged(self, spark):
        df = spark.createDataFrame([(1, "hello")], ["id", "name"])
        flat = flatten_struct_cols(df)
        assert flat.columns == ["id", "name"]

    def test_non_struct_types_untouched(self, spark):
        schema = StructType([
            StructField("id", IntegerType()),
            StructField("data", StructType([StructField("val", StringType())])),
            StructField("name", StringType()),
        ])
        df = spark.createDataFrame([(1, ("inner",), "test")], schema)
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

import pytest
from pyspark.sql import SparkSession

from src.config_loader import lakehouse_table, load_config


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[*]").getOrCreate()


@pytest.fixture(scope="session")
def config():
    return load_config()


def test_gold_tables_exist(spark, config):
    tables = [t.name for t in spark.catalog.listTables(config["lakehouses"]["gold"])]
    expected_tables = ["dim_student", "dim_course", "fact_training_completion"]

    for table in expected_tables:
        assert table in tables


def test_gold_fact_completeness(spark, config):
    fact_df = spark.table(lakehouse_table(config, "gold", "fact_training_completion"))

    null_student_keys = fact_df.filter("student_key IS NULL").count()
    null_course_keys = fact_df.filter("course_key IS NULL").count()

    assert null_student_keys == 0, "Found null student keys in fact table"
    assert null_course_keys == 0, "Found null course keys in fact table"

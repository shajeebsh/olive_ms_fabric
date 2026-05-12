import json
import os
from typing import Any


_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


def load_config(env: str | None = None) -> dict[str, Any]:
    if env is None:
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            env = spark.conf.get("pipeline.env", "DEV")
        except Exception:
            env = os.environ.get("FABRIC_ENVIRONMENT", "DEV")

    filename = f"config_{env.lower()}.json"
    path = os.path.join(_CONFIG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return json.load(f)


def lakehouse_table(config: dict, layer: str, table: str) -> str:
    lakehouse = config["lakehouses"][layer]
    return f"{lakehouse}.{table}"


def lakehouse_name(config: dict, layer: str) -> str:
    return config["lakehouses"][layer]

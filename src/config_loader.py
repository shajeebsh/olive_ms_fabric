import json
import os
from typing import Any


_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


def load_config(env: str | None = None) -> dict[str, Any]:
    if env is None:
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder.getOrCreate()
            env = spark.conf.get("pipeline.env", None)
        except Exception:
            env = None

    if env is None:
        env = os.environ.get("FABRIC_ENVIRONMENT", None)

    if env is None:
        raise EnvironmentError(
            "Environment not set. Pass pipeline.env as a Fabric "
            "Pipeline parameter, or set the FABRIC_ENVIRONMENT "
            "environment variable. Valid values: DEV, TEST, PROD"
        )

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

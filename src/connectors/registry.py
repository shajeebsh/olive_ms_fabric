from __future__ import annotations

from pyspark.sql import SparkSession

from src.connectors.base import BaseConnector, ConnectorResult


class ConnectorRegistry:

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector):
        self._connectors[connector.source_system] = connector

    def get(self, source_system: str) -> BaseConnector | None:
        return self._connectors.get(source_system)

    def list_connectors(self) -> list[str]:
        return list(self._connectors.keys())

    def run_all(
        self,
        spark: SparkSession,
        config: dict,
        only: list[str] | None = None,
    ) -> list[ConnectorResult]:
        results = []
        for name, connector in self._connectors.items():
            if only and name not in only:
                continue
            print(f"Running connector: {name}")
            result = connector.run(spark, config)
            print(f"  {result.status}: {result.rows_written} rows")
            results.append(result)
        return results

    def summary(self, results: list[ConnectorResult]) -> dict:
        return {
            "total": len(results),
            "success": sum(
                1 for r in results if r.status == "SUCCESS"
            ),
            "failed": sum(
                1 for r in results if r.status == "FAILED"
            ),
            "skipped": sum(
                1 for r in results if r.status == "SKIPPED"
            ),
            "rows": sum(r.rows_written for r in results),
        }

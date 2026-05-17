from __future__ import annotations

import json
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class HubSpotConnector(BaseConnector):
    connector_type = "hubspot_api"
    source_system = "aws_hubspot"
    object_type: str = "contacts"
    properties: list[str] = [
        "firstname", "lastname", "email", "hs_object_id",
    ]

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        token = secrets.get(
            scope, "hubspot-private-app-token"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        base = (
            f"https://api.hubapi.com/crm/v3/objects/"
            f"{self.object_type}"
        )
        props = ",".join(self.properties)

        all_records, after = [], None
        while True:
            params = {"limit": 100, "properties": props}
            if after:
                params["after"] = after
            resp = requests.get(
                base, headers=headers,
                params=params, timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            all_records.extend(data.get("results", []))
            paging = data.get("paging", {}).get("next", {})
            after = paging.get("after")
            if not after:
                break

        if not all_records:
            return None

        flat = [
            {**r.get("properties", {}), "id": r.get("id")}
            for r in all_records
        ]
        rdd = spark.sparkContext.parallelize(
            [json.dumps(r) for r in flat]
        )
        return spark.read.json(rdd)


def register_connectors(registry, config=None):
    registry.register(HubSpotConnector())

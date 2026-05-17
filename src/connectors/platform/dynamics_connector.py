from __future__ import annotations

import json
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class DynamicsConnector(BaseConnector):
    connector_type = "dynamics_odata"
    source_system = "ms_dynamics"
    entity: str = "contacts"

    def _get_aad_token(
        self, config: dict[str, Any]
    ) -> str:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        tenant = secrets.get(scope, "dynamics-tenant-id")
        client_id = secrets.get(scope, "dynamics-client-id")
        client_secret = secrets.get(
            scope, "dynamics-client-secret"
        )
        resource = secrets.get(
            scope, "dynamics-resource-url"
        )
        resp = requests.post(
            f"https://login.microsoftonline.com/"
            f"{tenant}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "resource": resource,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        base_url = secrets.get(scope, "dynamics-base-url")
        token = self._get_aad_token(config)
        headers = {
            "Authorization": f"Bearer {token}",
            "OData-MaxVersion": "4.0",
            "Prefer": "odata.track-changes",
        }

        delta_row = spark.sql(f"""
            SELECT last_batch_id
            FROM Bronze_Lakehouse.control_watermark
            WHERE source_system = 'ms_dynamics_{self.entity}'
        """).first()
        delta_token = (
            delta_row["last_batch_id"] if delta_row else None
        )

        if delta_token:
            url = (
                f"{base_url}/api/data/v9.2/{self.entity}"
                f"?$deltatoken={delta_token}"
            )
        else:
            url = (
                f"{base_url}/api/data/v9.2/{self.entity}"
                f"?$top=5000"
            )

        all_records, next_link = [], url
        new_token = None
        while next_link:
            resp = requests.get(
                next_link, headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            all_records.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            delta_link = data.get("@odata.deltaLink", "")
            if delta_link:
                new_token = delta_link.split(
                    "deltatoken="
                )[-1]

        if not all_records:
            return None

        if new_token:
            spark.sql(f"""
                UPDATE Bronze_Lakehouse.control_watermark
                SET last_batch_id='{new_token}',
                    updated_at=current_timestamp()
                WHERE source_system='ms_dynamics_{self.entity}'
            """)

        rdd = spark.sparkContext.parallelize(
            [json.dumps(r) for r in all_records]
        )
        return spark.read.json(rdd)


def register_connectors(registry, config=None):
    registry.register(DynamicsConnector())

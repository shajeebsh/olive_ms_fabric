from __future__ import annotations

import json
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import flatten_struct_cols
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class MailchimpConnector(BaseConnector):
    connector_type = "mailchimp_api"
    source_system = "mailchimp"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        api_key = secrets.get(scope, "mailchimp-api-key")
        dc = api_key.split("-")[-1]
        base_url = f"https://{dc}.api.mailchimp.com/3.0"
        auth = ("anystring", api_key)

        all_campaigns = []
        offset, count = 0, 100
        while True:
            resp = requests.get(
                f"{base_url}/campaigns",
                auth=auth,
                params={
                    "count": count,
                    "offset": offset,
                    "fields": (
                        "campaigns.id,campaigns.settings,"
                        "campaigns.stats"
                    ),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("campaigns", [])
            all_campaigns.extend(batch)
            if len(batch) < count:
                break
            offset += count

        if not all_campaigns:
            return None

        rdd = spark.sparkContext.parallelize(
            [json.dumps(c) for c in all_campaigns]
        )
        df = spark.read.json(rdd)
        return flatten_struct_cols(df)


def register_connectors(registry, config=None):
    registry.register(MailchimpConnector())

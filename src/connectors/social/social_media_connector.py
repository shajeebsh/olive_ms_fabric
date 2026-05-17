from __future__ import annotations

import json
from typing import Any

import requests
from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import flatten_struct_cols
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class MetaGraphConnector(BaseConnector):
    connector_type = "meta_graph_api"
    source_system = "social_meta"
    fields: str = (
        "id,message,created_time,story,"
        "likes.summary(true)"
    )

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        page_token = secrets.get(scope, "meta-page-token")
        page_id = secrets.get(scope, "meta-page-id")

        posts, next_url = [], (
            f"https://graph.facebook.com/v19.0/"
            f"{page_id}/posts"
            f"?fields={self.fields}"
            f"&access_token={page_token}"
        )
        while next_url:
            resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            posts.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")

        if not posts:
            return None

        rdd = spark.sparkContext.parallelize(
            [json.dumps(p) for p in posts]
        )
        df = spark.read.json(rdd)
        return flatten_struct_cols(df)


class LinkedInConnector(BaseConnector):
    connector_type = "linkedin_api"
    source_system = "social_linkedin"

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        token = secrets.get(
            scope, "linkedin-access-token"
        )
        org_id = secrets.get(
            scope, "linkedin-org-id"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": "202402",
        }
        resp = requests.get(
            "https://api.linkedin.com/v2/ugcPosts"
            f"?q=authors&authors=urn:li:organization:"
            f"{org_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("elements", [])

        if not data:
            return None

        rdd = spark.sparkContext.parallelize(
            [json.dumps(p) for p in data]
        )
        return spark.read.json(rdd)


def register_connectors(registry, config=None):
    registry.register(MetaGraphConnector())
    registry.register(LinkedInConnector())

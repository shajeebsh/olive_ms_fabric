from __future__ import annotations

import json
from typing import Any

from pyspark.sql import DataFrame, SparkSession

from src.api_ingestion import flatten_struct_cols
from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class SoapConnector(BaseConnector):
    connector_type = "soap"
    source_system = "soap_webservice"
    wsdl_url: str = ""
    operation: str = ""
    secret_key: str = ""

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        from zeep import Client
        from zeep.helpers import serialize_object
        from zeep.transports import Transport
        from requests import Session

        secrets = get_secrets()
        token = secrets.get(
            config.get("secret_scope", ""), self.secret_key
        )

        session = Session()
        session.headers.update(
            {"Authorization": f"Bearer {token}"}
        )
        transport = Transport(session=session)
        client = Client(wsdl=self.wsdl_url, transport=transport)

        response = getattr(client.service, self.operation)()
        raw_dict = serialize_object(response, target_cls=dict)
        records = (
            raw_dict if isinstance(raw_dict, list) else [raw_dict]
        )

        if not records:
            return None

        rdd = spark.sparkContext.parallelize(
            [json.dumps(r) for r in records]
        )
        df = spark.read.json(rdd)
        return flatten_struct_cols(df)


def register_connectors(registry, config=None):
    if config and "connectors" in config:
        soap_cfg = config["connectors"].get("soap_webservice", {})
        if soap_cfg:
            connector = SoapConnector()
            connector.wsdl_url = soap_cfg.get("wsdl_url", "")
            connector.operation = soap_cfg.get("operation", "")
            connector.secret_key = soap_cfg.get("secret_key", "")
            registry.register(connector)

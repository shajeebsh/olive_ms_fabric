from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame, SparkSession

from src.connectors.base import BaseConnector
from src.secrets import get_secrets


class AwsDataHubConnector(BaseConnector):
    connector_type = "aws_s3"
    source_system = "aws_datahub"
    s3_prefix: str = "exports/"

    def _get_s3_client(
        self, config: dict[str, Any]
    ):
        import boto3
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        return boto3.client(
            "s3",
            aws_access_key_id=secrets.get(
                scope, "aws-access-key-id"
            ),
            aws_secret_access_key=secrets.get(
                scope, "aws-secret-access-key"
            ),
            region_name="eu-west-1",
        )

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        secrets = get_secrets()
        scope = config.get("secret_scope", "")
        bucket = secrets.get(scope, "aws-s3-bucket")
        s3 = self._get_s3_client(config)
        landing = "Files/landing/aws/"

        wm_row = spark.sql("""
            SELECT last_run_ts
            FROM Bronze_Lakehouse.control_watermark
            WHERE source_system = 'aws_datahub'
        """).first()
        since = (
            wm_row["last_run_ts"] if wm_row else None
        )

        objects = s3.list_objects_v2(
            Bucket=bucket, Prefix=self.s3_prefix
        )
        new_keys = []
        for obj in objects.get("Contents", []):
            if since is None or (
                obj["LastModified"].replace(tzinfo=None)
                > since
            ):
                new_keys.append(obj["Key"])

        if not new_keys:
            return None

        from src.filesystem import get_filesystem
        fs = get_filesystem()
        fs.mkdirs(landing)
        for key in new_keys:
            local_name = key.replace("/", "_")
            s3.download_file(
                bucket, key, f"/tmp/{local_name}"
            )
            mssparkutils.fs.cp(
                f"file:///tmp/{local_name}",
                f"{landing}{local_name}",
            )

        return spark.read.parquet(landing)


def register_connectors(registry, config=None):
    registry.register(AwsDataHubConnector())

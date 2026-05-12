# NB_03_Bronze_REST_API_Ingest
# Layer: Bronze
# Purpose: Resilient REST API ingestion using watermark CDC, retries, token caching, and api_call_log.

import json
import traceback
import uuid
from datetime import datetime, timezone

from pyspark.sql.functions import col, current_timestamp, lit

from src.config_loader import load_config, lakehouse_table
from src.secrets import get_secrets
from src.api_ingestion import (
    is_circuit_open,
    get_oauth2_token,
    flatten_struct_cols,
    fetch_all_pages,
    log_api_call,
)

config = load_config()
secrets = get_secrets()

API_CONFIG = {
    "rest_api_lms": {
        "base_url": config["api_base_url"],
        "endpoint": "/enrolments",
        "auth_type": "bearer",
        "secret_scope": config["secret_scope"],
        "secret_key": "lms-api-token",
        "delta_param": "updated_since",
        "page_size": 500,
        "target_table": lakehouse_table(config, "bronze", "bronze_lms_enrolments"),
    },
    "rest_api_hr": {
        "base_url": "https://hr.example.org/api/v1",
        "endpoint": "/staff",
        "auth_type": "oauth2",
        "secret_scope": config["secret_scope"],
        "secret_key": "hr-client-secret",
        "client_id": "fabric_client",
        "token_url": "https://hr.example.org/oauth/token",
        "delta_param": "modified_after",
        "page_size": 200,
        "target_table": lakehouse_table(config, "bronze", "bronze_hr_staff"),
    },
}


for api_name, cfg in API_CONFIG.items():
    batch_id = str(uuid.uuid4())
    print(f"REST API ingest: {api_name}")

    if is_circuit_open(api_name):
        continue

    control_watermark = lakehouse_table(config, "bronze", "control_watermark")

    try:
        watermark_row = spark.sql(
            f"SELECT last_run_ts FROM {control_watermark} WHERE source_system = '{api_name}' LIMIT 1"
        ).first()
        watermark_ts = watermark_row["last_run_ts"] if watermark_row else datetime(1900, 1, 1, tzinfo=timezone.utc)
        watermark_value = watermark_ts.isoformat()

        if cfg["auth_type"] == "oauth2":
            token = get_oauth2_token(secrets, api_name, cfg)
        else:
            token = secrets.get(cfg["secret_scope"], cfg["secret_key"])

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        params = {cfg["delta_param"]: watermark_value, "page_size": cfg["page_size"]}
        records = fetch_all_pages(spark, config, api_name, cfg, headers, params, watermark_ts)

        if not records:
            print(f"No new records for {api_name}; watermark not advanced.")
            continue

        df_api = spark.read.json(spark.sparkContext.parallelize([json.dumps(record) for record in records]))
        df_api = flatten_struct_cols(df_api)

        df_bronze = (
            df_api.withColumn("_ingested_at", current_timestamp())
            .withColumn("_source_system", lit(api_name))
            .withColumn("_batch_id", lit(batch_id))
        )

        df_bronze.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(cfg["target_table"])

        spark.sql(f"""
            UPDATE {control_watermark}
            SET last_run_ts = current_timestamp(),
                last_batch_id = '{batch_id}',
                last_row_count = {len(records)},
                status = 'SUCCESS',
                updated_at = current_timestamp()
            WHERE source_system = '{api_name}'
        """)
        print(f"Loaded {len(records)} records for {api_name}.")
    except Exception:
        traceback.print_exc()
        spark.sql(f"""
            UPDATE {control_watermark}
            SET status = 'FAILED',
                updated_at = current_timestamp()
            WHERE source_system = '{api_name}'
        """)
        raise

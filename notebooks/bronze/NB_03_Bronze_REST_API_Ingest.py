# NB_03_Bronze_REST_API_Ingest
# Layer: Bronze
# Purpose: Resilient REST API ingestion using watermark CDC, retries, token caching, and api_call_log.

import json
import time
import traceback
import uuid
from datetime import datetime

import requests
from pyspark.sql.functions import col, current_timestamp, lit
from pyspark.sql.types import StructType

MAX_RETRIES = 3
RETRY_BASE_WAIT = 5
CIRCUIT_THRESHOLD = 5
REQUEST_TIMEOUT = 30

API_CONFIG = {
    "rest_api_lms": {
        "base_url": "https://lms.example.org/api/v2",
        "endpoint": "/enrolments",
        "auth_type": "bearer",
        "secret_scope": "fabric-secrets",
        "secret_key": "lms-api-token",
        "delta_param": "updated_since",
        "page_size": 500,
        "target_table": "Bronze_Lakehouse.bronze_lms_enrolments",
    },
    "rest_api_hr": {
        "base_url": "https://hr.example.org/api/v1",
        "endpoint": "/staff",
        "auth_type": "oauth2",
        "secret_scope": "fabric-secrets",
        "secret_key": "hr-client-secret",
        "client_id": "fabric_client",
        "token_url": "https://hr.example.org/oauth/token",
        "delta_param": "modified_after",
        "page_size": 200,
        "target_table": "Bronze_Lakehouse.bronze_hr_staff",
    },
}

circuit_state = {}
token_cache = {}


def get_secret(scope, key):
    try:
        return mssparkutils.credentials.getSecret(scope, key)
    except Exception:
        return dbutils.secrets.get(scope=scope, key=key)


def is_circuit_open(api_name):
    failures = circuit_state.get(api_name, 0)
    if failures >= CIRCUIT_THRESHOLD:
        print(f"Circuit open for {api_name}: {failures} consecutive failures.")
        return True
    return False


def record_failure(api_name):
    circuit_state[api_name] = circuit_state.get(api_name, 0) + 1


def reset_circuit(api_name):
    circuit_state[api_name] = 0


def get_oauth2_token(api_name, cfg):
    cached = token_cache.get(api_name)
    if cached and (datetime.utcnow() - cached["fetched_at"]).total_seconds() < 3000:
        return cached["token"]

    secret = get_secret(cfg["secret_scope"], cfg["secret_key"])
    response = requests.post(
        cfg["token_url"],
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": secret,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    token_cache[api_name] = {"token": token, "fetched_at": datetime.utcnow()}
    return token


def log_api_call(api_name, endpoint, http_status, attempt, response_ms, records, watermark, status, error=None):
    rows = [(
        str(uuid.uuid4()),
        api_name,
        endpoint,
        http_status,
        attempt,
        response_ms,
        records,
        watermark,
        datetime.utcnow(),
        status,
        str(error) if error else None,
    )]
    spark.createDataFrame(
        rows,
        "call_id STRING, api_name STRING, endpoint STRING, http_status INT, attempt_num INT, "
        "response_ms LONG, records_returned LONG, watermark_used TIMESTAMP, called_at TIMESTAMP, "
        "status STRING, error_message STRING",
    ).write.format("delta").mode("append").saveAsTable("Bronze_Lakehouse.api_call_log")


def flatten_struct_cols(df):
    for field in df.schema.fields:
        if isinstance(field.dataType, StructType):
            for nested_column in df.select(f"{field.name}.*").columns:
                df = df.withColumn(f"{field.name}_{nested_column}", col(f"{field.name}.{nested_column}"))
            df = df.drop(field.name)
    return df


def fetch_all_pages(api_name, cfg, headers, params, watermark_ts):
    all_records = []
    page = 1
    endpoint = cfg["endpoint"]

    while True:
        params["page"] = page
        last_error = None
        has_next_page = False

        for attempt in range(1, MAX_RETRIES + 1):
            started = datetime.utcnow()
            try:
                response = requests.get(
                    f"{cfg['base_url']}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response_ms = int((datetime.utcnow() - started).total_seconds() * 1000)

                if response.status_code == 429:
                    wait_seconds = int(response.headers.get("Retry-After", 60))
                    log_api_call(api_name, endpoint, 429, attempt, response_ms, 0, watermark_ts, "RATE_LIMITED")
                    time.sleep(wait_seconds)
                    continue

                if response.status_code == 401:
                    token_cache.pop(api_name, None)
                    raise requests.HTTPError("401 Unauthorized; token cache cleared for retry")

                if response.status_code == 503:
                    record_failure(api_name)
                    log_api_call(api_name, endpoint, 503, attempt, response_ms, 0, watermark_ts, "FAILED")
                    raise requests.HTTPError("503 Service Unavailable")

                response.raise_for_status()
                payload = response.json()
                records = payload.get("results", payload if isinstance(payload, list) else [])
                has_next_page = bool(payload.get("next")) if isinstance(payload, dict) else False
                log_api_call(api_name, endpoint, response.status_code, attempt, response_ms, len(records), watermark_ts, "SUCCESS")
                reset_circuit(api_name)
                break
            except requests.RequestException as exc:
                last_error = exc
                response_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
                if attempt == MAX_RETRIES:
                    record_failure(api_name)
                    log_api_call(api_name, endpoint, 0, attempt, response_ms, 0, watermark_ts, "FAILED", exc)
                    raise
                time.sleep(RETRY_BASE_WAIT * (2 ** (attempt - 1)))
        else:
            raise Exception(f"All retries exhausted for {api_name}: {last_error}")

        all_records.extend(records)
        if not has_next_page or not records:
            break
        page += 1

    return all_records


for api_name, cfg in API_CONFIG.items():
    batch_id = str(uuid.uuid4())
    print(f"REST API ingest: {api_name}")

    if is_circuit_open(api_name):
        continue

    try:
        watermark_row = spark.sql(f"""
            SELECT last_run_ts
            FROM Bronze_Lakehouse.control_watermark
            WHERE source_system = '{api_name}'
        """).first()
        watermark_ts = watermark_row["last_run_ts"] if watermark_row else datetime(1900, 1, 1)
        watermark_value = watermark_ts.isoformat()

        if cfg["auth_type"] == "oauth2":
            token = get_oauth2_token(api_name, cfg)
        else:
            token = get_secret(cfg["secret_scope"], cfg["secret_key"])

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        params = {cfg["delta_param"]: watermark_value, "page_size": cfg["page_size"]}
        records = fetch_all_pages(api_name, cfg, headers, params, watermark_ts)

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
            UPDATE Bronze_Lakehouse.control_watermark
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
            UPDATE Bronze_Lakehouse.control_watermark
            SET status = 'FAILED',
                updated_at = current_timestamp()
            WHERE source_system = '{api_name}'
        """)
        raise

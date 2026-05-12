from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from pyspark.sql.types import StructType

from src.config_loader import lakehouse_table
from src.secrets import SecretsProvider

MAX_RETRIES = 3
RETRY_BASE_WAIT = 5
CIRCUIT_THRESHOLD = 5
REQUEST_TIMEOUT = 30

_circuit_state: dict[str, int] = {}
_token_cache: dict[str, dict] = {}


def is_circuit_open(api_name: str) -> bool:
    failures = _circuit_state.get(api_name, 0)
    if failures >= CIRCUIT_THRESHOLD:
        print(f"Circuit open for {api_name}: {failures} consecutive failures.")
        return True
    return False


def _record_failure(api_name: str) -> None:
    _circuit_state[api_name] = _circuit_state.get(api_name, 0) + 1


def _reset_circuit(api_name: str) -> None:
    _circuit_state[api_name] = 0


def get_oauth2_token(
    secrets: SecretsProvider, api_name: str, cfg: dict
) -> str:
    cached = _token_cache.get(api_name)
    if cached and (
        datetime.now(timezone.utc) - cached["fetched_at"]
    ).total_seconds() < 3000:
        return cached["token"]

    secret = secrets.get(cfg["secret_scope"], cfg["secret_key"])
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
    _token_cache[api_name] = {"token": token, "fetched_at": datetime.now(timezone.utc)}
    return token


def log_api_call(
    spark: SparkSession,
    config: dict,
    api_name: str,
    endpoint: str,
    http_status: int,
    attempt: int,
    response_ms: int,
    records: int,
    watermark: datetime,
    status: str,
    error: Optional[str] = None,
) -> None:
    api_log = lakehouse_table(config, "bronze", "api_call_log")
    rows = [
        (
            str(uuid.uuid4()),
            api_name,
            endpoint,
            http_status,
            attempt,
            response_ms,
            records,
            watermark,
            datetime.now(timezone.utc),
            status,
            error,
        )
    ]
    spark.createDataFrame(
        rows,
        "call_id STRING, api_name STRING, endpoint STRING, http_status INT, attempt_num INT, "
        "response_ms LONG, records_returned LONG, watermark_used TIMESTAMP, called_at TIMESTAMP, "
        "status STRING, error_message STRING",
    ).write.format("delta").mode("append").saveAsTable(api_log)


def flatten_struct_cols(df: DataFrame) -> DataFrame:
    for field in df.schema.fields:
        if isinstance(field.dataType, StructType):
            for nested_column in df.select(f"{field.name}.*").columns:
                df = df.withColumn(
                    f"{field.name}_{nested_column}", col(f"{field.name}.{nested_column}")
                )
            df = df.drop(field.name)
    return df


def fetch_all_pages(
    spark: SparkSession,
    config: dict,
    api_name: str,
    cfg: dict,
    headers: dict,
    params: dict,
    watermark_ts: datetime,
) -> list[dict[str, Any]]:
    all_records = []
    page = 1
    endpoint = cfg["endpoint"]

    while True:
        params["page"] = page
        last_error = None
        has_next_page = False

        for attempt in range(1, MAX_RETRIES + 1):
            started = datetime.now(timezone.utc)
            try:
                response = requests.get(
                    f"{cfg['base_url']}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response_ms = int(
                    (datetime.now(timezone.utc) - started).total_seconds() * 1000
                )

                if response.status_code == 429:
                    wait_seconds = int(response.headers.get("Retry-After", 60))
                    log_api_call(
                        spark, config, api_name, endpoint, 429, attempt,
                        response_ms, 0, watermark_ts, "RATE_LIMITED"
                    )
                    time.sleep(wait_seconds)
                    continue

                if response.status_code == 401:
                    _token_cache.pop(api_name, None)
                    raise requests.HTTPError(
                        "401 Unauthorized; token cache cleared for retry"
                    )

                if response.status_code == 503:
                    _record_failure(api_name)
                    log_api_call(
                        spark, config, api_name, endpoint, 503, attempt,
                        response_ms, 0, watermark_ts, "FAILED"
                    )
                    raise requests.HTTPError("503 Service Unavailable")

                response.raise_for_status()
                payload = response.json()
                records = payload.get(
                    "results", payload if isinstance(payload, list) else []
                )
                has_next_page = (
                    bool(payload.get("next"))
                    if isinstance(payload, dict)
                    else False
                )
                log_api_call(
                    spark, config, api_name, endpoint, response.status_code,
                    attempt, response_ms, len(records), watermark_ts, "SUCCESS"
                )
                _reset_circuit(api_name)
                break
            except requests.RequestException as exc:
                last_error = exc
                response_ms = int(
                    (datetime.now(timezone.utc) - started).total_seconds() * 1000
                )
                if attempt == MAX_RETRIES:
                    _record_failure(api_name)
                    log_api_call(
                        spark, config, api_name, endpoint, 0, attempt,
                        response_ms, 0, watermark_ts, "FAILED", str(exc)
                    )
                    raise
                time.sleep(RETRY_BASE_WAIT * (2 ** (attempt - 1)))
        else:
            raise Exception(f"All retries exhausted for {api_name}: {last_error}")

        all_records.extend(records)
        if not has_next_page or not records:
            break
        page += 1

    return all_records

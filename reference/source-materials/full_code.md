# Full Codebase Reference — olive_ms_fabric

---

## Configuration Files

### `config/config_dev.json`

```json
{
  "environment": "DEV",
  "workspace": "UNIV-DEV",
  "git_branch": "feature/*",
  "bronze_lakehouse": "Bronze_Lakehouse",
  "silver_lakehouse": "Silver_Lakehouse",
  "gold_lakehouse": "Gold_Lakehouse",
  "api_base_url": "https://lms-uat.example.org/api/v2",
  "secret_scope": "fabric-secrets-dev",
  "lakehouses": {
    "bronze": "Bronze_Lakehouse",
    "silver": "Silver_Lakehouse",
    "gold": "Gold_Lakehouse"
  },
  "warehouse": "Gold_Warehouse",
  "data_policy": "synthetic_or_anonymised_only",
  "schedule_enabled": false
}
```

### `config/config_prod.json`

```json
{
  "environment": "PROD",
  "workspace": "UNIV-PROD",
  "git_branch": "main",
  "bronze_lakehouse": "Bronze_Lakehouse",
  "silver_lakehouse": "Silver_Lakehouse",
  "gold_lakehouse": "Gold_Lakehouse",
  "api_base_url": "https://lms.example.org/api/v2",
  "secret_scope": "fabric-secrets-prod",
  "lakehouses": {
    "bronze": "Bronze_Lakehouse",
    "silver": "Silver_Lakehouse",
    "gold": "Gold_Lakehouse"
  },
  "warehouse": "Gold_Warehouse",
  "data_policy": "live_data_rbac_required",
  "schedule_enabled": true
}
```

### `config/config_test.json`

```json
{
  "environment": "TEST",
  "workspace": "UNIV-TEST",
  "git_branch": "develop",
  "bronze_lakehouse": "Bronze_Lakehouse",
  "silver_lakehouse": "Silver_Lakehouse",
  "gold_lakehouse": "Gold_Lakehouse",
  "api_base_url": "https://lms-test.example.org/api/v2",
  "secret_scope": "fabric-secrets-test",
  "lakehouses": {
    "bronze": "Bronze_Lakehouse",
    "silver": "Silver_Lakehouse",
    "gold": "Gold_Lakehouse"
  },
  "warehouse": "Gold_Warehouse",
  "data_policy": "anonymised_or_masked_test_data",
  "schedule_enabled": true
}
```

### `requirements-dev.txt`

```
pyspark>=3.5.0
delta-spark>=3.1.0
pytest>=8.0.0
requests>=2.31.0
```

### `.gitignore`

```
__pycache__/
*.py[cod]
.DS_Store
.env
*.log
*.parquet
*.delta
*.xlsx
*.xls
*.csv
*.tsv
```

---

## Source Code — `src/`

### `src/__init__.py`

```python

```

### `src/api_ingestion.py`

```python
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
```

### `src/config_loader.py`

```python
import json
import os
from typing import Any

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


def load_config(env: str | None = None) -> dict[str, Any]:
    if env is None:
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder.getOrCreate()
            env = spark.conf.get("pipeline.env", "DEV")
        except Exception:
            env = os.environ.get("FABRIC_ENVIRONMENT", "DEV")

    filename = f"config_{env.lower()}.json"
    path = os.path.join(_CONFIG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return json.load(f)


def lakehouse_table(config: dict, layer: str, table: str) -> str:
    lakehouse = config["lakehouses"][layer]
    return f"{lakehouse}.{table}"


def lakehouse_name(config: dict, layer: str) -> str:
    return config["lakehouses"][layer]
```

### `src/data_quality.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql.functions import col as spark_col, current_timestamp


def dq_check(
    df: DataFrame,
    entity: str,
    name: str,
    description: str,
    fail_condition: Any,
    severity: str = "HIGH",
) -> dict:
    total_rows = df.count()
    failed_rows = df.filter(fail_condition).count()
    fail_pct = round(failed_rows / total_rows * 100, 2) if total_rows else 0
    status = "PASS" if failed_rows == 0 else ("WARN" if severity != "HIGH" else "FAIL")
    print(f"{status}: {entity}.{name} failed {failed_rows}/{total_rows}")
    return {
        "run_id": str(uuid.uuid4()),
        "entity": entity,
        "check_name": name,
        "description": description,
        "total_rows": total_rows,
        "failed_rows": failed_rows,
        "fail_pct": fail_pct,
        "status": status,
        "severity": severity,
    }
```

### `src/file_ingestion.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, input_file_name, lit
from src.config_loader import lakehouse_table
from src.filesystem import FileInfo, FileSystem


def md5_of_file(fs: FileSystem, path: str) -> str:
    return fs.md5(path)


def registry_action(
    spark: SparkSession, config: dict, file_name: str, file_hash: str
) -> str:
    registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
    df_registry = spark.table(registry)

    existing_hash = df_registry.filter(
        (col("file_hash_md5") == file_hash) & (col("status") == "SUCCESS")
    ).select("file_name").limit(1)
    if existing_hash.count():
        return "DUPLICATE"

    existing_name = df_registry.filter(
        (col("file_name") == file_name) & (col("status") == "SUCCESS")
    ).select("file_name").limit(1)
    if existing_name.count():
        return "CORRECTION"

    failed_hash = df_registry.filter(
        (col("file_hash_md5") == file_hash) & (col("status") == "FAILED")
    ).select("file_id").limit(1)
    if failed_hash.count():
        return "RETRY"

    return "NEW"


def register_file(
    spark: SparkSession,
    config: dict,
    file_name: str,
    file_path: str,
    file_size: int,
    file_hash: str,
    source: str,
    status: str,
    batch_id: str,
    row_count: int = 0,
    error: Optional[str] = None,
) -> None:
    registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
    now = datetime.now(timezone.utc)
    rows = [
        (
            str(uuid.uuid4()),
            file_name,
            file_path,
            file_size,
            file_hash,
            source,
            now,
            now if status in ("SUCCESS", "DUPLICATE", "CORRECTION") else None,
            row_count,
            status,
            batch_id,
            error,
        )
    ]
    spark.createDataFrame(
        rows,
        "file_id STRING, file_name STRING, file_path STRING, file_size_bytes LONG, "
        "file_hash_md5 STRING, source_system STRING, detected_at TIMESTAMP, "
        "processed_at TIMESTAMP, row_count LONG, status STRING, batch_id STRING, error_message STRING",
    ).write.format("delta").mode("append").saveAsTable(registry)


def log_schema_drift(
    spark: SparkSession,
    config: dict,
    source_system: str,
    file_name: str,
    actual_columns: list[str],
    expected_columns: list[str],
    batch_id: str,
) -> int:
    if not expected_columns:
        return 0

    schema_log = lakehouse_table(config, "bronze", "schema_change_log")
    now = datetime.now(timezone.utc)
    changes = []
    for column_name in actual_columns:
        if column_name not in expected_columns:
            changes.append(
                (
                    str(uuid.uuid4()),
                    source_system,
                    file_name,
                    "NEW_COLUMN",
                    column_name,
                    None,
                    now,
                    batch_id,
                    False,
                )
            )
    for column_name in expected_columns:
        if column_name not in actual_columns:
            changes.append(
                (
                    str(uuid.uuid4()),
                    source_system,
                    file_name,
                    "REMOVED_COLUMN",
                    column_name,
                    column_name,
                    now,
                    batch_id,
                    False,
                )
            )

    if changes:
        spark.createDataFrame(
            changes,
            "change_id STRING, source_system STRING, file_name STRING, change_type STRING, "
            "column_name STRING, previous_value STRING, detected_at TIMESTAMP, batch_id STRING, resolved BOOLEAN",
        ).write.format("delta").mode("append").saveAsTable(schema_log)
    return len(changes)


def move_file(fs: FileSystem, src_path: str, zone: str) -> None:
    file_name = src_path.split("/")[-1]
    source_dir = src_path.split("/")[-2]
    dest = f"Files/{zone}/{source_dir}/{file_name}"
    fs.mkdirs(f"Files/{zone}/{source_dir}/")
    fs.mv(src_path, dest)
```

### `src/filesystem.py`

```python
from __future__ import annotations

import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class FileInfo:
    name: str
    path: str
    size: int


class FileSystem(ABC):

    @abstractmethod
    def ls(self, path: str) -> List[FileInfo]:
        ...

    @abstractmethod
    def head(self, path: str, max_bytes: int) -> bytes:
        ...

    @abstractmethod
    def mkdirs(self, path: str) -> None:
        ...

    @abstractmethod
    def mv(self, src: str, dst: str) -> None:
        ...

    @abstractmethod
    def md5(self, path: str) -> str:
        ...


class FabricFileSystem(FileSystem):

    def ls(self, path: str) -> List[FileInfo]:
        from mssparkutils import fs
        return [FileInfo(f.name, f.path, f.size) for f in fs.ls(path)]

    def head(self, path: str, max_bytes: int) -> bytes:
        from mssparkutils import fs
        result = fs.head(path, max_bytes)
        if isinstance(result, str):
            return result.encode("utf-8")
        return result

    def mkdirs(self, path: str) -> None:
        from mssparkutils import fs
        fs.mkdirs(path)

    def mv(self, src: str, dst: str) -> None:
        from mssparkutils import fs
        fs.mv(src, dst)

    def md5(self, path: str) -> str:
        raw = self.head(path, 10 * 1024 * 1024)
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        return hashlib.md5(data).hexdigest()


class LocalFileSystem(FileSystem):

    def ls(self, path: str) -> List[FileInfo]:
        entries = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                entries.append(FileInfo(name, full, os.path.getsize(full)))
        return entries

    def head(self, path: str, max_bytes: int) -> bytes:
        with open(path, "rb") as f:
            return f.read(max_bytes)

    def mkdirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def mv(self, src: str, dst: str) -> None:
        shutil.move(src, dst)

    def md5(self, path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


def get_filesystem() -> FileSystem:
    try:
        from mssparkutils import fs
        fs.ls("/")
        return FabricFileSystem()
    except (ImportError, NameError):
        return LocalFileSystem()
```

### `src/gold_dimensional.py`

```python
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, current_timestamp, row_number, lit
from pyspark.sql.window import Window


def build_dim_student(training: DataFrame) -> DataFrame:
    window_spec = Window.orderBy("student_id")
    return (
        training.select("student_id")
        .dropDuplicates()
        .withColumn("student_key", row_number().over(window_spec))
        .withColumn("is_current", lit(True))
        .withColumn("last_refreshed", current_timestamp())
    )


def build_dim_course(training: DataFrame) -> DataFrame:
    window_spec = Window.orderBy("course_id")
    return (
        training.select("course_id")
        .dropDuplicates()
        .withColumn("course_key", row_number().over(window_spec))
        .withColumn("is_current", lit(True))
        .withColumn("last_refreshed", current_timestamp())
    )


def build_fact_training_completion(
    training: DataFrame, dim_student: DataFrame, dim_course: DataFrame
) -> DataFrame:
    return (
        training.alias("f")
        .join(dim_student.alias("s"), "student_id", "left")
        .join(dim_course.alias("c"), "course_id", "left")
        .select(
            col("s.student_key"),
            col("c.course_key"),
            col("f.enrolment_date"),
            col("f.completion_date"),
            col("f.score_pct"),
            col("f.is_completed"),
            col("f.enrolment_status"),
        )
        .withColumn("last_refreshed", current_timestamp())
    )
```

### `src/secrets.py`

```python
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretsProvider(ABC):

    @abstractmethod
    def get(self, scope: str, key: str) -> str:
        ...


class FabricSecrets(SecretsProvider):

    def get(self, scope: str, key: str) -> str:
        from mssparkutils import credentials
        return credentials.getSecret(scope, key)


class LocalSecrets(SecretsProvider):

    def get(self, scope: str, key: str) -> str:
        env_var = f"{scope}_{key}"
        val = os.environ.get(env_var)
        if val is None:
            raise KeyError(
                f"Secret not found. Set environment variable {env_var}"
            )
        return val


def get_secrets() -> SecretsProvider:
    try:
        from mssparkutils import credentials
        return FabricSecrets()
    except (ImportError, NameError):
        return LocalSecrets()
```

### `src/transformations/__init__.py`

```python

```

### `src/transformations/silver_training.py`

```python
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    coalesce,
    col,
    concat_ws,
    current_timestamp,
    lit,
    md5,
    to_date,
    trim,
    upper,
    when,
)


def transform_training_enrolments(df: DataFrame) -> DataFrame:
    if "_source_system" not in df.columns:
        df = df.withColumn("_source_system", lit("unknown"))
    return (
        df.withColumn("student_id", upper(trim(col("StudentID"))))
        .withColumn("course_id", upper(trim(col("CourseCode"))))
        .withColumn("enrolment_date", to_date(col("EnrolDate"), "dd/MM/yyyy"))
        .withColumn("completion_date", to_date(col("CompletionDate"), "dd/MM/yyyy"))
        .withColumn("score_pct", col("Score").cast("decimal(5,2)"))
        .withColumn(
            "enrolment_status",
            when(col("Status") == "C", "Completed")
            .when(col("Status") == "A", "Active")
            .when(col("Status") == "D", "Dropped")
            .otherwise("Unknown"),
        )
        .withColumn("is_completed", col("enrolment_status") == "Completed")
        .withColumn("valid_from", current_timestamp())
        .withColumn("valid_to", lit(None).cast("timestamp"))
        .withColumn("is_current", col("student_id").isNotNull())
        .withColumn("_silver_created", current_timestamp())
        .withColumn("_silver_updated", current_timestamp())
        .withColumn(
            "row_hash",
            md5(
                concat_ws(
                    "|",
                    col("student_id"),
                    col("course_id"),
                    col("enrolment_status"),
                    col("score_pct"),
                )
            ),
        )
        .select(
            "student_id",
            "course_id",
            "enrolment_date",
            "completion_date",
            "score_pct",
            "enrolment_status",
            "is_completed",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "_silver_created",
            "_silver_updated",
            "_source_system",
        )
    )
```

---

## Notebooks

### `notebooks/bronze/NB_00_Data_Profiling.py`

```python
# NB_00_Data_Profiling
# Layer: Pre-Bronze
# Purpose: Profile source files before production ingestion is designed.

from pyspark.sql.functions import col, count, when, countDistinct
from pyspark.sql.types import StringType
import json
from src.config_loader import load_config

config = load_config()
SOURCE_PATH = "Files/raw/profiling/"
REPORT_PATH = "Files/profiling_reports/"


def null_blank_rate(df):
    total = df.count()
    result = {}
    for column_name in df.columns:
        null_count = df.filter(
            col(column_name).isNull() | (col(column_name).cast(StringType()) == "")
        ).count()
        result[column_name] = {
            "null_count": null_count,
            "null_pct": round(null_count / total * 100, 2) if total else 0,
            "total_rows": total,
        }
    return result


def find_duplicates(df, key_columns):
    return (
        df.groupBy(key_columns)
        .count()
        .filter("count > 1")
        .orderBy("count", ascending=False)
    )


df_excel = (
    spark.read.format("com.crealytics.spark.excel")
    .option("header", "true")
    .option("inferSchema", "false")
    .option("dataAddress", "Sheet1!A1")
    .load(f"{SOURCE_PATH}training_enrolments_sample.xlsx")
)

print(f"Rows: {df_excel.count()}")
print(f"Columns: {df_excel.columns}")
df_excel.printSchema()

null_report = null_blank_rate(df_excel)
for column_name, stats in null_report.items():
    flag = " HIGH_NULL" if stats["null_pct"] > 10 else ""
    print(f"{column_name}: {stats['null_pct']}%{flag}")

find_duplicates(df_excel, ["StudentID", "CourseCode"]).show(20, truncate=False)
df_excel.groupBy("Status").count().orderBy("count", ascending=False).show()

report = {
    "training_excel": {
        "rows": df_excel.count(),
        "columns": len(df_excel.columns),
        "nulls": null_report,
    }
}

spark.sparkContext.parallelize([json.dumps(report, indent=2)]).saveAsTextFile(
    f"{REPORT_PATH}profile_{spark._sc.applicationId}"
)
```

### `notebooks/bronze/NB_02_Bronze_Excel_Ingest.py`

```python
# NB_02_Bronze_Excel_Ingest
# Layer: Bronze
# Purpose: Ingest Excel files with duplicate detection and file registry tracking.

import re
import uuid
from pyspark.sql.functions import current_timestamp, input_file_name, lit

from src.config_loader import load_config, lakehouse_table
from src.filesystem import get_filesystem
from src.file_ingestion import (
    md5_of_file,
    registry_action,
    register_file,
    log_schema_drift,
    move_file,
)

config = load_config()
fs = get_filesystem()

FILE_PATTERN = re.compile(
    r"^(training_enrolments|doctor_schedules|staff_roster|room_bookings)_"
    r"\d{4}_(0[1-9]|1[0-2]|W\d{2})\.xlsx$"
)

SOURCES = {
    "training": {
        "path": "Files/landing/training/",
        "table": lakehouse_table(config, "bronze", "bronze_training_enrolments"),
        "system": "excel_training",
    },
    "medical": {
        "path": "Files/landing/medical/",
        "table": lakehouse_table(config, "bronze", "bronze_doctor_schedules"),
        "system": "excel_medical",
    },
    "hr": {
        "path": "Files/landing/hr/",
        "table": lakehouse_table(config, "bronze", "bronze_hr_staff_excel"),
        "system": "excel_hr",
    },
    "facilities": {
        "path": "Files/landing/facilities/",
        "table": lakehouse_table(config, "bronze", "bronze_room_bookings"),
        "system": "excel_facilities",
    },
}

EXPECTED_COLUMNS = {
    "excel_training": ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"],
    "excel_medical": ["DoctorID", "ScheduleDate", "ShiftStart", "ShiftEnd", "HoursLogged", "ProcedureCode", "Department"],
    "excel_hr": ["EmployeeID", "FirstName", "LastName", "JobTitle", "Department", "ContractedHoursPerMonth"],
    "excel_facilities": ["RoomID", "BookedBy", "BookingDate", "StartTime", "EndTime", "Purpose"],
}


for source_name, cfg in SOURCES.items():
    print(f"Processing source: {source_name}")
    try:
        files = [f for f in fs.ls(cfg["path"]) if f.name.endswith(".xlsx")]
    except Exception:
        print(f"No landing folder found for {source_name}")
        continue

    for file_info in files:
        batch_id = str(uuid.uuid4())
        file_name = file_info.name
        file_path = file_info.path

        if not FILE_PATTERN.match(file_name):
            register_file(spark, config, file_name, file_path, file_info.size, "", cfg["system"], "FAILED", batch_id, error="Invalid filename")
            move_file(fs, file_path, "rejected")
            continue

        file_hash = md5_of_file(fs, file_path)
        action = registry_action(spark, config, file_name, file_hash)

        if action == "DUPLICATE":
            register_file(spark, config, file_name, file_path, file_info.size, file_hash, cfg["system"], "DUPLICATE", batch_id)
            move_file(fs, file_path, "rejected")
            continue

        try:
            df_raw = (
                spark.read.format("com.crealytics.spark.excel")
                .option("header", "true")
                .option("inferSchema", "false")
                .option("treatEmptyValuesAsNulls", "true")
                .option("dataAddress", "Sheet1!A1")
                .load(file_path)
            )
            row_count = df_raw.count()
            if row_count == 0:
                raise ValueError(f'File "{file_name}" contains 0 rows')

            drift_count = log_schema_drift(spark, config, cfg["system"], file_name, df_raw.columns, EXPECTED_COLUMNS.get(cfg["system"], []), batch_id)
            if drift_count:
                print(f"Schema drift detected for {file_name}: {drift_count} change(s). Check schema_change_log.")

            df_bronze = (
                df_raw.withColumn("_ingested_at", current_timestamp())
                .withColumn("_source_file", input_file_name())
                .withColumn("_source_system", lit(cfg["system"]))
                .withColumn("_batch_id", lit(batch_id))
                .withColumn("_file_hash", lit(file_hash))
                .withColumn("_is_correction", lit(action == "CORRECTION"))
            )

            df_bronze.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(cfg["table"])
            register_file(spark, config, file_name, file_path, file_info.size, file_hash, cfg["system"], "SUCCESS", batch_id, row_count)
            move_file(fs, file_path, "processed")
        except Exception as exc:
            register_file(spark, config, file_name, file_path, file_info.size, file_hash, cfg["system"], "FAILED", batch_id, error=str(exc))
            move_file(fs, file_path, "rejected")
            raise
```

### `notebooks/bronze/NB_03_Bronze_REST_API_Ingest.py`

```python
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
```

### `notebooks/silver/NB_04_Silver_Training_Enrolments.py`

```python
# NB_04_Silver_Training_Enrolments
# Layer: Silver
# Purpose: Clean and upsert training enrolments from Bronze to Silver.

from delta.tables import DeltaTable
from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.transformations.silver_training import transform_training_enrolments

config = load_config()

ENTITY = "training_enrolments"
TARGET_TABLE = lakehouse_table(config, "silver", "silver_training_enrolments")
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_training_enrolments")
SILVER_WATERMARK = lakehouse_table(config, "silver", "control_silver_watermark")

df_bronze = spark.sql(f"""
    SELECT *
    FROM {BRONZE_TABLE}
    WHERE _ingested_at > (
        SELECT coalesce(max(last_run_ts), timestamp('1900-01-01'))
        FROM {SILVER_WATERMARK}
        WHERE entity = '{ENTITY}'
    )
""")

df_silver = transform_training_enrolments(df_bronze)

if not spark.catalog.tableExists(TARGET_TABLE):
    df_silver.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)
else:
    target = DeltaTable.forName(spark, TARGET_TABLE)
    target.alias("t").merge(
        df_silver.alias("s"),
        "t.student_id = s.student_id AND t.course_id = s.course_id AND t.is_current = true",
    ).whenMatchedUpdate(
        condition="t.row_hash <> s.row_hash",
        set={
            "valid_to": "current_timestamp()",
            "is_current": "false",
            "_silver_updated": "current_timestamp()",
        },
    ).whenNotMatchedInsertAll().execute()

rows_merged = df_silver.count()

spark.sql(f"""
    MERGE INTO {SILVER_WATERMARK} t
    USING (
        SELECT '{ENTITY}' AS entity,
               current_timestamp() AS last_run_ts,
               {rows_merged} AS rows_merged,
               current_timestamp() AS updated_at
    ) s
    ON t.entity = s.entity
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

print(f"Silver transformation complete for {ENTITY}: {rows_merged} rows considered.")
```

### `notebooks/silver/NB_05_Bronze_to_Silver_Streaming.py`

```python
# NB_05_Bronze_to_Silver_Streaming
# Layer: Bronze to Silver
# Purpose: Micro-batch processing using Delta Change Data Feed.

from pyspark.sql.functions import col, current_timestamp, lit

from src.config_loader import load_config, lakehouse_table

config = load_config()
BRONZE_TABLE = lakehouse_table(config, "bronze", "bronze_lms_enrolments")
SILVER_TABLE = lakehouse_table(config, "silver", "silver_lms_enrolments")


def transform_to_silver(batch_df, batch_id):
    df_silver = (
        batch_df.filter(col("_change_type").isin("insert", "update_postimage"))
        .withColumn("_silver_ingested_at", current_timestamp())
        .withColumn("_stream_batch_id", lit(batch_id))
        .drop("_change_type", "_commit_version", "_commit_timestamp")
    )
    df_silver.write.format("delta").mode("append").saveAsTable(SILVER_TABLE)


df_stream = (
    spark.readStream.format("delta")
    .option("readChangeFeed", "true")
    .option("startingVersion", "latest")
    .table(BRONZE_TABLE)
)

query = (
    df_stream.writeStream.foreachBatch(transform_to_silver)
    .option("checkpointLocation", "Files/checkpoints/bronze_to_silver_lms")
    .trigger(processingTime="15 minutes")
    .start()
)

query.awaitTermination(timeout=900)
```

### `notebooks/gold/NB_06_Gold_Dimensional_Model.py`

```python
# NB_06_Gold_Dimensional_Model
# Layer: Gold
# Purpose: Build starter Gold dimensions and facts.

from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.gold_dimensional import build_dim_student, build_dim_course, build_fact_training_completion

config = load_config()

training = spark.table(lakehouse_table(config, "silver", "silver_training_enrolments")).filter(col("is_current") == True)

dim_student = build_dim_student(training)
dim_student.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "dim_student")
)

dim_course = build_dim_course(training)
dim_course.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "dim_course")
)

fact_training_completion = build_fact_training_completion(training, dim_student, dim_course)
fact_training_completion.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    lakehouse_table(config, "gold", "fact_training_completion")
)

print("Gold starter model complete.")
```

### `notebooks/gold/NB_09_PowerBI_Semantic_Model_Prep.py`

```python
# NB_09_PowerBI_Semantic_Model_Prep
# Layer: Gold
# Purpose: Build Power BI-ready summary tables.

from pyspark.sql.functions import avg, col, count, current_timestamp, round as spark_round, sum as spark_sum, when

from src.config_loader import load_config, lakehouse_table

config = load_config()

fact_table = lakehouse_table(config, "gold", "fact_training_completion")
dim_course_table = lakehouse_table(config, "gold", "dim_course")
vw_summary = lakehouse_table(config, "gold", "vw_training_summary")
file_ingestion_summary_table = lakehouse_table(config, "gold", "vw_file_ingestion_summary")
file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")

summary = spark.sql(f"""
    SELECT
        c.course_id,
        count(*) AS total_enrolments,
        sum(CASE WHEN f.is_completed THEN 1 ELSE 0 END) AS completed_count,
        round(avg(f.score_pct), 2) AS avg_score,
        round(sum(CASE WHEN f.is_completed THEN 1.0 ELSE 0 END) / count(*) * 100, 2) AS completion_rate_pct
    FROM {fact_table} f
    LEFT JOIN {dim_course_table} c ON f.course_key = c.course_key
    GROUP BY c.course_id
""").withColumn("last_refreshed", current_timestamp())

summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(vw_summary)

file_ingestion_summary = spark.sql(f"""
    SELECT
        cast(detected_at AS DATE) AS load_date,
        source_system,
        status,
        count(*) AS file_count,
        sum(row_count) AS total_rows,
        max(detected_at) AS last_seen
    FROM {file_ingestion_registry}
    WHERE cast(detected_at AS DATE) >= current_date() - 30
    GROUP BY cast(detected_at AS DATE), source_system, status
""")

file_ingestion_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    file_ingestion_summary_table
)

required_tables = [
    lakehouse_table(config, "gold", "dim_student"),
    lakehouse_table(config, "gold", "dim_course"),
    lakehouse_table(config, "gold", "fact_training_completion"),
    vw_summary,
    file_ingestion_summary_table,
]

for table_name in required_tables:
    rows = spark.table(table_name).count()
    print(f"{table_name}: {rows} rows")

print("Power BI semantic model prep complete.")
```

### `notebooks/ops/NB_01_Create_Control_Tables.py`

```python
# NB_01_Create_Control_Tables
# Layer: Setup
# Purpose: Create control tables, file registry, monitoring tables, and Files zones.

from pyspark.sql.functions import col, current_timestamp
from delta.tables import DeltaTable
from src.config_loader import load_config, lakehouse_name, lakehouse_table
from src.filesystem import get_filesystem

config = load_config()
fs = get_filesystem()

bronze_lh = lakehouse_name(config, "bronze")
silver_lh = lakehouse_name(config, "silver")

spark.sql(f"USE {bronze_lh}")

spark.sql("""
CREATE TABLE IF NOT EXISTS control_watermark (
    source_system STRING NOT NULL,
    last_run_ts TIMESTAMP,
    last_batch_id STRING,
    last_row_count LONG,
    status STRING,
    updated_at TIMESTAMP
) USING DELTA
COMMENT 'Tracks last successful ingest per source'
""")

sources = [
    ("excel_training", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_medical", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_hr", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("excel_facilities", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("rest_api_lms", "1900-01-01 00:00:00", "INIT", 0, "READY"),
    ("rest_api_hr", "1900-01-01 00:00:00", "INIT", 0, "READY"),
]

df_sources = spark.createDataFrame(
    sources,
    "source_system STRING, last_run_ts STRING, last_batch_id STRING, last_row_count LONG, status STRING",
).withColumn("last_run_ts", col("last_run_ts").cast("timestamp")).withColumn(
    "updated_at", current_timestamp()
)

DeltaTable.forName(spark, f"{bronze_lh}.control_watermark").alias("t").merge(
    df_sources.alias("s"), "t.source_system = s.source_system"
).whenNotMatchedInsertAll().execute()

spark.sql("""
CREATE TABLE IF NOT EXISTS control_pipeline_log (
    log_id STRING,
    pipeline_name STRING,
    source_system STRING,
    batch_id STRING,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    rows_read LONG,
    rows_written LONG,
    status STRING,
    error_message STRING
) USING DELTA
COMMENT 'Audit log for every pipeline and notebook run'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS file_ingestion_registry (
    file_id STRING,
    file_name STRING,
    file_path STRING,
    file_size_bytes LONG,
    file_hash_md5 STRING,
    source_system STRING,
    detected_at TIMESTAMP,
    processed_at TIMESTAMP,
    row_count LONG,
    status STRING,
    batch_id STRING,
    error_message STRING
) USING DELTA
COMMENT 'Registry of every file seen for duplicate detection'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS api_call_log (
    call_id STRING,
    api_name STRING,
    endpoint STRING,
    http_status INT,
    attempt_num INT,
    response_ms LONG,
    records_returned LONG,
    watermark_used TIMESTAMP,
    called_at TIMESTAMP,
    status STRING,
    error_message STRING
) USING DELTA
COMMENT 'Tracks every REST API call for retry, SLA, and failure monitoring'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS schema_change_log (
    change_id STRING,
    source_system STRING,
    file_name STRING,
    change_type STRING,
    column_name STRING,
    previous_value STRING,
    detected_at TIMESTAMP,
    batch_id STRING,
    resolved BOOLEAN
) USING DELTA
COMMENT 'Tracks Excel column header changes between loads'
""")

folders = [
    "Files/landing/training",
    "Files/landing/medical",
    "Files/landing/hr",
    "Files/landing/facilities",
    "Files/processed/training",
    "Files/processed/medical",
    "Files/processed/hr",
    "Files/processed/facilities",
    "Files/rejected/training",
    "Files/rejected/medical",
    "Files/rejected/hr",
    "Files/rejected/facilities",
    "Files/archive",
    "Files/profiling_reports",
    "Files/checkpoints",
    "Files/checkpoints/stream_bronze_to_silver_lms",
]

for folder in folders:
    fs.mkdirs(folder)

spark.sql(f"USE {silver_lh}")

spark.sql("""
CREATE TABLE IF NOT EXISTS control_silver_watermark (
    entity STRING NOT NULL,
    last_run_ts TIMESTAMP,
    rows_merged LONG,
    updated_at TIMESTAMP
) USING DELTA
COMMENT 'Silver transformation watermark per entity'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS dq_log (
    run_id STRING,
    entity STRING,
    check_name STRING,
    description STRING,
    total_rows LONG,
    failed_rows LONG,
    fail_pct DECIMAL(5,2),
    status STRING,
    severity STRING,
    run_ts TIMESTAMP
) USING DELTA
COMMENT 'Data quality check results'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS monitoring_alerts (
    alert_ts TIMESTAMP,
    alert_type STRING,
    entity STRING,
    severity STRING,
    message STRING,
    value DOUBLE,
    threshold DOUBLE,
    status STRING,
    run_ts TIMESTAMP
) USING DELTA
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS monitoring_metrics (
    snapshot_ts TIMESTAMP,
    entity STRING,
    metric_name STRING,
    value DOUBLE,
    threshold DOUBLE,
    unit STRING
) USING DELTA
""")

print("Control tables and folder structure are ready.")
```

### `notebooks/ops/NB_07_Data_Quality_Checks.py`

```python
# NB_07_Data_Quality_Checks
# Layer: Silver
# Purpose: Log data quality results and fail fast on severe issues.

from pyspark.sql.functions import col, current_timestamp

from src.config_loader import load_config, lakehouse_table
from src.data_quality import dq_check

config = load_config()
dq_log_table = lakehouse_table(config, "silver", "dq_log")

results = []

training = spark.table(lakehouse_table(config, "silver", "silver_training_enrolments"))

results.append(
    dq_check(training, "training_enrolments", "no_null_student_id", "Student id must not be null", col("student_id").isNull())
)
results.append(
    dq_check(training, "training_enrolments", "no_null_course_id", "Course id must not be null", col("course_id").isNull())
)
results.append(
    dq_check(
        training,
        "training_enrolments",
        "score_range_0_100",
        "Score must be between 0 and 100 when supplied",
        col("score_pct").isNotNull() & ((col("score_pct") < 0) | (col("score_pct") > 100)),
    )
)
results.append(
    dq_check(
        training,
        "training_enrolments",
        "enrolment_date_not_future",
        "Enrolment date must not be in the future",
        col("enrolment_date") > current_timestamp().cast("date"),
    )
)

import uuid
from datetime import datetime, timezone

dq_df = spark.createDataFrame(
    [
        (
            r["run_id"],
            r["entity"],
            r["check_name"],
            r["description"],
            r["total_rows"],
            r["failed_rows"],
            r["fail_pct"],
            r["status"],
            r["severity"],
        )
        for r in results
    ],
    "run_id STRING, entity STRING, check_name STRING, description STRING, total_rows LONG, "
    "failed_rows LONG, fail_pct DECIMAL(5,2), status STRING, severity STRING",
).withColumn("run_ts", current_timestamp())

dq_df.write.format("delta").mode("append").saveAsTable(dq_log_table)

if any(r["status"] == "FAIL" for r in results):
    raise Exception("DQ failure detected. Stop downstream Gold processing.")

print("DQ checks complete.")
```

### `notebooks/ops/NB_08_Monitoring_and_Alerting.py`

```python
# NB_08_Monitoring_and_Alerting
# Layer: Operations
# Purpose: Capture monitoring alerts for freshness and DQ failures.

from pyspark.sql.functions import current_timestamp

from src.config_loader import load_config, lakehouse_table

config = load_config()

control_watermark = lakehouse_table(config, "bronze", "control_watermark")
dq_log_table = lakehouse_table(config, "silver", "dq_log")
api_call_log = lakehouse_table(config, "bronze", "api_call_log")
file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
monitoring_alerts = lakehouse_table(config, "silver", "monitoring_alerts")

alerts = []

freshness = spark.sql(f"""
    SELECT source_system, last_run_ts
    FROM {control_watermark}
    WHERE last_run_ts < current_timestamp() - INTERVAL 26 HOURS
""")

for row in freshness.collect():
    alerts.append((
        "FRESHNESS",
        row["source_system"],
        "HIGH",
        f"No successful load within SLA for {row['source_system']}",
        26.0,
        26.0,
        "OPEN",
    ))

dq_failures = spark.sql(f"""
    SELECT entity, check_name, fail_pct
    FROM {dq_log_table}
    WHERE status = 'FAIL'
      AND run_ts >= current_timestamp() - INTERVAL 30 MINUTES
""")

for row in dq_failures.collect():
    alerts.append((
        "DQ_FAILURE",
        row["entity"],
        "HIGH",
        f"DQ check failed: {row['check_name']}",
        float(row["fail_pct"]),
        0.0,
        "OPEN",
    ))

api_health = spark.sql(f"""
    SELECT api_name,
           sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
           sum(CASE WHEN status = 'RATE_LIMITED' THEN 1 ELSE 0 END) AS rate_limits,
           round(avg(response_ms), 0) AS avg_response_ms
    FROM {api_call_log}
    WHERE called_at >= current_timestamp() - INTERVAL 24 HOURS
    GROUP BY api_name
""")

for row in api_health.collect():
    if row["failures"] and row["failures"] > 0:
        alerts.append((
            "API_FAILURE",
            row["api_name"],
            "HIGH",
            f"{row['failures']} API failures in the last 24h",
            float(row["failures"]),
            0.0,
            "OPEN",
        ))
    if row["rate_limits"] and row["rate_limits"] > 5:
        alerts.append((
            "API_RATE_LIMIT",
            row["api_name"],
            "MEDIUM",
            f"{row['rate_limits']} API rate-limit responses in the last 24h",
            float(row["rate_limits"]),
            5.0,
            "OPEN",
        ))
    if row["avg_response_ms"] and row["avg_response_ms"] > 5000:
        alerts.append((
            "API_SLOW",
            row["api_name"],
            "MEDIUM",
            f"Average response time is {row['avg_response_ms']}ms",
            float(row["avg_response_ms"]),
            5000.0,
            "OPEN",
        ))

file_health = spark.sql(f"""
    SELECT source_system, status, count(*) AS file_count
    FROM {file_ingestion_registry}
    WHERE cast(detected_at AS DATE) = current_date()
    GROUP BY source_system, status
""")

for row in file_health.collect():
    if row["status"] == "DUPLICATE":
        alerts.append((
            "DUPLICATE_FILE",
            row["source_system"],
            "MEDIUM",
            f"{row['file_count']} duplicate file(s) detected today",
            float(row["file_count"]),
            0.0,
            "OPEN",
        ))
    if row["status"] == "FAILED":
        alerts.append((
            "FILE_INGEST_FAILED",
            row["source_system"],
            "HIGH",
            f"{row['file_count']} file ingestion failure(s) today",
            float(row["file_count"]),
            0.0,
            "OPEN",
        ))

if alerts:
    alert_df = spark.createDataFrame(
        alerts,
        "alert_type STRING, entity STRING, severity STRING, message STRING, value DOUBLE, threshold DOUBLE, status STRING",
    ).withColumn("alert_ts", current_timestamp()).withColumn("run_ts", current_timestamp())
    alert_df.write.format("delta").mode("append").saveAsTable(monitoring_alerts)
    print(f"Raised {len(alerts)} alerts.")
else:
    print("No alerts raised.")
```

### `notebooks/ops/NB_10_Purview_Lineage_Annotations.py`

```python
# NB_10_Purview_Lineage_Annotations
# Layer: Governance
# Purpose: Apply Delta table properties that support cataloguing and lineage review.

from datetime import datetime, timezone

from src.config_loader import load_config, lakehouse_table

config = load_config()

TABLE_CATALOGUE = [
    {
        "table": lakehouse_table(config, "bronze", "bronze_training_enrolments"),
        "description": "Raw training enrolment data ingested from controlled Excel landing folders.",
        "source": "Files/landing/training/training_enrolments_*.xlsx",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Bronze",
        "pii": "false",
        "retention_years": "7",
    },
    {
        "table": lakehouse_table(config, "bronze", "file_ingestion_registry"),
        "description": "Registry of every file ingested. MD5 hash enables duplicate detection and audit reconciliation.",
        "source": "Generated by NB_02_Bronze_Excel_Ingest",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Bronze",
        "pii": "false",
        "retention_years": "7",
    },
    {
        "table": lakehouse_table(config, "bronze", "api_call_log"),
        "description": "REST API call audit log for SLA monitoring and failure diagnosis.",
        "source": "Generated by NB_03_Bronze_REST_API_Ingest",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Bronze",
        "pii": "false",
        "retention_years": "2",
    },
    {
        "table": lakehouse_table(config, "bronze", "schema_change_log"),
        "description": "Excel schema drift log for new and removed source columns.",
        "source": "Generated by NB_02_Bronze_Excel_Ingest",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Bronze",
        "pii": "false",
        "retention_years": "3",
    },
    {
        "table": lakehouse_table(config, "silver", "silver_training_enrolments"),
        "description": "Cleansed and deduplicated training enrolments.",
        "source": lakehouse_table(config, "bronze", "bronze_training_enrolments"),
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Silver",
        "pii": "false",
        "retention_years": "5",
    },
    {
        "table": lakehouse_table(config, "gold", "fact_training_completion"),
        "description": "Gold fact table for training completion analytics.",
        "source": lakehouse_table(config, "silver", "silver_training_enrolments"),
        "owner": "analytics@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Gold",
        "pii": "false",
        "retention_years": "3",
    },
]

for entry in TABLE_CATALOGUE:
    stamp = str(datetime.now(timezone.utc))
    props = {
        "description": entry["description"],
        "lineage.source": entry["source"],
        "lineage.layer": entry["layer"],
        "owner": entry["owner"],
        "sensitivity_label": entry["sensitivity"],
        "gdpr.contains_pii": entry["pii"],
        "data_retention_years": entry["retention_years"],
        "last_annotated": stamp,
    }
    prop_sql = ", ".join([f"'{key}' = '{value}'" for key, value in props.items()])
    try:
        spark.sql(f"ALTER TABLE {entry['table']} SET TBLPROPERTIES ({prop_sql})")
        print(f"Annotated {entry['table']}")
    except Exception as exc:
        print(f"Could not annotate {entry['table']}: {exc}")
```

### `notebooks/ops/NB_11_Delta_Maintenance.py`

```python
# NB_11_Delta_Maintenance
# Layer: All
# Purpose: Weekly Delta housekeeping.

from src.config_loader import load_config, lakehouse_table

config = load_config()

VACUUM_HOURS = 168

TABLES = [
    (lakehouse_table(config, "bronze", "bronze_training_enrolments"), None),
    (lakehouse_table(config, "bronze", "bronze_lms_enrolments"), None),
    (lakehouse_table(config, "bronze", "file_ingestion_registry"), ["source_system"]),
    (lakehouse_table(config, "bronze", "api_call_log"), ["api_name"]),
    (lakehouse_table(config, "silver", "silver_training_enrolments"), ["student_id", "course_id"]),
    (lakehouse_table(config, "silver", "dq_log"), ["entity"]),
    (lakehouse_table(config, "gold", "fact_training_completion"), ["student_key", "course_key"]),
    (lakehouse_table(config, "gold", "dim_student"), ["student_id"]),
    (lakehouse_table(config, "gold", "dim_course"), ["course_id"]),
]

for table_name, zorder_columns in TABLES:
    print(f"Maintaining {table_name}")
    spark.sql(f"VACUUM {table_name} RETAIN {VACUUM_HOURS} HOURS")
    if zorder_columns:
        zorder_sql = ", ".join(zorder_columns)
        spark.sql(f"OPTIMIZE {table_name} ZORDER BY ({zorder_sql})")
    spark.sql(f"ANALYZE TABLE {table_name} COMPUTE STATISTICS")

file_ingestion_registry = lakehouse_table(config, "bronze", "file_ingestion_registry")
file_ingestion_registry_archive = lakehouse_table(config, "bronze", "file_ingestion_registry_archive")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {file_ingestion_registry_archive}
    USING DELTA AS
    SELECT * FROM {file_ingestion_registry} WHERE 1 = 0
""")

archive_count = spark.sql(f"""
    SELECT count(*) AS row_count
    FROM {file_ingestion_registry}
    WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
""").first()["row_count"]

if archive_count:
    spark.sql(f"""
        INSERT INTO {file_ingestion_registry_archive}
        SELECT *
        FROM {file_ingestion_registry}
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    spark.sql(f"""
        DELETE FROM {file_ingestion_registry}
        WHERE detected_at < current_timestamp() - INTERVAL 90 DAYS
    """)
    print(f"Archived {archive_count} file registry rows older than 90 days.")

print("Delta maintenance complete.")
```

---

## Tests

### `tests/test_config.py`

```python
import json
import os
import pytest

CONFIG_DIR = "config"

def test_config_files_valid_json():
    """
    Ensure all config files are valid JSON.
    """
    config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith(".json")]
    for file_name in config_files:
        with open(os.path.join(CONFIG_DIR, file_name), 'r') as f:
            try:
                json.load(f)
            except json.JSONDecodeError:
                pytest.fail(f"{file_name} is not a valid JSON file")

def test_config_keys_consistency():
    """
    Ensure all environment configs have the same required keys.
    """
    required_keys = {"environment", "workspace", "bronze_lakehouse", "silver_lakehouse", "gold_lakehouse", "lakehouses"}
    
    config_files = ["config_dev.json", "config_prod.json", "config_test.json"]
    
    for file_name in config_files:
        path = os.path.join(CONFIG_DIR, file_name)
        if not os.path.exists(path):
            continue
            
        with open(path, 'r') as f:
            config = json.load(f)
            missing_keys = required_keys - set(config.keys())
            assert not missing_keys, f"{file_name} is missing keys: {missing_keys}"
```

### `tests/test_gold_smoke.py`

```python
import pytest
from pyspark.sql import SparkSession

from src.config_loader import lakehouse_table, load_config


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[*]").getOrCreate()


@pytest.fixture(scope="session")
def config():
    return load_config()


def test_gold_tables_exist(spark, config):
    tables = [t.name for t in spark.catalog.listTables(config["lakehouses"]["gold"])]
    expected_tables = ["dim_student", "dim_course", "fact_training_completion"]

    for table in expected_tables:
        assert table in tables


def test_gold_fact_completeness(spark, config):
    fact_df = spark.table(lakehouse_table(config, "gold", "fact_training_completion"))

    null_student_keys = fact_df.filter("student_key IS NULL").count()
    null_course_keys = fact_df.filter("course_key IS NULL").count()

    assert null_student_keys == 0, "Found null student keys in fact table"
    assert null_course_keys == 0, "Found null course keys in fact table"
```

### `tests/test_silver_transformations.py`

```python
import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType

from src.transformations.silver_training import transform_training_enrolments


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder \
        .appName("unit-tests") \
        .master("local[*]") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()


class TestTransformTrainingEnrolments:

    def test_standard_case(self, spark):
        data = [("  S123  ", "C001", "01/01/2023", "01/02/2023", "85.5", "C")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["student_id"] == "S123"
        assert row["course_id"] == "C001"
        assert str(row["enrolment_date"]) == "2023-01-01"
        assert str(row["completion_date"]) == "2023-02-01"
        assert row["score_pct"] == 85.50
        assert row["enrolment_status"] == "Completed"
        assert row["is_completed"] is True
        assert row["row_hash"] is not None

    def test_trim_and_upper(self, spark):
        data = [("  abc123  ", "  XYZ  ", "01/01/2023", None, None, "A")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["student_id"] == "ABC123"
        assert row["course_id"] == "XYZ"

    def test_status_mapping(self, spark):
        data = [
            ("S1", "C1", "01/01/2023", None, None, "C"),
            ("S2", "C2", "01/01/2023", None, None, "A"),
            ("S3", "C3", "01/01/2023", None, None, "D"),
            ("S4", "C4", "01/01/2023", None, None, "X"),
        ]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        rows = {r["student_id"]: r for r in df_output.collect()}

        assert rows["S1"]["enrolment_status"] == "Completed"
        assert rows["S1"]["is_completed"] is True
        assert rows["S2"]["enrolment_status"] == "Active"
        assert rows["S2"]["is_completed"] is False
        assert rows["S3"]["enrolment_status"] == "Dropped"
        assert rows["S3"]["is_completed"] is False
        assert rows["S4"]["enrolment_status"] == "Unknown"
        assert rows["S4"]["is_completed"] is False

    def test_null_score_cast_to_zero(self, spark):
        data = [("S1", "C1", "01/01/2023", None, None, "C")]
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        df_input = spark.createDataFrame(data, schema)

        df_output = transform_training_enrolments(df_input)
        row = df_output.collect()[0]

        assert row["score_pct"] is None

    def test_empty_input_does_not_crash(self, spark):
        schema = StructType([
            StructField("StudentID", StringType()),
            StructField("CourseCode", StringType()),
            StructField("EnrolDate", StringType()),
            StructField("CompletionDate", StringType()),
            StructField("Score", StringType()),
            StructField("Status", StringType()),
        ])
        df_input = spark.createDataFrame([], schema)

        df_output = transform_training_enrolments(df_input)

        assert df_output.count() == 0

    def test_row_hash_changes_on_data_change(self, spark):
        schema = ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"]
        data_a = [("S1", "C1", "01/01/2023", None, "80", "C")]
        data_b = [("S1", "C1", "01/01/2023", None, "90", "C")]

        hash_a = transform_training_enrolments(spark.createDataFrame(data_a, schema)).collect()[0]["row_hash"]
        hash_b = transform_training_enrolments(spark.createDataFrame(data_b, schema)).collect()[0]["row_hash"]

        assert hash_a != hash_b
```

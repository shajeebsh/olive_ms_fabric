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

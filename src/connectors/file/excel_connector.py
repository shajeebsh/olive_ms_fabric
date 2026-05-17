from __future__ import annotations

import re
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import input_file_name, lit

from src.config_loader import lakehouse_table
from src.connectors.base import BaseConnector
from src.file_ingestion import (
    log_schema_drift,
    md5_of_file,
    move_file,
    register_file,
    registry_action,
)
from src.filesystem import get_filesystem


FILE_PATTERN = re.compile(
    r"^(training_enrolments|doctor_schedules|staff_roster|room_bookings)_"
    r"\d{4}_(0[1-9]|1[0-2]|W\d{2})\.xlsx$"
)

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "excel_training": [
        "StudentID", "CourseCode", "EnrolDate", "CompletionDate",
        "Score", "Status",
    ],
    "excel_medical": [
        "DoctorID", "ScheduleDate", "ShiftStart", "ShiftEnd",
        "HoursLogged", "ProcedureCode", "Department",
    ],
    "excel_hr": [
        "EmployeeID", "FirstName", "LastName", "JobTitle",
        "Department", "ContractedHoursPerMonth",
    ],
    "excel_facilities": [
        "RoomID", "BookedBy", "BookingDate", "StartTime",
        "EndTime", "Purpose",
    ],
}

SOURCE_LANDING_PATHS = {
    "excel_training": "Files/landing/training/",
    "excel_medical": "Files/landing/medical/",
    "excel_hr": "Files/landing/hr/",
    "excel_facilities": "Files/landing/facilities/",
}


class ExcelConnector(BaseConnector):
    connector_type = "file_excel"

    def __init__(
        self,
        source_system: str = "excel_training",
        landing_path: str | None = None,
    ):
        super().__init__(source_system=source_system)
        self.landing_path = landing_path or SOURCE_LANDING_PATHS.get(
            source_system, "Files/landing/"
        )
        self.expected_cols = EXPECTED_COLUMNS.get(source_system, [])

    def extract(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        batch_id: str,
    ) -> DataFrame | None:
        fs = get_filesystem()
        try:
            files = [f for f in fs.ls(self.landing_path)
                     if f.name.endswith(".xlsx")]
        except Exception:
            print(f"No landing folder found: {self.landing_path}")
            return None

        if not files:
            return None

        dfs = []
        for file_info in files:
            file_name = file_info.name
            file_path = file_info.path

            if not FILE_PATTERN.match(file_name):
                register_file(
                    spark, config, file_name, file_path,
                    file_info.size, "", self.source_system,
                    "FAILED", batch_id, error="Invalid filename",
                )
                move_file(fs, file_path, "rejected")
                continue

            file_hash = md5_of_file(fs, file_path)
            action = registry_action(
                spark, config, file_name, file_hash
            )

            if action == "DUPLICATE":
                register_file(
                    spark, config, file_name, file_path,
                    file_info.size, file_hash, self.source_system,
                    "DUPLICATE", batch_id,
                )
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
                    register_file(
                        spark, config, file_name, file_path,
                        file_info.size, file_hash, self.source_system,
                        "FAILED", batch_id, error="File contains 0 rows",
                    )
                    move_file(fs, file_path, "rejected")
                    continue

                drift_count = log_schema_drift(
                    spark, config, self.source_system, file_name,
                    df_raw.columns, self.expected_cols, batch_id,
                )
                if drift_count:
                    print(
                        f"Schema drift for {file_name}: "
                        f"{drift_count} change(s)."
                    )

                df_enriched = (
                    df_raw
                    .withColumn("_source_file", input_file_name())
                    .withColumn("_file_hash", lit(file_hash))
                    .withColumn(
                        "_is_correction", lit(action == "CORRECTION")
                    )
                )

                register_file(
                    spark, config, file_name, file_path,
                    file_info.size, file_hash, self.source_system,
                    "SUCCESS", batch_id, row_count,
                )
                move_file(fs, file_path, "processed")
                dfs.append(df_enriched)

            except Exception as exc:
                register_file(
                    spark, config, file_name, file_path,
                    file_info.size, file_hash, self.source_system,
                    "FAILED", batch_id, error=str(exc),
                )
                move_file(fs, file_path, "rejected")

        if not dfs:
            return None

        result = dfs[0]
        for d in dfs[1:]:
            result = result.unionByName(d, allowMissingColumns=True)
        return result


def register_connectors(registry, config=None):
    for source_system in SOURCE_LANDING_PATHS:
        registry.register(ExcelConnector(source_system=source_system))

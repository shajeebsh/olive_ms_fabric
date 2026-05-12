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

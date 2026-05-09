# NB_02_Bronze_Excel_Ingest
# Layer: Bronze
# Purpose: Ingest Excel files with duplicate detection and file registry tracking.

import hashlib
import re
import uuid
from datetime import datetime
from pyspark.sql.functions import current_timestamp, input_file_name, lit

FILE_PATTERN = re.compile(
    r"^(training_enrolments|doctor_schedules|staff_roster|room_bookings)_"
    r"\d{4}_(0[1-9]|1[0-2]|W\d{2})\.xlsx$"
)

SOURCES = {
    "training": {
        "path": "Files/landing/training/",
        "table": "Bronze_Lakehouse.bronze_training_enrolments",
        "system": "excel_training",
    },
    "medical": {
        "path": "Files/landing/medical/",
        "table": "Bronze_Lakehouse.bronze_doctor_schedules",
        "system": "excel_medical",
    },
    "hr": {
        "path": "Files/landing/hr/",
        "table": "Bronze_Lakehouse.bronze_hr_staff_excel",
        "system": "excel_hr",
    },
    "facilities": {
        "path": "Files/landing/facilities/",
        "table": "Bronze_Lakehouse.bronze_room_bookings",
        "system": "excel_facilities",
    },
}

EXPECTED_COLUMNS = {
    "excel_training": ["StudentID", "CourseCode", "EnrolDate", "CompletionDate", "Score", "Status"],
    "excel_medical": ["DoctorID", "ScheduleDate", "ShiftStart", "ShiftEnd", "HoursLogged", "ProcedureCode", "Department"],
    "excel_hr": ["EmployeeID", "FirstName", "LastName", "JobTitle", "Department", "ContractedHoursPerMonth"],
    "excel_facilities": ["RoomID", "BookedBy", "BookingDate", "StartTime", "EndTime", "Purpose"],
}


def md5_of_file(path):
    content = mssparkutils.fs.head(path, 10 * 1024 * 1024)
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.md5(data).hexdigest()


def registry_action(file_name, file_hash):
    existing_hash = spark.sql(f"""
        SELECT file_name
        FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_hash_md5 = '{file_hash}' AND status = 'SUCCESS'
        LIMIT 1
    """)
    if existing_hash.count():
        return "DUPLICATE"

    existing_name = spark.sql(f"""
        SELECT file_name
        FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_name = '{file_name}' AND status = 'SUCCESS'
        LIMIT 1
    """)
    if existing_name.count():
        return "CORRECTION"

    failed_hash = spark.sql(f"""
        SELECT file_id
        FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_hash_md5 = '{file_hash}' AND status = 'FAILED'
        LIMIT 1
    """)
    if failed_hash.count():
        return "RETRY"

    return "NEW"


def register_file(file_name, file_path, file_size, file_hash, source, status, batch_id, row_count=0, error=None):
    now = datetime.utcnow()
    rows = [(
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
        str(error) if error else None,
    )]
    spark.createDataFrame(
        rows,
        "file_id STRING, file_name STRING, file_path STRING, file_size_bytes LONG, "
        "file_hash_md5 STRING, source_system STRING, detected_at TIMESTAMP, "
        "processed_at TIMESTAMP, row_count LONG, status STRING, batch_id STRING, error_message STRING",
    ).write.format("delta").mode("append").saveAsTable("Bronze_Lakehouse.file_ingestion_registry")


def log_schema_drift(source_system, file_name, actual_columns, batch_id):
    expected_columns = EXPECTED_COLUMNS.get(source_system, [])
    if not expected_columns:
        return 0

    changes = []
    now = datetime.utcnow()
    for column_name in actual_columns:
        if column_name not in expected_columns:
            changes.append((
                str(uuid.uuid4()),
                source_system,
                file_name,
                "NEW_COLUMN",
                column_name,
                None,
                now,
                batch_id,
                False,
            ))
    for column_name in expected_columns:
        if column_name not in actual_columns:
            changes.append((
                str(uuid.uuid4()),
                source_system,
                file_name,
                "REMOVED_COLUMN",
                column_name,
                column_name,
                now,
                batch_id,
                False,
            ))

    if changes:
        spark.createDataFrame(
            changes,
            "change_id STRING, source_system STRING, file_name STRING, change_type STRING, "
            "column_name STRING, previous_value STRING, detected_at TIMESTAMP, batch_id STRING, resolved BOOLEAN",
        ).write.format("delta").mode("append").saveAsTable("Bronze_Lakehouse.schema_change_log")
    return len(changes)


def move_file(src_path, zone):
    file_name = src_path.split("/")[-1]
    source_dir = src_path.split("/")[-2]
    dest = f"Files/{zone}/{source_dir}/{file_name}"
    mssparkutils.fs.mkdirs(f"Files/{zone}/{source_dir}/")
    mssparkutils.fs.mv(src_path, dest)


for source_name, cfg in SOURCES.items():
    print(f"Processing source: {source_name}")
    try:
        files = [f for f in mssparkutils.fs.ls(cfg["path"]) if f.name.endswith(".xlsx")]
    except Exception:
        print(f"No landing folder found for {source_name}")
        continue

    for file_info in files:
        batch_id = str(uuid.uuid4())
        file_name = file_info.name
        file_path = file_info.path

        if not FILE_PATTERN.match(file_name):
            register_file(file_name, file_path, file_info.size, "", cfg["system"], "FAILED", batch_id, error="Invalid filename")
            move_file(file_path, "rejected")
            continue

        file_hash = md5_of_file(file_path)
        action = registry_action(file_name, file_hash)

        if action == "DUPLICATE":
            register_file(file_name, file_path, file_info.size, file_hash, cfg["system"], "DUPLICATE", batch_id)
            move_file(file_path, "rejected")
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

            drift_count = log_schema_drift(cfg["system"], file_name, df_raw.columns, batch_id)
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
            register_file(file_name, file_path, file_info.size, file_hash, cfg["system"], "SUCCESS", batch_id, row_count)
            move_file(file_path, "processed")
        except Exception as exc:
            register_file(file_name, file_path, file_info.size, file_hash, cfg["system"], "FAILED", batch_id, error=exc)
            move_file(file_path, "rejected")
            raise

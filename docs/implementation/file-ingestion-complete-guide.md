# File Ingestion Complete Guide

Complete guide covering how raw Excel files flow into the Bronze Lakehouse, how duplicate files are detected and handled, four options for how the client delivers files, and the PySpark code for each scenario.

---

## 1. Files / Folder Structure

### The problem with a flat /Files folder

**Never read directly from one flat /Files folder**

If all Excel files land in one folder with no structure, you have no way to know: which files have already been processed, which are new, whether the same file was uploaded twice with a different name, or which department it belongs to. You need a structured landing zone with clear zones for incoming, processed, and rejected files.

### The correct folder structure inside Bronze_Lakehouse/Files/

```
Files/
│
├── landing/                          ← client drops files HERE only
│   ├── training/
│   │   ├── training_enrolments_2025_05.xlsx   ← new file
│   │   └── training_enrolments_2025_04.xlsx   ← last month (not yet moved)
│   ├── medical/
│   │   └── doctor_schedules_2025_W20.xlsx
│   ├── hr/
│   │   └── staff_roster_2025_05.xlsx
│   └── facilities/
│       └── room_bookings_2025_05.xlsx
│
├── processed/                        ← pipeline moves files here after success
│   ├── training/
│   │   └── training_enrolments_2025_04.xlsx  ← already loaded
│   ├── medical/
│   └── hr/
│
├── rejected/                         ← pipeline moves files here on failure
│   └── training_enrolments_CORRUPT.xlsx  ← bad file, with error log
│
├── archive/                          ← processed files older than 90 days
│
└── file_registry/                    ← Delta table tracking every file ever seen
    └── (Delta table: file_ingestion_registry)
```

### The file_ingestion_registry Delta table — the key to everything

**This table is the memory of your ingestion layer**

Every file the pipeline has ever seen is recorded here with its MD5 hash, size, status, and batch ID. Before processing any file, the pipeline checks this table. If the file's hash already exists with status SUCCESS, it is a duplicate — skip it. This is the foundation of idempotent, duplicate-safe ingestion.

```sql
-- Create once in NB_01_Create_Control_Tables
CREATE TABLE IF NOT EXISTS Bronze_Lakehouse.file_ingestion_registry (
    file_id          STRING,       -- UUID generated on first sight
    file_name        STRING,       -- original filename
    file_path        STRING,       -- full path in Files/ zone
    file_size_bytes  LONG,         -- size at time of detection
    file_hash_md5    STRING,       -- MD5 of file content — the duplicate key
    source_system    STRING,       -- 'excel_training', 'excel_medical' etc
    detected_at      TIMESTAMP,    -- when pipeline first saw this file
    processed_at     TIMESTAMP,    -- when pipeline finished loading it
    row_count        LONG,         -- rows loaded to Bronze
    status           STRING,       -- PENDING / SUCCESS / FAILED / DUPLICATE / SKIPPED
    batch_id         STRING,       -- links to control_pipeline_log
    error_message    STRING        -- populated only on FAILED status
) USING DELTA
COMMENT 'Registry of every file seen by ingestion pipelines';
```

---

## 2. Duplicate Handling

### The four types of duplicate you will encounter

**Type 1 — Exact same file uploaded twice (same name, same content)**

Most common. Training manager uploads January file, realises they uploaded it already, uploads again. The MD5 hash of both files will be identical. Detection: compute hash on arrival, check registry. Action: mark as DUPLICATE, move to rejected/, send alert. Do NOT load.

**Type 2 — Same content, different filename**

Training manager renames the file before uploading. "training_jan_v1.xlsx" vs "training_january_FINAL.xlsx" — same rows inside. Detection: MD5 hash match in registry even though filename is different. Action: mark as DUPLICATE, alert with message "Content already loaded under different filename [original name]". This is the sneaky one that catches people out if they only check filenames.

**Type 3 — Updated file with same name (corrected data)**

Training manager uploads "training_jan.xlsx", realises row 47 had a typo, fixes it, uploads "training_jan.xlsx" again. Same name but different content — different MD5 hash. This is NOT a duplicate — it is a correction. Detection: filename exists in registry with SUCCESS status, but hash is different. Action: load the new file, flag in the registry as a CORRECTION, and trigger Silver re-processing for affected rows. This needs a decision from the manager — do you overwrite or keep both versions? Default: keep both, apply the latest.

**Type 4 — Partial overlap (new file contains rows already in Bronze)**

Monthly file contains all current month rows plus some carry-over from last month. The file itself is new, but some rows inside it are duplicates of rows already loaded. Detection: row-level deduplication in the Silver transformation using the row_hash. Bronze always gets the full file — Silver handles row-level deduplication via Delta MERGE on business keys. Never try to deduplicate at Bronze level — preserve everything raw.

### The duplicate detection decision tree

1. **Compute MD5 hash of the file on arrival** — Before reading a single row, compute the file's MD5 hash using Python's hashlib. This is fast — a 5MB Excel file hashes in milliseconds.

2. **Check hash against file_ingestion_registry** — Query: does this hash exist with status = 'SUCCESS'? If yes → DUPLICATE, skip. If hash exists with status = 'FAILED' → retry allowed, proceed. If hash is new → proceed to load.

3. **Check filename against registry (different hash)** — If filename was seen before but hash is different → CORRECTION. Log it, alert the manager, load the new version, re-trigger Silver for that source.

4. **Move file after processing** — Success → move to Files/processed/[source]/. Duplicate → move to Files/rejected/[source]/ with a .log file explaining why. Failed → move to Files/rejected/[source]/ with the error message in the .log file.

> **Warning:** Never delete files from the landing zone from inside the pipeline. Always move them. Deleting is irreversible. Moving to processed/ or rejected/ keeps a full audit trail and lets you manually re-process a rejected file after investigation.

---

## 3. File Delivery Options

### Four ways files can reach your landing zone — pick the right one for each department

**Recommended — SharePoint upload**

Departments upload Excel files to a named SharePoint folder. ADF copies them automatically to Files/landing/ on a schedule (every hour or nightly). Client never touches Fabric directly. IT can control who uploads per folder. Audit trail built in via SharePoint version history.

**Recommended — Power Automate flow**

A Power Automate flow triggers when a file is added to a specific SharePoint folder and copies it to the Fabric Lakehouse Files/landing/ zone immediately. Near-real-time delivery without scheduling. Good for medical team who update doctor schedules weekly.

**Acceptable — Email attachment trigger**

Power Automate watches a shared mailbox. When an email with an Excel attachment arrives from a known sender, it extracts the attachment to Files/landing/. Works well for departments who already send monthly reports by email. No behaviour change needed from the client.

**Avoid — Direct Fabric access**

Giving business users (doctors, training managers) direct access to upload to Files/ in the Fabric Lakehouse. They might upload to the wrong folder, overwrite existing files, or upload incompatible formats. Keep business users out of Fabric entirely — they interact only via SharePoint or email.

### Recommended architecture — SharePoint as the client-facing interface

1. **Client uploads to SharePoint folder (familiar, no training needed)** — Create one SharePoint folder per department: /DataUploads/Training/, /DataUploads/Medical/, /DataUploads/HR/. Training manager already knows SharePoint. No new tools to learn. Set folder permissions so each department can only see their own folder.

2. **Power Automate copies to Fabric Files/landing/ immediately** — Flow trigger: "When a file is created or modified in SharePoint folder /DataUploads/Training/" → Action: Copy file to Fabric Lakehouse Files/landing/training/ using the Fabric connector. This happens within seconds of the upload — no waiting for a nightly pipeline.

3. **Fabric pipeline polls landing/ and triggers ingestion** — Fabric pipeline PL_Daily_Bronze runs on schedule (hourly or nightly). It runs NB_02_Bronze_All_Sources_Ingest which auto-discovers file connectors, runs duplicate detection, loads to Bronze, moves processed files. Client sees nothing of this — they only care that their SharePoint upload was acknowledged.

4. **Automated confirmation email back to the uploader** — After a successful Bronze load, Power Automate sends a confirmation email: "Your file training_enrolments_may.xlsx was successfully processed — 1,247 rows loaded on 11 May 2025 at 09:14." If it failed: "Your file could not be processed — the date column contains an unrecognised format. Please contact data-team@university.ie." This closes the loop for the client without requiring them to log into anything.

### File naming convention — agree this with the client before go-live

Agree a mandatory file naming convention in writing and enforce it in the pipeline. If a file does not match the pattern, reject it immediately with a clear error message — do not try to guess what it is.

Pattern: `[source]_[YYYY]_[MM].xlsx`

Examples: `training_enrolments_2025_05.xlsx`, `doctor_schedules_2025_W20.xlsx`

This gives you: the source system from the name, the period the data covers, a natural sort order in the folder, and a way to detect a file uploaded for the wrong period.

---

## 4. Complete PySpark Code

### Complete duplicate-safe ingestion notebook

```python
# NB_02_Bronze_All_Sources_Ingest.ipynb
# Handles: unified ingestion via connector framework — Excel, CSV, REST API, platform,
# and social connectors with auto-discovery, duplicate detection, and audit logging

import hashlib, uuid, shutil, re
from datetime import datetime
from pyspark.sql.functions import current_timestamp, lit, input_file_name
from delta.tables import DeltaTable

# ── FILE NAMING PATTERN ──────────────────────────────────────────
# Enforced: [source]_[YYYY]_[MM].xlsx or [source]_[YYYY]_W[WW].xlsx
FILE_PATTERN = re.compile(
    r'^(training_enrolments|doctor_schedules|staff_roster|room_bookings)'
    r'_\d{4}_(0[1-9]|1[0-2]|W\d{2})\.xlsx$'
)

# ── COMPUTE MD5 HASH OF A FILE ───────────────────────────────────
def md5_of_file(path):
    # path is the ABFSS path in OneLake — read via mssparkutils
    content = mssparkutils.fs.head(path, 10 * 1024 * 1024)  # read up to 10MB
    return hashlib.md5(content.encode('utf-8') if isinstance(content, str)
                       else content).hexdigest()

# ── CHECK REGISTRY FOR DUPLICATE ─────────────────────────────────
def check_registry(file_name, file_hash):
    """
    Returns: ('NEW', None) | ('DUPLICATE', existing_row)
           | ('CORRECTION', existing_row) | ('RETRY', existing_row)
    """
    reg = spark.sql(f"""
        SELECT * FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_hash_md5 = '{file_hash}'
          AND status = 'SUCCESS'
        LIMIT 1
    """)
    if reg.count() > 0:
        return 'DUPLICATE', reg.first()

    name_match = spark.sql(f"""
        SELECT * FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_name  = '{file_name}'
          AND status     = 'SUCCESS'
        LIMIT 1
    """)
    if name_match.count() > 0:
        return 'CORRECTION', name_match.first()

    failed = spark.sql(f"""
        SELECT * FROM Bronze_Lakehouse.file_ingestion_registry
        WHERE file_hash_md5 = '{file_hash}'
          AND status = 'FAILED'
        LIMIT 1
    """)
    if failed.count() > 0:
        return 'RETRY', failed.first()

    return 'NEW', None

# ── REGISTER FILE IN REGISTRY ─────────────────────────────────────
def register_file(file_name, file_path, file_size,
                  file_hash, source, status,
                  batch_id, row_count=0, error=None):
    file_id = str(uuid.uuid4())
    now     = datetime.utcnow()
    row = [(file_id, file_name, file_path, file_size,
            file_hash, source, now,
            now if status == 'SUCCESS' else None,
            row_count, status, batch_id,
            str(error) if error else None)]
    spark.createDataFrame(row,
        'file_id STRING, file_name STRING, file_path STRING,'
        ' file_size_bytes LONG, file_hash_md5 STRING,'
        ' source_system STRING, detected_at TIMESTAMP,'
        ' processed_at TIMESTAMP, row_count LONG,'
        ' status STRING, batch_id STRING, error_message STRING'
    ).write.format('delta').mode('append') \
     .saveAsTable('Bronze_Lakehouse.file_ingestion_registry')

# ── MOVE FILE AFTER PROCESSING ─────────────────────────────────────
def move_file(src_path, status):
    # status: 'processed' | 'rejected' | 'duplicate'
    file_name  = src_path.split('/')[-1]
    source_dir = src_path.split('/')[-2]
    dest_base  = f'Files/{status}/{source_dir}/'
    dest_path  = f'{dest_base}{file_name}'
    mssparkutils.fs.mkdirs(dest_base)
    mssparkutils.fs.mv(src_path, dest_path)
    print(f'  Moved: {file_name} → {status}/')

# ── ENFORCE NAMING CONVENTION ─────────────────────────────────────
def validate_filename(file_name):
    if not FILE_PATTERN.match(file_name):
        raise ValueError(
            f'Filename "{file_name}" does not match naming convention. '
            f'Expected: [source]_YYYY_MM.xlsx — e.g. training_enrolments_2025_05.xlsx'
        )

# ── MAIN INGESTION LOOP ───────────────────────────────────────────
SOURCES = {
    'training'  : 'Files/landing/training/',
    'medical'   : 'Files/landing/medical/',
    'hr'        : 'Files/landing/hr/',
    'facilities': 'Files/landing/facilities/',
}

TARGET_TABLES = {
    'training'  : 'Bronze_Lakehouse.bronze_training_enrolments',
    'medical'   : 'Bronze_Lakehouse.bronze_doctor_schedules',
    'hr'        : 'Bronze_Lakehouse.bronze_hr_staff',
    'facilities': 'Bronze_Lakehouse.bronze_room_bookings',
}

for source_name, landing_path in SOURCES.items():
    print(f'\n=== Source: {source_name} ===')

    # List all .xlsx files in landing folder
    try:
        files = [f for f in mssparkutils.fs.ls(landing_path)
                 if f.name.endswith('.xlsx')]
    except:
        print(f'  No landing folder yet: {landing_path} — skipping')
        continue

    if not files:
        print(f'  No new files in landing folder')
        continue

    for f in files:
        batch_id = str(uuid.uuid4())
        print(f'  File: {f.name}')

        try:
            # Step 1: Validate filename convention
            validate_filename(f.name)

            # Step 2: Compute hash
            file_hash = md5_of_file(f.path)
            print(f'  Hash: {file_hash[:8]}...')

            # Step 3: Check registry
            action, existing = check_registry(f.name, file_hash)
            print(f'  Action: {action}')

            if action == 'DUPLICATE':
                register_file(f.name, f.path, f.size, file_hash,
                              source_name, 'DUPLICATE', batch_id)
                move_file(f.path, 'rejected')
                print(f'  SKIP — duplicate of {existing["file_name"]}'
                      f'loaded on {existing["processed_at"]}')
                continue

            if action == 'CORRECTION':
                print(f'  CORRECTION detected — same name, different content')
                print(f'  Original loaded: {existing["processed_at"]}')
                # Still load — Silver MERGE will handle row-level corrections

            # Step 4: Load to Bronze (all strings — no type casting here)
            df_raw = spark.read \
                .format('com.crealytics.spark.excel') \
                .option('header', 'true') \
                .option('inferSchema', 'false') \
                .option('treatEmptyValuesAsNulls', 'true') \
                .load(f.path)

            row_count = df_raw.count()
            if row_count == 0:
                raise ValueError('File loaded but contains 0 rows')

            df_bronze = df_raw \
                .withColumn('_ingested_at',   current_timestamp()) \
                .withColumn('_source_file',   lit(f.name)) \
                .withColumn('_source_system', lit(source_name)) \
                .withColumn('_batch_id',      lit(batch_id)) \
                .withColumn('_file_hash',     lit(file_hash)) \
                .withColumn('_is_correction', lit(action == 'CORRECTION'))

            df_bronze.write.format('delta').mode('append') \
                .option('mergeSchema', 'true') \
                .saveAsTable(TARGET_TABLES[source_name])

            # Step 5: Register success and move to processed/
            register_file(f.name, f.path, f.size, file_hash,
                          source_name, 'SUCCESS', batch_id, row_count)
            move_file(f.path, 'processed')
            print(f'  SUCCESS — {row_count} rows. Batch: {batch_id}')

        except ValueError as ve:
            # Naming convention or empty file — reject cleanly
            register_file(f.name, f.path, f.size,
                          'UNKNOWN', source_name, 'FAILED',
                          batch_id, error=ve)
            move_file(f.path, 'rejected')
            print(f'  REJECTED: {ve}')

        except Exception as e:
            # Unexpected error — register failure, leave file for retry
            register_file(f.name, f.path, f.size,
                          'UNKNOWN', source_name, 'FAILED',
                          batch_id, error=e)
            move_file(f.path, 'rejected')
            print(f'  ERROR: {e}')
            raise  # re-raise so Fabric Pipeline marks run as FAILED

print('\nNB_02 complete.')
```

### Query to check what has been processed — your daily monitoring query

```sql
-- Run this in a Fabric Notebook or SQL endpoint daily
SELECT
    source_system,
    status,
    COUNT(*) AS file_count,
    SUM(row_count) AS total_rows,
    MAX(detected_at) AS last_seen
FROM Bronze_Lakehouse.file_ingestion_registry
WHERE detected_at >= current_date() - 7
GROUP BY source_system, status
ORDER BY source_system, status;
```

> **Success:** The `_file_hash` and `_is_correction` columns added to every Bronze row mean you can always trace any Bronze record back to the exact file it came from, whether it was a new load or a correction — full audit trail at row level.

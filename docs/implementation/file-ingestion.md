# File Ingestion Design

## Landing Zone Structure

Raw files should never land in one flat folder. Use a structured landing zone in `Bronze_Lakehouse/Files`.

```text
Files/
├── landing/
│   ├── training/
│   ├── medical/
│   ├── hr/
│   └── facilities/
├── processed/
│   ├── training/
│   ├── medical/
│   ├── hr/
│   └── facilities/
├── rejected/
│   ├── training/
│   ├── medical/
│   ├── hr/
│   └── facilities/
├── archive/
├── profiling_reports/
└── checkpoints/
```

## File Registry

Create a Delta table named `Bronze_Lakehouse.file_ingestion_registry` to track every file seen by ingestion.

| Column | Purpose |
| --- | --- |
| `file_id` | Unique file registry identifier |
| `file_name` | Original filename |
| `file_path` | Full landing path |
| `file_size_bytes` | Size at detection time |
| `file_hash_md5` | Duplicate detection key |
| `source_system` | Logical source |
| `detected_at` | When the file was first seen |
| `processed_at` | When processing completed |
| `row_count` | Rows loaded |
| `status` | `PENDING`, `SUCCESS`, `FAILED`, `DUPLICATE`, `CORRECTION`, `SKIPPED` |
| `batch_id` | Pipeline run identifier |
| `error_message` | Failure details |

## Schema Change Log

Version 3 adds a dedicated schema drift audit table: `Bronze_Lakehouse.schema_change_log`.

The Excel connector in the connector framework compares the columns in each incoming file with the expected baseline for that source. New or missing columns are logged to `schema_change_log` before the file is written to Bronze.

| Column | Purpose |
| --- | --- |
| `change_id` | Unique schema change identifier |
| `source_system` | Source where the drift was detected |
| `file_name` | File that introduced the drift |
| `change_type` | `NEW_COLUMN` or `REMOVED_COLUMN` |
| `column_name` | Affected column |
| `previous_value` | Previous expected value when relevant |
| `detected_at` | Detection timestamp |
| `batch_id` | Pipeline batch identifier |
| `resolved` | Set to true after STTM and notebook mappings are updated |

Schema drift should not be ignored. Review unresolved rows before the Silver transformation runs:

```sql
SELECT *
FROM Bronze_Lakehouse.schema_change_log
WHERE resolved = false;
```

## Duplicate Scenarios

| Scenario | Detection | Action |
| --- | --- | --- |
| Same name, same content | Existing successful hash | Mark duplicate, move to rejected, do not load |
| Different name, same content | Existing successful hash | Mark duplicate, alert source owner, do not load |
| Same name, changed content | Existing name with new hash | Mark correction, load to Bronze, trigger Silver reprocessing |
| Row overlap inside new file | Business key or row hash duplicate in Silver | Load Bronze fully, deduplicate in Silver |

## Decision Tree

1. Detect files in `Files/landing/<source>/`.
2. Validate naming convention.
3. Compute MD5 hash.
4. Check hash against successful registry records.
5. Check filename against successful registry records.
6. Classify as `NEW`, `DUPLICATE`, `CORRECTION`, or `RETRY`.
7. Load valid files to Bronze.
8. Register result.
9. Move successful files to `processed/`.
10. Move failed or duplicate files to `rejected/`.

## Schema Change Response

1. Review unresolved entries in `schema_change_log`.
2. Confirm whether the change is intentional or a source error.
3. Update the STTM document.
4. Update the expected columns in the relevant connector's `extract()` method (e.g. `src/connectors/file/excel_connector.py`).
5. Update Silver mappings if the new column is required downstream.
6. Mark the schema change as resolved after review.

## Delivery Options

| Option | When to use | Notes |
| --- | --- | --- |
| SharePoint upload | Most departments | Recommended for Excel-based business users |
| Power Automate to OneLake | Managed handoff | Good for controlled file movement and alerts |
| SFTP landing | External partners | Useful when sources cannot access SharePoint |
| Direct API ingestion | System-to-system | Prefer for structured, frequent sources |

## Naming Convention

Use a predictable pattern:

```text
training_enrolments_YYYY_MM.xlsx
doctor_schedules_YYYY_WNN.xlsx
staff_roster_YYYY_MM.xlsx
room_bookings_YYYY_MM.xlsx
```

Bad filenames should be rejected before ingestion and logged with a clear reason.

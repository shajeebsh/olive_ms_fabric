# Operational Runbook

## Daily Checks

| Time | Check | How to verify | Owner |
| --- | --- | --- | --- |
| 07:00 | Bronze pipelines completed | Fabric Monitor activity runs | Data engineer |
| 07:15 | Silver transformations completed | Notebook run history | Data engineer |
| 07:30 | DQ checks have no severe failures | `Silver_Lakehouse.dq_log` | Data steward |
| 07:45 | Gold tables refreshed | Gold table row counts and timestamps | Data engineer |
| 08:00 | Reports are current | Power BI semantic model refresh status | Report owner |

## Failure Handling

### Unified Bronze Ingestion Fails (NB_02)

Likely causes:

- Filename does not match convention.
- Excel sheet name changed or CSV format changed.
- Header row changed.
- File is corrupt or password-protected.
- Connector config or secret missing.
- API endpoint or token expired.

Resolution:

1. Check `control_pipeline_log` for the failed connector's `error_message`.
2. Check `file_ingestion_registry` for file-level errors.
3. Open rejected file details.
4. Confirm expected sheet and headers per the connector's `extract()` logic.
5. Update STTM if the source contract changed.
6. Fix the connector's `extract()` method or config as needed — no changes to NB_02 itself.
7. Reprocess only after the cause is understood.

### REST API Returns 401 or 403

Likely causes:

- Expired API key.
- Revoked OAuth client.
- Changed API permissions.

Resolution:

1. Confirm secret value and expiry.
2. Request credential refresh from source owner.
3. Update secret store.
4. Rerun REST ingestion notebook.

### REST API Fails Repeatedly or Hits Rate Limits

Likely causes:

- Source API is unavailable.
- Rate limits are too low for the current page size.
- Network path is blocked.
- Token refresh flow is failing.

Resolution:

1. Query `Bronze_Lakehouse.api_call_log` for the last 24 hours.
2. Check `status`, `http_status`, `response_ms`, and `attempt_num`.
3. If 429 responses are frequent, reduce page size or adjust schedule.
4. If repeated 503 responses occur, leave the circuit open and contact the source owner.
5. Do not manually advance the watermark unless records were successfully written to Bronze.

### Schema Drift Detected

Likely causes:

- Source owner added a new Excel column.
- Source owner renamed or deleted a column.
- Header row changed or shifted.

Resolution:

1. Query `Bronze_Lakehouse.schema_change_log` where `resolved = false`.
2. Compare the file headers against the STTM.
3. Confirm whether the change is intentional with the source owner.
4. Update `docs/implementation/source-to-target-mapping.md`.
5. Update the expected columns in the relevant connector (e.g. `src/connectors/file/excel_connector.py`).
6. Update Silver mapping code if the column is required.
7. Mark the schema change as resolved.

### Silver DQ Failure

Likely causes:

- Missing business keys.
- Invalid dates.
- Range violations.
- New source values not in reference mappings.

Resolution:

1. Query `Silver_Lakehouse.dq_log`.
2. Identify failed check and entity.
3. Trace affected rows back to Bronze using `_batch_id`.
4. Decide whether to fix source data, update mapping, or add an accepted exception.
5. Rerun Silver and DQ before Gold.

### Power BI Shows Stale Data

Likely causes:

- Gold processing failed.
- Semantic model has not refreshed metadata.
- Schema changed without model update.

Resolution:

1. Check Gold pipeline status.
2. Validate Gold table timestamps.
3. Refresh semantic model metadata.
4. Re-test RLS roles after model changes.

## Reprocessing Guidance

| Need | Recommended action |
| --- | --- |
| Reprocess a failed file | Move from rejected to landing after fixing root cause |
| Reprocess a correction | Load as correction and rerun impacted Silver entity |
| Undo bad Silver write | Use Delta time travel after impact assessment |
| Rebuild Gold | Rerun Gold notebook after Silver DQ passes |

## Weekly Checks

- Review pipeline failure trends.
- Review DQ warning trends.
- Run Delta maintenance.
- Confirm Purview scans completed.
- Review access changes.
- Archive processed files older than retention threshold.

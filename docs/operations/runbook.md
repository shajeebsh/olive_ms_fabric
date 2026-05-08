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

### Bronze Excel Pipeline Fails

Likely causes:

- Filename does not match convention.
- Excel sheet name changed.
- Header row changed.
- File is corrupt or password-protected.

Resolution:

1. Check pipeline run error.
2. Check `file_ingestion_registry`.
3. Open rejected file details.
4. Confirm expected sheet and headers.
5. Update STTM if the source contract changed.
6. Reprocess only after the cause is understood.

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


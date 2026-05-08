# Architecture Decision Log

## ADR-001: Use Three Separate Lakehouses

Decision: Use `Bronze_Lakehouse`, `Silver_Lakehouse`, and `Gold_Lakehouse`.

Rationale: This provides a hard boundary between raw, cleansed, and reporting data. It supports stronger RBAC, clearer Purview lineage, and better protection for sensitive operational and personal data.

Alternatives considered:

| Option | Outcome |
| --- | --- |
| One Lakehouse with table prefixes | Rejected for production because it lacks a physical access boundary. |
| Bronze/Silver Lakehouses plus Gold Warehouse | Valid option for SQL-first teams; kept as an extension path. |
| All Warehouse | Rejected because raw Excel and nested REST API ingestion are easier in Spark and Lakehouse patterns. |
| Hybrid by domain | Useful later, but too complex for the first production release. |

## ADR-002: Bronze Is Append-Only

Decision: Bronze loads are append-only. Corrections are loaded as new records with correction metadata.

Rationale: Bronze is the audit layer. Overwriting raw data weakens lineage and makes issue investigation harder.

## ADR-003: Use File Hashes for Duplicate Detection

Decision: Compute a file hash before processing each uploaded file and compare it with `file_ingestion_registry`.

Rationale: Filename checks alone miss renamed duplicate files. Content hashes catch exact duplicates even when the filename changes.

## ADR-004: Use Watermark CDC for REST APIs

Decision: REST API ingestion uses `updated_since` or equivalent watermark parameters where available.

Rationale: The source APIs do not guarantee transaction logs or webhooks. Watermark CDC is simple, explainable, and recoverable.

## ADR-005: Run DQ Before Gold

Decision: Silver data quality checks must run before Gold processing. Severe failures stop downstream Gold loads.

Rationale: Gold is the trusted reporting layer. Loading Gold after known severe Silver failures creates visible business risk.

## ADR-006: Use Git Promotion for Environments

Decision: Use pull requests to promote code from feature branches to `develop`, then to `main`.

Rationale: This avoids manual copy-paste between Fabric workspaces, provides code review, and enables rollback through Git history.


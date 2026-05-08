# Governance, RBAC, and Privacy

## Governance Objectives

- Make data discoverable through Microsoft Purview.
- Protect personal and sensitive data.
- Maintain lineage from source to report.
- Restrict raw data access to engineering roles.
- Provide audit evidence for operational and compliance reviews.

## Workspace Access Model

| Role | Workspace role | Bronze | Silver | Gold | Power BI |
| --- | --- | --- | --- | --- | --- |
| Data Engineer | Member | Read/write | Read/write | Read/write | Admin for platform reports |
| Data Steward | Contributor | Read | Read | Read | Viewer or contributor |
| Analyst | Viewer | None | Read selected | Read selected | Contributor where approved |
| Department Manager | Viewer | None | None | RLS-filtered | Viewer |
| Executive | Viewer | None | None | Aggregates only | Viewer |
| Auditor | Viewer | None | Read audit tables | Read monitor views | Viewer |

Use security groups rather than individual user assignments.

## Sensitivity Labels

| Label | Applied to | Examples |
| --- | --- | --- |
| Highly Confidential - Clinical | Clinical or patient-related data | Procedure notes, diagnosis codes, clinical schedule details |
| Confidential - PII | Staff and student personal data | Email, phone, date of birth, address |
| Confidential - Internal | Internal operational data | Department metrics, quality scores |
| General | Non-sensitive reference data | Course title, campus name, date |

## Purview Lineage

Expected lineage path:

```text
SharePoint or API source
  -> Bronze ingestion pipeline
  -> Bronze Delta table
  -> Silver transformation notebook
  -> Silver entity
  -> Gold dimensional model
  -> Power BI semantic model
  -> Report
```

Add notebook markdown annotations for lineage:

```markdown
## Lineage
- Source: Bronze_Lakehouse.bronze_training_enrolments
- Target: Silver_Lakehouse.silver_training_enrolments
- Mapping: docs/implementation/source-to-target-mapping.md
```

## Dynamic Data Masking

Use Warehouse masking for SQL consumers where appropriate:

```sql
ALTER TABLE Gold_Warehouse.dbo.dim_student
ALTER COLUMN email
ADD MASKED WITH (FUNCTION = 'email()');

GRANT UNMASK ON Gold_Warehouse.dbo.dim_student TO [DataEngineers];
GRANT UNMASK ON Gold_Warehouse.dbo.dim_student TO [DataStewards];
```

## Privacy Controls

- Keep raw files out of Git.
- Use DEV only with synthetic or anonymised data.
- Avoid storing credentials in notebooks.
- Store API keys and secrets in approved secret management.
- Apply RLS in Power BI for department-scoped dashboards.
- Review access quarterly.


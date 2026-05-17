# Fabric Deployment Wireframe — Enterprise Connector Framework

> Step-by-step blueprint for deploying all Python source modules, connectors, notebooks, and configuration into Microsoft Fabric across DEV/TEST/PROD environments.

---

## 1. Workspace Layout

Three Fabric workspaces, each connected to a Git branch via Fabric Git integration:

| Workspace | Git Branch | Capacity | Data |
|-----------|-----------|----------|------|
| `UNIV-DEV` | `feature/*` | F2 (dev) | Synthetic |
| `UNIV-TEST` | `develop` | F8 | Anonymised |
| `UNIV-PROD` | `main` | F64 | Live |

Each workspace contains three lakehouses and one warehouse:

| Lakehouse/Warehouse | Purpose |
|--------------------|---------|
| `Bronze_Lakehouse` | Raw ingested data (Delta tables) |
| `Silver_Lakehouse` | Cleaned, merged, quality-checked data |
| `Gold_Lakehouse` | Dimensional model (star schema) |
| `Gold_Warehouse` | SQL analytics endpoint for Power BI |

---

## 2. Source Module Deployment

The `src/` package must be available as a Spark library attached to every notebook and pipeline. Do NOT bundle code inside notebooks.

### Option A — Fabric Spark Environment (recommended)

1. In each workspace, go to **Settings** → **Data Engineering/Science** → **Spark environments**
2. Create environment `univ-spark-env` with:
   - **Python files** → Upload `src/` as a `.zip` archive named `src.zip` (preserve package structure)
   - **Libraries** → Add PyPI packages: `requests`, `zeep`, `boto3`
3. Attach this environment to every notebook and every pipeline activity

Result: `from src.connectors.registry import ConnectorRegistry` works in any notebook.

### Option B — Notebook files on Lakehouse (fallback)

Upload `src/` as `Files/src/` in Bronze_Lakehouse, then prepend to `sys.path`:

```python
import sys
sys.path.insert(0, "/lakehouse/default/Files/src")
```

Option A is strongly preferred — it avoids path hacks and makes imports consistent.

### `src/` package structure (what gets deployed)

```
src/
├── __init__.py
├── api_ingestion.py         # REST API helpers: pagination, circuit breaker, token cache
├── config_loader.py          # load_config(), lakehouse_table(), lakehouse_name()
├── data_quality.py           # dq_check() — generic null/duplicate/range checks
├── file_ingestion.py         # MD5 dedup, file registry, schema drift, move_file
├── filesystem.py             # FileSystem ABC, FabricFileSystem, LocalFileSystem, get_filesystem()
├── gold_dimensional.py       # build_dim_student, build_dim_course, build_fact_training_completion
├── secrets.py                # SecretsProvider ABC, FabricSecrets, LocalSecrets, get_secrets()
├── connectors/               # Enterprise connector framework
│   ├── __init__.py           # register_all() — auto-discovery via pkgutil.walk_packages
│   ├── base.py               # BaseConnector ABC + ConnectorResult dataclass
│   ├── registry.py           # ConnectorRegistry — register, run_all, summary
│   ├── file/
│   │   ├── excel_connector.py     # 4 Excel sources (training, medical, HR, facilities)
│   │   └── csv_connector.py       # CSV import with MD5 dedup
│   ├── api/
│   │   ├── rest_connector.py      # REST APIs (LMS, HR) with watermark CDC
│   │   ├── soap_connector.py      # SOAP web services via zeep
│   │   └── webhook_connector.py   # Fabric Eventstream receiver
│   ├── platform/
│   │   ├── dynamics_connector.py           # Dynamics 365 OData v4 + delta token
│   │   ├── aws_connector.py                # AWS S3/Glue via boto3
│   │   ├── hubspot_connector.py            # HubSpot CRM API v3
│   │   ├── ghost_inspector_connector.py    # Ghost Inspector test suite results
│   │   ├── quercus_connector.py            # University LMS sync
│   │   ├── tlmf_connector.py               # TLMF user portal
│   │   └── power_pages_connector.py        # MS Power Pages / Dataverse
│   └── social/
│       ├── mailchimp_connector.py          # Mailchimp Marketing API v3
│       └── social_media_connector.py       # Meta Graph API + LinkedIn API
└── transformations/
    ├── __init__.py
    └── silver_training.py   # transform_training_enrolments()
```

---

## 3. Config File Placement

Three config files (`config_dev.json`, `config_test.json`, `config_prod.json`) must be uploaded to each lakehouse as JSON files, not as Spark library files. The `config_loader.py` reads them from the `Files/config/` path.

### Upload

In each workspace's `Bronze_Lakehouse`, upload:

```
Bronze_Lakehouse/Files/config/config_dev.json      ← UNIV-DEV only
Bronze_Lakehouse/Files/config/config_test.json     ← UNIV-TEST only
Bronze_Lakehouse/Files/config/config_prod.json     ← UNIV-PROD only
```

### Environment detection

`load_config()` determines which file to load:
1. Spark config `pipeline.env` (set by Fabric pipeline parameter) → e.g. `"DEV"` → loads `config_dev.json`
2. Fallback: `FABRIC_ENVIRONMENT` environment variable
3. Fallback: defaults to `DEV`

### Config reference

```json
{
  "environment": "DEV",
  "workspace": "UNIV-DEV",
  "git_branch": "feature/*",
  "bronze_lakehouse": "Bronze_Lakehouse",
  "silver_lakehouse": "Silver_Lakehouse",
  "gold_lakehouse": "Gold_Lakehouse",
  "api_base_url": "https://lms-uat.example.org/api/v2",
  "secret_scope": "fabric-secrets-dev",
  "lakehouses": {
    "bronze": "Bronze_Lakehouse",
    "silver": "Silver_Lakehouse",
    "gold": "Gold_Lakehouse"
  },
  "warehouse": "Gold_Warehouse",
  "data_policy": "synthetic_or_anonymised_only",
  "schedule_enabled": false,
  "connectors": {
    "enabled": [
      "excel_training",
      "excel_medical",
      "excel_hr",
      "excel_facilities",
      "csv_import",
      "rest_api_lms",
      "rest_api_hr"
    ]
  }
}
```

| Key | What it controls | Per-environment |
|-----|-----------------|-----------------|
| `api_base_url` | Base URL for LMS REST API | PROD → production URL, DEV → UAT URL |
| `secret_scope` | Azure Key Vault scope name | Each env has its own KV |
| `connectors.enabled` | Which sources to run in this env | DEV → subset, PROD → all |
| `schedule_enabled` | Whether pipelines run on schedule | DEV → false, TEST/PROD → true |

---

## 4. Secret Management (Azure Key Vault)

Each workspace has a linked Azure Key Vault. The `secret_scope` config value maps to the KV linked service name.

### Key Vault: `fabric-secrets-dev`

| Secret Name | Used By |
|-------------|---------|
| `lms-api-token` | `rest_api_lms` connector |
| `hr-client-secret` | `rest_api_hr` connector |
| `hubspot-private-app-token` | HubSpot connector |
| `ghost-inspector-api-key` | Ghost Inspector connector |
| `quercus-api-key` | Quercus connector |
| `tlmf-api-key` | TLMF connector |
| `meta-page-token` | Meta Graph connector |
| `meta-page-id` | Meta Graph connector |
| `linkedin-access-token` | LinkedIn connector |
| `linkedin-org-id` | LinkedIn connector |
| `mailchimp-api-key` | Mailchimp connector |
| `dynamics-tenant-id` | Dynamics 365 connector |
| `dynamics-client-id` | Dynamics 365 connector |
| `dynamics-client-secret` | Dynamics 365 connector |
| `dynamics-resource-url` | Dynamics 365 connector |
| `dynamics-base-url` | Dynamics 365 connector |
| `aws-access-key-id` | AWS connector |
| `aws-secret-access-key` | AWS connector |
| `aws-s3-bucket` | AWS connector |

### KV per environment

| Environment | Key Vault | Secret Scope |
|-------------|-----------|-------------|
| DEV | `kv-univ-dev` | `fabric-secrets-dev` |
| TEST | `kv-univ-test` | `fabric-secrets-test` |
| PROD | `kv-univ-prod` | `fabric-secrets-prod` |

Each KV has the same secret *names* but different *values* (pointing to sandbox/UAT/production endpoints).

---

## 5. Control Tables — Prerequisite Setup

Run `NB_01_Create_Control_Tables.py` once per workspace (first-run only). It creates:

### Bronze Lakehouse
| Table | Purpose |
|-------|---------|
| `control_watermark` | Tracks last successful run per source for CDC |
| `control_pipeline_log` | Audit log for every connector run |
| `file_ingestion_registry` | MD5-based duplicate detection for file sources |
| `api_call_log` | Every REST API call: status, latency, records |
| `schema_change_log` | Excel column header drift tracking |

### Silver Lakehouse
| Table | Purpose |
|-------|---------|
| `control_silver_watermark` | Watermark for silver transformation |
| `dq_log` | Data quality check results |
| `monitoring_alerts` | Alert history |
| `monitoring_metrics` | Metric snapshots for dashboards |

### File system folders

```
Bronze_Lakehouse/Files/landing/{training,medical,hr,facilities,csv}/
Bronze_Lakehouse/Files/processed/{training,medical,hr,facilities,csv}/
Bronze_Lakehouse/Files/rejected/{training,medical,hr,facilities,csv}/
Bronze_Lakehouse/Files/archive/
Bronze_Lakehouse/Files/profiling_reports/
Bronze_Lakehouse/Files/checkpoints/
Bronze_Lakehouse/Files/config/
```

### Watermark seed rows (seeded by NB_01)

| source_system | last_run_ts | Notes |
|---------------|-------------|-------|
| `excel_training` | `1900-01-01` | CDC not applicable (files), but uses registry |
| `excel_medical` | `1900-01-01` | Same |
| `excel_hr` | `1900-01-01` | Same |
| `excel_facilities` | `1900-01-01` | Same |
| `rest_api_lms` | `1900-01-01` | Watermark-based CDC — will pull all records on first run |
| `rest_api_hr` | `1900-01-01` | Same |
| `csv_import` | `1900-01-01` | Uses registry, but watermark row for consistency |
| `ghost_inspector` | `1900-01-01` | Watermark-based CDC |
| `quercus` | `1900-01-01` | Watermark-based CDC |
| `tlmf` | `1900-01-01` | Watermark-based CDC |
| `ms_dynamics_contacts` | `1900-01-01` | Uses delta token (stored in last_batch_id) |
| `ms_dynamics_*` | `1900-01-01` | One row per entity |
| `aws_datahub` | `1900-01-01` | Watermark-based CDC |
| `ms_power_pages` | `1900-01-01` | Uses delta token |

> The `social_*`, `mailchimp`, `soap_webservice`, and `webhook` sources do not use watermark tables (full-refresh or event-driven).

---

## 6. Notebook Deployment

Import these `.py` files as Fabric notebooks (use Fabric's **Import → Notebook → From file**). The `.py` extension is a Fabric convention for notebook files in Git — Fabric treats them as `.ipynb` internally.

### Import order (dependency order)

| Order | Notebook | Layer | Depends on |
|-------|----------|-------|------------|
| 1 | `NB_01_Create_Control_Tables` | Setup | Nothing (runs first) |
| 2 | `NB_02_Bronze_All_Sources_Ingest` | Bronze | NB_01, src/ package, config, secrets |
| 3 | `NB_04_Silver_Training_Enrolments` | Silver | NB_02 (bronze data exists) |
| 4 | `NB_05_Bronze_to_Silver_Streaming` | Silver (streaming) | NB_02 |
| 5 | `NB_06_Gold_Dimensional_Model` | Gold | NB_04 |
| 6 | `NB_07_Data_Quality_Checks` | Ops | NB_04 (silver exists) |
| 7 | `NB_08_Monitoring_and_Alerting` | Ops | All above |
| 8 | `NB_09_PowerBI_Semantic_Model_Prep` | Gold | NB_06 |
| 9 | `NB_10_Purview_Lineage_Annotations` | Ops | Nothing (metadata only) |
| 10 | `NB_11_Delta_Maintenance` | Ops | All above |
| 11 | `NB_00_Data_Profiling` | Pre-Bronze | Nothing (ad-hoc, not in pipeline) |

### NB_02 — The Unified Ingestion Notebook

`NB_02_Bronze_All_Sources_Ingest.py` replaces both `NB_02_Bronze_Excel_Ingest.py` and `NB_03_Bronze_REST_API_Ingest.py`. It:

1. Creates a `ConnectorRegistry`
2. Calls `register_all(registry, config)` — auto-discovers all connector modules
3. Filters by `config.connectors.enabled` (if present)
4. Calls `registry.run_all(spark, config)` — executes each connector's `extract()` → `_add_audit_cols()` → write to Bronze Delta
5. Writes results to `control_pipeline_log`
6. Fails the pipeline if any connector returned `FAILED`

Internal flow per connector:

```
run()                              ← BaseConnector (inherited)
  ├── batch_id = uuid4()
  ├── extract()                    ← implemented by each connector subclass
  │     ├── File connectors:       read Excel/CSV from Files/landing/
  │     ├── REST API connectors:   fetch pages, handle pagination
  │     ├── Platform connectors:   SDK calls (boto3), REST calls
  │     └── Social connectors:     Graph API, LinkedIn, Mailchimp
  ├── _add_audit_cols(df)          ← 5 standard audit columns
  ├── df.write → Bronze Delta      ← append, mergeSchema=true
  └── return ConnectorResult       ← SUCCESS/FAILED/SKIPPED
```

### Gold notebook — NB_06

`NB_06_Gold_Dimensional_Model` reads silver and builds:
- `dim_student` — surrogate key + row_number
- `dim_course` — surrogate key + row_number
- `fact_training_completion` — joins facts to dimensions

---

## 7. Pipeline Wiring

Each Fabric pipeline runs one or more notebooks sequentially. Parameters like `pipeline.env` are set at the pipeline level.

### PL_Daily_Bronze (runs daily at 02:00)

```
Step 1: Notebook → NB_02_Bronze_All_Sources_Ingest
  Parameters: pipeline.env = "DEV|TEST|PROD"
  Spark environment: univ-spark-env

Step 2: Notebook → NB_01_Create_Control_Tables
  (idempotent — safe to run daily)
```

### PL_Daily_Silver (runs daily at 03:00)

```
Step 1: Notebook → NB_04_Silver_Training_Enrolments
Step 2: Notebook → NB_05_Bronze_to_Silver_Streaming (checkpoint)
Step 3: Notebook → NB_07_Data_Quality_Checks
```

### PL_Daily_Gold (runs daily at 04:00)

```
Step 1: Notebook → NB_06_Gold_Dimensional_Model
Step 2: Notebook → NB_09_PowerBI_Semantic_Model_Prep
```

### PL_Weekly_Maintenance (runs Sunday 06:00)

```
Step 1: Notebook → NB_11_Delta_Maintenance
Step 2: Notebook → NB_08_Monitoring_and_Alerting
Step 3: Notebook → NB_10_Purview_Lineage_Annotations
```

### PL_Stream_15min (runs every 15 minutes)

```
Step 1: Notebook → NB_05_Bronze_to_Silver_Streaming
  (reads from checkpoint, processes CDC from bronze)
```

### Parameter passing pattern

All pipelines pass `pipeline.env` as a pipeline parameter. Notebooks read it via:

```python
from src.config_loader import load_config
config = load_config()  # reads spark.conf.get("pipeline.env", "DEV")
```

---

## 8. Connector-to-Fabric Resource Mapping

Each connector maps to specific Fabric resources. This table tells you what must exist in the workspace before the connector runs.

| Connector | Source System | Bronze Target Table | Requires | Type |
|-----------|--------------|---------------------|----------|------|
| `ExcelConnector` | `excel_training` | `bronze_training_enrolments` | `Files/landing/training/` | file |
| `ExcelConnector` | `excel_medical` | `bronze_doctor_schedules` | `Files/landing/medical/` | file |
| `ExcelConnector` | `excel_hr` | `bronze_hr_staff_excel` | `Files/landing/hr/` | file |
| `ExcelConnector` | `excel_facilities` | `bronze_room_bookings` | `Files/landing/facilities/` | file |
| `CsvConnector` | `csv_import` | `bronze_csv_import` | `Files/landing/csv/` | file |
| `RestApiConnector` | `rest_api_lms` | `bronze_lms_enrolments` | KV: `lms-api-token`, watermark row | api |
| `RestApiConnector` | `rest_api_hr` | `bronze_hr_staff` | KV: `hr-client-secret`, watermark row | api |
| `SoapConnector` | `soap_webservice` | `bronze_soap_webservice` | Config: wsdl_url, operation | api |
| `WebhookConnector` | `webhook` | `bronze_webhook_events` | Eventstream writing to this table | api |
| `DynamicsConnector` | `ms_dynamics` | `bronze_ms_dynamics` | KV: 5 dynamics-* secrets | platform |
| `AwsDataHubConnector` | `aws_datahub` | `bronze_aws_datahub` | KV: 3 aws-* secrets | platform |
| `HubSpotConnector` | `aws_hubspot` | `bronze_aws_hubspot` | KV: hubspot token | platform |
| `GhostInspectorConnector` | `ghost_inspector` | `bronze_ghost_inspector` | KV: ghost-inspector-api-key | platform |
| `QuercusConnector` | `quercus` | `bronze_quercus` | KV: quercus-api-key | platform |
| `TlmfConnector` | `tlmf` | `bronze_tlmf` | KV: tlmf-api-key | platform |
| `PowerPagesConnector` | `ms_power_pages` | `bronze_ms_power_pages` | KV: 5 dynamics-* secrets | platform |
| `MailchimpConnector` | `mailchimp` | `bronze_mailchimp` | KV: mailchimp-api-key | social |
| `MetaGraphConnector` | `social_meta` | `bronze_social_meta` | KV: meta-page-token, meta-page-id | social |
| `LinkedInConnector` | `social_linkedin` | `bronze_social_linkedin` | KV: linkedin-access-token, linkedin-org-id | social |

> Bronze target tables are created automatically on first write (Spark delta `mode("append").option("mergeSchema", "true").saveAsTable(target)`). Schema is inferred from the source data. No DDL is needed.

---

## 9. Enabling / Disabling Connectors Per Environment

The `connectors.enabled` array in each config controls which connectors run. This allows:

**DEV config** — only file + basic REST (safe with synthetic data):
```json
"connectors": {
  "enabled": ["excel_training", "csv_import", "rest_api_lms"]
}
```

**PROD config** — all 19 source systems:
```json
"connectors": {
  "enabled": [
    "excel_training", "excel_medical", "excel_hr", "excel_facilities",
    "csv_import", "rest_api_lms", "rest_api_hr",
    "soap_webservice", "webhook",
    "ms_dynamics", "aws_datahub", "hubspot",
    "ghost_inspector", "quercus", "tlmf", "ms_power_pages",
    "mailchimp", "social_meta", "social_linkedin"
  ]
}
```

If `connectors.enabled` is omitted entirely, ALL registered connectors run.

---

## 10. Deployment Sequence — Step by Step

### Phase 1: Fabric Setup (once per workspace)

1. Create 3 lakehouses: `Bronze_Lakehouse`, `Silver_Lakehouse`, `Gold_Lakehouse`
2. Create 1 warehouse: `Gold_Warehouse`
3. Create Spark environment `univ-spark-env` with `src.zip` attached and PyPI deps
4. Link Azure Key Vault → Fabric workspace (settings → security)
5. Upload config JSON to `Bronze_Lakehouse/Files/config/`
6. Upload `Files/landing/` and `Files/processed/` folder structure (or let NB_01 create them)
7. *(Optional)* Connect workspace to Azure DevOps Git

### Phase 2: Source Code

8. Build `src.zip` preserving the package structure:
   ```
   zip -r src.zip src/ --exclude "*/__pycache__/*" "*.pyc"
   ```
9. Upload `src.zip` to the Spark environment (or to `Bronze_Lakehouse/Files/`)

### Phase 3: Notebooks

10. Import notebooks into Fabric workspace via **Import → Notebook → From file**, in the order listed in Section 6:
    - `notebooks/ops/NB_01_Create_Control_Tables.py`
    - `notebooks/bronze/NB_02_Bronze_All_Sources_Ingest.py`
    - `notebooks/silver/NB_04_Silver_Training_Enrolments.py`
    - `notebooks/silver/NB_05_Bronze_to_Silver_Streaming.py`
    - `notebooks/gold/NB_06_Gold_Dimensional_Model.py`
    - `notebooks/gold/NB_09_PowerBI_Semantic_Model_Prep.py`
    - `notebooks/ops/NB_07_Data_Quality_Checks.py`
    - `notebooks/ops/NB_08_Monitoring_and_Alerting.py`
    - `notebooks/ops/NB_10_Purview_Lineage_Annotations.py`
    - `notebooks/ops/NB_11_Delta_Maintenance.py`
    - `notebooks/bronze/NB_00_Data_Profiling.py`

### Phase 4: First Run

11. Run `NB_01_Create_Control_Tables` — creates all control tables and seed data
12. Place a test `.xlsx` file in `Files/landing/training/`
13. Run `NB_02_Bronze_All_Sources_Ingest` — should see `excel_training` → SUCCESS
14. Verify `bronze_training_enrolments` table exists with data + 5 audit columns
15. Run `NB_04_Silver_Training_Enrolments` — cleans and upserts to silver
16. Run `NB_06_Gold_Dimensional_Model` — builds star schema

### Phase 5: Pipelines

17. Create Fabric pipelines per Section 7
18. Set `pipeline.env` as a pipeline parameter
19. Run PL_Daily_Bronze → verify
20. Run PL_Daily_Silver → verify
21. Run PL_Daily_Gold → verify
22. Set up schedules

---

## 11. Adding a New Connector (Extension Pattern)

When a new source needs to be ingested:

1. Create file: `src/connectors/platform/<name>_connector.py`
2. Extend `BaseConnector`:
   ```python
   class MyConnector(BaseConnector):
       connector_type = "my_type"
       source_system = "my_source"
       def extract(self, spark, config, batch_id) -> DataFrame | None:
           # fetch data, return raw DataFrame
   ```
3. Add `register_connectors(registry, config)` function — auto-discovery picks it up
4. Add secrets to the workspace's Azure Key Vault
5. Add entry to `connectors.enabled` in config (if selective run is desired)
6. No changes to NB_02 — the unified notebook auto-discovers via `register_all()`

---

## 12. Dependency Summary — Full Inventory

```
Fabric Resources
├── 3 Lakehouses (Bronze/Silver/Gold)
├── 1 Warehouse (Gold_Warehouse)
├── 1 Spark Environment (with src.zip + PyPI deps)
├── 1 Azure Key Vault (linked, with all secrets populated)
├── 11 Notebooks (NB_01 through NB_11, plus NB_00)
├── 3 Fabric Pipelines (Daily_Bronze, Daily_Silver, Daily_Gold)
├── 1 Streaming Pipeline (Stream_15min)
└── 1 Weekly Maintenance Pipeline

Control Tables (created by NB_01)
├── Bronze: control_watermark, control_pipeline_log, file_ingestion_registry
│            api_call_log, schema_change_log
└── Silver: control_silver_watermark, dq_log, monitoring_alerts, monitoring_metrics

Config (on Bronze_Lakehouse/Files/config/)
├── config_dev.json
├── config_test.json
└── config_prod.json

Secrets (in Azure Key Vault, linked as `secret_scope`)
└── 19 secrets across all 19 source systems
```

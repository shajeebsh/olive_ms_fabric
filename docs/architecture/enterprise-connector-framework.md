# Enterprise Connector Framework

> Architecture blueprint for the enterprise connector framework in Microsoft Fabric, covering all 15 source types with a unified BaseConnector pattern.

---

## Key Design Principle

Every connector does three things — **extract, audit, land**. Nothing else. The connector's job stops at Bronze. It extracts raw data from the source, adds five audit columns, and lands it in Bronze as Delta. All transformation, validation, and business logic happens in Silver and beyond. This keeps connectors small, testable, and replaceable.

### Audit columns added to every Bronze row

| Column | Purpose |
|---|---|
| `_ingested_at` | Timestamp of when the row was written to Bronze |
| `_source_system` | Identifies the origin (e.g. `excel_training`, `rest_api_lms`) |
| `_connector_type` | Type of connector that produced the row (e.g. `file_excel`, `rest_api`) |
| `_batch_id` | UUID tying all rows from a single connector run |
| `_schema_version` | Version tag for forward compatibility |

### Connector contract

| Must do | Must NOT do |
|---|---|
| Extract raw data from source | Cast types or apply business rules |
| Add 5 audit columns | Raise exceptions silently |
| Write append-only to Bronze Delta table | Write anywhere except Bronze |
| Register in `file_ingestion_registry` (file sources) or `control_watermark` (API sources) | — |
| Return a `ConnectorResult` | — |

---

## Source Inventory

| Source | Connector Type | Status |
|---|---|---|
| Excel files | `FileConnector` — crealytics spark-excel, landing zone, MD5 registry | Exists |
| CSV import/export | `FileConnector` — spark.read.csv with schema inference guard | Extend |
| REST API | `RestApiConnector` — watermark CDC, pagination, OAuth2, circuit breaker | Exists |
| SOAP / Web services | `SoapConnector` — zeep library, WSDL parsing, XML to JSON flatten | New |
| Webhooks | `WebhookConnector` — Fabric Eventstream receiver endpoint | New |
| Microsoft Dynamics | `DynamicsConnector` — OData v4 REST API, AAD auth, delta token CDC | New |
| AWS DataHub | `AwsConnector` — boto3 S3/Glue, cross-account IAM role | New |
| HubSpot | `HubSpotConnector` — REST API v3, private app token, cursor pagination | New |
| Ghost Inspector | `GhostInspectorConnector` — REST API, test suite results | New |
| Quercus sync | `QuercusConnector` — automated sync via REST or DB direct | New |
| TLMF user portal | `TlmfConnector` — portal API or scheduled export | New |
| MS Power Pages | `PowerPagesConnector` — Dataverse REST API (OData), AAD auth | New |
| Social media | `SocialConnector` — Meta Graph, LinkedIn, X/Twitter v2 APIs | New |
| Mailchimp | `MailchimpConnector` — Marketing API v3, campaign + member data | New |

---

## Project Structure

```
src/connectors/
├── __init__.py                # register_all() — central registration entry point
├── base.py                    # BaseConnector ABC + ConnectorResult dataclass
├── registry.py                # ConnectorRegistry — register, run_all, summary
├── file/                      # File-based source connectors
│   ├── excel_connector.py     # 4 Excel sources (training, medical, HR, facilities)
│   └── csv_connector.py       # CSV import with MD5 dedup
├── api/                       # API-based source connectors
│   ├── rest_connector.py      # REST APIs (LMS, HR) with watermark CDC
│   ├── soap_connector.py      # SOAP web services via zeep
│   └── webhook_connector.py   # Fabric Eventstream receiver
├── platform/                  # Third-party platform connectors
│   ├── dynamics_connector.py  # Microsoft Dynamics 365 OData v4
│   ├── aws_connector.py       # AWS S3/Glue via boto3
│   ├── hubspot_connector.py   # HubSpot CRM API v3
│   ├── ghost_inspector_connector.py
│   ├── quercus_connector.py   # University LMS sync
│   ├── tlmf_connector.py      # TLMF user portal
│   └── power_pages_connector.py  # MS Power Pages / Dataverse
└── social/                    # Social media & marketing connectors
    ├── mailchimp_connector.py
    └── social_media_connector.py  # Meta Graph + LinkedIn
```

---

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    NB_02_Bronze_All_Sources_Ingest               │
│                                                                  │
│   registry = ConnectorRegistry()                                 │
│   register_all(registry, config)    ← auto-discovers modules    │
│   results = registry.run_all(spark, config)                     │
│                                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │     ConnectorRegistry     │
              │                          │
              │  for each connector:      │
              │    result = connector.run()│
              └──────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │Excel     │ │RestApi   │ │Csv       │ ...
        │Connector │ │Connector │ │Connector │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             ▼            ▼            │
   extract() → DataFrame │             │
   _add_audit_cols()     │             │
   write → Bronze Delta  │             │
             │            │            │
             ▼            ▼            ▼
        ┌─────────────────────────────────────┐
        │       Bronze Lakehouse Delta Tables  │
        │  bronze_excel_training               │
        │  bronze_excel_medical                │
        │  bronze_rest_api_lms                 │
        │  bronze_csv_import                   │
        │  ...                                 │
        └─────────────────────────────────────┘
```

### Connector lifecycle

1. `register_all()` walks the `src/connectors/` package tree, imports every module, and calls each module's `register_connectors(registry, config)` function
2. Each module creates its connector instances and registers them with the registry keyed by `source_system`
3. `registry.run_all(spark, config)` iterates registered connectors and calls `connector.run()` on each
4. `connector.run()` calls the abstract `extract()` method, adds audit columns via `_add_audit_cols()`, writes to the bronze Delta table, and returns a `ConnectorResult`
5. The notebook logs results to `control_pipeline_log` and fails the pipeline if any connectors errored

---

## Adding a New Connector — Four Steps

1. **Create a new file** in the correct category folder — e.g. `src/connectors/platform/quercus_connector.py`
2. **Extend `BaseConnector`**, set `connector_type` and `source_system`, implement `extract()` — the `run()` method is inherited; you never need to implement Bronze write logic yourself
3. **Add secrets to Azure Key Vault** — name them `{source}-api-key` or `{source}-client-secret` following the existing naming convention
4. **Add a watermark seed row** to `control_watermark` — e.g. `INSERT INTO Bronze_Lakehouse.control_watermark VALUES ('quercus', '1900-01-01', 'INIT', 0, 'READY', current_timestamp())`

The registry auto-discovers the new connector via `pkgutil.walk_packages` — there is no registration step. As soon as the file exists in the connectors package and exposes a `register_connectors(registry, config)` function, it will be picked up on the next pipeline run.

---

## Connector Categories

### File Connectors
Use the existing `Files/` landing zone pattern with MD5-based duplicate detection, file naming validation, and the `file_ingestion_registry` Delta table. Files move through `landing/` → `processed/` | `rejected/`.

### API Connectors
Use watermark-based CDC via the `control_watermark` Delta table. Support OAuth2 client credentials and bearer token auth. Implement circuit breaker pattern (fail after N consecutive errors) and retry with exponential backoff.

### Platform Connectors
Third-party platforms with REST APIs (OData, custom REST) or SDK-based access (boto3 for AWS). Each follows the same extract → audit → land contract.

### Social & Marketing Connectors
Strictest rate limits of all source types. Meta: 200 calls/hour per token. LinkedIn: 100 calls/day on free tier. X/Twitter v2: 500,000 tweets/month on Basic. Daily batch is safer than hourly for social sources.

---

## Configuration

The `connectors.enabled` array in each environment config controls which connectors run:

```json
{
  "connectors": {
    "enabled": [
      "excel_training", "excel_medical", "excel_hr", "excel_facilities",
      "csv_import", "rest_api_lms", "rest_api_hr"
    ]
  }
}
```

Connectors not in this list are skipped. To enable all registered connectors, omit the `enabled` key entirely.

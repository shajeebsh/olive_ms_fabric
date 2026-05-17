# Tests

## Running Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Run only unit tests (skip integration tests requiring Fabric):

```bash
python -m pytest tests/ -v -m "not integration"
```

## Test Coverage

| Test file | Module(s) tested | Type | Status |
|-----------|-----------------|------|--------|
| `test_config.py` | Config JSON validity and required keys | Unit | Pass |
| `test_config_loader.py` | `lakehouse_table()`, `lakehouse_name()` | Unit | Pass |
| `test_connector_registry.py` | `ConnectorRegistry` (register, list, run_all, summary), `ConnectorResult` | Unit | Pass |
| `test_connector_base.py` | `BaseConnector._add_audit_cols()`, `run()` lifecycle (SUCCESS/SKIPPED/FAILED) | Unit | Pass |
| `test_filesystem.py` | `LocalFileSystem` (ls, head, mkdirs, mv, md5), `FileInfo`, `get_filesystem()` | Unit | Pass |
| `test_secrets.py` | `LocalSecrets` (env var retrieval, missing key error) | Unit | Pass |
| `test_api_ingestion.py` | Circuit breaker, `flatten_struct_cols()`, `move_file()`, connector auto-discovery | Unit | Pass |
| `test_data_quality.py` | `dq_check()` (PASS/FAIL/WARN, empty input, all-fail edge case) | Unit | Pass |
| `test_gold_dimensional.py` | `build_dim_student()`, `build_dim_course()`, `build_fact_training_completion()` | Unit | Pass |
| `test_silver_transformations.py` | `transform_training_enrolments()` (trim, status mapping, nulls, hash stability) | Unit | Pass |
| `test_gold_smoke.py` | Gold table existence and fact completeness in a real Fabric workspace | Integration | `skip` without `FABRIC_ENVIRONMENT` |

## What's NOT Unit Testable

The following require **Fabric runtime** (`mssparkutils`, real Delta tables, live API endpoints):

- `src/connectors/file/*` — Excel/CSV connectors (need Fabric Filesystem and Delta Lake)
- `src/connectors/api/*` — REST/SOAP/Webhook connectors (need live endpoints + secrets)
- `src/connectors/platform/*` — All platform connectors (need live API credentials)
- `src/connectors/social/*` — Social media connectors (need live API tokens)
- `src/filesystem.FabricFileSystem` — Requires `mssparkutils`
- `src/secrets.FabricSecrets` — Requires `mssparkutils.credentials`
- `src/api_ingestion.log_api_call()` — Writes to Delta tables
- `src/api_ingestion.fetch_all_pages()` — Requires live HTTP endpoints
- `src/file_ingestion.registry_action()` / `register_file()` / `log_schema_drift()` — Read/write Delta tables
- `src/gold_dimensional.*` table writes (reading Bronze/Silver is integration-only)

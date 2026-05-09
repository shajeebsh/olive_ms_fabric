# Git and Deployment

## Principle

Git stores code, configuration, pipeline definitions, and documentation. Data remains in OneLake.

## Branch Strategy

```text
feature/<work-item>
        |
        v
develop
        |
        v
main
```

| Branch | Fabric workspace | Purpose |
| --- | --- | --- |
| `feature/*` | DEV | Engineering work and isolated testing |
| `develop` | TEST | Integration testing and UAT |
| `main` | PROD | Production deployment |
| `governance` | GOVERNANCE | Governance documentation and metadata work |

Rules:

- Do not edit directly in PROD.
- Do not commit directly to `develop` or `main`.
- Every change uses a pull request.
- Attach test evidence and DQ results to production pull requests.

## Promotion Flow

1. Engineer develops in DEV on a feature branch.
2. Engineer syncs Fabric item changes to Git.
3. Pull request from feature branch to `develop`.
4. Tests run and peer review completes.
5. TEST workspace updates from `develop`.
6. Integration testing and UAT complete.
7. Pull request from `develop` to `main`.
8. Production approval completes.
9. PROD workspace updates from `main`.
10. First production run is monitored.

## Rollback

Preferred code rollback:

```text
Find bad commit on main -> Revert -> merge revert commit -> PROD syncs clean version
```

Data rollback when required:

```sql
RESTORE TABLE Silver_Lakehouse.silver_training_enrolments
TO VERSION AS OF <version_number>;
```

Only restore data after confirming downstream impact on Gold and Power BI.

## What Belongs in Git

| Include | Exclude |
| --- | --- |
| Notebooks | Delta data |
| Pipeline JSON definitions | Parquet files |
| Config templates | Secrets |
| DQ rule definitions | Production extracts |
| Documentation | Local credentials |
| Tests | Temporary profiling output |

## Environment Config Pattern

Each environment has a JSON config file under `config/`. Notebooks should read environment values from config instead of hardcoding Lakehouse names, API URLs, or secret scopes.

Example:

```python
import json

env = spark.conf.get("pipeline.env", "dev")
with open(f"config/config_{env}.json") as config_file:
    cfg = json.load(config_file)

BRONZE = cfg["bronze_lakehouse"]
SILVER = cfg["silver_lakehouse"]
GOLD = cfg["gold_lakehouse"]
```

## Pull Request Checklist

- Scope is clear.
- Notebook or pipeline has been run in DEV.
- Unit tests or validation queries are attached.
- DQ impact is documented.
- Config changes are environment-safe.
- No secrets are committed.
- No raw or personal data is committed.

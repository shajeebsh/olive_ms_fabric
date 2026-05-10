# Microsoft Fabric Medallion Implementation

This repository is a practical implementation starter for a Microsoft Fabric data platform using a Bronze, Silver, and Gold Medallion architecture.

It consolidates the supplied planning documents, implementation guide, PySpark notebook patterns, file ingestion guidance, DevOps notes, and operational runbooks into a project structure that a delivery team can use immediately.

No client or consultancy company name is used in this documentation. Use your organisation, programme, or client naming conventions when adapting the templates.

## Target Architecture

The recommended production pattern is three physically separate Lakehouses:

| Layer | Fabric item | Purpose | Access |
| --- | --- | --- | --- |
| Bronze | `Bronze_Lakehouse` | Raw, append-only source data with ingestion audit columns | Data engineers only |
| Silver | `Silver_Lakehouse` | Cleansed, deduplicated, conformed entities with data quality checks | Engineers and selected analysts |
| Gold | `Gold_Lakehouse` plus optional `Gold_Warehouse` | Star schema, aggregates, semantic model-ready tables | Business users through governed Power BI models |

This separation keeps raw data isolated, simplifies retention and governance, gives Microsoft Purview clearer lineage, and prevents reports from accidentally connecting to unvalidated Bronze data.

## Repository Map

```text
.
├── README.md
├── config/
│   ├── config_dev.json
│   ├── config_test.json
│   └── config_prod.json
├── docs/
│   ├── architecture/
│   │   ├── medallion-architecture.md
│   │   └── decision-log.md
│   ├── devops/
│   │   └── git-and-deployment.md
│   ├── governance/
│   │   └── purview-rbac-and-privacy.md
│   ├── implementation/
│   │   ├── roadmap.md
│   │   ├── source-to-target-mapping.md
│   │   └── file-ingestion.md
│   ├── operations/
│   │   ├── runbook.md
│   │   └── monitoring-and-alerting.md
│   └── templates/
│       ├── weekly-status-template.md
│       └── implementation-questions.md
├── notebooks/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── ops/
├── pipelines/
└── tests/
```

## Architecture Overview

### How Notebooks Are Triggered in Fabric

Notebooks in this architecture are triggered through three mechanisms:

| Trigger | Mechanism | Scope | Status |
|---|---|---|---|
| **Fabric Scheduled Pipeline** | A Fabric pipeline activity runs a notebook item. Pipelines can be chained to enforce order (Bronze → DQ → Silver → Gold). | Multi-notebook workflows | Planned (pipeline JSONs to be exported via Git sync) |
| **Fabric Notebook Schedule** | Built-in schedule on a single notebook item; gated by `schedule_enabled` in config. | Single notebook (e.g. streaming) | Planned (DEV has `schedule_enabled: false`) |
| **Manual / Ad-hoc** | Engineer opens and runs the notebook interactively in the Fabric UI. | Any notebook | Current primary mode |

### Where Notebooks Live and What Connects Them

Notebooks are organised by medallion layer: `notebooks/bronze/`, `notebooks/silver/`, `notebooks/gold/`, and `notebooks/ops/`. They follow a numbered naming convention (`NB_<NN>_<Purpose>.py`) that implies execution order.

Notebooks are connected by three things:

1. **Control tables** — Created by `NB_01_Create_Control_Tables`, these act as the shared state between notebooks. Watermark tables (`control_watermark`, `control_silver_watermark`) track what each notebook has already processed, making all notebooks idempotent. Other tables like `file_ingestion_registry`, `dq_log`, and `monitoring_alerts` pass data quality, auditing, and lineage information between layers.

2. **Configuration** — A shared `config_loader` module reads environment-specific JSON (`config/config_dev.json`, `config_test.json`, `config_prod.json`). Every notebook calls `load_config(env)` at startup to resolve lakehouse names, API endpoints, and secret scopes. The helper `lakehouse_table(config, layer, table)` produces fully qualified Delta table paths.

3. **Delta tables** — Notebooks do not call each other directly. Instead, output tables in one lakehouse become input tables for the next layer: Bronze notebooks write to `Bronze_Lakehouse.*`, Silver notebooks read from there and write to `Silver_Lakehouse.*`, and Gold notebooks consume Silver tables to build the dimensional model.

### End-to-End Data Flow

```mermaid
flowchart TD
    subgraph Sources["Sources"]
        A[Excel Files] --> NB_02
        B[REST APIs] --> NB_03
    end

    subgraph Bronze["Bronze_Lakehouse"]
        NB_02["NB_02_Bronze_Excel_Ingest"] --> BT1[(bronze_excel_*)]
        NB_03["NB_03_Bronze_REST_API_Ingest"] --> BT2[(bronze_rest_*)]
        NB_01["NB_01_Create_Control_Tables"] --> CT[(control_watermark\nfile_ingestion_registry\napi_call_log)]
    end

    subgraph Silver["Silver_Lakehouse"]
        NB_04["NB_04_Silver_Training_Enrolments"] --> ST[(silver_training_*)]
        NB_05["NB_05_Bronze_to_Silver_Streaming"] --> ST
        NB_07["NB_07_Data_Quality_Checks"] --> DQ[(dq_log)]
        NB_08["NB_08_Monitoring_and_Alerting"] --> MA[(monitoring_alerts\nmonitoring_metrics)]
    end

    subgraph Gold["Gold_Lakehouse"]
        NB_06["NB_06_Gold_Dimensional_Model"] --> GT[(dim_* / fact_*)]
        NB_09["NB_09_PowerBI_Semantic_Model_Prep"] --> GT
    end

    subgraph Governance["Governance & Maintenance"]
        NB_10["NB_10_Purview_Lineage_Annot."] --> PV[Purview Lineage]
        NB_11["NB_11_Delta_Maintenance"] --> DM[Vacuum / Optimize]
    end

    subgraph Orchestration["Orchestration (Planned)"]
        PL_B["PL_Daily_Bronze"] --> NB_02 & NB_03
        PL_S["PL_Daily_Silver"] --> NB_04
        PL_G["PL_Daily_Gold"] --> NB_07 --> NB_06 & NB_09
        PL_W["PL_Weekly_Maint."] --> NB_10 & NB_11
    end

    BT1 & BT2 --> NB_04 & NB_05
    CT --> NB_02 & NB_03 & NB_04 & NB_08
    ST --> NB_07
    ST --> NB_06 & NB_09

    Config[(config/*.json)] -->|load_config()| NB_01
    Config --> NB_02 & NB_03 & NB_04 & NB_05 & NB_06
    Config --> NB_07 & NB_08 & NB_09 & NB_10 & NB_11
```

**Legend:**
- `[NB_xx]` = Fabric notebook
- `[(table)]` = Delta table in a lakehouse
- `[PL_xx]` = Fabric pipeline (planned)
- Solid arrows = data flow; dashed = pipeline orchestration

## Implementation Sequence

1. Set up Fabric workspaces and capacities for DEV, TEST, PROD, and GOVERNANCE.
2. Create separate Bronze, Silver, and Gold Lakehouses in each environment.
3. Connect workspaces to Git using `feature/* -> develop -> main` promotion.
4. Run the control table setup notebook.
5. Build Bronze ingestion for Excel and REST API sources.
6. Implement Silver transformations using source-to-target mappings and Delta MERGE.
7. Add data quality checks before Gold processing.
8. Build Gold dimensions, facts, and Power BI-ready summary tables.
9. Configure Purview scanning, sensitivity labels, RBAC, and lineage review.
10. Schedule monitoring, alerting, Delta maintenance, and operational checks.

## Key Design Principles

- Bronze preserves source data as-is and never overwrites history.
- Duplicate file detection happens before Bronze loading, using file hashes.
- Excel schema changes are logged to `Bronze_Lakehouse.schema_change_log` before Silver processing.
- REST API calls are logged to `Bronze_Lakehouse.api_call_log` with response status, duration, and retry count.
- REST ingestion uses retry, rate-limit, token-cache, and circuit-breaker patterns.
- Row-level deduplication and business corrections are handled in Silver.
- Gold is designed around business questions, not source-system layouts.
- Production changes move through pull requests and deployment gates.
- All sensitive data is labelled, access-controlled, and masked where appropriate.

## Source Material Incorporated

The structure and content are based on the supplied implementation guide, PySpark notebook library, file ingestion guide, Medallion separation guide, DevOps guide, day-one toolkit, contract-success guide, implementation question checklist, and the later v3 implementation updates.

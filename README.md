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
- Row-level deduplication and business corrections are handled in Silver.
- Gold is designed around business questions, not source-system layouts.
- Production changes move through pull requests and deployment gates.
- All sensitive data is labelled, access-controlled, and masked where appropriate.

## Source Material Incorporated

The structure and content are based on the supplied implementation guide, PySpark notebook library, file ingestion guide, Medallion separation guide, DevOps guide, day-one toolkit, contract-success guide, and implementation question checklist.


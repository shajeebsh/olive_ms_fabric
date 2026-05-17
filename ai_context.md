# Olive MS Fabric — Enterprise Data Management Platform

**Session ID:** ses_current
**Branch:** feature/local-testability-refactor
**Last Updated:** 5/17/2026

---

## Goal
Align the existing enterprise data management framework with the documented scope covering 12 source systems, medallion architecture, governance, and ML readiness.

## Architecture
- **Three physically separate Lakehouses** (Bronze/Silver/Gold) for hard RBAC and independent retention (ADR-001)
- **Bronze:** Append-only with correction metadata; no overwrites (ADR-002)
- **Silver:** SCD Type 2 with row hashes and Delta MERGE for upserts
- **Gold:** Star schema dimensional model (facts + dimensions)
- **7 capability areas:** Design, Recruit, Apply, Enrol, Manage Members & Fellows, Manage Enquiries, Manage Records & Info

## Implemented

### Connector Framework (14 connector files in `src/connectors/`)
| Type | Connectors |
|------|-----------|
| File | excel, csv |
| API | rest, soap, webhook |
| Platform | dynamics, power_pages, tlmf, quercus, ghost_inspector, hubspot, aws |
| Social | social_media, mailchimp |

### Bronze Layer
- Excel ingestion with duplicate detection, file registry, schema drift tracking (NB_02)
- REST API ingestion with OAuth2/token caching, circuit breaker, watermark CDC (NB_03)
- Control tables: watermark, pipeline log, file registry, API call log, schema change log (NB_01)
- 13 source systems seeded in `control_watermark` (NB_01)

### Silver Layer
- Training enrolments transformation (SCD Type 2, DQ checks, watermark tracking) (NB_04)
- Streaming LMS enrolments via Delta Change Data Feed (NB_05)

### Gold Layer
- dim_student, dim_course, fact_training_completion (NB_06)
- Power BI semantic model prep (summary views) (NB_09)

### Governance
- Purview lineage annotations with TBLPROPERTIES (NB_10)
- Data quality framework with severity-based gating (NB_07)
- Monitoring and alerting for freshness, DQ, API health, file health (NB_08)
- Delta maintenance, ZORDER, archiving (NB_11)
- RBAC model documented in `docs/governance/purview-rbac-and-privacy.md`

### Documentation
- Architecture decision log (8 ADRs)
- Medallion architecture guide
- Source-to-target mapping
- Runbook, monitoring guide, team collaboration guide
- System integration & enterprise data management plan appended to team-collaboration-guide.md

## To Be Implemented (Alignment Gaps)

### 1. Enable All Connectors in Config
- **Current:** Only 7 of 19+ source types enabled in `config_dev.json`
- **Action:** Add remaining connector types (soap, webhook, dynamics_contacts, aws_datahub, power_pages, tlmf, quercus, ghost_inspector, hubspot, social_media, mailchimp, csv_import) to `connectors.enabled` in all configs

### 2. Silver Transformations for Remaining Capabilities
- **Current:** Only `silver_training.py` exists (covers Enrol capability)
- **Missing:** Design, Recruit, Apply, Manage Members & Fellows, Manage Enquiries, Manage Records & Info
- **Action:** Create `silver_design.py`, `silver_recruit.py`, `silver_apply.py`, `silver_members_fellows.py`, `silver_enquiries.py`, `silver_records_info.py` plus corresponding notebooks

### 3. Gold Dimensional Models for All Capabilities
- **Current:** Only training (dim_student, dim_course, fact_training_completion)
- **Missing:** dim_staff, dim_campus, dim_date, fact_clinical_hours, fact_room_booking, and models for all 7 capabilities
- **Action:** Extend `gold_dimensional.py` and create notebooks for each capability area

### 4. ML Readiness
- **Current:** Zero ML infrastructure
- **Missing:**
  - Feature store (Gold-layer feature tables)
  - ML pipelines (training, evaluation, deployment)
  - MLflow integration for experiment tracking and model registry
  - ML-ready data marts as documented in scope
- **Action:** Implement feature engineering framework, ML pipeline templates, MLflow tracking

### 5. Control Table Coverage
- **Current:** `silver_watermark` only references `training_enrolments`
- **Action:** Expand to track every capability entity

### 6. Cross-Capability Data Models
- **Current:** No unified cross-capability models (e.g., Recruit → Apply → Enrol funnel)
- **Action:** Build conformed dimensions and cross-domain fact tables

## Key Decisions
- Medallion architecture: three physically separate Lakehouses (ADR-001)
- Bronze is append-only; corrections marked with `_is_correction` flag (ADR-002)
- DQ checks gate promotion from Silver to Gold (ADR-005)

## Active Branch
- `feature/local-testability-refactor` — clean working tree

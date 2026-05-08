# 90-Day Implementation Roadmap

## Phase 0: Foundation, Days 1-10

Deliverables:

- DEV, TEST, PROD, and GOVERNANCE workspaces created.
- Bronze, Silver, and Gold Lakehouses created in each environment.
- Git integration connected.
- Control tables and folder structures created.
- Source inventory and initial profiling complete.

Success criteria:

- Engineers can run notebooks in DEV.
- Purview scanning is connected or scheduled.
- Source owners and data stewards are identified.

## Phase 1: Bronze Ingestion, Days 11-25

Deliverables:

- Excel ingestion pipeline for each department source.
- REST API ingestion with watermark control.
- File registry and duplicate detection active.
- Pipeline run logging active.
- Historical backfill plan agreed.

Success criteria:

- Bronze tables contain raw data with audit columns.
- Duplicate uploads are detected and moved to rejected folders.
- Failed loads are visible in logs.

## Phase 2: Silver Transformation, Days 26-45

Deliverables:

- Source-to-target mappings for each entity.
- Silver notebooks for students, staff, courses, enrolments, clinical hours, and room bookings.
- SCD Type 2 handling where required.
- Data quality notebook and DQ log table.

Success criteria:

- Silver entities are conformed and deduplicated.
- Data quality checks are passing or have documented remediation.
- Watermarks update only after successful processing.

## Phase 3: Gold and Reporting, Days 46-65

Deliverables:

- Gold dimensions and facts.
- Power BI summary views.
- Direct Lake semantic model.
- Initial dashboards for executive, training, clinical, and data quality audiences.

Success criteria:

- Stakeholders validate core metrics.
- RLS roles are configured and tested.
- Gold refresh completes after successful DQ.

## Phase 4: Governance, Days 66-75

Deliverables:

- Sensitivity labels applied.
- RBAC groups assigned.
- Purview lineage reviewed.
- Dynamic data masking configured in Warehouse where needed.
- Data retention rules agreed.

Success criteria:

- Sensitive columns are labelled.
- Business users cannot access Bronze.
- Audit evidence can be produced from Purview and Fabric logs.

## Phase 5: Production, Days 76-85

Deliverables:

- PROD deployment.
- Scheduled orchestration.
- Monitoring and alerting.
- Operational dashboard.
- User training.

Success criteria:

- Production pipeline runs successfully for five consecutive business days.
- Alerts route to the correct owners.
- Support team can investigate failures using the runbook.

## Phase 6: Handover, Days 86-90

Deliverables:

- Final runbook.
- Architecture and data dictionary review.
- Known issues and backlog.
- Hypercare plan.

Success criteria:

- Delivery team can operate the platform independently.
- Open risks have owners and target dates.


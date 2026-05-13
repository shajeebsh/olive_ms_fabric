# Self-study framework — 62 questions

**Context block** (paste before every question):

> Context: I'm building a medallion architecture in Microsoft Fabric for a university. Sources: messy Excel files (doctors, surgeons, training team) + one third-party REST API. No structured storage yet. Architecture: Option 1 — 3 separate Lakehouses (Bronze/Silver/Gold) in UNIV-PROD. Git: Azure DevOps, branch-per-environment (feature/* → develop → main). Requirement: near-real-time streaming Bronze→Silver using Delta Change Data Feed.

---

## Phase 1: Environment & Git setup

### Workspace & Lakehouse setup

1. Teach me exactly how to enable Microsoft Fabric in a Microsoft 365 tenant — what admin settings to change, what licence is needed, and how to verify it is working.
2. Walk me through creating the four workspaces UNIV-DEV, UNIV-TEST, UNIV-PROD, and UNIV-GOVERNANCE step by step — what capacity to assign each and why.
3. What is the difference between Fabric capacity tiers F2, F8, and F64 — what does each cost roughly and which is appropriate for DEV vs TEST vs PROD?
4. Teach me how to create three Lakehouses inside UNIV-PROD — Bronze_Lakehouse, Silver_Lakehouse, Gold_Lakehouse — and explain why we use three separate Lakehouses instead of one.
5. How do I create a Fabric Warehouse called Gold_Warehouse inside UNIV-PROD, and when would I use the Warehouse instead of the Gold Lakehouse?

### Git & branch strategy

6. Teach me step by step how to connect a Fabric workspace to an Azure DevOps repository, including how to configure UNIV-DEV to track feature branches, UNIV-TEST to track develop, and UNIV-PROD to track main.
7. Show me the exact Azure DevOps folder structure I should use to store notebooks, pipeline definitions, config files, and documentation for this university project.
8. What is saved to Git when I commit a Fabric notebook — what file format, what metadata — and what is NOT saved to Git and stays only in OneLake?
9. Explain the feature branch PR flow in plain terms: when do I create a branch, how do I raise a PR, and what exactly happens to UNIV-TEST the moment a PR is merged to develop?
10. How do I roll back a bad deployment in Fabric — show me both the Git revert approach and the Delta RESTORE TABLE TO VERSION approach and when to use each.

### Config & secrets

11. Show me the config.json pattern so the same notebook automatically reads from Bronze_LH_DEV in DEV and Bronze_Lakehouse in PROD — include the exact PySpark first-cell code to load the config.
12. How do I store API keys and connection strings securely in Fabric — walk me through Azure Key Vault, creating a secret scope, and calling dbutils.secrets.get() inside a PySpark notebook.

---

## Phase 2: Bronze ingestion layer

### Excel ingestion

13. Teach me how to ingest Excel files from SharePoint into a Fabric Lakehouse using Azure Data Factory — what linked service to create, what the Copy Data activity looks like, and where files land in the Lakehouse Files/ zone.
14. Show me the complete PySpark code to read an Excel file from Files/ using the crealytics spark-excel library, append the four audit columns (_ingested_at, _source_file, _source_system, _batch_id), and write as a Delta table to Bronze with mergeSchema.
15. What does inferSchema:false mean when reading Excel in PySpark, and why is it critical to keep everything as STRING in Bronze? What production problems does it prevent?
16. My university Excel files have inconsistent column headers — different people rename columns between monthly exports. How do I detect this automatically and alert rather than silently fail?

### REST API ingestion

17. Before I build any REST API pipeline, how do I profile and test the unknown third-party LMS API — what specific checks do I run to understand its response structure, pagination pattern, rate limits, and reliability?
18. Teach me the watermark CDC pattern for REST API ingestion — show the complete PySpark code including reading last_run_ts from control_watermark, passing it as a query parameter, handling pagination, and updating the watermark only after a successful write.
19. My REST API uses OAuth2 client credentials. Show me the full PySpark code to get a token, handle token expiry during a long pagination loop, and retry on 429 rate-limit responses with exponential backoff.
20. What is idempotency in a data pipeline and how do I make my Bronze REST API notebook idempotent so re-running after a failure never creates duplicate rows?
21. How do I flatten nested JSON from a REST API response in PySpark — show the code to detect StructType fields and expand them into flat columns before writing to Bronze.

### Control tables & logging

22. Show me the exact SQL DDL and PySpark seed code to create and populate control_watermark, control_pipeline_log, and control_silver_watermark tables.
23. How do I write a reusable pipeline run logging helper function in PySpark that every notebook calls at start and end, writing status, row counts, batch ID, and any error message to control_pipeline_log?

---

## Phase 3: Silver & Gold transformation

### Silver transformation patterns

24. Explain SCD Type 2 in plain terms using a university staff member changing department as the example — what the valid_from, valid_to, is_current, and row_hash columns do and why we need them.
25. Show me the complete PySpark Delta MERGE that implements SCD Type 2 — the two-step pattern of expiring changed rows first then inserting new ones, with the row_hash comparison logic.
26. I need to parse UK date formats (dd/MM/yyyy) from Excel in PySpark. Show the transformation code including handling nulls, invalid date strings, and detecting dd/MM/yyyy vs MM/dd/yyyy without being told.
27. Show me how to build a derived academic_year column in PySpark that produces "2024/2025" for Sept–Dec dates and "2023/2024" for Jan–Aug — explain the when/otherwise logic step by step.
28. What is an MD5 row hash and how do I generate one in PySpark across multiple columns? Show the concat_ws + md5 pattern and explain why it is better than comparing every column individually in a MERGE.

### Gold dimensional model

29. Teach me star schema design from scratch using the university training data — what makes something a fact vs a dimension table, what a surrogate key is, and how to choose the grain of a fact table.
30. Show me the PySpark code to generate a complete date spine dim_date from 2010 to 2035 using spark.sql sequence and explode — with date_key, year, quarter, month, month_name, day_name, is_weekend, academic_year, and academic_semester.
31. How do I add a surrogate key to a Gold dimension using monotonically_increasing_id() and what are its limitations? When should I use a different approach?
32. Show me the Gold fact table build notebook — joining Silver entities, resolving surrogate keys via left joins to dims, and writing the fact partitioned by academic_year. Explain why partitioning on academic_year improves query performance.
33. How do I build a pre-aggregated vw_training_summary view in Gold that Power BI uses instead of the raw fact table? Show the PySpark SQL including completion_rate_pct and dropout_rate_pct calculations.

### Schema & Delta management

34. What is Delta Lake schema evolution and how does mergeSchema work? Give me a real example where a new column appears in next month's Excel file — what happens at Bronze, Silver, and Gold and what alerts should I raise.
35. How do I use DESCRIBE HISTORY on a Delta table to see what changed, and how does RESTORE TABLE TO VERSION work as a rollback if Silver transformation writes bad data?

---

## Phase 4: Streaming, DQ & monitoring

### Streaming Bronze to Silver

36. Teach me Delta Change Data Feed from the beginning — how to enable it with ALTER TABLE SET TBLPROPERTIES, what the _change_type column values mean (insert, update_preimage, update_postimage, delete), and why we only process insert and update_postimage in Silver.
37. Show me the complete Structured Streaming notebook using spark.readStream with readChangeFeed=true and a foreachBatch function that runs a Delta MERGE into Silver — explain checkpoint, trigger(processingTime), and why awaitTermination(timeout=900) is used.
38. What is the difference between Structured Streaming and Fabric Eventstream/Eventhouse — when would I use each for this university project and what would make me switch to Eventstream in phase 2?
39. If my streaming notebook fails halfway through a micro-batch, what happens to the checkpoint? How does exactly-once processing work in foreachBatch and what do I do if the checkpoint gets corrupted?

### Data quality framework

40. Teach me how to build a reusable dq_check() function in PySpark that takes a DataFrame, a filter condition, entity name, and severity level — writing a structured result row to a dq_log Delta table on every run.
41. What are the five categories of DQ checks I should run for university data? Show me one example rule per category — null completeness, range validity, referential integrity, date logic, and volume anomaly — with the actual PySpark filter condition.
42. How do I implement volume anomaly detection — show the PySpark code comparing today's row count against the 7-day rolling average and raising an alert when deviation exceeds 40%.
43. How do I make a DQ FAIL status halt the Gold pipeline from running? Show the Python exception raise pattern and explain how Fabric Pipeline activity dependencies use it as a gate.
44. What is a referential integrity check in a star schema? Show the PySpark left_anti join that finds student_ids in Silver not in dim_student, and explain why this should be WARNING not CRITICAL in the first few weeks.

### Monitoring & alerting

45. How do I build a data freshness SLA check in PySpark — show the code reading max(_ingested_at) from each Bronze table, calculating hours_old, comparing against a threshold, and writing an alert row if breached.
46. Teach me how to set up a Fabric Data Activator (Reflex) alert step by step in the UI — firing a Teams message when the DQ log table contains a FAIL status written in the last 30 minutes.
47. How do I build a pipeline success rate monitor that queries control_pipeline_log for the last 24 hours and raises a CRITICAL alert if any pipeline has more than zero failed runs?
48. What should the Power BI Data Quality Monitor page show and what pre-aggregated Gold table do I build to support it efficiently with Direct Lake? Show the vw_dq_monitor SQL.

---

## Phase 5: Power BI, governance & deployment

### Power BI & Direct Lake

49. Explain Direct Lake mode in Power BI — how it differs from Import and DirectQuery, why it is faster, what fallback to DirectQuery means in practice, and how to connect it to a Gold Lakehouse step by step.
50. How do I implement Row-Level Security in a Power BI semantic model over the Gold Lakehouse — show the DAX role expressions giving a Medical Director access only to medical data and a Training Manager only to training data.
51. What are the five Power BI report pages I should build for the university, what audience does each serve, and what are the two or three most important visuals on each page?
52. Show me the mandatory training compliance SQL that finds active students who never completed a mandatory course OR whose last completion was over 365 days ago — with the compliance_status label Never Completed / Overdue / Due Soon / Compliant.
53. Show me the clinical hours vs target SQL that calculates each doctor's actual hours vs contracted hours, pct_of_contracted, and assigns On Target / At Risk / Below Target status labels.

### Governance & Purview

54. How do I connect Microsoft Purview to a Fabric workspace — what steps in the Azure Portal, what steps in the Fabric Admin Portal, and how do I verify Purview is automatically scanning and cataloguing my Lakehouse tables?
55. Teach me how to apply sensitivity labels to Delta tables and columns using ALTER TABLE SET TBLPROPERTIES and ALTER COLUMN COMMENT in PySpark — and how Purview picks these up in the lineage graph.
56. What is Dynamic Data Masking in Fabric Warehouse — show me how to apply it to the email column in dim_student and how to grant UNMASK only to the data engineering group with exact SQL.
57. What does end-to-end data lineage look like in Purview for this project — describe the complete chain from a SharePoint Excel file to a Power BI visual, and what I must do to ensure every step is visible.
58. A university GDPR audit asks: what PII do we hold, who can access it, and how does it flow through the system. Which specific Purview feature answers each question and where in UNIV-GOVERNANCE do I find the evidence?

### Production deployment & maintenance

59. Walk me through the complete DEV → TEST → PROD deployment of a new notebook using Fabric Deployment Pipelines — what I click, what the approval gate looks like, and how to verify the PROD workspace updated correctly.
60. How do I create a smoke test pipeline PL_SmokeTest that runs after every PROD deployment and validates row counts in all Bronze and Silver tables — failing the deployment if any table is empty or below a threshold?
61. What is Delta VACUUM and OPTIMIZE, when do I run each, what Z-ORDER columns do I choose for the university tables, and what is the 7-day retention rule I must not override?
62. Show me the complete weekly Delta maintenance notebook that runs VACUUM 168h, OPTIMIZE with Z-ORDER, and ANALYZE TABLE COMPUTE STATISTICS for all 15 tables across Bronze, Silver, and Gold.
63. How do I write a README.md for the Azure DevOps repo so a new engineer with no prior knowledge of this project can set up the full environment from scratch in one day — what sections must it contain?

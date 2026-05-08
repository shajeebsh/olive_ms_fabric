# Medallion Architecture

## Recommended Pattern

Use three separate Fabric Lakehouses:

```text
Source files and APIs
        |
        v
Bronze_Lakehouse
        |
        v
Silver_Lakehouse
        |
        v
Gold_Lakehouse and Gold_Warehouse
        |
        v
Power BI semantic models and reports
```

## Why Three Lakehouses

| Benefit | Explanation |
| --- | --- |
| Physical boundary | Analysts and reports cannot accidentally query raw Bronze data. |
| Independent access | Bronze, Silver, and Gold can each have different RBAC groups. |
| Governance clarity | Purview lineage clearly shows movement between layers. |
| Retention control | Raw files can be retained longer than curated reporting tables. |
| Team ownership | Ingestion, transformation, and BI teams can own separate surfaces. |
| Future flexibility | Gold can later move fully into a Warehouse without redesigning ingestion. |

## Layer Definitions

| Layer | State | Storage | Retention | Consumers |
| --- | --- | --- | --- | --- |
| Bronze | Raw, append-only, source-shaped | Delta tables plus Files landing zones | 7 years by default | Data engineers |
| Silver | Cleaned, deduplicated, conformed | Delta tables | 5 years by default | Engineers, analysts, data stewards |
| Gold | Dimensional model and summary tables | Delta tables and optional Warehouse | 3 years by default | Power BI, SQL consumers, executives |

## Bronze Rules

Bronze is the evidence layer. It should preserve what arrived, when it arrived, and from where.

Every Bronze table should include these audit columns:

| Column | Type | Purpose |
| --- | --- | --- |
| `_ingested_at` | timestamp | Load timestamp |
| `_source_file` | string | File path or source object |
| `_source_system` | string | Logical source name |
| `_batch_id` | string | Pipeline run identifier |
| `_file_hash` | string | MD5 or SHA hash for file-level traceability |
| `_is_correction` | boolean | Marks corrected file loads |

Do not cast data types, standardise values, remove rows, or repair nulls in Bronze. Those actions belong in Silver.

## Silver Rules

Silver contains trusted business entities. It applies:

- Data type casting
- Date parsing
- Trimming and standardisation
- Business key validation
- SCD Type 2 history where required
- Row-level deduplication
- Referential integrity checks
- Data quality logging

Use Delta MERGE for upserts and row hashes for change detection.

## Gold Rules

Gold should be shaped around reporting and analytics. Use a star schema with facts and dimensions:

| Table | Grain |
| --- | --- |
| `fact_training_completion` | One row per learner per course completion |
| `fact_enrolment` | One row per enrolment event |
| `fact_clinical_hours` | One row per staff member per procedure date |
| `fact_room_booking` | One row per room booking |
| `dim_student` | One row per student version |
| `dim_staff` | One row per staff version |
| `dim_course` | One row per course |
| `dim_date` | One row per calendar date |
| `dim_campus` | One row per campus |

Use `Gold_Warehouse` when SQL-native consumers need stored procedures, T-SQL views, or dynamic data masking.

## Naming Standards

| Asset | Pattern | Example |
| --- | --- | --- |
| Workspace | `<ORG>-<ENV>` | `UNIV-PROD` |
| Lakehouse | `<Layer>_Lakehouse` | `Bronze_Lakehouse` |
| Bronze table | `bronze_<source>_<entity>` | `bronze_excel_training_enrolments` |
| Silver table | `silver_<entity>` | `silver_training_enrolments` |
| Gold dimension | `dim_<entity>` | `dim_student` |
| Gold fact | `fact_<process>` | `fact_training_completion` |
| Pipeline | `PL_<Layer>_<Purpose>` | `PL_Bronze_Excel_Ingest` |
| Notebook | `NB_<NN>_<Purpose>` | `NB_04_Silver_Transformation` |


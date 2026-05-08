# Fabric Notebook Library

These `.py` files are notebook-ready starter scripts. In Fabric, create notebooks with matching names and paste the relevant script into the notebook, or import them through Git integration if your workspace supports notebook source control.

## Execution Order

| Order | Notebook | Purpose |
| --- | --- | --- |
| 00 | `bronze/NB_00_Data_Profiling.py` | Profile incoming source files and API samples in DEV |
| 01 | `ops/NB_01_Create_Control_Tables.py` | Create control, registry, DQ, and monitoring tables |
| 02 | `bronze/NB_02_Bronze_Excel_Ingest.py` | Ingest duplicate-safe Excel files to Bronze |
| 03 | `bronze/NB_03_Bronze_REST_API_Ingest.py` | Ingest REST API data using watermark CDC |
| 04 | `silver/NB_04_Silver_Training_Enrolments.py` | Transform Bronze training enrolments to Silver |
| 05 | `silver/NB_05_Bronze_to_Silver_Streaming.py` | Micro-batch Bronze to Silver processing using Delta CDF |
| 06 | `gold/NB_06_Gold_Dimensional_Model.py` | Build Gold dimensions and facts |
| 07 | `ops/NB_07_Data_Quality_Checks.py` | Run DQ checks and stop downstream processing on failures |
| 08 | `ops/NB_08_Monitoring_and_Alerting.py` | Write freshness, row count, and DQ alert metrics |
| 09 | `gold/NB_09_PowerBI_Semantic_Model_Prep.py` | Build Power BI-ready Gold summary tables |
| 10 | `ops/NB_10_Purview_Lineage_Annotations.py` | Apply table metadata for cataloguing and lineage |
| 11 | `ops/NB_11_Delta_Maintenance.py` | Vacuum, optimize, and analyze Delta tables |


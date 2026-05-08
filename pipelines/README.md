# Pipeline Definitions

This folder is reserved for Fabric pipeline JSON definitions exported through Git integration.

Recommended pipeline set:

| Pipeline | Purpose | Trigger |
| --- | --- | --- |
| `PL_Daily_Bronze` | Run Excel and REST Bronze ingestion | Daily morning |
| `PL_Daily_Silver` | Run Silver transformations after Bronze | Daily after Bronze |
| `PL_Daily_Gold` | Run Gold build after DQ passes | Daily after DQ |
| `PL_Stream_15min` | Run micro-batch streaming from Bronze to Silver | Every 15 minutes |
| `PL_Weekly_Maintenance` | Run Purview annotations and Delta maintenance | Weekly |


# Monitoring and Alerting

## Monitoring Objectives

- Detect pipeline failures quickly.
- Detect data freshness breaches.
- Detect data quality failures before they reach Gold.
- Detect row count anomalies.
- Track operational health over time.

## Core Tables

| Table | Purpose |
| --- | --- |
| `Bronze_Lakehouse.control_pipeline_log` | Pipeline and notebook run audit |
| `Bronze_Lakehouse.control_watermark` | Source ingestion watermarks |
| `Silver_Lakehouse.control_silver_watermark` | Silver transformation watermarks |
| `Silver_Lakehouse.dq_log` | Data quality results |
| `Silver_Lakehouse.monitoring_alerts` | Active monitoring alerts |
| `Silver_Lakehouse.monitoring_metrics` | Metric snapshots |

## Alert Rules

| Alert | Condition | Severity |
| --- | --- | --- |
| Pipeline failure | Any scheduled pipeline fails | High |
| Freshness breach | No successful load within SLA | High |
| DQ failure | DQ status is `FAIL` | High |
| DQ warning | DQ status is `WARN` | Medium |
| Row count anomaly | Current load differs from 7-day average by more than 30% | Medium |
| Long-running pipeline | Runtime exceeds expected duration | Medium |

## Data Activator / Reflex Patterns

Pipeline failure:

```sql
SELECT pipeline_name, source_system, status, error_message
FROM Bronze_Lakehouse.control_pipeline_log
WHERE status = 'FAILED'
  AND end_ts >= dateadd(minute, -30, current_timestamp());
```

Data quality failure:

```sql
SELECT entity, check_name, fail_pct, severity
FROM Silver_Lakehouse.dq_log
WHERE status = 'FAIL'
  AND cast(run_ts AS TIMESTAMP) >= dateadd(minute, -30, current_timestamp());
```

Freshness breach:

```sql
SELECT source_system, last_run_ts
FROM Bronze_Lakehouse.control_watermark
WHERE last_run_ts < dateadd(hour, -26, current_timestamp());
```

## Alert Routing

| Alert type | Primary recipient | Secondary recipient |
| --- | --- | --- |
| Pipeline failure | Data engineering team | Platform owner |
| DQ failure | Data steward | Data engineering team |
| Freshness breach | Data engineering team | Source owner |
| Privacy or access issue | Data governance lead | Security owner |


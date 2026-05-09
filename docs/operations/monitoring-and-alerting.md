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
| `Bronze_Lakehouse.api_call_log` | REST API status, response time, retries, and record counts |
| `Bronze_Lakehouse.schema_change_log` | Excel header drift and unresolved schema changes |
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
| API failure | Any API call fails after retries | High |
| API rate limit | More than 5 rate-limit responses in 24 hours | Medium |
| Duplicate file | Duplicate file detected today | Medium |
| Schema drift | Unresolved row in `schema_change_log` | High |

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

API health:

```sql
SELECT api_name,
       count(*) AS total_calls,
       sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
       sum(CASE WHEN status = 'RATE_LIMITED' THEN 1 ELSE 0 END) AS rate_limits,
       round(avg(response_ms), 0) AS avg_response_ms
FROM Bronze_Lakehouse.api_call_log
WHERE called_at >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY api_name;
```

File ingestion health:

```sql
SELECT source_system, status, count(*) AS file_count, sum(row_count) AS total_rows
FROM Bronze_Lakehouse.file_ingestion_registry
WHERE cast(detected_at AS DATE) = current_date()
GROUP BY source_system, status;
```

## Alert Routing

| Alert type | Primary recipient | Secondary recipient |
| --- | --- | --- |
| Pipeline failure | Data engineering team | Platform owner |
| DQ failure | Data steward | Data engineering team |
| Freshness breach | Data engineering team | Source owner |
| Privacy or access issue | Data governance lead | Security owner |

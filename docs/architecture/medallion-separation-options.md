# Fabric Medallion Architecture — Separation Options

Interactive guide comparing 5 approaches with pros, cons, and recommendations.

---

## Option 1 — Three separate Lakehouses

**Recommended for most**

```
Bronze Lakehouse → Silver Lakehouse → Gold Lakehouse → Power BI (Direct Lake)
```

| Layer | Description |
|-------|-------------|
| **Bronze Lakehouse** | Raw Delta tables, append-only. Source files in **Files/**. Tables in **Tables/**. No transformations. 7-year retention. |
| **Silver Lakehouse** | Cleansed, deduplicated conformed entities. SCD Type 2 history. Delta MERGE for upserts. DQ checks run here. |
| **Gold Lakehouse** | Star schema dimensional model. Fact + dimension tables. Consumed directly by Power BI via Direct Lake mode. |

### Advantages
- Hard physical boundary — a report literally cannot query Bronze
- Independent access control per layer (RBAC, sensitivity labels)
- Independent retention policies per layer
- Independent compute and capacity limits
- Purview lineage tracks movement between Lakehouses clearly
- Easier to swap Gold for a Warehouse later without touching Bronze/Silver
- Teams can own individual layers (ingestion team, transformation team)

### Trade-offs
- Three Lakehouse items to manage in the workspace
- Cross-Lakehouse reads in PySpark need explicit qualified names
- Slightly more setup steps initially
- Capacity costs apply per Lakehouse if on separate capacities

### When to use
Production data platforms with multiple teams, GDPR/regulated data, or where different departments own different layers. This is the pattern used in the university implementation guide — medical data governance requires hard Bronze isolation.

### Cross-Lakehouse read pattern in PySpark
```python
# From Silver Notebook, reading Bronze data:
df = spark.read.table("Bronze_Lakehouse.bronze_training_enrolments")

# Writing to Silver — fully qualified:
df.write.format("delta").mode("append")
  .saveAsTable("Silver_Lakehouse.silver_training_enrolments")
```

---

## Option 2 — One Lakehouse, separate schemas/folders

**Good for small teams**

```
Single Lakehouse → Tables/bronze_* + Tables/silver_* + Tables/gold_*
```

| Layer | Description |
|-------|-------------|
| **Tables/** | All Delta tables in one Lakehouse. Naming convention separates layers: `bronze_`, `silver_`, `gold_` prefix on every table name. |
| **Files/** | Raw source files in `Files/raw/bronze/`, staging in `Files/staging/`. All in the same OneLake path. |
| **Access Control** | All access managed at workspace level only — no layer-level isolation. Everyone with workspace access sees all tables. |

### Advantages
- Simplest setup — one item to manage
- No cross-Lakehouse qualified names in notebooks
- Easiest for a solo developer or small team
- Lower workspace item count

### Trade-offs
- No physical access boundary — Power BI can accidentally see Bronze
- Cannot apply different retention per layer
- Cannot assign different sensitivity labels per layer
- Hard to split ownership between teams
- Purview lineage less clear — all assets in same container
- Scales poorly — all tables in one list becomes unwieldy

> **Not recommended for the university project** — medical data requires Bronze to be physically isolated from analyst access. A governance auditor expects layer-level access control, which this option cannot provide.

### When to use
Proof-of-concept, personal projects, or very small teams (1–2 engineers) with non-sensitive data where simplicity outweighs governance requirements.

---

## Option 3 — Lakehouses (Bronze + Silver) + Warehouse (Gold)

**Best for SQL-first teams**

```
Bronze Lakehouse → Silver Lakehouse → Gold Warehouse (T-SQL) → Power BI (DirectQuery or Import)
```

| Layer | Description |
|-------|-------------|
| **Bronze Lakehouse** | Raw ingestion via PySpark/ADF. Delta tables. Append-only. Spark is the right engine for messy raw data. |
| **Silver Lakehouse** | PySpark transformations, Delta MERGE for SCD Type 2. PySpark is better than T-SQL for complex cleansing logic. |
| **Gold Warehouse** | T-SQL dimensional model. Stored procedures for Gold logic. Views, RBAC, DDM. SSRS-compatible. Full SQL Server semantics. |

### Advantages
- Best engine for each job — Spark for raw/messy, SQL for structured Gold
- Gold Warehouse supports stored procedures, views, DDM natively
- SQL-native analysts and BI developers work in familiar T-SQL
- Warehouse has full ANSI SQL compliance — easier query migration
- Power BI DirectQuery on Warehouse is more predictable than Direct Lake for complex models
- Works well if university already has SQL Server expertise

### Trade-offs
- Two different engines to understand (Spark + T-SQL)
- Warehouse does not support Direct Lake mode — must use DirectQuery or Import
- Loading Silver → Warehouse requires a pipeline step (COPY INTO or ADF)
- Warehouse storage costs separately from Lakehouse

### When to use
When the Gold layer consumers are SQL-first (BI analysts, report developers) and need stored procedures, complex views, or need to migrate existing SQL Server models into Fabric. Strong choice if the university already has SQL Server skills.

### Loading Silver → Gold Warehouse
```sql
-- In Gold Warehouse, create external table over Silver Delta:
CREATE TABLE dbo.dim_student AS
SELECT * FROM Silver_Lakehouse.silver_students
WHERE is_current = 1;

-- Or use COPY INTO from Silver parquet files:
COPY INTO dbo.fact_training_completion
FROM 'abfss://silver@onelake.dfs.fabric.microsoft.com/...'
WITH (FILE_TYPE = 'PARQUET');
```

---

## Option 4 — All layers in Fabric Warehouse only

**Avoid for this project**

```
Single Warehouse → Schema: bronze + Schema: silver + Schema: gold
```

| Layer | Description |
|-------|-------------|
| **schema: bronze** | Raw staging tables in T-SQL. Works if all sources are relational — struggles with nested JSON, semi-structured Excel. |
| **schema: silver** | T-SQL transformations via stored procedures or CTAS. No PySpark — complex transformations become very verbose SQL. |
| **schema: gold** | Dimensional model, views, aggregates in T-SQL. This part is well-suited to the Warehouse — it's the other layers that are the problem. |

### Advantages
- Single item — one connection string for everything
- Pure T-SQL — no Spark knowledge required at all
- Schema-level access control (GRANT on schema)
- Good if all sources are already structured/relational

### Trade-offs
- Fabric Warehouse cannot natively read Excel files
- Semi-structured JSON from REST APIs needs preprocessing first
- No Delta Change Data Feed or time travel in Warehouse tables
- PySpark features (schema evolution, CDC streams) unavailable
- Transformation logic in stored procedures becomes unmaintainable at scale
- Warehouse storage is more expensive than Lakehouse Delta for raw/Bronze volume

> The university has Excel + REST API sources. The Fabric Warehouse cannot ingest these natively — you'd need an ADF pipeline to flatten them before they even reach the Warehouse. At that point you're doing the Bronze work outside anyway, making "all in Warehouse" meaningless. Not the right pattern here.

### When it makes sense
Only when all sources are already structured SQL databases (SQL Server, PostgreSQL, Snowflake mirrors) and the team has zero Spark experience. Even then, most architects use at least a Lakehouse for Bronze to retain raw data cheaply.

---

## Option 5 — Hybrid (Lakehouses + Warehouse + Eventhouse)

**Enterprise / advanced**

```
Bronze Lakehouse → Silver Lakehouse → Gold Warehouse → Power BI

Real-time source → Eventstream → Eventhouse (KQL) → Silver Lakehouse (mirror)
```

| Layer | Description |
|-------|-------------|
| **Bronze Lakehouse** | Batch sources: Excel, daily REST API pulls. Append-only Delta. |
| **Silver Lakehouse** | Unified entity store. Receives from both Bronze (batch) and Eventhouse (streaming). Single truth for Gold. |
| **Gold Warehouse** | T-SQL analytical layer. Reads from Silver via shortcuts. Views, DDM, RBAC. |
| **Eventhouse (KQL)** | Real-time event stream landing zone. Near-instant latency for live feeds. Mirrors to Silver Lakehouse for unified access. |

### Advantages
- Right engine for every workload — batch, streaming, SQL analytics
- Eventhouse gives sub-second latency for real-time alerts
- Gold Warehouse serves T-SQL consumers without Spark knowledge
- Scales independently — each component scales on its own capacity
- OneLake Shortcuts allow Gold Warehouse to query Silver data without copying it

### Trade-offs
- Most complex setup — 4+ Fabric items to maintain
- Team needs Spark, KQL, and T-SQL skills simultaneously
- Higher cost at smaller scale
- Overkill unless real-time streaming is a genuine requirement

### When to use
When the platform genuinely has both batch (Excel/API) and real-time (event stream, IoT, webhook) sources and needs them unified in the same Silver layer. For the university, consider this as Phase 2 once batch pipelines are stable — not day one.

---

## Side-by-side Comparison

All five options compared across the dimensions that matter most.

| Criterion | Option 1 — 3 Lakehouses | Option 2 — 1 Lakehouse | Option 3 — LH + Warehouse | Option 4 — All Warehouse | Option 5 — Hybrid |
|-----------|--------------------------|------------------------|----------------------------|--------------------------|--------------------|
| **Excel ingestion** | ✓ Native PySpark | ✓ Native PySpark | ✓ PySpark to LH | ✗ Needs pre-processing | ✓ PySpark to Bronze LH |
| **REST API (JSON)** | ✓ PySpark flatten | ✓ PySpark flatten | ✓ PySpark to LH | ✗ Must flatten before load | ✓ PySpark or Eventstream |
| **Real-time streaming** | ~ Spark Streaming | ~ Spark Streaming | ~ Spark Streaming | ✗ Not supported | ✓ Eventhouse native |
| **Layer access control** | ✓ Per Lakehouse RBAC | ✗ Workspace-level only | ✓ Per item RBAC | ~ Per schema GRANT | ✓ Per item RBAC |
| **GDPR / data isolation** | ✓ Strong | ✗ Weak | ✓ Strong | ~ Moderate | ✓ Strong |
| **Direct Lake (Power BI)** | ✓ From Gold LH | ✓ From any table | ✗ Not from Warehouse | ✗ Not from Warehouse | ~ From Silver LH only |
| **T-SQL / stored procs** | ✗ PySpark only | ✗ PySpark only | ✓ In Warehouse | ✓ Full SQL Server | ✓ In Warehouse |
| **Delta time travel** | ✓ All layers | ✓ All layers | ✓ Bronze + Silver | ✗ Warehouse tables only | ✓ Bronze + Silver |
| **Purview lineage** | ✓ Clear cross-LH | ~ Within one item | ✓ LH → Warehouse | ~ Schema-level only | ✓ Full end-to-end |
| **Setup complexity** | Medium | Low | Medium | Low–Medium | High |
| **Team skill needed** | PySpark + Fabric | PySpark + Fabric | PySpark + T-SQL | T-SQL only | PySpark + T-SQL + KQL |
| **University fit** | ✓ **Best fit** | ✗ Not suitable | ✓ Good if SQL team | ✗ Not suitable | ~ Phase 2 evolution |

### Recommendation for the university project

**Start with Option 1** (3 separate Lakehouses). It gives you hard layer isolation for GDPR compliance, Direct Lake for Power BI, and is the cleanest pattern to hand off to a new team. If you find the Gold layer consumers are strongly T-SQL-first, evolve Gold to a Warehouse (Option 3) — the Bronze and Silver Lakehouses do not change at all. Add Eventhouse only when genuine real-time requirements emerge.

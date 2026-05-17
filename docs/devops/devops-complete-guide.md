# Complete Guide — Git Integration, Deployment Pipeline, and Document Storage Strategy for Microsoft Fabric University Data Platform

## What Git Does in This Architecture

Git stores your code — not your data. Every Notebook (.ipynb), every Pipeline definition (.json), and every configuration file lives in Git. The _data_ (Delta tables, Parquet files) lives in OneLake. Git gives you version history, the ability to roll back a broken notebook, and the mechanism to promote code from DEV → TEST → PROD without copy-pasting.

---

## Repository Structure (Azure DevOps)

```
fabric-university-platform/          ← root repo
│
├── notebooks/                       ← all PySpark notebooks
│   ├── bronze/
│   │   ├── NB_00_Data_Profiling.ipynb
│   │   └── NB_02_Bronze_All_Sources_Ingest.ipynb
│   ├── silver/
│   │   ├── NB_04_Silver_Training_Enrolments.ipynb
│   │   └── NB_05_Bronze_to_Silver_Streaming.ipynb
│   ├── gold/
│   │   ├── NB_06_Gold_Dimensional_Model.ipynb
│   │   └── NB_09_PowerBI_Semantic_Model_Prep.ipynb
│   └── ops/
│       ├── NB_01_Create_Control_Tables.ipynb
│       ├── NB_07_Data_Quality_Checks.ipynb
│       ├── NB_08_Monitoring_and_Alerting.ipynb
│       ├── NB_10_Purview_Annotations.ipynb
│       └── NB_11_Delta_Maintenance.ipynb
│
├── pipelines/                       ← Fabric Pipeline JSON definitions
│   ├── PL_Daily_Bronze.json
│   ├── PL_Daily_Silver.json
│   ├── PL_Daily_Gold.json
│   ├── PL_Stream_15min.json
│   └── PL_Weekly_Maintenance.json
│
├── config/                          ← environment-specific settings
│   ├── config_dev.json              ← DEV connection strings
│   ├── config_test.json             ← TEST connection strings
│   └── config_prod.json             ← PROD connection strings
│
├── docs/                            ← technical documentation
│   ├── STTM_v1.2.xlsx              ← Source-to-Target Mapping
│   ├── architecture_decision_log.md
│   └── runbook.md
│
├── tests/                           ← unit tests for transformation logic
│   ├── test_silver_transformations.py
│   └── test_dq_rules.py
│
└── README.md                        ← setup guide for new engineers
```

---

## Branch Strategy

```
feature/NB-04-silver-staff    ← engineer works here
        ↓  Pull Request + code review
develop                       ← TEST workspace tracks this branch
        ↓  Pull Request + manager approval
main                          ← PROD workspace tracks this branch
```

**Rule:** NO direct commits to `develop` or `main`. Every change goes: feature branch → PR → develop → PR → main.

> When you connect a Fabric workspace to Git and switch to the `develop` branch, that workspace **automatically reflects whatever is in develop**. Push a notebook change to develop → TEST workspace updates within seconds. No manual copy-paste ever.

---

## Deployment Pipeline — How Code Moves DEV → TEST → PROD

### Step 1 — Engineer writes code in UNIV-DEV workspace `DEV`
Open a Fabric Notebook in UNIV-DEV. Write and test NB_04_Silver_Training_Enrolments. When ready, click **Sync** in the Fabric Git panel — this commits the notebook to your `feature/NB-04-silver-staff` branch in Azure DevOps automatically.

**↓**

### Step 2 — Raise a Pull Request: feature → develop `automatic`
In Azure DevOps → Repos → Pull Requests → New PR. Source: `feature/NB-04-silver-staff` → Target: `develop`. Assign the consultancy manager as reviewer. PR description: what changed, why, which DQ checks pass. The CI pipeline runs your unit tests automatically on every PR.

**↓**

### Step 3 — UNIV-TEST workspace auto-updates `TEST` `automatic`
The moment the PR is merged to `develop`, UNIV-TEST workspace — which is connected to the `develop` branch — shows the updated notebook immediately. No manual steps. Run the notebook in TEST against TEST data. Run integration tests. If all green, raise a second PR.

**↓**

### Step 4 — Raise a Pull Request: develop → main `manual approval`
Source: `develop` → Target: `main`. This PR requires approval from the consultancy Data Lead (not just the manager). Attach: test run results, DQ scorecard, confirmation of UAT sign-off. No notebook goes to PROD without this gate.

**↓**

### Step 5 — UNIV-PROD workspace auto-updates `PROD` `automatic`
UNIV-PROD is connected to `main`. Merging the PR updates PROD immediately. The nightly pipeline trigger picks up the new notebook version automatically — no manual restart needed. Verify in Fabric Monitor that the first production run succeeds.

> Never edit a notebook directly in the PROD workspace. Every change — even a one-line fix — must go through the feature → develop → main flow. This keeps the Git history clean and makes rollbacks trivial.

---

## How to Roll Back a Bad Deployment

### Option 1 — Git revert (preferred)
In Azure DevOps → Commits on main → find the bad commit → Revert → creates a new commit undoing the change → PROD workspace auto-updates to the reverted version.

### Option 2 — Delta time travel (data only)
If bad code wrote bad data to Silver:
```
RESTORE TABLE Silver_Lakehouse.silver_training_enrolments
TO VERSION AS OF 3;   ← roll back to version 3
```

---

## Workspace Breakdown — What Lives Where

### UNIV-DEV
| Attribute | Value |
|---|---|
| **Git branch** | feature/* |
| **Data** | Synthetic / sample (never real PII) |
| **Capacity** | F2 (small — cheap) |
| **Who uses it** | Data engineers only |
| **Purpose** | Write, test, break things safely. Notebooks are experimental here. |
| **Contains** | Bronze_LH_DEV, Silver_LH_DEV, Gold_LH_DEV (all with fake data) |

### UNIV-TEST
| Attribute | Value |
|---|---|
| **Git branch** | develop |
| **Data** | Anonymised copy of real data |
| **Capacity** | F8 (medium) |
| **Who uses it** | Engineers + analysts + UAT testers |
| **Purpose** | Integration testing, UAT with university stakeholders, performance testing. |
| **Contains** | Bronze_LH_TEST, Silver_LH_TEST, Gold_LH_TEST |

### UNIV-PROD
| Attribute | Value |
|---|---|
| **Git branch** | main |
| **Data** | Live university data (real PII — RBAC enforced) |
| **Capacity** | F64 (production grade) |
| **Who uses it** | All roles (RBAC controls access per layer) |
| **Purpose** | Live platform. Pipelines scheduled here. Power BI reports connect here. |
| **Contains** | Bronze_LH, Silver_LH, Gold_LH, Gold_Warehouse |

### UNIV-GOVERNANCE
| Attribute | Value |
|---|---|
| **Git branch** | governance (separate) |
| **Data** | Metadata only (no raw data) |
| **Capacity** | F8 |
| **Who uses it** | Data stewards, compliance officers, auditors |
| **Purpose** | Purview policies, sensitivity labels, lineage review, audit reports. Completely isolated from engineering work. |
| **Contains** | Purview connection, audit log dashboards, policy definitions |

---

## Key Rule: Data Never Crosses Workspace Boundaries Directly

### OneLake Shortcuts — How TEST Reads PROD Data Safely

You never copy production data into TEST manually. Instead, use an **OneLake Shortcut** — a pointer that lets TEST read a _read-only snapshot_ of PROD Bronze tables without duplicating the data. The shortcut appears as a normal table in TEST but cannot be written to.

In UNIV-TEST Lakehouse → New shortcut → OneLake → select UNIV-PROD/Bronze_Lakehouse/Tables/bronze_training_enrolments → Create.

For anonymisation: run a one-time PySpark notebook that reads the shortcut, masks PII columns (e.g. replace email with fake@test.com), and writes to a local TEST Silver table.

---

## Document Storage Strategy

| Document | What It Contains | Where It Lives |
|---|---|---|
| **STTM (Source-to-Target Mapping)** | Every source column → target column mapping, transformation rules, data types, validation logic. One row per attribute across all entities. | Confluence (also backed up in Git /docs/) |
| **Business Questions & KPI definitions** | All agreed business questions, KPI formulas, target values, alert thresholds. The contract between business and data team. | Confluence (linked from JIRA stories) |
| **Data Profiling Reports** | Output of NB_00. Null rates, duplicate counts, value distributions, anomalies found in raw source files. Evidence base for STTM decisions. | Lakehouse (Files/profiling_reports/ in Bronze_LH_DEV) |
| **Architecture Decision Log** | Why we chose Option 1 (3 Lakehouses), why watermark CDC, why Direct Lake. Each decision has a date, options considered, and rationale. | Git (/docs/architecture_decision_log.md) |
| **Runbook (operational guide)** | Daily checklist, troubleshooting guide, how to restart a failed pipeline, how to roll back. Written for whoever operates the platform day-to-day. | Confluence (also in Git /docs/runbook.md) |
| **DQ Log (live)** | Every DQ check result written by NB_07. Queryable as a Delta table. Feeds the Power BI DQ Monitor page. | Lakehouse (Silver_Lakehouse.dq_log) |
| **Weekly Status Report** | Friday update to the consultancy manager: completed, in progress, blockers. One page. Sent via Teams/email. | SharePoint (the consultancy project folder) |
| **JIRA / Sprint board** | All work items, user stories, bugs, scope change requests. Every feature branch name references a JIRA ticket (e.g. feature/UNIV-42-silver-staff). | JIRA (linked to Azure DevOps PRs) |
| **Stakeholder meeting notes** | Discovery sessions with doctors, training managers, IT. Requirements captured, open questions, decisions made. | Confluence (per-meeting page, linked to sprint) |
| **Sensitivity label policy** | Which columns carry which label, who approved, GDPR legal basis. Signed off by Data Steward. | Purview (UNIV-GOVERNANCE workspace) |

> The STTM is the most important document on the project. Keep it in Confluence so it is version-controlled, searchable, and anyone (including the university client) can be given read access. Never keep the canonical STTM in someone's personal OneDrive or email inbox.

---

## Governance Workspace (UNIV-GOVERNANCE)

The Governance workspace is not where data lives. It is where **policies, lineage, and audit evidence** live. Separating it means an auditor or compliance officer can be given access to this workspace without ever being able to see Bronze raw data or Silver PII tables.

### Items Inside UNIV-GOVERNANCE

1. **Microsoft Purview connection** — The Purview account (univ-purview) is registered here. Purview automatically scans all four workspaces and catalogues every table, column, and pipeline. The scan schedule: Bronze daily, Silver daily, Gold weekly, streaming tables on-demand.

2. **Sensitivity label dashboard (Power BI report)** — A report connected to Purview's API that shows: how many assets are labelled, which PII columns exist, which tables have no sensitivity label (governance gap). Updated automatically as Purview scans run.

3. **Lineage viewer** — Purview's lineage graph, surfaced in this workspace. Shows the complete chain: Excel file → ADF pipeline → Bronze table → Silver notebook → Gold fact table → Power BI report. Any auditor can click on a column in a Power BI report and trace it back to the original Excel cell it came from.

4. **GDPR audit log report** — A Power BI report over the Purview audit log showing: who accessed which table, when, from which application. This is what the university's Data Protection Officer will ask for if there is ever a GDPR query.

5. **RBAC assignment documentation** — A Notebook (NB_10) that documents every role assignment across all workspaces as a Delta table — who has what access, when it was granted, by whom. Not the access control itself (that is managed in Fabric Admin), but the evidence that access was managed correctly.

> During a GDPR audit, you need to demonstrate three things: (1) you know what PII data you hold and where — Purview catalogue answers this. (2) You control who can access it — RBAC + DDM answers this. (3) You can show the complete trail of how data moves — Purview lineage answers this. UNIV-GOVERNANCE is the single place a Data Protection Officer goes to find all three.

---

## Daily Git Workflow

### Morning — check last night's runs
Open Fabric Monitor in UNIV-PROD → Activity runs → filter last 12 hours. All green? Check the DQ log query. Any WARN or FAIL? Investigate before touching any code today.

### 1. Create a JIRA ticket for today's work
Example: UNIV-47 — "Add academic_semester column to silver_training_enrolments". Every piece of work, even a small one, gets a ticket. This links your PR to a business requirement.

### 2. Create a feature branch in Azure DevOps
```
In Azure DevOps → Repos → Branches → New branch
Name: feature/UNIV-47-silver-academic-semester
From: develop  ← always branch from develop, never from main
```

### 3. Switch UNIV-DEV workspace to your feature branch
```
UNIV-DEV workspace → top bar → Git branch indicator
→ Switch branch → feature/UNIV-47-silver-academic-semester
→ Update (pulls the branch into your DEV workspace)
```

Now your DEV workspace reflects your feature branch. Any notebook you edit here will be committed to that branch.

### 4. Edit the notebook in UNIV-DEV
Open NB_04_Silver_Training_Enrolments in DEV. Make the change. Run it against DEV data. DQ checks pass. The Fabric Git panel shows the notebook as "Modified".

### 5. Commit to your feature branch
```
Fabric workspace → Source control panel (top right)
→ Changes: NB_04_Silver_Training_Enrolments.ipynb (modified)
→ Commit message: "UNIV-47: add academic_semester derived column"
→ Commit and push
```

The notebook is now in Azure DevOps under your feature branch.

### 6. Raise a Pull Request to develop
Azure DevOps → Repos → Pull Requests → New → feature/UNIV-47 → develop. Add the JIRA ticket number in the description. CI pipeline runs unit tests automatically. Assign reviewer.

### 7. After PR approval — TEST picks it up automatically
Once merged to develop, UNIV-TEST shows the updated notebook immediately. Run it in TEST. If it passes, create the develop → main PR for PROD promotion.

> The full cycle for a small change (one notebook, one column) is: 30 min to write and test in DEV → PR raised → 24h for review → 30 min TEST validation → PR to PROD → live. For urgent hotfixes, the manager can approve both PRs on the same day.

---

## Config Files — How DEV, TEST, PROD Know Which Lakehouse to Use

```json
config_dev.json:
{
  "bronze_lakehouse" : "Bronze_LH_DEV",
  "silver_lakehouse" : "Silver_LH_DEV",
  "gold_lakehouse"   : "Gold_LH_DEV",
  "api_base_url"     : "https://lms-uat.university.ie/api/v2",
  "secret_scope"     : "univ-secrets-dev"
}

config_prod.json:
{
  "bronze_lakehouse" : "Bronze_Lakehouse",
  "silver_lakehouse" : "Silver_Lakehouse",
  "gold_lakehouse"   : "Gold_Lakehouse",
  "api_base_url"     : "https://lms.university.ie/api/v2",
  "secret_scope"     : "univ-secrets-prod"
}
```

In every notebook — first cell reads the config:
```python
import json
env = spark.conf.get("pipeline.env", "dev")
cfg = json.load(open(f"config/config_{env}.json"))
BRONZE = cfg["bronze_lakehouse"]   # use this everywhere instead of hardcoding
```

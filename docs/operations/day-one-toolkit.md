# Complete Day-One Toolkit — Contract Start

> Weekly status report template, 6-month project timeline, bronze layer data verification approach, and pre-start checklist.

---

## Weekly Status Report

### Why send it and when

**Send every Friday by 4:30pm — no exceptions.**

The weekly status report is the single most powerful reputation-building tool available to a contractor. It shows control, transparency, and professionalism. Most contractors never send one unprompted. Doing it consistently from week one creates a permanent impression that carries through the entire engagement. Keep it short — 3 sections, under one page. The manager should be able to read it in 90 seconds.

---

### Week 1 — first ever status report (special format)

```
Subject: University Data Platform — Week 1 Status | Shajeeb S

Hi [Manager name],

Here is my week 1 summary for the university data platform engagement.

COMPLETED THIS WEEK
─────────────────────────────────────────
• Onboarded to the consultancy systems, tools, and project context
• Attended kickoff and stakeholder introduction meetings
• Reviewed all available documentation and existing source files
• Completed initial source inventory — identified 5 Excel sources across 3 departments and 1 REST API (LMS system)
• Completed data profiling on 2 of the 5 Excel sources — findings document attached

KEY FINDINGS FROM PROFILING
─────────────────────────────────────────
• Training enrolments: 3 columns with >15% null rate — flagged for STTM discussion
• Doctor schedules: date format inconsistency detected (mix of dd/MM/yyyy and MM/dd/yyyy)
• LMS REST API: access credentials requested from IT — awaiting response
• No existing data governance documentation found — Purview setup required from scratch

NEXT WEEK PLAN
─────────────────────────────────────────
• Complete profiling on remaining 3 Excel sources
• Draft STTM v0.1 for training enrolments entity
• Set up UNIV-DEV workspace and Git repository structure
• First Bronze pipeline (training enrolments Excel) in DEV

BLOCKERS / DECISIONS NEEDED
─────────────────────────────────────────
• LMS API credentials — need IT contact introduced by [date]
• SharePoint folder structure — confirm where department teams will drop Excel files

Happy to discuss any of the above. Have a great weekend.

Shajeeb S
Senior Data Analyst | the consultancy (Contract)
```

---

### Weeks 2–24 — standard weekly format

```
Subject: University Data Platform — Week [N] Status | Shajeeb S

Hi [Manager name],

Week [N] summary below.

COMPLETED THIS WEEK
─────────────────────────────────────────
• [Specific deliverable with measurable outcome — e.g. "Bronze Excel pipeline live in DEV — 4,832 rows loaded, 0 errors"]
• [Second deliverable]
• [Third deliverable — keep to 3–5 bullets max]

IN PROGRESS
─────────────────────────────────────────
• [Item currently being worked — include % complete estimate if useful]
• [Second in-progress item]

NEXT WEEK PLAN
─────────────────────────────────────────
• [Specific planned deliverable]
• [Second planned item]

BLOCKERS / DECISIONS NEEDED FROM YOU
─────────────────────────────────────────
• [Specific ask — name the person or decision needed]
  → If none: "No blockers this week — all items on track"

METRICS THIS WEEK
─────────────────────────────────────────
• Pipeline runs: [X] successful / [Y] failed
• DQ checks: [X] passing / [Y] warnings / [Z] failures
• Rows processed: [X] Bronze / [Y] Silver / [Z] Gold
• Quality score: [X]%

[Optional: one sentence on anything notable — good or bad]

Shajeeb S
Senior Data Analyst | the consultancy (Contract)
```

> **Note:** The metrics section becomes available once pipelines are running (from about week 4 onwards). Before that, replace it with "Setup progress: DEV ✓ / TEST — / PROD —" so the manager always has a visual indicator of where things stand.

---

### Rules for writing good status updates

| ✅ Always do | ❌ Never do |
|---|---|
| Use specific numbers — "4,832 rows" not "data loaded" | Use vague language — "worked on Bronze layer" tells nothing |
| Name the blocker owner — "awaiting IT contact from [name]" | Skip a week because "nothing happened" — always send |
| State next week's plan before being asked | Bury a problem at the bottom — blockers go in their own section |
| Mention risks even if you plan to resolve them yourself | Write more than 5 bullets per section |
| Keep it under one page — managers skim | Wait until Monday morning to send the Friday report |
| Send at the same time every week — 4:30pm Friday | Send without a subject line that includes the week number |
| Attach any profiling reports or draft documents as evidence | |

---

## 6-Month Delivery Plan

> Present this as a living document — not a fixed contract. Frame it to the manager as "my proposed plan — I'd like your input before we share with the client." This positions you as organised and proactive without over-committing on day one.

| Weeks | Phase | Details |
|---|---|---|
| **Week 1–2** | Discovery & environment setup | Stakeholder interviews, source inventory, data profiling all 5 Excel sources + REST API investigation. Git repo + 4 workspaces created. STTM v0.1 drafted. Control tables created. |
| **Week 3–5** | Bronze layer — all sources ingesting in DEV | NB_02 Excel ingestion live for all 4 sources. NB_03 REST API ingestion live with watermark CDC. Control/watermark tables seeded. Pipeline run logging active. Historical backfill complete. |
| **Week 6–7** | Bronze → TEST + business sign-off on source data | Bronze pipelines promoted to TEST. Source data reconciliation session with university IT — they verify row counts match their source systems. STTM v1.0 signed off by data steward. |
| **Week 8–10** | Silver layer — all entities transformed & DQ framework live | NB_04 Silver transformations for all 6 entities. SCD Type 2 active. NB_05 streaming Bronze→Silver live. NB_07 DQ checks running — minimum 90% quality score required before Gold build begins. |
| **Week 11–13** | Gold layer + Power BI prototype — first stakeholder demo | Star schema built. dim_date, dim_student, dim_staff, dim_course, fact tables live. Power BI prototype with Training Dashboard and Clinical Hours report shown to university stakeholders. Feedback captured in writing. |
| **Week 14–15** | UAT — stakeholders test reports against known data | University training manager, medical director, and IT review TEST environment. Each verifies their report numbers against their known source data. UAT sign-off document produced. |
| **Week 16–17** | Governance — Purview, RBAC, sensitivity labels, DDM | Purview scanning all workspaces. Sensitivity labels applied to all PII columns. Dynamic Data Masking on Gold Warehouse. RBAC groups assigned. GDPR audit evidence report generated in UNIV-GOVERNANCE. |
| **Week 18–20** | Production deployment + monitoring live | Full platform promoted to UNIV-PROD via Fabric Deployment Pipeline. All scheduled triggers activated. NB_08 monitoring running every 30 min. Reflex alerts configured for Teams. Smoke test pipeline passing. All 5 Power BI reports live. |
| **Week 21–24** | Hypercare, runbook, handover & extension planning | Two weeks of hypercare — daily monitoring, rapid fix of any production issues. Runbook completed. University IT staff trained on platform operation. Architecture documentation finalised. Extension conversation with the consultancy manager about Phase 2 scope. |

> ⚠️ **Buffer weeks:** weeks 7, 13, and 17 are intentionally lighter. Do not fill them with extra scope — they exist to absorb delays from stakeholder sign-offs, access requests, and API issues that always take longer than expected in a university environment.

---

## Bronze Layer Data Verification

### The core rule — who accesses what layer

**Business users never see Bronze directly — and here is exactly why.**

Bronze is your raw, unmodified source data. It contains everything exactly as it came in — wrong date formats, status codes like "C" instead of "Completed", nulls, duplicates, and all. Showing this to a doctor or training manager would confuse them and undermine trust in the platform. The Bronze layer is for engineers only. Business verification happens at Silver and Gold.

### The three levels of data verification

**1. Bronze reconciliation — engineer-to-IT only**

After the first Bronze load, you run a reconciliation session with the university's IT contact or the person who provided the Excel files. You share a simple count report — "we loaded 4,832 rows from training_enrolments_oct.xlsx — does that match the row count in your source?" This is a technical handshake between engineers, not a business meeting.

**2. Silver verification — business users verify cleansed data**

This is where business stakeholders first get involved. You give the training manager access to a simple Silver verification report in Power BI — a plain table showing the cleansed data with readable column names ("Completed" instead of "C", proper dates). They check: do the student names look right? Are the course names correct? Are any records obviously wrong? This is the UAT for transformation logic.

**3. Gold UAT — business users verify numbers match reality**

The most important verification. The training manager is asked: "From your records, how many students completed the Mandatory Fire Safety course in October?" They give you a number — say 87. You show them the Gold dashboard — it says 87. That match is your UAT sign-off. Do this for 5–10 specific known numbers across different domains before going live.

### What to actually build for verification at each stage

**Bronze — build a reconciliation report (engineers only, never shared with business)**

A simple PySpark notebook that produces a row-count summary table — one row per source file loaded, with batch_id, file name, row count, and load timestamp. Output this as a Delta table and optionally a CSV. You share this with the university IT contact to confirm nothing was missed during ingestion. This is not a Power BI dashboard — it is a technical handover document.

**Silver — build a simple data verification view (shared with business users in TEST only)**

A basic Power BI report page — one table per entity — showing the cleansed Silver data in plain business language. No aggregations, no KPIs. Just the raw rows with readable column names and proper formatting. Give the training manager read access to this in TEST only. Ask them to flag any rows that look wrong. Document all feedback in a verification log before proceeding to Gold.

**Gold — formal UAT sign-off document**

Prepare a one-page UAT sign-off sheet with 10 spot-check numbers — specific counts or totals the business can verify against their own records. Example: "Total active enrolments in Semester 1 2024/25 = 1,204 — verified by Training Manager [name] on [date]." Get this signed (or emailed confirmation) before PROD deployment. This protects both you and the consultancy if anyone later questions the numbers.

| ✅ What business users should see | ❌ What business users should never see |
|---|---|
| Silver verification table in TEST (plain rows, no aggregation) | Bronze Delta tables — raw unprocessed data |
| Gold Power BI dashboards in TEST during UAT | Bronze files in the Lakehouse Files/ zone |
| Gold Power BI dashboards in PROD after sign-off | The DQ log detail table (too technical) |
| DQ monitor page (summary only — pass/fail counts) | Pipeline run logs or error messages |

> ✅ **Bottom line:** The bronze layer never needs a business-facing dashboard. The reconciliation report you build is for your own confidence and for the IT handshake — not for doctors or training managers. Keep that boundary clean from day one.

---

## Pre-Start Checklist

### Complete before your first day — tick each off

**Tools & access**
- [ ] Set up Microsoft Teams (the consultancy tenant)
- [ ] Set up Azure DevOps account
- [ ] Install VS Code with Python extension
- [ ] Install Azure Data Studio
- [ ] Create a Fabric trial workspace for personal practice
- [ ] Request JIRA / Confluence access from the consultancy manager

**Knowledge prep**
- [ ] Re-read the full implementation guide document
- [ ] Re-read the PySpark script library document
- [ ] Practise explaining the 3-Lakehouse architecture aloud in 2 minutes
- [ ] Practise explaining watermark CDC without notes
- [ ] Practise explaining Direct Lake vs DirectQuery in plain English
- [ ] Write 10 discovery questions for the university stakeholders

**Pre-start questions sent to manager**
- [ ] Ask about tools and credential setup before day one
- [ ] Ask if Fabric capacity is provisioned or needs to be created
- [ ] Ask for main university contact name and role
- [ ] Ask for any existing project documents to read in advance
- [ ] Confirm preferred status report format (email vs Teams)

**Day one preparation**
- [ ] Prepare a printed or digital one-page project overview to reference
- [ ] Write your Week 1 status report template (fill in Friday)
- [ ] Set a recurring Friday 4:00pm calendar reminder — "Write status report"
- [ ] Set up a private notes document to log decisions, blockers, and meeting notes

### Questions to ask the consultancy before day one

Email or message your manager this week — not on day one — and ask:

1. **What tools will I be using day-to-day — Teams, JIRA, Confluence, Azure DevOps? Can I get credentials set up before I start?**

2. **Is there an existing Azure DevOps organisation and project I should join, or do I need to create one?**

3. **Has a Fabric capacity been provisioned for this engagement, or is that part of my first week's tasks?**

4. **Who is my main point of contact at the university — IT lead, data owner, or project sponsor?**

5. **Are there any existing documents — previous data audit, IT architecture diagrams, or SharePoint structure — I should read before day one?**

6. **What is the preferred status reporting format — email, Teams message, or shared document?**

---

## Things You Haven't Asked Yet — But Need to Know

### 1. What happens when the university changes an Excel file mid-project?

This will happen. A department will rename a column, add a new tab, or change a date format. You need a formal source change request process from day one — a simple rule: "Any change to source Excel file structure must be notified to the data team at least 3 business days in advance." Put this in writing in the project governance document. Without it, a silent column rename will break your Silver transformation in production at 6am on a Monday.

### 2. Who owns the data at the university — and who can approve changes to it?

You need a named Data Owner and a named Data Steward at the university before you write a single pipeline. The Data Owner (typically a department head) approves what data enters the platform. The Data Steward (typically an IT or compliance person) approves sensitivity labels and access control decisions. Without these two roles filled, GDPR compliance is impossible and every access decision becomes a debate.

### 3. What is the data retention policy?

The university will have a data retention policy — how long student records, medical records, and training records must be kept (often 7 years for medical, varies for academic). This affects your Bronze retention setting, your Silver VACUUM policy, and whether you can ever truly delete a record or must only soft-delete it. Ask the university's Data Protection Officer for the retention schedule in week one. Design it in later is expensive.

### 4. What happens to the platform when your contract ends?

This is uncomfortable to think about before you start, but critical. Who at the university or the consultancy will operate the platform after you leave? If nobody has the skills to run it, either you train someone during the engagement (the right answer), or the platform dies within months of your departure. Identify the person who will own it operationally and build them into your documentation and training plan from week one. This also makes the extension conversation easier — "I want to stay to ensure proper handover."

### 5. How do you handle student or medical data under GDPR for a university in Ireland?

Ireland's Data Protection Commission is strict. University data containing student records falls under GDPR Article 6 (lawful basis for processing). Medical/clinical data falls under Article 9 (special category data) and requires explicit additional safeguards. The university must have a lawful basis documented for every data processing activity you build. Ask for their Data Processing Register in week one — if it does not exist, flag it to the consultancy manager immediately as a governance risk.

### 6. What if the REST API specs change during the project?

Third-party systems release updates. The LMS vendor might change their API response structure, deprecate an endpoint, or require a new authentication method during your 6-month engagement. Your Bronze REST API notebook must be written to detect unexpected schema changes and fail loudly rather than silently swallowing the change. Also get the vendor's API changelog URL and subscribe to notifications on day one — knowing about a breaking change 2 weeks in advance versus 2 hours changes everything.

### 7. Are there existing Power BI reports or Excel-based reports you are replacing?

Almost certainly yes. The training manager is probably sending a manually compiled Excel report to someone every week. The medical director probably has a spreadsheet someone maintains. Before you build any dashboard, identify every existing report and understand who depends on it. Your Gold layer must produce the same numbers those reports show — or the stakeholders will not trust your platform. Run a "numbers match" exercise in UAT where you compare your dashboard output against the last manually produced report.

### 8. What is your escalation path if you are blocked for more than 2 days?

Define this with your manager in week one: if you are waiting for an API credential, a SharePoint access request, or a stakeholder decision for more than 2 business days, what do you do? Who do you escalate to? On a 6-month contract, 5 days of blocked time is nearly 1% of your entire engagement. Have an agreed escalation process so you are never sitting idle while waiting for someone to action a request.

### 9. What does the third-party system actually contain — and can it be fully replaced long term?

You know there is a third-party LMS system with a REST API, but you do not yet know: what data it holds that is NOT in Excel, whether the university owns that data, whether the vendor allows bulk export, and whether the university plans to renew that contract. The answers affect your architecture. If the LMS contract ends in 18 months, building a deep integration with it may be wasted effort. Ask about the vendor contract status in your discovery sessions.

### 10. What is the network and firewall situation for API calls from Fabric?

Fabric Notebooks make outbound HTTP calls to REST APIs. University networks often have restrictive firewall rules. The LMS API may only be accessible from within the university network — which Fabric (a Microsoft cloud service) is not part of. This is a day-one infrastructure question for the university IT team. If the API is behind a firewall, you may need a VNet integration or an Azure API Management gateway. Find out before you design the ingestion pipeline.

# Team Collaboration Guide

> Complete guide to working effectively in a multi-person team on the consultancy university data platform project, covering team structure, task allocation, Git workflow, communication, and day one priorities.

---

## Day One Priorities

**Your day one goal — listen, map, and observe. Do not build anything yet.**

The single most important thing on day one: You already know more about this project technically than almost anyone in that office. That is not the risk. The risk is coming in with solutions before you understand the people, the politics, and the context. Spend day one understanding the landscape, not demonstrating your knowledge. Your moment to shine will come in week two when you present your first findings.

### Day One Checklist

1. Arrive 10 minutes early. Set up your laptop and be ready when others arrive.
2. Introduce yourself to every person on the team — name, role, and one sentence on your background.
3. Ask the manager: who are all the people involved in this project and what are their roles?
4. Ask for access: Azure DevOps repo, Fabric workspace, Teams channel, JIRA/Confluence.
5. Ask to see any existing project documents — previous work, architecture diagrams, data inventory.
6. Find out: what is the most urgent deliverable right now and when is it expected?
7. Lunch with a team member if possible — relationship-building matters as much as technical skill.
8. Map the university stakeholders: who are the doctors, training managers, IT contact, DPO?
9. Identify any blockers already known: missing credentials, pending access, unclear requirements.
10. Write your day one notes: what you learned, open questions, first impressions of the project state.
11. Message the manager: "Thanks for the welcome today — here are my initial observations and my plan for tomorrow." (2-3 bullet points only)

### The Five Questions to Answer by End of Day One

1. **Who is my daily contact — manager or lead?** — The person you report progress to, ask for unblocking, and send the Friday status report to. Confirm their name, Teams handle, and preferred communication style today.
2. **Who are the other people on this project?** — Names, roles, skills, and which part of the project they are covering. Draw a simple mental map — you need to know who to ask for what.
3. **What has already been started or decided?** — Any previous work, existing infrastructure, decisions already made. You do not want to propose something that was already tried and rejected six months ago.
4. **What is the most urgent deliverable right now?** — The thing the manager or client is waiting for. Align your first week's work to that, not to what you think is most interesting technically.
5. **What does the university client expect to see first?** — Their first impression of the project will be shaped by whatever you show them first. Know what that is before you start building.

---

## Team Structure

**Map the team before you assign any work.** Every person on the project has a different skill level, context, and motivation. Before splitting work, spend your first two days understanding each person. A junior analyst given a task that is too hard will go quiet and miss the deadline. A senior person given something too basic will disengage. Your job as the technical lead is to match the task difficulty to the person's capability and give them enough context to succeed independently.

### Typical Roles on a Consultancy Data Project

| Role | Description |
|---|---|
| **Engagement Manager** | Owns the client relationship and commercial delivery. Not technical. Needs a weekly status summary, risk flags, and to look good in front of the university. Give them a one-page update every Friday — they will use it verbatim with the client. |
| **Data Lead / Senior Engineer** | Your closest collaborator. Probably has broader consultancy context you lack. Respect their decisions in front of the client even if you disagree — resolve differences privately. Make them look good and they will protect you. |
| **Mid-level analyst / engineer** | Can own a specific layer or pipeline independently if given clear specs. Assign them Bronze ingestion or Silver transformations with the STTM document as their reference. Check in daily, not hourly — give autonomy but stay available. |
| **Junior analyst** | Best used for data profiling, documentation, testing, and STTM updates. Do not give them production pipeline work without a senior reviewer. Pair them with a mid-level person for the first two weeks so they learn the patterns before working alone. |
| **University IT contact** | Not the consultancy staff but critical. They control SharePoint access, API credentials, and network firewall approvals. Identify them on day one and build a good relationship. Every blocked task eventually traces back to waiting for something from IT. |
| **University data steward / DPO** | The governance gatekeeper. Needs to sign off on sensitivity labels, RBAC changes, and the GDPR evidence package. Brief them early — a late surprise from the DPO can delay PROD deployment by weeks. |

---

## How to Split the Work

**Split work by Medallion layer** — each layer is a natural ownership boundary. The three-Lakehouse architecture gives you a clean way to divide work. Bronze, Silver, and Gold can each be owned by a different person or pair. They are loosely coupled — as long as the schema contract between layers is agreed upfront, people can work in parallel without stepping on each other.

### Recommended Work Split for a 3-4 Person Team

- **You** — Overall architecture + Gold layer + stakeholder management. You own the technical direction, the config/Git structure, the Gold dimensional model, and the Power BI semantic model. You are also the one in stakeholder meetings translating business needs into data design. You review every PR before it merges to develop.
- **P2 (Mid-level engineer)** — Silver transformation layer. Owns NB_04, NB_05 streaming, and the Silver DQ framework (NB_07). Give them the STTM document and the silver_training.py transformer as their starting point. Definition of done: Silver tables pass all DQ checks with >95% quality score.
- **P3 (Mid-level engineer)** — Bronze ingestion layer. Owns NB_02 Excel ingestion, NB_03 REST API, and the file_ingestion_registry. Give them the codebase repo and the file ingestion design doc. Definition of done: all five Excel sources and both REST APIs loading to Bronze with zero manual intervention.
- **P4 (Junior analyst)** — Data profiling, documentation, testing. Owns NB_00 profiling runs, STTM documentation updates, test writing in tests/, and the weekly reconciliation report. This work is critical but well-defined — perfect for someone building confidence. Pair them with P3 for the first week.

### The Schema Contract

The interface between Bronze and Silver must be agreed on day two. Bronze engineer and Silver engineer need to agree the Bronze table schema before either writes production code. The Bronze engineer writes the column names and data types. The Silver engineer agrees to transform from exactly those names. If they build in parallel without this, you get a schema mismatch that only surfaces in production. Hold a 30-minute alignment session: "Bronze produces these columns in these types — Silver takes them and produces these output columns." Write it in the STTM. Done.

### Parallel Work Dependency Timeline

```
Week 1-2: Everyone can work in parallel on their layer in DEV
  P3 → Bronze ingestion (DEV only, synthetic data)
  P2 → Silver transformation (DEV only, reads from P3's Bronze tables)
  P4 → Data profiling + STTM documentation
  You → Architecture, config setup, Gold skeleton, stakeholder meetings

Week 3-4: P3 Bronze must be complete before P2 Silver can be finalised
  P3 Bronze PR reviewed and merged to develop
  P2 Silver can now test against real Bronze output
  P4 writes tests for P2's Silver transformations
  You → Gold dimensional model, Power BI prototype

Week 5+: Gold depends on Silver being stable
  P2 Silver DQ checks passing >95%
  You → Build Gold on top of stable Silver
  P3 → REST API ingestion completion + monitoring notebooks
  P4 → UAT support, reconciliation reports
```

---

## Git Team Workflow

With multiple people, Git discipline is the difference between smooth delivery and chaos.

**One rule that prevents 90% of team Git problems:** Nobody commits directly to develop or main. Every change — including a two-line fix — goes through a feature branch and a Pull Request. This sounds slow but it is faster overall because you catch problems before they block the whole team. A broken notebook merged directly to develop blocks everyone working in TEST.

### Branch Naming Convention

```
feature/UNIV-{ticket-number}-{short-description}

Examples:
  feature/UNIV-01-bronze-excel-ingest
  feature/UNIV-02-silver-training-transform
  feature/UNIV-03-gold-dim-student
  feature/UNIV-04-dq-checks-framework
  bugfix/UNIV-15-silver-scd2-second-pass
  hotfix/UNIV-22-prod-watermark-stuck
```

### PR Review Rules

- **R1:** Every PR needs at least one reviewer who did not write it. Junior PRs reviewed by mid-level or senior. Mid-level PRs reviewed by you or the data lead. PRs to main require your sign-off plus the consultancy manager's approval.
- **R2:** PR description must include: what changed, why, how to test it. Create a PR template in Azure DevOps so this is enforced. A PR with only a title and no description does not get reviewed — it gets returned to the author.
- **R3:** DQ checks must pass before any Silver PR merges. Run NB_07 in DEV against the feature branch output. Attach the DQ scorecard screenshot to the PR. If quality score is below 90%, the PR does not merge.
- **R4:** Resolve PR comments within 24 hours. A PR that sits unreviewed for 3 days blocks the person who raised it. Set a team norm: PRs get reviewed within one business day, and authors address comments within one business day of receiving them.

### Conflict Prevention

| Do (prevents conflicts) | Don't (creates conflicts) |
|---|---|
| Each person owns their own notebook files | Two people editing silver_training.py simultaneously |
| Shared src/ files get a named owner who reviews all changes | Long-running branches open for 2+ weeks |
| config/*.json only edited by you (architecture decisions) | Force-pushing to develop or main |
| Rebase feature branches on develop daily if they diverge | Merging without running the notebooks first |
| Short-lived branches — merge within 3 days of opening | Resolving merge conflicts without telling the original author |

---

## Meetings & Communication

### Meeting Cadence

| Frequency | Meeting | Details |
|---|---|---|
| **Daily** | 15-minute standup — 09:15 | Three questions only: what did I complete yesterday, what am I doing today, is anything blocking me. No problem-solving in standup — blockers get a separate conversation after. Keep it to 15 minutes or people stop attending. |
| **Weekly** | 45-minute team sync — Wednesday 14:00 | Review the sprint board together. Discuss any cross-layer dependencies surfacing. Demo any working prototype from the week. Raise scope change requests before they become assumptions. This is the meeting where you catch drift before it becomes a problem. |
| **Weekly** | Friday status report to manager — 16:30 | You write this and send it. It covers the whole team's output, not just yours. This is the single most visible thing you do all week. Make it crisp: completed, in progress, next week, blockers. Include one metric — something the manager can quote to their engagement lead. |
| **Bi-weekly** | University stakeholder update — alternate Thursdays | Show progress to the university team. Never show raw data or Bronze layer outputs. Always show a working dashboard or prototype, even if on synthetic data. End with three specific questions for them so they feel ownership over the direction. |

### Communication Rules for a Distributed Team

- **Everything important goes in writing — no verbal-only decisions.** If a decision is made in a meeting, one person writes a summary in the Teams channel within an hour. A decision that was only verbal does not exist.
- **Use channels, not DMs, for project decisions.** When you ask a question or share a finding in a Teams DM, only one person sees it. When you post it in the project channel, the whole team benefits. Reserve DMs for sensitive conversations — everything else is in the open channel so knowledge stays with the project, not with individuals.

---

## Leading as a Contractor

You are a contractor, not a permanent staff member — this changes how you lead. Your authority comes from technical credibility, not from hierarchy. You cannot tell a consultancy employee what to do. What you can do is make recommendations so clearly reasoned that following them is the obvious choice. Build your influence through expertise and reliability, not through assertiveness.

### Specific Leadership Behaviours

1. **Unblock people before they ask** — Check in with each team member daily in standup. If someone says they are waiting for an API credential, offer to escalate it with the IT contact on their behalf. Removing blockers is the highest-value thing a technical lead does on a consulting project.

2. **Give credit publicly, give feedback privately** — In the Friday status report: "This week P3 completed the Bronze Excel ingestion ahead of schedule." In the standup: never correct someone's approach in front of the group. Pull them aside for a 5-minute conversation instead.

3. **Write the architecture decisions — do not just say them** — Every technical decision you make should be in the architecture decision log within 24 hours. This protects you and teaches the rest of the team the reasoning behind choices they inherit.

4. **Share knowledge deliberately, not accidentally** — When you solve a tricky problem, write a short note in the Teams channel explaining what the problem was and how you solved it. This builds your reputation and raises the whole team's capability.

5. **Protect your team from scope creep, not just yourself** — When the university asks for something new mid-sprint, your job is to log it, size it, and bring it to the manager for a scope conversation — before anyone on the team starts building it. Junior engineers say yes to everything because they want to be helpful. You protect them from that.

> The difference between a good contractor and a great one is not technical skill — it is how they make the people around them better. If the team ships more because of how you organised and supported them, that is the kind of reputation that gets you extended, recommended, and brought back on future engagements.

### The Question to Ask Yourself Every Morning

> "What is the one thing I can do today that would make the biggest difference to the project — and am I doing that thing, or something easier?"

---

# System Integration & Enterprise Data Management

## Goal
Establish an enterprise-wide data management framework for NUH that integrates all source systems into a governed, ML-ready data platform following the medallion architecture (Bronze → Silver → Gold).

## Scope

**In Scope:**
- Data ingestion from 12 source system types (Microsoft Dynamics, Excel, REST API, SOAP, CSV, webhooks, AWS DataHub, AWS HubSpot, Ghost Inspector, TLMF User Portal, Social Media, MailChimp)
- Enterprise data management across 7 capability areas: Design, Recruit, Apply, Enrol, Manage Members & Fellows, Manage Enquiries, Manage Records & Info
- Medallion architecture implementation (Bronze/Silver/Gold layers)
- Data governance framework
- ML-ready data pipeline preparation

**Out of Scope:**
- Direct system-to-system integrations (ETL only, not system replacement)
- Real-time operational processing (focus is analytical/enterprise data)

## Key Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Medallion Architecture Pipeline | Bronze (raw), Silver (cleansed), Gold (aggregated/curated) data layers |
| 2 | Data Governance Framework | Policies, data quality rules, lineage tracking, access controls |
| 3 | Source System Connectors | Standardised connectors for all 12 source types |
| 4 | ML-Ready Data Marts | Feature-engineered datasets accessible by ML pipelines |
| 5 | Capability Data Models | Unified data models for each of the 7 capability areas |
| 6 | Monitoring & Observability | Data pipeline health, SLA tracking, error handling |

## Benefits

| Area | Benefit |
|------|---------|
| **Insights** | Unified view across all capabilities enables cross-functional analytics (e.g., Recruit → Apply → Enrol funnel analysis) |
| **Visibility** | End-to-end data lineage and governance provide auditability and compliance for NUH's data assets |
| **Scalability** | Medallion architecture allows incremental refinement without reprocessing the full dataset |
| **ML Readiness** | Gold-layer data marts are engineered for direct consumption by ML models, reducing time-to-insight |

## Sample Deliverables

### Sample 1: Medallion Pipeline Structure
```yaml
bronze/
  dynamics/
  excel/
  rest_api/
  soap/
  csv/
  webhooks/
  aws_datahub/
  aws_hubspot/
  ghost_inspector/
  tlmf_portal/
  social_media/
  mailchimp/
silver/
  design/
  recruit/
  apply/
  enrol/
  members_fellows/
  enquiries/
  records_info/
gold/
  capability_marts/
  ml_features/
```

### Sample 2: Governance Rule (Data Quality)
```yaml
rule: email_not_null
scope: apply.applicants
severity: error
action: reject_record
logic: applicant_email IS NULL OR applicant_email NOT LIKE '%@%'
```

### Sample 3: ML-Ready Feature Table (Gold Layer)
| column | type | description |
|--------|------|-------------|
| applicant_id | string | Unique applicant identifier |
| num_applications_12m | int | Application count in last 12 months |
| avg_days_to_enrol | float | Average days from Apply → Enrol |
| source_channel | string | Originating channel (web/social/phone) |
| is_converted | boolean | Did applicant complete enrolment? |

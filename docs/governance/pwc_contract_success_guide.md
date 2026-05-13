# PwC Contract Success Guide

> Extracted from `pwc_contract_success_guide.html` — interactive guide to succeeding in a PwC contract role, covering the first 90 days, how to build reputation, avoid common mistakes, and position for extension.

---

## Before Day One

### The single most important mindset shift

You are not arriving as a technical resource who executes tasks. You are arriving as a **trusted advisor who happens to be technical**. PwC sells advisory — their managers notice who thinks like a consultant and who thinks like a developer. Your CV proves you can build. Day one starts proving you can *lead*.

### Practical preparation

**Research the client** — Understand the university before your first call. Read about their faculties, medical school, and any published digital strategy. Know their size — how many students, campuses, key departments. Skim their annual report if available.

**Prepare questions** — Write 10 intelligent discovery questions. Examples:
- "What does success look like at 6 months for the client?"
- "Who are the key stakeholders and what are their biggest frustrations?"
- "Is there a data steward or IT contact already identified at the university?"
- "What previous attempts at data consolidation have been tried and why didn't they succeed?"

**Know your own work** — Re-read the implementation guide and script library. Know the architecture cold — Bronze/Silver/Gold separation rationale, why Direct Lake, why watermark CDC over log-based. Have a crisp one-line answer for each decision.

**Set up your tools** — Have your environment ready on day one. Ask PwC ahead of time what tools you will use (Teams, Azure DevOps, JIRA, Confluence). Arrive with VS Code, Azure Data Studio, and a Fabric trial workspace already configured.

---

## First 90 Days

| Phase | Focus |
|-------|-------|
| Day 1–10 | Listen & discover |
| Day 11–30 | Deliver something visible |
| Day 31–60 | Own your domain |
| Day 61–90 | Lead and mentor |

### Week by week

**Week 1** — Shut up and listen. Attend every meeting, take detailed notes, ask one smart question per meeting (not five). Map who the real decision-makers are versus who just attends. Identify the person at the university who is most frustrated — they will become your biggest advocate if you solve their pain.

**Week 2** — Do the source inventory yourself. Do not wait to be asked. Get access to the Excel files and spend a day profiling them. Come back to the manager with a written findings document — column quality issues, date format inconsistencies, missing keys.

**Week 3** — Deliver something the client can see. Build a rough Power BI prototype on synthetic or sample data. Show the university stakeholders what the Training Dashboard will look like.

**Week 4** — Produce the STTM (Source-to-Target Mapping) documentation proactively. This signals you understand the professional standard for data projects.

**Weeks 5–8** — Bronze and Silver pipelines live in DEV. Get all ingestion notebooks running, DQ checks passing, Silver entities loading. Run a weekly status update to the PwC manager — one page, three sections: what was done, what is next, any blockers.

**Weeks 9–12** — Gold layer and first production dashboard. UAT session with university stakeholders. Capture feedback in a written log.

> The difference between a contractor who gets extended and one who doesn't is nearly always visible in weeks 2 and 3. Early proactive delivery creates a perception of competence that carries you through the entire engagement.

---

## Impressing the Manager

### What PwC managers actually watch for

**Communicate up before you are asked** — Send a brief written update every Friday — even if nothing dramatic happened. Three bullets: completed, in progress, blockers. Managers who have to chase for status updates lose confidence fast.

**Translate technical work into business language** — Every technical milestone should have a business sentence attached to it. Not "Bronze pipelines are live" but "We now have a reliable, automated feed pulling all five Excel sources into a governed raw data layer."

**Bring the solution, not just the problem** — Every time you raise a blocker, come with at least one proposed solution. This is the difference between a contractor and a consultant.

**Show awareness of the wider engagement** — Ask the manager if there are other workstreams on this engagement. Offer to support a briefing or write a technical summary. Contractors who make the whole engagement look good get extended.

**Own your mistakes fast and clean** — If a pipeline breaks, a DQ check fails, or you miss a deadline — tell the manager before they find out from someone else. Speed of acknowledgement matters far more than the mistake itself.

> PwC managers are often under pressure from their own engagement leads. Make your manager look good to their boss — that is the fastest path to a strong relationship.

---

## Building Reputation

### Do these consistently

- Be the first person to respond to a Teams message
- Always have your camera on in video calls
- Take notes in every meeting and share them after
- Arrive 2 minutes early to every call
- Deliver what you said you would, exactly when you said
- Acknowledge other people's contributions publicly
- Ask the university stakeholders about their experience, not just their requirements
- Write documentation nobody asked for but everyone needs
- Raise risks early — even ones you can solve yourself
- Say "I'll find out and come back to you" rather than guessing

### Never do these

- Go quiet when things are difficult
- Disagree with the client in front of the PwC manager
- Promise a delivery date you are not 90% sure of
- Use jargon in stakeholder meetings
- Wait to be told what to do next
- Complain about the client's data quality to the client
- Skip the Friday update even once
- Let a blocker sit for more than 24 hours without escalating
- Over-engineer when a simple solution works
- Talk about other clients or past employers negatively

### Reputation with the university client specifically

The doctors and training staff are not data people — adapt accordingly. Ask about their day-to-day frustrations first. A surgeon does not care about Delta Lake — they care about not having to chase someone for a report every Monday.

Become the person who makes things easier for everyone. Spot things outside your strict scope and mention them.

> Reputation compounds. One week of strong delivery is forgotten. Six weeks of consistent delivery, clear communication, and proactive thinking makes you genuinely irreplaceable by month three.

---

## Mistakes to Avoid

**Going too deep, too fast on technical solutions** — The number one mistake of strong technical contractors. Spend the first two weeks understanding the actual problem before proposing anything.

**Underestimating the stakeholder management side** — This is a university with doctors, surgeons, training managers, and IT staff. Each group has different priorities and different levels of data literacy. Spend time with each user group.

**Scope creep without flagging it** — Every request outside agreed scope must be logged and discussed with the PwC manager before you commit to it.

**Waiting for perfect data before showing something** — Show rough, early, honest prototypes. Frame them correctly. Early visibility builds trust. Late reveals create anxiety.

**Treating the PwC manager as an obstacle rather than an ally** — Your manager has context you do not have. Treat them as a partner. Ask what would make their life easier.

---

## Getting Extended

### The extension conversation starts in month two, not month five

**Make yourself indispensable without making yourself irreplaceable** — Indispensable means the engagement goes better with you on it. Irreplaceable means you are the only one who understands it — which is a risk, not a strength. Write documentation. Build runbooks. Train at least one person at the university.

### Evidence you should be building from day one

- **Value** — Keep a private log of every measurable outcome: hours saved, processes automated, errors caught by DQ checks, positive stakeholder feedback.
- **Trust** — Every promise kept, every risk flagged early, every problem solved before it became visible — these are trust deposits. Make them daily.
- **Future** — Around month three or four, start planting the seed of what phase two could look like (Eventhouse, automated compliance triggers, HR analytics module).

> The formal extension decision is almost always already made informally 6–8 weeks before the contract end date. The manager forms a view based on your pattern over the whole engagement — not a single brilliant moment at the end.

### The question to ask yourself every Friday

> *"If I were the PwC manager reviewing this week, would I feel confident that this contractor is in control, communicating clearly, and making the engagement better — or would I have any doubt?"*

If the answer is anything other than a clear yes, fix it before Monday.

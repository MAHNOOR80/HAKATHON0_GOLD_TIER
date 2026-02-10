# CEO Briefing Skill

> "Monday Morning CEO Briefing" — a weekly executive summary that audits
> financials, project health, and social engagement so the CEO starts the
> week fully informed.

---

## Description

This skill performs a **multi-source audit** across the entire AI Employee
system — bank transactions, project tasks, social engagement, and Odoo
accounting — then compiles a single executive briefing document in
`/Plans/CEO_Briefing_<YYYY-MM-DD>.md`.

The briefing is designed to be sent via `send_email` or posted as a
LinkedIn summary. Both delivery methods are gated by
`Approval_Check_Skill` (`approval_needed: true`).

This is an **autonomous, multi-step skill** — it integrates with
`Ralph_Wiggum_Loop_Skill` to walk through each audit phase without
premature completion.

---

## Position in Reasoning Loop

```
[Scheduler triggers Monday 9:00 AM]
    --> CEO_Briefing_Skill activates
    --> Ralph_Wiggum_Loop wraps the full audit
        │
        │  Iteration 1: FINANCIAL AUDIT
        │  ├── Read bank tasks in /Needs_Action/ and /Done/ (revenue/expenses)
        │  ├── Query Odoo MCP: get_report (summary, revenue_weekly)
        │  └── Compile revenue vs expense totals, flag unpaid invoices
        │
        │  Iteration 2: PROJECT AUDIT
        │  ├── Read all tasks in /Needs_Action/ (pending work, bottlenecks)
        │  ├── Read /Pending_Approval/ (blocked items awaiting human decision)
        │  ├── Read /Done/ (completed since last briefing)
        │  └── Identify delays: stale tasks (>7 days), approval bottlenecks
        │
        │  Iteration 3: SOCIAL AUDIT
        │  ├── Read latest Social_Summary in /Plans/
        │  ├── Extract engagement metrics, revenue leads
        │  └── Summarize top performers and lead pipeline
        │
        │  Iteration 4: COMPILE BRIEFING
        │  ├── Generate /Plans/CEO_Briefing_<date>.md
        │  ├── Create delivery task in /Needs_Action/ (approval_needed: true)
        │  ├── Update Dashboard.md
        │  └── Log to System_Log.md
        │
        └── RALPH_DONE
```

---

## Trigger Conditions

Activate this skill when:
- **Scheduler** fires the weekly CEO briefing job (default: Monday 9:00 AM)
- User says: "CEO briefing", "Monday briefing", "Executive summary"
- User says: "How's the business doing?", "Weekly report"
- Manually: triggered by user prompt or `ralph_wrapper.py`

---

## Inputs

### Data Sources (in audit order)

| # | Source | Location | Data Extracted |
|---|--------|----------|----------------|
| 1 | Bank tasks | `/Needs_Action/task_bank_*.md`, `/Done/task_bank_*.md` | Transaction totals, anomalies, revenue vs expenses |
| 2 | Odoo Accounting | MCP `odoo_accounting` → `get_report` | Revenue (weekly/monthly), expenses, invoice status |
| 3 | Project tasks | `/Needs_Action/*.md`, `/Pending_Approval/*.md`, `/Done/*.md` | Pending count, bottlenecks, completed work, stale items |
| 4 | Social summaries | `/Plans/Social_Summary_*.md` (latest) | Engagement rate, revenue leads, top posts |
| 5 | Dashboard.md | Root | Recent actions, CEO summary history, system health |

### Fallback Behavior

| Source | If unavailable | Fallback |
|--------|---------------|----------|
| Odoo MCP | Connection fails or no credentials | Use bank task files only; note "Odoo unavailable" in briefing |
| Social summary | No summary exists for the period | Note "No social data this week"; skip social section |
| Bank tasks | No bank files found | Note "No bank data this week"; skip financial section |

---

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Briefing report | `/Plans/CEO_Briefing_<YYYY-MM-DD>.md` | Full executive summary |
| Delivery task | `/Needs_Action/task_ceo_briefing_send_<date>.md` | Email/LinkedIn delivery task (`approval_needed: true`) |
| Dashboard update | `Dashboard.md` → "Latest Updates" + "Recent Actions" | Briefing reference and action log |
| System log entry | `Logs/System_Log.md` | Audit trail |

---

## Briefing Report Structure

```markdown
---
type: ceo_briefing
status: completed
created_at: <timestamp>
period: "2026-02-03 to 2026-02-10"
approval_needed: false
mcp_action: []
---

# CEO Briefing — Week of <YYYY-MM-DD>

## Executive Summary

> One-paragraph overview: business health, key numbers, what needs
> the CEO's attention this week.

---

## 1. Financial Overview

### Revenue & Expenses (This Week)

| Category | Amount | Change vs Last Week |
|----------|--------|---------------------|
| Revenue  | $X,XXX | ▲/▼ X%              |
| Expenses | $X,XXX | ▲/▼ X%              |
| Net      | $X,XXX | ▲/▼ X%              |

### Odoo Accounting Snapshot

| Metric | Value |
|--------|-------|
| Open invoices (draft) | X ($X,XXX total) |
| Overdue invoices | X ($X,XXX total) |
| Payments received this week | X ($X,XXX) |
| Payments sent this week | X ($X,XXX) |

### Anomalies Flagged

| Date | Description | Amount | Status |
|------|-------------|--------|--------|
| 2026-02-07 | Large vendor payment | $2,500 | Pending approval |

---

## 2. Project & Task Health

### Task Pipeline

| Status | Count | Details |
|--------|-------|---------|
| Completed this week | X | [list key completions] |
| In progress | X | [list active work] |
| Pending (Needs Action) | X | [list pending items] |
| Blocked (Awaiting Approval) | X | [list blocked items] |

### Bottlenecks & Delays

| Task | Age (days) | Blocker | Recommended Action |
|------|------------|---------|-------------------|
| Reply to client_john | 3 | Awaiting CEO approval | Approve or reject in /Pending_Approval/ |
| Partnership reply | 3 | Awaiting CEO approval | Review draft and decide |

### Key Completions

- [Task 1] — completed [date]
- [Task 2] — completed [date]

---

## 3. Social Media & Leads

### Engagement Summary (from latest Social_Summary)

| Metric | LinkedIn | X | Total |
|--------|----------|---|-------|
| Posts | X | X | X |
| Likes | X | X | X |
| Comments | X | X | X |
| Engagement rate | X% | X% | X% |

### Revenue Lead Pipeline

| # | Lead | Platform | Signal | Status |
|---|------|----------|--------|--------|
| 1 | client_john | LinkedIn | Pricing inquiry | Hot — awaiting follow-up |

### Social Recommendations

- [Key recommendation 1]
- [Key recommendation 2]

---

## 4. Recommendations for This Week

1. **[Priority 1]** — [specific action + why]
2. **[Priority 2]** — [specific action + why]
3. **[Priority 3]** — [specific action + why]

## 5. Decisions Needed from CEO

| # | Decision | Deadline | Impact |
|---|----------|----------|--------|
| 1 | Approve/reject client reply | Today | Revenue opportunity ($X,XXX) |
| 2 | Review partnership proposal | This week | Strategic partnership |

---

## System Health

| Component | Status |
|-----------|--------|
| File Watcher | Operational |
| Gmail Watcher | Operational |
| Bank Watcher | Operational |
| Social Watcher | Operational |
| MCP Server | Connected |
| Odoo ERP | Connected |
| Scheduler | Running |

---

_Generated by CEO_Briefing_Skill via Ralph_Wiggum_Loop — <timestamp>_
```

---

## Ralph Wiggum Loop Integration

The CEO Briefing is a **multi-step audit** — exactly the kind of task
Ralph Loop is designed for. The loop prevents premature completion by
ensuring every data source is audited before the briefing is compiled.

### Loop Plan (4 iterations minimum)

| Iteration | Phase | Actions | Completion Check |
|-----------|-------|---------|-----------------|
| 1 | Financial Audit | Read bank tasks, query Odoo `get_report` (read-only, no approval needed) | Financial data collected? |
| 2 | Project Audit | Scan `/Needs_Action/`, `/Pending_Approval/`, `/Done/` | Task counts and bottlenecks identified? |
| 3 | Social Audit | Read latest `Social_Summary_*.md` from `/Plans/` | Social metrics extracted? |
| 4 | Compile & Deliver | Write briefing to `/Plans/`, create send task, update Dashboard | Briefing file exists AND delivery task created? → `RALPH_DONE` |

### Ralph Loop Configuration for CEO Briefing

```yaml
ralph_loop:
  task_id: "ceo_briefing_<date>"
  max_iterations: 8          # 4 phases + buffer for retries
  auto_plan: false            # Phases are pre-defined above, not dynamic
  pause_on_approval: true     # Pause if send_email gate triggers
  verbose_logging: true       # Log each audit phase
```

### Prompt to Trigger via Ralph Loop

```
Use Ralph_Wiggum_Loop_Skill on this task:
Execute CEO_Briefing_Skill — perform the full 4-phase audit
(financial, project, social, compile) and generate the Monday
Morning CEO Briefing in /Plans/CEO_Briefing_<date>.md.
Then create a delivery task for send_email with approval_needed: true.
```

---

## Delivery Options

After the briefing is compiled, the skill creates a delivery task with
`approval_needed: true`. The CEO chooses the delivery method:

### Option A: Email to CEO

```yaml
---
type: ceo_briefing_delivery
status: pending
priority: high
approval_needed: true
approved: false
mcp_action: ["send_email"]
---
```

- **To:** CEO's email (configured in `.env` as `CEO_EMAIL`)
- **Subject:** "Weekly CEO Briefing — Week of <date>"
- **Body:** Full briefing content (markdown rendered)

### Option B: LinkedIn Summary Post

```yaml
---
type: ceo_briefing_delivery
status: pending
priority: medium
approval_needed: true
approved: false
mcp_action: ["post_linkedin"]
---
```

- **Content:** Condensed version (Executive Summary + key metrics only)
- **Visibility:** CONNECTIONS (not PUBLIC — internal update)

### Option C: Both (two separate approval-gated tasks)

The skill can create both delivery tasks simultaneously. Each goes
through `Approval_Check_Skill` independently.

---

## Odoo MCP Integration

The skill queries Odoo for live accounting data using read-only calls
(no approval needed for `get_report`):

### Queries Made

| # | Action | Parameters | Purpose |
|---|--------|------------|---------|
| 1 | `get_report` | `report_type: "summary"` | Overall financial health |
| 2 | `get_report` | `report_type: "revenue_weekly"` | This week's revenue breakdown |
| 3 | `get_report` | `report_type: "expenses_weekly"` | This week's expense breakdown |

### Odoo Data Mapping

| Odoo Field | Briefing Section |
|------------|-----------------|
| Total revenue | Financial Overview → Revenue |
| Total expenses | Financial Overview → Expenses |
| Open invoices | Financial Overview → Odoo Snapshot |
| Overdue invoices | Bottlenecks (flagged as unpaid) |
| Recent payments | Financial Overview → Payments |

### If Odoo Is Unavailable

```markdown
> **Note:** Odoo ERP data unavailable this week (connection error).
> Financial figures below are based on bank task files only.
> Recommend verifying totals manually in Odoo.
```

---

## Integration with Existing Skills

| Skill | Relationship |
|-------|-------------|
| `Ralph_Wiggum_Loop_Skill` | **Wraps entire briefing** — ensures all 4 audit phases complete before finalizing |
| `Plan_Tasks_Skill` | Briefing references task pipeline data; briefing itself is not a plan but an audit |
| `Approval_Check_Skill` | Delivery task (email/LinkedIn) is gated — briefing compilation is NOT gated |
| `MCP_Action_Logger_Skill` | Logs Odoo `get_report` calls and final delivery action |
| `Social_Summary_Skill` | Briefing consumes the latest social summary as input for Section 3 |
| `LinkedIn_Post_Skill` | If LinkedIn delivery is chosen, the post follows LinkedIn_Post_Skill conventions |

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BRIEFING_DAY` | `monday` | Day of week for scheduled trigger |
| `BRIEFING_TIME` | `09:00` | Time of day (24h format) |
| `CEO_EMAIL` | from `.env` | Recipient for email delivery |
| `DELIVERY_METHOD` | `email` | `email`, `linkedin`, or `both` |
| `INCLUDE_ODOO` | `true` | Query Odoo for live accounting data |
| `INCLUDE_SOCIAL` | `true` | Include social engagement section |
| `LOOKBACK_DAYS` | `7` | Days of history to audit |
| `STALE_TASK_THRESHOLD` | `7` | Days before a task is flagged as stale |
| `MAX_RECOMMENDATIONS` | `5` | Max recommendations in Section 4 |

---

## Scheduler Integration

The skill is triggered by `scheduler.py` via a weekly job:

```python
# In scheduler.py — CEO Briefing (Gold Tier)
CEO_BRIEFING_DAY = "monday"
CEO_BRIEFING_TIME = "09:00"

schedule.every().monday.at("09:00").do(scheduled_ceo_briefing)
```

The scheduler:
1. Checks if a briefing already exists for this week
2. If not, creates a trigger task in `/Needs_Action/`
3. The trigger task is picked up by Ralph Loop or manual prompt
4. Ralph Loop executes the 4-phase audit
5. Briefing is compiled and delivery task created

---

## Duplicate Prevention

| Check | How |
|-------|-----|
| Same-week briefing | Look for `/Plans/CEO_Briefing_<YYYY-MM-DD>.md` where date falls in current week (Mon–Sun) |
| Duplicate trigger task | Check `/Needs_Action/` for `task_ceo_briefing_*.md` prefix |
| Already-delivered | Check `/Done/` for completed briefing delivery tasks |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Odoo query fails | Log warning, continue with bank-file-only financials |
| No bank tasks exist | Skip Section 1 financial details, note "No bank data" |
| No social summary exists | Skip Section 3, note "No social data this week" |
| No tasks in any folder | Generate minimal briefing: "All clear — no pending work" |
| Ralph Loop hits max iterations | Output partial briefing with "[INCOMPLETE]" flag |
| Delivery task approval rejected | Log rejection, briefing file still preserved in `/Plans/` |

---

## Notes

- The briefing **compilation** is read-only and does not require approval
- Only the **delivery** (email/LinkedIn) requires approval via Approval_Check_Skill
- Briefing files accumulate in `/Plans/` — archive old briefings as needed
- The CEO can request an ad-hoc briefing at any time ("Give me a CEO briefing")
- Combine with Odoo `get_report` for the most accurate financial picture
- If the Ralph Loop is not available, the skill can run as a single-pass
  audit — but multi-phase is preferred for thoroughness
- The briefing is the **highest-level summary** in the system — it
  consumes outputs from every other skill

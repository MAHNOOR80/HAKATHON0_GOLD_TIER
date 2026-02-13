# Gold Tier AI Employee (Autonomous Business Agent)

An autonomous AI Employee system that monitors files, Gmail, bank transactions, and social media, plans and executes tasks, posts to LinkedIn, sends emails, manages accounting via Odoo ERP, generates weekly CEO briefings, and enforces human approval for all sensitive actions. Built on Obsidian with Claude Code as the AI backbone.

## Overview

The Gold Tier AI Employee is the final evolution of the Bronze and Silver tiers. It adds financial perception (bank CSV monitoring + Odoo ERP), social media intelligence (LinkedIn + X engagement tracking with revenue-lead detection), a self-correcting reasoning loop (Ralph Wiggum Loop), automated CEO briefings, structured error recovery, and Gmail reply drafting. Everything runs through markdown files in an Obsidian vault.

## Architecture

```
                        +------------------------+
                        |     Claude Code (AI)   |
                        |   Reads/writes vault   |
                        +----------+-------------+
                                   |
              +--------------------+--------------------+
              |                    |                     |
     +--------+--------+  +-------+--------+  +---------+---------+
     | Agent Skills     |  | Ralph Wiggum   |  | MCP Server        |
     | (10 skills)      |  | Loop (auto-    |  | (external actions)|
     +--------+---------+  | reasoning)     |  +---------+---------+
              |            +-------+--------+            |
              |                    |            +--------+---------+
   +----------+----------+        |            |    |    |    |    |
   |    |    |    |    |  |        |          Email  LI  Odoo Config
Planning  Approval  Social        |
          Gate      Summary       |
           |                      |
   +-------+--------+    +-------+--------+
   | Pending_Approval|    | 4 Watchers     |
   | (human reviews) |    | File/Gmail/    |
   +----------------+    | Bank/Social    |
                          +----------------+
```

## Tier Comparison

| Feature | Bronze | Silver | Gold |
|---------|--------|--------|------|
| Obsidian vault + Dashboard | Yes | Yes | Yes |
| File watcher | Yes | Yes | Yes |
| Gmail watcher | - | Yes | Yes |
| Bank transaction watcher | - | - | Yes |
| Social media watcher | - | - | Yes |
| MCP server (email + LinkedIn) | - | Yes | Yes |
| Odoo ERP accounting | - | - | Yes |
| Human-in-the-loop approval | - | Yes | Yes |
| Task planning skill | - | Yes | Yes |
| Scheduler (hourly + daily) | - | Yes | Yes |
| Ralph Wiggum Loop (auto-reasoning) | - | - | Yes |
| CEO weekly briefing | - | - | Yes |
| Revenue-lead detection | - | - | Yes |
| Error recovery skill | - | - | Yes |
| Gmail reply drafting | - | - | Yes |
| Agent Skills count | 2 | 5 | 10 |

## Folder Structure

```
Gold/
+-- Inbox/                  # Drop files here for processing
+-- Bank_Drops/             # Drop CSV bank statements here
+-- Needs_Action/           # Tasks awaiting AI processing
+-- Pending_Approval/       # Tasks gated for human approval
+-- Done/                   # Completed tasks archive
+-- Plans/                  # Execution plans, social summaries, CEO briefings
+-- Logs/                   # System logs and error logs
+-- Agent_Skills/           # All AI behavior definitions (10 skills)
|   +-- Plan_Tasks_Skill.md
|   +-- Approval_Check_Skill.md
|   +-- Approval_Handler_Skill.md
|   +-- LinkedIn_Post_Skill.md
|   +-- MCP_Action_Logger_Skill.md
|   +-- Ralph_Wiggum_Loop_Skill.md
|   +-- Social_Summary_Skill.md
|   +-- CEO_Briefing_Skill.md
|   +-- Error_Recovery_Skill.md
|   +-- Gmail_Reply_And_Send_Skill.md
+-- mcp_server/             # Node.js MCP server
|   +-- mcp_server.js       # Server with 4 tools
|   +-- package.json
|   +-- .env.example
+-- file_watcher.py         # Watcher 1: file system monitor
+-- gmail_watcher.py        # Watcher 2: Gmail IMAP monitor
+-- bank_watcher.py         # Watcher 3: bank CSV monitor
+-- social_watcher.py       # Watcher 4: social media monitor
+-- scheduler.py            # Hourly tasks + daily bank audit + daily social + weekly CEO
+-- ralph_wrapper.py        # Ralph Wiggum Loop CLI wrapper
+-- log_manager.py          # Centralized log rotation utility
+-- Dashboard.md            # Central status hub
+-- Company_Handbook.md     # Operating rules
+-- .mcp.json               # MCP server configuration
```

## Gold Tier Requirements - All Met

| # | Requirement | Implementation | Status |
|---|------------|----------------|--------|
| 1 | Bronze + Silver foundations | All Silver features inherited (vault, watchers, MCP, approval, scheduler) | Done |
| 2 | Financial Perception | `bank_watcher.py` monitors `/Bank_Drops/` for CSV transactions, flags anomalies > $500 | Done |
| 3 | Social Perception | `social_watcher.py` polls LinkedIn + X APIs, detects revenue leads from comments | Done |
| 4 | ERP Integration (Odoo) | `odoo_accounting` MCP tool: create invoices, log payments, get financial reports | Done |
| 5 | Autonomous Reasoning Loop | `Ralph_Wiggum_Loop_Skill` + `ralph_wrapper.py` — Reason-Act-Check-Reprompt until done | Done |
| 6 | CEO Briefing | `CEO_Briefing_Skill` — weekly 4-phase audit (financial, project, social, compile) | Done |
| 7 | Error Recovery | `Error_Recovery_Skill` — classify, retry with backoff, escalate to human | Done |
| 8 | Gmail Reply Drafting | `Gmail_Reply_And_Send_Skill` — draft replies, gate through approval before sending | Done |
| 9 | 4+ Watchers | file_watcher + gmail_watcher + bank_watcher + social_watcher | Done |
| 10 | 10 Agent Skills | All AI behavior codified in 10 markdown skill files | Done |

## How It Works

### Complete Workflow

```
1. PERCEPTION: 4 Watchers detect new input
   file_watcher.py   -->  new file in /Inbox/       -->  task in /Needs_Action/
   gmail_watcher.py  -->  new email in Gmail         -->  task in /Needs_Action/
   bank_watcher.py   -->  new CSV in /Bank_Drops/    -->  task in /Needs_Action/
   social_watcher.py -->  LinkedIn/X engagement      -->  summary in /Plans/

2. PLANNING: AI creates execution plans
   Plan_Tasks_Skill  -->  analyzes /Needs_Action/    -->  Plan.md in /Plans/

3. REASONING LOOP: Ralph Wiggum Loop wraps multi-step tasks
   Ralph_Wiggum_Loop  -->  Reason -> Act -> Check -> Re-prompt
     --> Continues until task is truly complete (RALPH_DONE)
     --> Prevents premature completion on complex tasks

4. APPROVAL CHECK: Gate before sensitive actions
   Approval_Check_Skill  -->  send_email? post_linkedin? payment?
     --> Yes: move to /Pending_Approval/, update Dashboard, STOP
     --> No:  proceed to execution

5. HUMAN REVIEW: User approves or rejects
   /Pending_Approval/task.md  -->  user sets approved: true (or status: rejected)

6. EXECUTION: Approved actions are performed
   Approval_Handler_Skill  -->  calls MCP tool  -->  move to /Done/
   MCP_Action_Logger_Skill -->  logs result to Dashboard + System_Log

7. ERROR RECOVERY: When things go wrong
   Error_Recovery_Skill  -->  classify (transient/permanent)
     --> Transient: retry 3x with exponential backoff
     --> Permanent: escalate to human with task in /Needs_Action/

8. SCHEDULING: Automated periodic jobs
   scheduler.py:
     --> Every 60 min: check /Needs_Action/ and create planning tasks
     --> Every 24 hours: daily bank audit
     --> Every 24 hours: daily social media summary
     --> Every Monday 09:00: weekly CEO briefing
```

### Task File Format (Gold Tier)

```yaml
---
type: email_response | linkedin_post | file_review | bank_transaction | social_lead_followup | ceo_briefing | error_recovery
status: pending | in_progress | pending_approval | completed | rejected
priority: high | medium | low
created_at: 2026-02-05 22:00:00
completed_at: 2026-02-05 23:00:00
related_files: ["Bank_Drops/statement.csv"]
approval_needed: true | false
approved: true | false
mcp_action: ["send_email", "post_linkedin", "odoo_accounting"]
source: file_watcher | gmail_watcher | bank_watcher | social_watcher | scheduler
---
```

## Components

### Watchers (4 Perception Channels)

#### 1. file_watcher.py - File System Monitor

Monitors `/Inbox/` for new files and auto-creates task files.

```bash
python file_watcher.py
```

- Checks every 5 seconds
- Creates tasks with YAML frontmatter in `/Needs_Action/`
- Duplicate prevention via processed file tracking
- Error logging to `Logs/watcher_errors.log`

#### 2. gmail_watcher.py - Gmail IMAP Monitor

Monitors a Gmail inbox for new emails and auto-creates task files.

```bash
# Demo mode (no credentials needed):
python gmail_watcher.py

# Live mode (with credentials):
set GMAIL_USER=your_email@gmail.com
set GMAIL_APP_PASSWORD=your_app_password
python gmail_watcher.py
```

- Checks every 60 seconds via IMAP
- Parses sender, subject, body from emails
- Smart approval detection (flags emails requesting replies)
- Demo mode simulates 3 incoming emails
- Error logging to `Logs/gmail_watcher_errors.log`

**Gmail Setup (Live Mode):**
1. Enable IMAP in Gmail: Settings > See all settings > Forwarding and POP/IMAP
2. Enable 2-Step Verification on your Google Account
3. Generate App Password: Google Account > Security > App Passwords
4. Set environment variables: `GMAIL_USER` and `GMAIL_APP_PASSWORD`

#### 3. bank_watcher.py - Bank Transaction Monitor (Gold)

Monitors `/Bank_Drops/` for CSV bank statements, parses transactions, and flags anomalies.

```bash
# Demo mode (generates sample CSV with 10 transactions):
python bank_watcher.py

# Live mode (drop real CSV files into /Bank_Drops/):
python bank_watcher.py
```

- Checks every 10 seconds for new CSV files
- Parses transactions using pandas (falls back to stdlib csv if pandas not installed)
- Auto-categorizes as revenue (positive) or expense (negative)
- Flags anomalies: transactions exceeding $500 (absolute value)
- Anomaly tasks are flagged `approval_needed: true` for human review
- Creates one task per CSV file with full transaction detail table
- Demo mode generates a sample CSV with 10 transactions (4 normal, 6 anomalies)
- Error logging to `Logs/bank_watcher_errors.log`

**Expected CSV Format:**
```csv
date,description,amount
2026-02-01,Client payment - Acme Corp,1500.00
2026-02-01,AWS hosting fee,-249.99
```

#### 4. social_watcher.py - Social Media Monitor (Gold)

Polls LinkedIn and X (Twitter) for post engagement and detects revenue leads in comments.

```bash
# Demo mode (generates sample engagement data):
python social_watcher.py

# Live mode (with API credentials):
set LINKEDIN_ACCESS_TOKEN=your_token
set LINKEDIN_PERSON_URN=urn:li:person:your_id
set X_BEARER_TOKEN=your_bearer_token
python social_watcher.py
```

- Runs daily (every 24 hours)
- Scans comments for revenue-signal keywords (consulting, hire, budget, pricing, proposal, etc.)
- Classifies leads: Hot (2+ signals, reply within 24h), Warm (1 signal), Informational
- Generates summary report in `/Plans/Social_Summary_<date>.md`
- Auto-creates follow-up tasks for hot leads in `/Needs_Action/`
- Updates Dashboard with summary reference
- Demo mode provides realistic sample data (8 posts, 22 comments, 3+ leads)
- Error logging to `Logs/social_watcher_errors.log`

### MCP Server (External Actions)

Node.js server exposing 4 tools via Model Context Protocol:

| Tool | Description | Approval Required |
|------|-------------|-------------------|
| `send_email` | Send emails via SMTP | Yes |
| `post_linkedin` | Publish posts to LinkedIn | Yes |
| `check_email_config` | Test SMTP connection | No |
| `odoo_accounting` | Create invoices, log payments, get reports via Odoo ERP | Invoices/payments: Yes. Reports: No |

**Setup:**
```bash
cd mcp_server
npm install
```

**Configuration** (copy `.env.example` to `.env`):
```env
# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=your_email@gmail.com

# LinkedIn
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_PERSON_URN=urn:li:person:your_id

# Odoo ERP (Gold Tier)
ODOO_URL=https://your-instance.odoo.com
ODOO_DB=your_database
ODOO_USERNAME=your_username
ODOO_API_KEY=your_api_key
```

Without credentials, all tools run in **test/demo mode** (emails go to Ethereal, LinkedIn posts are logged, Odoo returns sample data).

**Odoo ERP Setup:**
1. Get a free Odoo instance at https://www.odoo.com/trial
2. Enable the Accounting app
3. Generate an API key: Settings > Users > API Keys
4. Set `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, and `ODOO_API_KEY`

**Odoo MCP Actions:**
| Action | Description | Example |
|--------|-------------|---------|
| `create_invoice` | Create a customer invoice (draft) | `action: create_invoice, customer: "Acme Corp", amount: 5000, description: "Consulting"` |
| `log_payment` | Record incoming/outgoing payment | `action: log_payment, customer: "Acme Corp", amount: 5000, payment_type: "inbound"` |
| `get_report` | Retrieve financial summary (read-only) | `action: get_report, report_type: "summary"` |

### Ralph Wiggum Loop (Autonomous Reasoning)

A self-correcting reasoning loop that prevents Claude from prematurely declaring a task complete. Wraps multi-step tasks in a **Reason -> Act -> Check -> Re-prompt** cycle.

```bash
# Run via CLI wrapper:
python ralph_wrapper.py --task "Build a CSV-to-JSON converter with tests"
python ralph_wrapper.py --task "Process all pending tasks" --max-loops 5
python ralph_wrapper.py --task-file Needs_Action/task_example.md
```

**How it works:**
1. **REASON** - Read current state, identify what remains
2. **ACT** - Execute the next concrete step
3. **CHECK** - Run completion checks (task in `/Done/`? YAML status completed? `RALPH_DONE` marker? Plan steps finished? `/Needs_Action/` empty?)
4. **RE-PROMPT** - If not done, feed updated context back and repeat

**Completion checks:**
- Task file moved to `/Done/`
- YAML `status: completed`
- Explicit `RALPH_DONE` marker in output
- All plan steps finished
- `/Needs_Action/` empty (for batch tasks)
- Max iterations reached (default: 10, safety valve)
- Approval gate waiting (pauses, resumes after human decision)

**Stuck-loop detection:** If the same output repeats 3 times, the loop force-exits and asks for guidance.

### CEO Weekly Briefing

Automated 4-phase executive summary generated every Monday at 09:00.

**Audit Phases (via Ralph Wiggum Loop):**

| Phase | What It Does |
|-------|-------------|
| 1. Financial Audit | Read bank tasks, query Odoo `get_report` (summary + weekly revenue/expenses) |
| 2. Project Audit | Scan `/Needs_Action/`, `/Pending_Approval/`, `/Done/` for task pipeline health |
| 3. Social Audit | Read latest `Social_Summary` for engagement metrics and revenue leads |
| 4. Compile Briefing | Generate `CEO_Briefing_<date>.md`, create delivery task (approval-gated) |

**Briefing includes:**
- Executive summary paragraph
- Revenue vs expenses table with week-over-week changes
- Odoo accounting snapshot (open invoices, overdue, payments)
- Flagged anomalies
- Task pipeline (completed, in-progress, pending, blocked)
- Bottlenecks and stale tasks (>7 days)
- Social engagement metrics and lead pipeline
- Top 5 recommendations for the week
- CEO decisions needed (with deadlines and impact)
- System health status for all components

**Delivery:** The briefing can be sent via email, posted to LinkedIn, or both. Each delivery method is gated through `Approval_Check_Skill`.

### Scheduler

Runs periodic checks for task planning, bank audits, social summaries, and CEO briefings.

```bash
pip install schedule
python scheduler.py
```

| Job | Frequency | What It Does |
|-----|-----------|-------------|
| Task planning | Every 60 minutes | Creates planning tasks when pending work exists |
| Bank audit | Every 24 hours | Creates audit task for unreviewed bank transactions |
| Social summary | Every 24 hours | Generates daily social engagement report |
| CEO briefing | Weekly (Monday 09:00) | Triggers 4-phase executive briefing |

All jobs run immediately on startup, then on schedule. Duplicate prevention ensures no redundant tasks.

### Log Manager

Centralized logging module used by all watchers and scheduler.

```bash
python log_manager.py
```

- Auto-rotates log files when they exceed 1 MB
- Captures full Python tracebacks via `sys.exc_info()`
- 6 log files monitored: watcher_errors, gmail_watcher_errors, bank_watcher_errors, social_watcher_errors, scheduler_errors, System_Log
- System_Log.md uses table format for structured audit trail

## Agent Skills

All AI behavior is defined in `/Agent_Skills/` markdown files:

| Skill | Purpose | Tier |
|-------|---------|------|
| **Plan_Tasks_Skill.md** | Analyzes pending tasks, generates prioritized execution plans in `/Plans/` | Silver |
| **Approval_Check_Skill.md** | Mandatory gate before sensitive MCP actions. Moves tasks to `/Pending_Approval/` | Silver |
| **Approval_Handler_Skill.md** | Polls `/Pending_Approval/` for human decisions, executes approved tasks | Silver |
| **LinkedIn_Post_Skill.md** | Generates professional LinkedIn posts with 5 content templates | Silver |
| **MCP_Action_Logger_Skill.md** | Logs all MCP tool results to Dashboard and System_Log | Silver |
| **Ralph_Wiggum_Loop_Skill.md** | Self-correcting Reason-Act-Check-Reprompt loop for multi-step tasks | Gold |
| **Social_Summary_Skill.md** | Daily social engagement report with revenue-lead detection | Gold |
| **CEO_Briefing_Skill.md** | Weekly 4-phase executive briefing (financial, project, social, compile) | Gold |
| **Error_Recovery_Skill.md** | Classify-retry-escalate pipeline for all errors across the system | Gold |
| **Gmail_Reply_And_Send_Skill.md** | Draft email replies, compose new emails, batch-process Gmail tasks | Gold |

### Approval Workflow (Human-in-the-Loop)

```
Task has sensitive action (send_email, post_linkedin, odoo_accounting, etc.)
  |
  v
Approval_Check_Skill gates it
  --> YAML: status: pending_approval, approved: false
  --> File moved to /Pending_Approval/
  --> Dashboard updated with link
  --> Execution STOPPED
  |
  v
Human opens file in Obsidian and edits YAML:
  --> To approve: set approved: true
  --> To reject:  set status: rejected
  |
  v
Approval_Handler_Skill detects the change:
  --> Approved: executes MCP action, moves to /Done/
  --> Rejected: archives to /Done/, no action taken
```

**Actions that require approval:**
`send_email`, `post_linkedin`, `create_invoice`, `log_payment`, `make_payment`, `delete_data`, `modify_config`

### Error Recovery

Structured error handling across the entire system:

```
Error occurs → Classify → Retry or Escalate

Transient errors (network timeout, rate limit, connection reset):
  → Retry 3x with exponential backoff (5s, 15s, 45s)
  → If retries exhausted → Escalate

Permanent errors (auth failure, invalid data, missing config):
  → Skip retry → Escalate immediately

Escalation:
  → Create error task in /Needs_Action/ (approval_needed: true)
  → Update Dashboard with error status
  → Log full traceback to System_Log
```

## AI Agent Commands

| Command | What it does |
|---------|-------------|
| "Process tasks" | Reads and executes all pending tasks in `/Needs_Action/` |
| "Make a plan for tasks" | Generates a Plan.md without executing anything |
| "Create a LinkedIn post about X" | Generates draft, gates through approval |
| "Send email to X" | Creates email task, gates through approval |
| "Reply to email from X" | Drafts reply, saves to `/Plans/`, gates through approval |
| "Check approvals" | Scans `/Pending_Approval/` and processes approved/rejected tasks |
| "Use Ralph Wiggum Loop on this task" | Wraps task in auto-reasoning loop until done |
| "CEO briefing" | Triggers 4-phase audit and generates executive summary |
| "Social summary" | Generates engagement report with lead detection |
| "Create invoice for X" | Creates Odoo invoice, gates through approval |
| "How's the business doing?" | Triggers CEO briefing (ad-hoc) |

## Dashboard

`Dashboard.md` is the central status hub with these sections:

- **Pending Tasks** - Work waiting to be processed
- **Pending Approval** - Tasks gated for human review (with wiki-links)
- **Completed Tasks** - History of all completed work
- **Recent Plans** - Links to generated execution plans, social summaries, CEO briefings
- **Recent Actions** - Last 10 MCP tool calls with results
- **System Notes** - Current status, active watchers, available skills

## Operating Rules

From `Company_Handbook.md`:

1. **Always Log Important Actions** - All actions recorded in System_Log
2. **Never Take Destructive Actions Without Confirmation** - Approval required
3. **Move Completed Tasks to Done** - Keep workspace organized
4. **Keep Task Files Structured** - Consistent YAML frontmatter
5. **If Unsure, Ask for Clarification** - No guessing

## Quick Start

### Requirements

- Python 3.x
- Node.js 18+
- Claude Code
- Optional: Obsidian (for viewing the vault)

### Python Dependencies

```bash
pip install schedule pandas requests
```

(Only `schedule` is required. `pandas` and `requests` are optional - the system degrades gracefully without them.)

### Installation

```bash
# 1. Navigate to the project
cd Gold

# 2. Install MCP server dependencies
cd mcp_server && npm install && cd ..

# 3. Install Python dependencies
pip install schedule pandas requests

# 4. Start the file watcher (Terminal 1)
python file_watcher.py

# 5. Start the Gmail watcher (Terminal 2)
python gmail_watcher.py

# 6. Start the bank watcher (Terminal 3)
python bank_watcher.py

# 7. Start the social watcher (Terminal 4)
python social_watcher.py

# 8. Start the scheduler (Terminal 5)
python scheduler.py

# 9. Open the folder in Claude Code and start working
```

### Testing Without Credentials

Everything works in **demo/test mode** out of the box:
- **File watcher**: Monitors `/Inbox/` for any dropped files
- **Gmail watcher**: Simulates 3 incoming emails
- **Bank watcher**: Generates a sample CSV with 10 transactions (4 normal, 6 anomalies)
- **Social watcher**: Generates realistic engagement data (8 posts, 22 comments, revenue leads)
- **MCP send_email**: Routes through Ethereal test SMTP
- **MCP post_linkedin**: Logs post content, returns simulated post ID
- **MCP odoo_accounting**: Returns sample financial data
- **Approval workflow**: Fully functional with local files
- **Ralph Wiggum Loop**: `python ralph_wrapper.py --task "Your task here"`
- **CEO Briefing**: `"CEO briefing"` in Claude Code triggers full audit

### Running the Ralph Wiggum Loop

```bash
# Simple task
python ralph_wrapper.py --task "Build a CSV parser and write tests"

# With custom max iterations
python ralph_wrapper.py --task "Process all pending tasks" --max-loops 5

# From a task file
python ralph_wrapper.py --task-file Needs_Action/task_example.md
```

### Triggering a CEO Briefing

**Automatic:** The scheduler triggers it every Monday at 09:00.

**Manual:** In Claude Code, say:
- "CEO briefing"
- "Monday briefing"
- "How's the business doing?"
- "Weekly report"

The briefing output lands in `/Plans/CEO_Briefing_<date>.md`.

## License

This project was created for the Hackathon 0 AI Employee challenge - Gold Tier.

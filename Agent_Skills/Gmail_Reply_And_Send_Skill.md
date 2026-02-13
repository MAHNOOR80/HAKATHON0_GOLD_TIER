# Gmail Reply and Send Skill

## Description

This skill generates **intelligent email reply drafts** for Gmail tasks and composes **new outbound emails** on demand. Every email — reply or new — is routed through the **Approval Check gate** (`approval_needed: true`) before sending. The human always reviews, edits, and approves the draft first. **Nothing is ever sent without explicit human approval.**

This skill handles the full lifecycle: trigger detection, email task reading, draft generation, approval gating, MCP execution, and Dashboard visibility.

## Position in Reasoning Loop

```
[Trigger detected]
    --> Gmail_Reply_And_Send_Skill reads source task or user instruction
    --> Generates draft in /Plans/Gmail_Reply_Draft_<id>.md
    --> Creates send task in /Needs_Action/ with draft + approval gate
    --> Approval_Check_Skill intercepts (send_email requires approval)
    --> Task moved to /Pending_Approval/
    --> Dashboard updated: "Email Draft Ready — Pending Approval"
    --> STOP — human reviews draft
    --> Human approves (approved: true) or rejects (status: rejected)
    --> Approval_Handler_Skill calls send_email(to, subject, body) via MCP
    --> MCP_Action_Logger_Skill logs result
    --> Original email task moved to /Done/
```

---

## Trigger Conditions

Activate this skill when any of the following occur:

### Reply to Existing Email Task
- User says: **"Reply to Gmail task [filename]"**
- User says: **"Reply to the email from [sender]"**
- User says: **"Draft a reply for [subject]"**
- User says: **"Process Gmail task [filename]"**

### Process All Gmail Tasks
- User says: **"Process all Gmail tasks"**
- User says: **"Handle all pending emails"**
- User says: **"Reply to all emails in Needs_Action"**
- Iterates over all `type: email_response` tasks in `/Needs_Action/`

### Send New Email (Not a Reply)
- User says: **"Send email to [person/address] about [topic]"**
- User says: **"Email [address] with [content/instructions]"**
- User says: **"Compose a new email to [address]"**

### Ralph Wiggum Loop Integration
- When Ralph Loop encounters an email task during `Plan_Tasks_Skill` execution
- Loop pauses at approval gate, resumes after human decision

---

## Inputs

### For Replies

| Input | Source | Required |
|-------|--------|----------|
| Email task file | `/Needs_Action/task_email_*.md` | Yes |
| Original sender (`from`) | YAML frontmatter of task file | Yes (auto-extracted) |
| Original subject | YAML frontmatter of task file | Yes (auto-extracted) |
| Email body/snippet | Task file body section | Yes (auto-extracted) |
| Message ID | YAML frontmatter of task file | Yes (for threading) |
| Reply instructions | User prompt (optional — AI generates if not given) | No |

### For New Emails

| Input | Source | Required |
|-------|--------|----------|
| Recipient address | User prompt | Yes |
| Subject | User prompt or AI-generated | Yes |
| Topic/instructions | User prompt | Yes |
| Tone | Default: professional, concise | No |

---

## Steps

### Step 1: Identify Trigger Type

```
IF user says "Reply to Gmail task [filename]" or "Reply to the email from [sender]":
    MODE = REPLY
    Load the specified task file from /Needs_Action/

ELSE IF user says "Process all Gmail tasks":
    MODE = BATCH_REPLY
    List all task_email_*.md files in /Needs_Action/
    Process each one sequentially (each gets its own draft)

ELSE IF user says "Send email to [address] about [topic]":
    MODE = NEW_SEND
    No source task — compose from scratch based on user instructions
```

### Step 2: Read Source Email (REPLY and BATCH_REPLY modes)

Parse the email task `.md` file from `/Needs_Action/`:

```
Extract from YAML frontmatter:
    - from: sender email address
    - subject: original subject line
    - message_id: for threading reference
    - received_at: when the email arrived
    - snippet: short preview

Extract from body:
    - Full email body text (## Email Body section)
    - Suggested actions (## Suggested Actions section)
```

### Step 3: Generate Email Draft

#### For Replies (MODE = REPLY or BATCH_REPLY)

Compose a professional reply following these rules:

**Tone (from Company_Handbook):**
- Professional, polite, and concise
- Helpful and action-oriented
- No jargon unless the original email uses it
- Match the formality level of the incoming email

**Structure:**
```
Hi [First Name],

[Acknowledge their email — 1 sentence]

[Address their request/question — 1-3 sentences]

[Next steps or call to action if applicable — 1-2 sentences]

Best regards,
[Sign-off — leave as placeholder for human to customize]
```

**Rules:**
- Subject: `Re: [original subject]`
- To: extract email address from `from` field
- Keep replies under 150 words unless the topic demands more
- If the email is a newsletter/digest: suggest archiving instead of replying
- If the email requests a meeting: propose availability (human will fill in times)
- If the email is a job application/resume: acknowledge receipt professionally
- Never fabricate commitments, pricing, or deadlines
- Never share confidential information

#### For New Emails (MODE = NEW_SEND)

Compose based on user instructions:

**Structure:**
```
Hi [Name if known],

[Body as instructed by user — professional tone]

[Closing]

Best regards,
[Sign-off placeholder]
```

**Rules:**
- Subject: as specified by user, or AI-generated from topic
- Keep concise unless user requests otherwise
- Professional tone by default

### Step 4: Create Reply Draft File

Save the draft to `/Plans/` for visibility and record-keeping:

**Filename:** `Gmail_Reply_Draft_<sanitized_subject>_<timestamp>.md`

```yaml
---
type: email_reply_draft
status: draft
created_at: <timestamp>
reply_to_task: "Needs_Action/task_email_<original>.md"
to: "<recipient email>"
subject: "Re: <original subject>"
message_id_ref: "<original message-id for threading>"
draft_mode: reply | new_send
---

# Email Draft: Re: <Original Subject>

## Recipient
- **To:** <email address>
- **Subject:** Re: <original subject>

## Draft Body

<generated reply text>

## Original Email Context

> From: <sender>
> Subject: <subject>
> Received: <date>
>
> <snippet or first 500 chars of body>

## Notes
- This draft was auto-generated by Gmail_Reply_And_Send_Skill
- Review and edit before approving
- The send task is in /Pending_Approval/ (or /Needs_Action/ before gate)
```

### Step 5: Create Send Task File

Create an actionable task in `/Needs_Action/` that the Approval Check gate will intercept:

**Filename:** `task_email_reply_<sanitized_subject>.md`

```yaml
---
type: email_send
status: pending
priority: medium
created_at: <timestamp>
to: "<recipient email>"
subject: "Re: <original subject>"
reply_to_task: "Needs_Action/task_email_<original>.md"
message_id_ref: "<original message-id>"
related_files: ["Plans/Gmail_Reply_Draft_<id>.md"]
approval_needed: true
approved: false
mcp_action: ["send_email"]
source: gmail_reply_skill
---

# Send Email: Re: <Original Subject>

## Email Details

| Field | Value |
|-------|-------|
| **To** | <recipient email> |
| **Subject** | Re: <original subject> |
| **Reply To Task** | [[Needs_Action/task_email_<original>.md]] |
| **Draft** | [[Plans/Gmail_Reply_Draft_<id>.md]] |

## Email Body (This Will Be Sent)

<the full email body text that will be sent via MCP>

## Approval Notes

- **Review the email body above carefully before approving**
- Edit the "Email Body" section directly if changes are needed
- Set `approved: true` in the YAML to send
- Set `status: rejected` to discard without sending
- The original email task will be moved to /Done/ after send

## Original Context

> From: <sender>
> Subject: <subject>
> Snippet: <snippet>
```

### Step 6: Approval Gate (Automatic)

The `Approval_Check_Skill` will intercept the send task because `mcp_action` contains `send_email`:

1. YAML updated: `status: pending_approval`, `approved: false`
2. Task moved to `/Pending_Approval/task_email_reply_<subject>.md`
3. Dashboard updated with draft preview

**The email is NOT sent at this point.**

### Step 7: Update Dashboard.md

Add the draft to the **Pending Approval** section and **Recent Actions**:

**Pending Approval table:**
```markdown
| Email Reply: Re: <Subject> | send_email | <timestamp> | Draft Ready — Awaiting Approval | [[Pending_Approval/task_email_reply_<subject>.md]] |
```

**Recent Actions table:**
```markdown
| <timestamp> | Email Draft | Reply drafted for <sender> — Subject: "Re: <Subject>" — Pending Approval | [[Plans/Gmail_Reply_Draft_<id>.md]] |
```

### Step 8: Log the Draft

Add entry to `System_Log.md`:
```
| <timestamp> | Email Draft | Generated reply draft for <to> — Subject: "Re: <Subject>" — moved to Pending_Approval |
```

### Step 9: STOP — Await Human Decision

The skill's work is done. The human will:
1. Open the task in `/Pending_Approval/task_email_reply_<subject>.md`
2. Read the generated email body
3. **Edit the email body directly** if changes are needed
4. Set `approved: true` to send, or `status: rejected` to discard

### Step 10: Execution (Handled by Approval_Handler_Skill)

When approved, the `Approval_Handler_Skill`:
1. Reads the email body from the `## Email Body (This Will Be Sent)` section
2. Reads `to` and `subject` from YAML frontmatter
3. Calls MCP: `mcp__silver-email__send_email(to, subject, body)`
4. On success:
   - Updates send task YAML: `status: completed`, `execution_result: "Success"`
   - Moves send task to `/Done/`
   - Moves the **original** email task (from `reply_to_task`) to `/Done/`
   - Logs via `MCP_Action_Logger_Skill`
5. On failure:
   - Keeps task in `/Pending_Approval/`
   - Sets `status: execution_failed`, `execution_result: "<error>"`
   - Logs failure to System_Log

### Step 11: Log Completion

Add entry to `System_Log.md`:
```
| <timestamp> | Email Sent | Sent email to <to> — Subject: "<subject>" — approved and delivered |
```

---

## Reply Templates

### Template 1: Acknowledge and Respond (General)

```
Hi [First Name],

Thank you for your email. [Acknowledge specific topic in 1 sentence.]

[Direct response to their request/question — 2-3 sentences.]

[Next step: "I'll follow up by [date]" or "Let me know if you need anything else."]

Best regards
```

### Template 2: Meeting/Call Request

```
Hi [First Name],

Thanks for reaching out — I'd be happy to discuss [topic].

I have availability [suggest general timeframe — human will fill in specifics]. Would any of those times work for you?

Looking forward to connecting.

Best regards
```

### Template 3: Resume/Job Application Acknowledgment

```
Hi [First Name],

Thank you for sending your resume. I've received it and will review it shortly.

I'll be in touch if there's a good fit for any current or upcoming opportunities.

Best regards
```

### Template 4: Information Request

```
Hi [First Name],

Thanks for your interest. Here's what I can share:

[Relevant information — 2-4 sentences based on context.]

Let me know if you have any other questions.

Best regards
```

### Template 5: Newsletter/Digest (No Reply — Archive)

```
[No reply generated]

Action: Archive this email — it's informational/newsletter content.
Move original task directly to /Done/ with note: "Newsletter archived — no reply needed"
```

---

## MCP Action Specification

```
Tool:       send_email (via mcp__silver-email__send_email)
Parameters: {
    to: "<recipient email address>",
    subject: "<subject line>",
    body: "<full email body text>"
}
Gate:       approval_needed: true (ALWAYS — no exceptions)
```

**The `send_email` MCP tool is already implemented in `mcp_server/mcp_server.js` using SMTP (nodemailer).** Ensure SMTP credentials are configured in `mcp_server/.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=drmallory900@gmail.com
SMTP_PASS=<app password>
SMTP_FROM=drmallory900@gmail.com
```

---

## Batch Processing (Process All Gmail Tasks)

When triggered with "Process all Gmail tasks":

1. Scan `/Needs_Action/` for all files matching `task_email_*.md`
2. For each email task:
   a. Read the task file and classify:
      - **Needs reply** → Generate draft, create send task, gate for approval
      - **Newsletter/digest** → Archive directly to `/Done/` (no reply)
      - **Informational** → Archive with note
   b. Create individual draft and send task for each reply-worthy email
3. Update Dashboard with all drafts created
4. Log batch processing to System_Log

**Classification rules:**
| Email Content | Classification | Action |
|---------------|---------------|--------|
| Contains "reply", "respond", "feedback", "review" | Needs Reply | Generate draft |
| Contains "schedule", "call", "meeting", "discuss" | Needs Reply (meeting) | Generate meeting reply draft |
| Contains "newsletter", "digest", "weekly", "update" | Informational | Archive to /Done/ |
| Contains "resume", "job", "application", "CV" | Job Application | Generate acknowledgment draft |
| Contains "invoice", "payment", "billing" | Financial | Flag high priority + generate draft |
| None of the above | Unknown | Generate generic acknowledgment draft |

---

## Integration with Ralph Wiggum Loop

When wrapped in a Ralph Loop (`Use Ralph_Wiggum_Loop_Skill on this task`):

```
Iteration 1 (REASON): Scan /Needs_Action for email tasks. Found 3.
    (ACT): Process email 1 — generate draft, create send task.
    (CHECK): 2 emails remaining → continue.

Iteration 2 (REASON): Email 1 draft created, gated for approval. Process email 2.
    (ACT): Email 2 is a newsletter → archive to /Done/.
    (CHECK): 1 email remaining → continue.

Iteration 3 (REASON): Process email 3 — generate draft, create send task.
    (ACT): Draft created, gated for approval.
    (CHECK): All emails processed. 2 drafts pending approval → PAUSE.

[Ralph Loop PAUSES — waits for human approval decisions]

Iteration 4 (REASON): Human approved email 1, rejected email 3.
    (ACT): Approval_Handler sends email 1. Email 3 archived as rejected.
    (CHECK): All work done → RALPH_DONE.
```

---

## Integration with Other Skills

| Skill | Relationship |
|-------|-------------|
| `Approval_Check_Skill` | **Always gates** this skill's output — `send_email` is in the sensitive actions list |
| `Approval_Handler_Skill` | Executes `send_email` after human approves the draft |
| `MCP_Action_Logger_Skill` | Logs the MCP result after email is sent |
| `Plan_Tasks_Skill` | Can include email replies in execution plans (Batch 2: Needs Approval) |
| `Ralph_Wiggum_Loop_Skill` | Wraps multi-email processing; pauses at approval gate |
| `Error_Recovery_Skill` | Handles SMTP failures with retry logic |

---

## Example Workflows

### Example 1: Reply to a Specific Gmail Task

**User prompt:**
```
Reply to Gmail task "task_email_Resume for job.md"
```

**Skill reads:**
```
From: MAHNOOR <mahno9248@gmail.com>
Subject: Resume for job
Body: I have attached my resume for your reference job
```

**Skill generates draft** (`/Plans/Gmail_Reply_Draft_Resume_for_job_2026-02-12.md`):
```
Hi Mahnoor,

Thank you for sending your resume. I've received it and will review it shortly.

I'll be in touch if there's a good fit for any current or upcoming opportunities.

Best regards
```

**Skill creates send task** (`/Needs_Action/task_email_reply_Resume_for_job.md`):
```yaml
---
type: email_send
status: pending
priority: medium
to: "mahno9248@gmail.com"
subject: "Re: Resume for job"
approval_needed: true
approved: false
mcp_action: ["send_email"]
---
```

**Approval Check gates it** → moved to `/Pending_Approval/`

**Human reviews, edits if needed, sets `approved: true`**

**Approval Handler sends:** `send_email(to: "mahno9248@gmail.com", subject: "Re: Resume for job", body: "...")`

**Result:** Email sent, both tasks moved to `/Done/`, logged.

---

### Example 2: Send New Email to Anyone

**User prompt:**
```
Send email to john@acmecorp.com about the Q2 consulting proposal — mention we can start March 1 and our rate is flexible for long-term engagements.
```

**Skill generates draft:**
```
Hi John,

I wanted to follow up regarding the Q2 consulting proposal. We're available to begin on March 1 and can structure the engagement to fit your timeline.

For long-term partnerships, our rates are flexible — I'd be happy to discuss options that work for both sides.

Let me know if you'd like to set up a call to go over the details.

Best regards
```

**Send task created** with `to: "john@acmecorp.com"`, `subject: "Q2 Consulting Proposal"`, gated for approval.

---

### Example 3: Process All Gmail Tasks (Batch)

**User prompt:**
```
Process all Gmail tasks
```

**Skill scans `/Needs_Action/`:**
1. `task_email_Resume for job.md` → Job application → Generate acknowledgment draft
2. `task_email_Project Proposal Review.md` → Needs reply → Generate reply draft
3. `task_email_Weekly Industry Digest.md` → Newsletter → Archive to /Done/

**Result:** 2 drafts pending approval, 1 archived. Dashboard updated.

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `default_tone` | professional | professional, casual, friendly, formal |
| `max_reply_length` | 150 words | Keep replies concise unless topic requires more |
| `auto_archive_newsletters` | true | Newsletters go straight to /Done/ without a draft |
| `include_original_context` | true | Include original email snippet in draft file |
| `sign_off` | "Best regards" | Default closing — human can edit before approving |
| `thread_reference` | true | Include message_id_ref for email threading |

---

## Guardrails

- **NEVER send without approval** — `send_email` is always gated. No exceptions. No auto-send.
- **NEVER fabricate** commitments, pricing, deadlines, or promises the user hasn't authorized
- **NEVER share** confidential data, API keys, passwords, or internal business details in replies
- **NEVER reply to spam or phishing** — flag suspicious emails for human review instead
- **NEVER CC/BCC** additional recipients unless explicitly instructed by the user
- **No client names** in replies to third parties unless authorized
- **Factual only** — do not invent meeting times, project statuses, or deliverables
- **Company Handbook Rule 2** applies: no irreversible external action without confirmation
- **Company Handbook Rule 5** applies: if unsure about reply content, ask the user

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Email task file not found | Log warning, notify user, skip |
| YAML frontmatter malformed | Log warning, attempt to extract fields from body, or skip |
| No `from` field in task | Skip — cannot reply without recipient |
| MCP `send_email` fails | Keep in `/Pending_Approval/`, set `status: execution_failed`, log error |
| SMTP credentials not configured | Log error, notify user to configure `mcp_server/.env` |
| Email body is empty | Generate a short acknowledgment: "Thank you for your email. I'll review and follow up." |
| Suspicious/phishing email | Do NOT draft a reply. Flag task with `priority: high` and note: "Possible phishing — review manually" |

---

## Notes

- This skill generates drafts only — it never sends directly
- The human has full editorial control over every outbound email
- Drafts can be edited directly in the Markdown file before approving
- The `send_email` MCP tool is available via `mcp_server/mcp_server.js` (SMTP/nodemailer)
- For Gmail-native sending (SMTP via Gmail), ensure an App Password is configured (not regular password)
- Pair with `gmail_watcher.py` for a complete receive → process → reply pipeline
- Both the reply draft (`/Plans/`) and the send task (`/Pending_Approval/`) are preserved for audit trail
- Original email tasks are moved to `/Done/` only after the reply is successfully sent (or the user explicitly archives them)

# Error Recovery Skill

> When something breaks, don't crash — classify, retry, or escalate.

---

## Description

This skill defines how the AI Employee handles errors across all
components (watchers, scheduler, MCP calls, skill execution). It
provides a structured **classify → retry → escalate** pipeline that
integrates with `Ralph_Wiggum_Loop_Skill` for autonomous retry and
`Approval_Check_Skill` for human escalation.

All errors are logged to `Logs/System_Log.md` with full tracebacks
via the centralized `log_manager.py` module.

---

## Position in Reasoning Loop

```
[Error occurs in any component]
    --> Error_Recovery_Skill activates
    --> Step 1: CLASSIFY the error (transient vs permanent)
    --> Step 2: LOG with full traceback (log_manager.log_error)
    -->
    |  IF transient:
    |      --> Step 3a: RETRY with backoff (max 3 attempts)
    |      --> IF retry succeeds: resume normal flow
    |      --> IF retries exhausted: escalate (Step 4)
    |
    |  IF permanent:
    |      --> Step 3b: SKIP retry, go directly to escalate
    |
    --> Step 4: ESCALATE
        --> Create error task in /Needs_Action/ (approval_needed: true)
        --> Update Dashboard.md with error status
        --> Log escalation to System_Log.md
        --> IF inside Ralph Loop: pause loop, yield to human
```

---

## Trigger Conditions

This skill activates automatically when:

- Any `except` block catches an exception in a watcher, scheduler, or skill
- An MCP tool call returns a failure result
- An API call (Gmail IMAP, LinkedIn, X, Odoo) times out or returns error
- A file operation fails (permission denied, disk full, corrupt data)
- A Ralph Loop iteration encounters an unrecoverable error

---

## Error Classification

### Transient Errors (auto-retry)

Errors that are likely to succeed on a subsequent attempt.

| Error Type | Examples | Retry Strategy |
|-----------|----------|----------------|
| **Network timeout** | MCP server unreachable, API timeout | Retry 3x with backoff |
| **Rate limiting** | LinkedIn API 429, Gmail IMAP throttle | Wait + retry after delay |
| **Temporary file lock** | Log file in use, CSV being written | Retry after 5s |
| **Connection reset** | IMAP connection dropped, socket error | Reconnect + retry |
| **Service unavailable** | Odoo 503, MCP 502 | Retry 3x with backoff |

### Permanent Errors (escalate immediately)

Errors that will not resolve without human intervention.

| Error Type | Examples | Action |
|-----------|----------|--------|
| **Authentication failure** | Bad API key, expired token, wrong password | Escalate — credentials need update |
| **Permission denied** | Cannot write to folder, read-only filesystem | Escalate — OS/permissions issue |
| **Invalid data** | Corrupt CSV, malformed email, bad JSON | Escalate — source data needs fix |
| **Missing dependency** | Module not installed, binary not found | Escalate — environment issue |
| **Configuration error** | Missing .env value, bad Odoo URL | Escalate — config needs update |
| **Disk full** | No space left on device | Escalate — infrastructure issue |

### Classification Logic

```python
TRANSIENT_PATTERNS = [
    "timeout", "timed out", "connection reset", "connection refused",
    "temporarily unavailable", "503", "502", "429", "rate limit",
    "try again", "resource busy", "file in use", "broken pipe",
    "connection aborted", "ssl error", "eof occurred",
]

PERMANENT_PATTERNS = [
    "permission denied", "authentication", "unauthorized", "403",
    "401", "invalid credentials", "no such file", "not found",
    "import error", "module not found", "disk full", "no space",
    "invalid data", "parse error", "corrupt", "malformed",
]

def classify_error(error_message):
    msg = str(error_message).lower()

    for pattern in PERMANENT_PATTERNS:
        if pattern in msg:
            return "permanent"

    for pattern in TRANSIENT_PATTERNS:
        if pattern in msg:
            return "transient"

    # Default: treat unknown errors as transient (give them a retry chance)
    return "transient"
```

---

## Retry Strategy

### Exponential Backoff

For transient errors, retry with increasing delays:

| Attempt | Delay | Cumulative Wait |
|---------|-------|-----------------|
| 1 (initial) | 0s | 0s |
| 2 (1st retry) | 5s | 5s |
| 3 (2nd retry) | 15s | 20s |
| 4 (3rd retry) | 45s | 65s |
| **Max retries exhausted** | — | **Escalate** |

### Formula

```
delay = base_delay * (multiplier ^ attempt)
base_delay = 5 seconds
multiplier = 3
max_retries = 3
```

### Retry Implementation Pattern

```python
import time
from log_manager import log_error, log_to_system_log

def retry_with_backoff(func, *args, max_retries=3, base_delay=5,
                       multiplier=3, error_log_file=None, **kwargs):
    """
    Call func(*args, **kwargs) with exponential backoff on failure.

    Returns:
        The return value of func on success, or None if all retries fail.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)
            if attempt > 0:
                log_to_system_log(
                    "Error Recovery",
                    f"{func.__name__} succeeded on attempt {attempt + 1}"
                )
            return result

        except Exception as e:
            last_exception = e
            classification = classify_error(str(e))

            log_error(
                f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1},"
                f" {classification}): {e}",
                error_log_file=error_log_file,
            )

            if classification == "permanent":
                break  # Don't retry permanent errors

            if attempt < max_retries:
                delay = base_delay * (multiplier ** attempt)
                print(f"[RETRY] Waiting {delay}s before attempt "
                      f"{attempt + 2}...")
                time.sleep(delay)

    # All retries exhausted (or permanent error) — escalate
    return None
```

---

## Escalation

When retries are exhausted or a permanent error is detected, the skill
creates an error task for human review.

### Error Task Template

```markdown
---
type: error_recovery
status: pending
priority: high
created_at: <timestamp>
related_files: []
approval_needed: true
approved: false
mcp_action: []
error_source: "<component name>"
error_classification: "<transient|permanent>"
retry_attempts: <number>
---

# Error: <component> — <short description>

## Error Details

- **Component:** <watcher/scheduler/skill name>
- **Error:** <error message>
- **Classification:** <transient|permanent>
- **Retry attempts:** <N> of 3
- **First seen:** <timestamp>
- **Last attempt:** <timestamp>

## Traceback

\`\`\`
<full traceback from log_manager>
\`\`\`

## Steps

- [ ] Review error details and traceback
- [ ] Diagnose root cause
- [ ] Fix the issue (update config, restart service, etc.)
- [ ] Verify the fix by re-running the component
- [ ] Mark this task as completed

## Notes

- This task was auto-generated by Error_Recovery_Skill
- The component is paused/degraded until this is resolved
- Check Logs/<component>_errors.log for full history
```

### Dashboard Update

Add a row to the **Recent Actions** table:

```markdown
| <timestamp> | Error Recovery | <component> | Escalated | <error summary> — task created in /Needs_Action/ |
```

---

## Ralph Wiggum Loop Integration

When an error occurs **inside** a Ralph Loop iteration:

### Transient Error

```
Ralph Loop Iteration N:
  -> ACT step fails with transient error
  -> Error_Recovery_Skill: retry_with_backoff (up to 3 attempts)
  -> IF retry succeeds:
       -> Resume iteration N (continue to CHECK step)
  -> IF retries exhausted:
       -> Log failure
       -> Ralph Loop CHECK step: mark this sub-task as failed
       -> Ralph Loop REASON step (next iteration): skip failed item,
          continue with remaining work
       -> When all other work is done: report failed item in final
          summary, create escalation task
```

### Permanent Error

```
Ralph Loop Iteration N:
  -> ACT step fails with permanent error
  -> Error_Recovery_Skill: classify as permanent, skip retry
  -> Create escalation task in /Needs_Action/
  -> Ralph Loop CHECK step: mark sub-task as blocked
  -> Ralph Loop continues with other items (does NOT stop entirely)
  -> Final summary includes the blocked item
```

### Ralph Loop Never Crashes

The loop's existing `except Exception` blocks in each iteration
already prevent crashes. Error_Recovery_Skill adds **structured
classification and retry** inside those blocks instead of just
logging and moving on.

---

## MCP Error Handling

### MCP Tool Failures

| MCP Tool | Common Errors | Recovery |
|----------|--------------|----------|
| `send_email` | SMTP timeout, auth failure, invalid recipient | Retry 3x (timeout), escalate (auth/invalid) |
| `post_linkedin` | Token expired, rate limit, API error | Retry 3x (rate limit), escalate (token) |
| `check_email_config` | SMTP unreachable | Retry 3x |
| `odoo_accounting` | Connection timeout, auth error, bad params | Retry 3x (timeout), escalate (auth/params) |

### MCP Retry Pattern

```python
# Before calling MCP tool:
result = retry_with_backoff(
    mcp_send_email,
    to="ceo@company.com",
    subject="Weekly Report",
    body="...",
    max_retries=3,
    error_log_file=ERROR_LOG_FILE,
)

if result is None:
    # All retries failed — create escalation task
    create_error_task(
        component="MCP send_email",
        error="Failed after 3 retries",
        classification="transient",
    )
```

---

## Integration with Existing Skills

| Skill | Relationship |
|-------|-------------|
| `Ralph_Wiggum_Loop_Skill` | Retry logic runs inside loop iterations; loop continues past failed items |
| `Approval_Check_Skill` | Escalation tasks have `approval_needed: true` — human must resolve |
| `Plan_Tasks_Skill` | Error tasks appear in plans as high-priority blockers |
| `MCP_Action_Logger_Skill` | Failed MCP calls are logged with error details |
| `CEO_Briefing_Skill` | Error count and unresolved issues appear in the weekly briefing |

---

## Integration with log_manager.py

All error handling flows through the centralized `log_manager` module:

```python
from log_manager import log_error, log_to_system_log

# In any except block — traceback is captured automatically:
try:
    result = call_mcp_tool()
except Exception as e:
    log_error(f"MCP call failed: {e}", error_log_file=ERROR_LOG_FILE)
    # ^^ Full traceback is auto-captured from sys.exc_info()
    # ^^ Auto-rotates the error log if it exceeds 1 MB
```

### What log_manager Provides

| Function | Purpose |
|----------|---------|
| `log_error(msg, error_log_file, exc)` | Write error + traceback to log file, auto-rotate |
| `log_to_system_log(action, details)` | Add row to System_Log.md, auto-rotate |
| `ensure_folder_exists(path, name)` | Safe folder creation |
| `check_and_rotate(path, header)` | Manual rotation check for any file |
| `rotate_all()` | Force rotation check on all known log files |

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RETRIES` | `3` | Maximum retry attempts for transient errors |
| `BASE_DELAY` | `5` | Initial delay in seconds before first retry |
| `BACKOFF_MULTIPLIER` | `3` | Multiply delay by this on each retry |
| `AUTO_ESCALATE` | `true` | Auto-create task in /Needs_Action/ on failure |
| `LOG_TRACEBACKS` | `true` | Include full Python traceback in error logs |
| `MAX_SIZE_BYTES` | `1048576` | Log rotation threshold (1 MB) |

---

## Watcher Integration Examples

### file_watcher.py

```python
from log_manager import log_error, log_to_system_log, ensure_folder_exists
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "watcher_errors.log")

# In the main loop:
except Exception as e:
    log_error(f"Unexpected error in main loop: {e}",
              error_log_file=ERROR_LOG_FILE)
    # Traceback auto-captured, auto-rotation checked
```

### scheduler.py

```python
from log_manager import (log_error, log_to_system_log,
                         ensure_folder_exists, check_and_rotate)

# Periodic rotation check (runs with each scheduled cycle):
check_and_rotate(SYSTEM_LOG_FILE, SYSTEM_LOG_HEADER)
```

---

## Notes

- **Never crash.** Every component must catch exceptions and route them
  through this skill. The AI Employee degrades gracefully, never stops.
- **Log everything.** Even if retry succeeds, the initial failure is
  logged for audit purposes.
- **Traceback always.** Full Python tracebacks make debugging possible
  without reproducing the error.
- **Rotate proactively.** Don't let logs fill the disk — 1 MB per file,
  archived with date stamps.
- **Human in the loop.** Permanent errors always escalate. The AI
  Employee never silently swallows a problem it can't fix.
- **Idempotent retries.** Retried operations must be safe to re-run
  (e.g., don't re-send an email that might have been sent).

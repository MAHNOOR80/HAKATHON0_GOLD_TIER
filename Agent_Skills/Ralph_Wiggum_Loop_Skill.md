# Ralph Wiggum Loop Skill

> "I'm in danger!" — Ralph Wiggum
> A self-referential reasoning loop that keeps working until the job is truly done.

---

## Purpose

Wrap any non-trivial task in a **Reason → Act → Check → Re-prompt** loop so Claude
never prematurely declares victory. The loop continues until an explicit completion
signal is detected, ensuring multi-step tasks (research, code generation, multi-file
edits, long plans) are fully finished before the agent stops.

This is the **Gold Tier stop-hook**: an autonomous loop that prevents Claude from
"wandering off" mid-task.

---

## When to Use

- User invokes with: **"Use Ralph_Wiggum_Loop_Skill on this task"**
- Any task expected to take multiple reasoning steps
- Tasks involving file creation, code generation, or multi-phase plans
- When combined with `Plan_Tasks_Skill` to execute every step of a plan
- Long-running research, analysis, or content creation

**Do NOT use** for:
- Single-shot questions ("What time is it?")
- Simple file reads or trivial edits
- Tasks the user explicitly says are one-step

---

## Loop Architecture

```
┌──────────────────────────────────────────────────┐
│                 RALPH LOOP START                  │
│  Receive task prompt + context                   │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│  STEP 1: REASON                                  │
│  - Read current state (files, tasks, context)    │
│  - Identify what remains to be done              │
│  - If Plan_Tasks_Skill plan exists, load it      │
│  - Determine the NEXT concrete action            │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│  STEP 2: ACT                                     │
│  - Execute the next action (edit, create, call)  │
│  - Respect Approval_Check_Skill gates            │
│  - Log action via MCP_Action_Logger conventions  │
│  - Update task file status if applicable         │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│  STEP 3: CHECK COMPLETION                        │
│  Run ALL completion checks (see below).          │
│  If ANY check returns DONE → exit loop.          │
│  Otherwise → continue to Step 4.                 │
└──────────┬────────────────────┬──────────────────┘
           │                    │
        NOT DONE              DONE
           │                    │
           ▼                    ▼
┌────────────────────┐  ┌─────────────────────────┐
│  STEP 4: RE-PROMPT │  │  STEP 5: FINALIZE       │
│  - Summarize what  │  │  - Log completion        │
│    was accomplished│  │  - Move task to /Done    │
│  - List remaining  │  │  - Update Dashboard.md   │
│    work            │  │  - Output final summary  │
│  - Feed updated    │  │  - Say: RALPH_DONE       │
│    context back    │  └─────────────────────────┘
│    into Step 1     │
│  - Increment loop  │
│    counter         │
└────────┬───────────┘
         │
         └──────────► Back to STEP 1
```

---

## Completion Checks

The loop exits when **any** of these conditions is true:

| # | Check | How |
|---|-------|-----|
| 1 | **Task file in `/Done/`** | The task `.md` that started this loop has been moved to `/Done/` |
| 2 | **YAML status: completed** | The task file's frontmatter has `status: completed` |
| 3 | **Explicit DONE flag** | The agent's own reasoning output contains the literal string `RALPH_DONE` |
| 4 | **All plan steps finished** | If a `Plan_Tasks_Skill` plan was loaded, every batch/step is marked complete |
| 5 | **No remaining work detected** | `/Needs_Action/` is empty AND no pending items in current plan |
| 6 | **Max iterations reached** | Safety valve — default `MAX_LOOPS = 10` (configurable) |
| 7 | **Approval gate waiting** | Task moved to `/Pending_Approval/` — pause loop, resume after human decision |

### Approval Gate Pause

If during execution the `Approval_Check_Skill` intercepts and moves a task to
`/Pending_Approval/`, the Ralph loop **pauses** (does not exit). It resumes
automatically once:
- The task is approved (`approved: true`) — continue executing
- The task is rejected (`status: rejected`) — log rejection, check if other work remains

---

## Integration with Existing Skills

### With Plan_Tasks_Skill
```
1. Ralph loop starts
2. Step 1 (REASON): Load Plan_Tasks_Skill → generate plan in /Plans/
3. Step 2 (ACT): Execute Batch 1 of the plan
4. Step 3 (CHECK): Are all batches done? No → continue
5. Step 2 (ACT): Execute Batch 2
6. ... repeat until all batches complete ...
7. Step 3 (CHECK): All batches done → RALPH_DONE
```

### With Approval_Check_Skill
```
1. Ralph loop encounters a sensitive action (e.g., send_email)
2. Approval_Check_Skill intercepts → task moves to /Pending_Approval/
3. Ralph loop PAUSES (does not spin-wait; yields control)
4. Human approves → Approval_Handler_Skill executes
5. Ralph loop RESUMES from where it paused
```

### With MCP_Action_Logger_Skill
- Every action inside the loop is logged per MCP_Action_Logger conventions
- Loop metadata (iteration number, elapsed time) included in log entries

---

## Loop State Tracking

Each iteration updates a **loop state block** appended to the task file or held in
memory:

```yaml
# Ralph Loop State
ralph_loop:
  task_id: "task_build_feature_2026-02-10"
  started_at: "2026-02-10T14:00:00"
  current_iteration: 3
  max_iterations: 10
  status: running          # running | paused | done | max_reached
  last_action: "Created auth module in /src/auth.py"
  remaining_work:
    - "Write unit tests for auth module"
    - "Update README with auth docs"
  completion_checks:
    task_in_done: false
    yaml_status_completed: false
    explicit_done_flag: false
    plan_steps_finished: false
    needs_action_empty: false
```

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_LOOPS` | `10` | Maximum iterations before forced stop |
| `PAUSE_ON_APPROVAL` | `true` | Pause loop when approval gate triggers |
| `AUTO_PLAN` | `true` | Automatically invoke Plan_Tasks_Skill on first iteration |
| `VERBOSE_LOGGING` | `true` | Log each iteration to System_Log.md |
| `COMPLETION_SUMMARY` | `true` | Output a summary of all actions on RALPH_DONE |

---

## Behavior Rules

1. **Never declare done prematurely.** Run all completion checks before exiting.
2. **Never spin-wait.** If blocked by approval, pause and yield.
3. **Always log.** Every iteration gets a System_Log entry.
4. **Respect existing skills.** The loop orchestrates — it does not replace
   Approval_Check, Plan_Tasks, or MCP_Action_Logger.
5. **Respect Company Handbook.** All 5 core rules apply inside the loop:
   - Log important actions (Rule 1)
   - Never destructive without confirmation (Rule 2)
   - Move completed tasks to Done (Rule 3)
   - Keep task files structured (Rule 4)
   - If unsure, ask (Rule 5)
6. **Degrade gracefully.** If MAX_LOOPS is hit, output what was accomplished,
   what remains, and let the user decide next steps.
7. **Idempotent iterations.** Each iteration should be safe to re-run if
   interrupted (e.g., don't re-send an already-sent email).

---

## Usage Examples

### Example 1: Simple task with loop
**User prompt:**
```
Use Ralph_Wiggum_Loop_Skill on this task:
Build a Python CLI that converts CSV to JSON.
Create the script, write tests, and update the README.
```

**Ralph loop iterations:**
1. REASON: Three deliverables needed (script, tests, README). ACT: Create `csv_to_json.py`. CHECK: Not done (tests + README missing).
2. REASON: Script exists, need tests. ACT: Create `test_csv_to_json.py`. CHECK: Not done (README missing).
3. REASON: Script + tests exist. ACT: Update README. CHECK: All deliverables created → `RALPH_DONE`.

### Example 2: With Plan_Tasks_Skill integration
**User prompt:**
```
Use Ralph_Wiggum_Loop_Skill on this task:
Process all pending tasks in /Needs_Action using Plan_Tasks_Skill.
```

**Ralph loop iterations:**
1. REASON: 4 tasks in /Needs_Action. ACT: Invoke Plan_Tasks_Skill → generates plan with 2 batches. CHECK: Batch 1 not started.
2. REASON: Plan loaded, Batch 1 has 2 tasks. ACT: Execute task 1 (email reply, needs approval). CHECK: Paused — awaiting approval.
3. *(resumes after approval)* REASON: Task 1 approved and executed. ACT: Execute task 2 (file review, no approval). CHECK: Batch 1 done, Batch 2 pending.
4. REASON: Batch 2 has 2 tasks. ACT: Execute task 3. CHECK: Not done.
5. REASON: Task 3 done. ACT: Execute task 4. CHECK: All batches complete → `RALPH_DONE`.

### Example 3: Using the Python wrapper
```bash
python ralph_wrapper.py --task "Refactor the auth module and write tests" --max-loops 5
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Action fails (e.g., MCP error) | Log error, do NOT retry same action immediately. Re-assess in next REASON step. |
| Task file missing or corrupted | Log warning, attempt to reconstruct from context. If impossible, ask user. |
| MAX_LOOPS reached | Output progress summary, list remaining work, exit with status `max_reached`. |
| Infinite loop detected (same action repeated 3x) | Force-exit, log warning, ask user for guidance. |
| External dependency unavailable | Pause loop, log issue, skip to next actionable item if possible. |

---

## System Log Format

Each Ralph iteration logs to `Logs/System_Log.md`:

```
### [2026-02-10 14:05] Ralph Loop — Iteration 3/10
- **Task:** task_build_feature_2026-02-10
- **Action:** Created unit tests in test_auth.py
- **Remaining:** 1 item (Update README)
- **Status:** running
```

On completion:
```
### [2026-02-10 14:12] Ralph Loop — COMPLETE
- **Task:** task_build_feature_2026-02-10
- **Total Iterations:** 4
- **Duration:** 12 minutes
- **Actions Taken:** 4 (create script, create tests, update README, move to Done)
- **Status:** RALPH_DONE
```

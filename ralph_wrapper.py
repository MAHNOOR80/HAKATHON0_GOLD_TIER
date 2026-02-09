"""
Ralph Wiggum Loop Wrapper
=========================
Gold Tier — Personal AI Employee Hackathon 0

Runs Claude Code CLI in a loop, re-feeding context after each invocation
until the task signals DONE (via RALPH_DONE in output or a file landing in /Done/).

Usage:
    python ralph_wrapper.py --task "Build a CSV-to-JSON converter with tests"
    python ralph_wrapper.py --task "Process all pending tasks" --max-loops 5
    python ralph_wrapper.py --task-file Needs_Action/task_example.md
"""

import argparse
import subprocess
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DONE_DIR = BASE_DIR / "Done"
NEEDS_ACTION_DIR = BASE_DIR / "Needs_Action"
LOGS_DIR = BASE_DIR / "Logs"
PLANS_DIR = BASE_DIR / "Plans"
SYSTEM_LOG = LOGS_DIR / "System_Log.md"

DEFAULT_MAX_LOOPS = 10
LOOP_COOLDOWN_SECONDS = 2          # brief pause between iterations
REPEATED_ACTION_THRESHOLD = 3      # detect infinite loops

RALPH_DONE_MARKER = "RALPH_DONE"
CLAUDE_CMD = "claude"              # assumes `claude` is on PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(message: str, *, level: str = "INFO") -> None:
    """Print timestamped log to console."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {message}")


def append_system_log(entry: str) -> None:
    """Append an entry to Logs/System_Log.md."""
    LOGS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(SYSTEM_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n### [{ts}] Ralph Wrapper\n{entry}\n")


def check_done_folder(task_id: str) -> bool:
    """Return True if a file matching task_id exists in /Done/."""
    if not DONE_DIR.exists():
        return False
    for f in DONE_DIR.iterdir():
        if task_id in f.name:
            return True
    return False


def check_needs_action_empty() -> bool:
    """Return True if /Needs_Action/ has zero .md files."""
    if not NEEDS_ACTION_DIR.exists():
        return True
    return len(list(NEEDS_ACTION_DIR.glob("*.md"))) == 0


def detect_repeated_action(history: list[str]) -> bool:
    """Return True if the last N actions are identical (stuck loop)."""
    if len(history) < REPEATED_ACTION_THRESHOLD:
        return False
    tail = history[-REPEATED_ACTION_THRESHOLD:]
    return len(set(tail)) == 1


def extract_task_id(task_description: str) -> str:
    """Derive a short, filesystem-safe task id from the description."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", task_description)[:40].strip("_").lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ralph_{slug}_{ts}"


def build_prompt(task: str, iteration: int, max_loops: int,
                 prev_summary: str, remaining: str) -> str:
    """Build the prompt that gets fed to Claude Code on each iteration."""

    prompt = f"""You are operating under the Ralph_Wiggum_Loop_Skill (Gold Tier).
This is iteration {iteration}/{max_loops} of the Ralph loop.

## Original Task
{task}

## Instructions
1. Load and follow Agent_Skills/Ralph_Wiggum_Loop_Skill.md.
2. REASON about what still needs to be done.
3. ACT — perform the next concrete step.
4. CHECK — evaluate the completion checks listed in the skill.
5. At the END of your response, output one of:
   - `RALPH_DONE` — if ALL work is complete.
   - `RALPH_CONTINUE` — if more work remains. Include a brief summary of what
     you accomplished and what is left.

Respect all existing Agent Skills (Approval_Check, Plan_Tasks, MCP_Action_Logger).
Respect all Company Handbook rules.
"""

    if prev_summary:
        prompt += f"""
## Previous Iteration Summary
{prev_summary}
"""

    if remaining:
        prompt += f"""
## Known Remaining Work
{remaining}
"""

    return prompt


def invoke_claude(prompt: str) -> str:
    """Call the Claude Code CLI with the given prompt and return stdout."""
    try:
        result = subprocess.run(
            [CLAUDE_CMD, "--print", "--prompt", prompt],
            capture_output=True,
            text=True,
            timeout=300,        # 5-minute timeout per iteration
            cwd=str(BASE_DIR),
        )
        output = result.stdout or ""
        if result.returncode != 0 and result.stderr:
            log(f"Claude stderr: {result.stderr.strip()}", level="WARN")
        return output
    except FileNotFoundError:
        log(f"'{CLAUDE_CMD}' not found on PATH. Install Claude Code CLI first.",
            level="ERROR")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log("Claude invocation timed out (300 s). Continuing to next iteration.",
            level="WARN")
        return "(timeout — no output)"


def parse_summary_and_remaining(output: str) -> tuple[str, str]:
    """Extract accomplishment summary and remaining work from Claude output."""
    summary = ""
    remaining = ""

    # Look for structured sections Claude may produce
    lines = output.strip().splitlines()
    capture_remaining = False
    summary_lines = []
    remaining_lines = []

    for line in lines:
        lower = line.lower().strip()
        if "remaining" in lower or "left to do" in lower or "still need" in lower:
            capture_remaining = True
            continue
        if capture_remaining:
            remaining_lines.append(line)
        else:
            summary_lines.append(line)

    # Keep summaries concise (last 30 lines at most)
    summary = "\n".join(summary_lines[-30:])
    remaining = "\n".join(remaining_lines[-15:]) if remaining_lines else ""

    return summary, remaining


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def ralph_loop(task: str, max_loops: int) -> None:
    """Run the Ralph Wiggum reasoning loop."""

    task_id = extract_task_id(task)
    log(f"Ralph loop started — task_id={task_id}, max_loops={max_loops}")
    append_system_log(
        f"- **Task:** {task_id}\n"
        f"- **Description:** {task}\n"
        f"- **Max Loops:** {max_loops}\n"
        f"- **Status:** started"
    )

    prev_summary = ""
    remaining = ""
    action_history: list[str] = []
    start_time = time.time()

    for iteration in range(1, max_loops + 1):
        log(f"--- Iteration {iteration}/{max_loops} ---")

        # Build and send prompt
        prompt = build_prompt(task, iteration, max_loops, prev_summary, remaining)
        output = invoke_claude(prompt)

        # Print abbreviated output
        preview = output[:500] + ("..." if len(output) > 500 else "")
        log(f"Claude output preview:\n{preview}")

        # Track for infinite-loop detection
        action_hash = output.strip()[-200:]  # last 200 chars as fingerprint
        action_history.append(action_hash)

        # ---- Completion Checks ----

        # Check 1: Explicit RALPH_DONE marker
        if RALPH_DONE_MARKER in output:
            log("Completion signal: RALPH_DONE found in output.")
            break

        # Check 2: Task file landed in /Done/
        if check_done_folder(task_id):
            log("Completion signal: task file found in /Done/.")
            break

        # Check 3: /Needs_Action/ is empty (applicable for batch-processing tasks)
        if "pending tasks" in task.lower() and check_needs_action_empty():
            log("Completion signal: /Needs_Action/ is empty.")
            break

        # Check 4: Stuck-loop detection
        if detect_repeated_action(action_history):
            log("Stuck loop detected — same output repeated "
                f"{REPEATED_ACTION_THRESHOLD} times. Exiting.", level="WARN")
            append_system_log(
                f"- **Iteration:** {iteration}\n"
                f"- **Status:** stuck_loop_detected — forcing exit"
            )
            break

        # Parse what happened and what's left
        prev_summary, remaining = parse_summary_and_remaining(output)

        # Cooldown
        time.sleep(LOOP_COOLDOWN_SECONDS)

    else:
        # max_loops exhausted without completion signal
        log(f"MAX_LOOPS ({max_loops}) reached without completion.", level="WARN")

    elapsed = round(time.time() - start_time, 1)
    log(f"Ralph loop finished — {iteration} iterations, {elapsed}s elapsed.")
    append_system_log(
        f"- **Task:** {task_id}\n"
        f"- **Total Iterations:** {iteration}\n"
        f"- **Duration:** {elapsed}s\n"
        f"- **Status:** {'RALPH_DONE' if RALPH_DONE_MARKER in output else 'max_reached'}"
    )


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ralph Wiggum Loop — run Claude Code in a self-correcting loop"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--task", "-t",
        type=str,
        help="Task description to loop on (plain text)"
    )
    group.add_argument(
        "--task-file", "-f",
        type=str,
        help="Path to a task .md file whose body is the task description"
    )
    parser.add_argument(
        "--max-loops", "-m",
        type=int,
        default=DEFAULT_MAX_LOOPS,
        help=f"Maximum loop iterations (default: {DEFAULT_MAX_LOOPS})"
    )

    args = parser.parse_args()

    # Resolve task text
    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.exists():
            log(f"Task file not found: {task_path}", level="ERROR")
            sys.exit(1)
        task = task_path.read_text(encoding="utf-8")
        log(f"Loaded task from file: {task_path}")
    else:
        task = args.task

    # Ensure directories exist
    for d in [DONE_DIR, NEEDS_ACTION_DIR, LOGS_DIR, PLANS_DIR]:
        d.mkdir(exist_ok=True)

    ralph_loop(task, args.max_loops)


if __name__ == "__main__":
    main()

"""
Gold Tier AI Employee - Task Scheduler

This script runs periodically (every hour) to check for pending tasks.
When pending tasks are found, it creates a "Generate daily plan" task
to trigger the Plan_Tasks_Skill.

Features:
- Hourly scheduling using the 'schedule' library
- Automatic task creation for planning
- Error handling that never crashes (Error_Recovery_Skill pattern)
- Error logging with traceback via centralized log_manager
- Auto-rotation when log files exceed 1 MB
- Duplicate prevention (won't create plan task if one already exists)

Requirements:
    pip install schedule

Usage:
    python scheduler.py

Press Ctrl+C to stop the scheduler.
"""

import os
import time
from datetime import datetime

# Centralized logging — replaces duplicated log_error / log_to_system_log
from log_manager import (
    log_error as _base_log_error,
    log_to_system_log,
    ensure_folder_exists,
)

# Try to import schedule library, provide helpful message if not installed
try:
    import schedule
except ImportError:
    print("=" * 50)
    print("ERROR: 'schedule' library not found!")
    print()
    print("Please install it by running:")
    print("    pip install schedule")
    print("=" * 50)
    exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

# How often to check for pending tasks (in minutes)
# Default: 60 minutes (1 hour)
CHECK_INTERVAL_MINUTES = 60

# How often the schedule loop runs internally (in seconds)
# This doesn't affect the hourly check, just how responsive the script is
LOOP_SLEEP_SECONDS = 30

# Folder paths (relative to where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "scheduler_errors.log")

# Task naming - used to detect if a plan/audit task already exists
PLAN_TASK_PREFIX = "task_generate_plan"
BANK_AUDIT_PREFIX = "task_bank_audit"

# Bank audit — how often to trigger (in hours). Default: every 24 hours.
BANK_AUDIT_INTERVAL_HOURS = 24
DONE_FOLDER = os.path.join(SCRIPT_DIR, "Done")

# Social summary — how often to trigger (in hours). Default: every 24 hours.
SOCIAL_SUMMARY_INTERVAL_HOURS = 24
SOCIAL_SUMMARY_PREFIX = "task_social_summary"
PLANS_FOLDER = os.path.join(SCRIPT_DIR, "Plans")

# CEO Briefing — weekly on Monday at 09:00 (Gold Tier).
CEO_BRIEFING_DAY = "monday"
CEO_BRIEFING_TIME = "09:00"
CEO_BRIEFING_PREFIX = "task_ceo_briefing"


# =============================================================================
# ERROR HANDLING — delegates to centralized log_manager.py
# =============================================================================

def log_error(error_message):
    """Route errors to the centralized log_manager with this component's log file."""
    _base_log_error(error_message, error_log_file=ERROR_LOG_FILE)

# log_to_system_log and ensure_folder_exists are imported directly from log_manager


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def count_pending_tasks():
    """
    Count the number of pending task files in the Needs_Action folder.

    Returns:
        int: Number of .md files in Needs_Action folder, or 0 if error.
    """
    try:
        if not os.path.exists(NEEDS_ACTION_FOLDER):
            # Folder doesn't exist = no pending tasks
            return 0

        # Count only .md files (task files)
        count = 0
        for item in os.listdir(NEEDS_ACTION_FOLDER):
            if item.endswith(".md"):
                item_path = os.path.join(NEEDS_ACTION_FOLDER, item)
                if os.path.isfile(item_path):
                    count += 1

        return count

    except PermissionError:
        log_error("Permission denied when reading Needs_Action folder")
        return 0

    except Exception as e:
        log_error(f"Error counting pending tasks: {e}")
        return 0


def plan_task_exists():
    """
    Check if a "Generate plan" task already exists in Needs_Action.

    This prevents creating duplicate planning tasks.

    Returns:
        bool: True if a plan task already exists, False otherwise.
    """
    try:
        if not os.path.exists(NEEDS_ACTION_FOLDER):
            return False

        for item in os.listdir(NEEDS_ACTION_FOLDER):
            # Check if filename starts with our plan task prefix
            if item.lower().startswith(PLAN_TASK_PREFIX):
                return True

        return False

    except Exception as e:
        log_error(f"Error checking for existing plan task: {e}")
        return False  # If we can't check, assume no task exists


def create_plan_task():
    """
    Create a "Generate daily plan" task in the Needs_Action folder.

    This task will trigger the Plan_Tasks_Skill when processed.

    Returns:
        str: Path to the created task file, or None if creation failed.
    """
    try:
        # Ensure the Needs_Action folder exists
        if not ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action"):
            return None

        # Generate timestamp for the task
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        # Create unique task filename with timestamp
        task_filename = f"{PLAN_TASK_PREFIX}_{date_stamp}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        # Build the task file content using Silver tier template
        task_content = f"""---
type: planning
status: pending
priority: high
created_at: {timestamp}
related_files: []
approval_needed: false
mcp_action: []
---

# Generate Daily Plan

## Description

The scheduler has detected pending tasks that need planning. Execute the Plan_Tasks_Skill to analyze all pending tasks and create an execution plan.

## Steps

- [ ] Load Plan_Tasks_Skill from /Agent_Skills/
- [ ] Scan /Needs_Action for all pending tasks
- [ ] Analyze task types, priorities, and dependencies
- [ ] Generate Plan_<timestamp>.md in /Plans/
- [ ] Update Dashboard.md with plan reference
- [ ] Log completion to System_Log

## Notes

- **Triggered by:** Scheduler (automatic)
- **Detected at:** {timestamp}
- **Skill to use:** Plan_Tasks_Skill.md
- This is a planning task only — do not execute other tasks.
- After plan is generated, this task can be marked complete.
"""

        # Write the task file
        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except PermissionError:
        log_error("Permission denied when creating plan task")
        return None

    except Exception as e:
        log_error(f"Error creating plan task: {e}")
        return None


def bank_audit_task_exists():
    """
    Check if a bank audit task already exists in Needs_Action.
    Prevents creating duplicate audit tasks.

    Returns:
        bool: True if a bank audit task already exists, False otherwise.
    """
    try:
        if not os.path.exists(NEEDS_ACTION_FOLDER):
            return False

        for item in os.listdir(NEEDS_ACTION_FOLDER):
            if item.lower().startswith(BANK_AUDIT_PREFIX):
                return True

        return False

    except Exception as e:
        log_error(f"Error checking for existing bank audit task: {e}")
        return False


def count_unreviewed_bank_tasks():
    """
    Count bank transaction tasks in Needs_Action that haven't been reviewed yet.

    Returns:
        int: Number of unreviewed bank task files.
    """
    try:
        count = 0
        if not os.path.exists(NEEDS_ACTION_FOLDER):
            return 0

        for item in os.listdir(NEEDS_ACTION_FOLDER):
            if item.startswith("task_bank_") and item.endswith(".md"):
                count += 1

        return count

    except Exception as e:
        log_error(f"Error counting bank tasks: {e}")
        return 0


def create_bank_audit_task():
    """
    Create a daily bank audit task in Needs_Action.
    This triggers a review of all unprocessed bank transactions.

    Returns:
        str: Path to the created task file, or None if creation failed.
    """
    try:
        if not ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action"):
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        unreviewed = count_unreviewed_bank_tasks()

        task_filename = f"{BANK_AUDIT_PREFIX}_{date_stamp}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        task_content = f"""---
type: bank_audit
status: pending
priority: high
created_at: {timestamp}
related_files: []
approval_needed: false
mcp_action: []
---

# Daily Bank Transaction Audit

## Description

The scheduler has triggered a daily bank audit. Review all pending bank
transaction tasks, verify anomalies, and ensure financial records are
up to date.

## Current State

- **Unreviewed bank tasks:** {unreviewed}

## Steps

- [ ] Review all task_bank_*.md files in /Needs_Action
- [ ] Verify transaction totals and categories (revenue/expense)
- [ ] Investigate flagged anomalies (> $500)
- [ ] Route anomalies through Approval_Check_Skill if needed
- [ ] Archive reviewed transactions to /Done
- [ ] Update Dashboard.md with audit summary
- [ ] Log completion to System_Log

## Notes

- **Triggered by:** Scheduler (daily bank audit)
- **Detected at:** {timestamp}
- **Skills to use:** Plan_Tasks_Skill, Approval_Check_Skill
- After audit is complete, this task can be marked complete.
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except Exception as e:
        log_error(f"Error creating bank audit task: {e}")
        return None


def scheduled_bank_audit():
    """
    Daily bank audit job. Creates an audit task if unreviewed bank
    transactions exist and no audit task is already pending.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[{timestamp}] Running daily bank audit check...")

    try:
        unreviewed = count_unreviewed_bank_tasks()
        print(f"  -> Found {unreviewed} unreviewed bank task(s)")

        if unreviewed == 0:
            print("  -> No bank tasks to audit. Skipping.")
            log_to_system_log("Bank Audit Check", "No unreviewed bank tasks found")
            return

        if bank_audit_task_exists():
            print("  -> Bank audit task already exists. Skipping.")
            log_to_system_log("Bank Audit Check", f"{unreviewed} bank tasks pending, audit task already exists")
            return

        task_path = create_bank_audit_task()

        if task_path:
            task_name = os.path.basename(task_path)
            print(f"  -> Created bank audit task: {task_name}")
            log_to_system_log("Bank Audit Created", f"Created {task_name} for {unreviewed} unreviewed bank tasks")
        else:
            print("  -> Failed to create bank audit task!")
            log_to_system_log("Bank Audit Error", "Failed to create bank audit task")

    except Exception as e:
        log_error(f"Error in bank audit check: {e}")


def social_summary_exists_today():
    """
    Check if a Social Summary has already been generated today.

    Returns:
        bool: True if today's summary already exists in /Plans/.
    """
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"Social_Summary_{today_str}.md"
        return os.path.exists(os.path.join(PLANS_FOLDER, filename))
    except Exception as e:
        log_error(f"Error checking social summary: {e}")
        return False


def scheduled_social_summary():
    """
    Daily social summary job. Invokes social_watcher.run_social_summary()
    if today's summary hasn't been generated yet.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[{timestamp}] Running daily social summary check...")

    try:
        if social_summary_exists_today():
            print("  -> Social summary already generated today. Skipping.")
            return

        # Import and run social_watcher
        try:
            import social_watcher
            result = social_watcher.run_social_summary()
            if result:
                print(f"  -> Social summary generated: {os.path.basename(result)}")
                log_to_system_log("Social Summary (Scheduler)", f"Generated {os.path.basename(result)}")
            else:
                print("  -> Social summary generation returned None")
        except ImportError:
            log_error("social_watcher.py not found — cannot generate social summary")
            print("  -> social_watcher.py not found. Skipping.")
        except Exception as e:
            log_error(f"Social summary failed: {e}")
            print(f"  -> Error: {e}")

    except Exception as e:
        log_error(f"Error in social summary check: {e}")


def ceo_briefing_exists_this_week():
    """
    Check if a CEO Briefing has already been generated for the current week.
    Looks for /Plans/CEO_Briefing_<date>.md where <date> falls in the current
    Monday-to-Sunday window.

    Returns:
        bool: True if this week's briefing already exists.
    """
    try:
        if not os.path.exists(PLANS_FOLDER):
            return False

        # Calculate the Monday of the current week
        today = datetime.now().date()
        monday = today - __import__("datetime").timedelta(days=today.weekday())

        for item in os.listdir(PLANS_FOLDER):
            if item.startswith("CEO_Briefing_") and item.endswith(".md"):
                # Extract date from filename: CEO_Briefing_YYYY-MM-DD.md
                try:
                    date_str = item.replace("CEO_Briefing_", "").replace(".md", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    # Check if the file date falls within the current week
                    if monday <= file_date <= monday + __import__("datetime").timedelta(days=6):
                        return True
                except ValueError:
                    continue

        return False

    except Exception as e:
        log_error(f"Error checking CEO briefing: {e}")
        return False


def ceo_briefing_task_exists():
    """
    Check if a CEO briefing trigger task already exists in Needs_Action.
    Prevents creating duplicate trigger tasks.

    Returns:
        bool: True if a CEO briefing task already exists, False otherwise.
    """
    try:
        if not os.path.exists(NEEDS_ACTION_FOLDER):
            return False

        for item in os.listdir(NEEDS_ACTION_FOLDER):
            if item.lower().startswith(CEO_BRIEFING_PREFIX):
                return True

        return False

    except Exception as e:
        log_error(f"Error checking for existing CEO briefing task: {e}")
        return False


def create_ceo_briefing_task():
    """
    Create a CEO Briefing trigger task in Needs_Action.
    This task tells Ralph Loop (or manual prompt) to execute the
    full 4-phase CEO Briefing audit.

    Returns:
        str: Path to the created task file, or None if creation failed.
    """
    try:
        if not ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action"):
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_stamp = datetime.now().strftime("%Y-%m-%d")

        task_filename = f"{CEO_BRIEFING_PREFIX}_{date_stamp}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        task_content = f"""---
type: ceo_briefing
status: pending
priority: high
created_at: {timestamp}
related_files: []
approval_needed: false
mcp_action: []
---

# Monday Morning CEO Briefing — {date_stamp}

## Description

The scheduler has triggered the weekly CEO Briefing. Execute the
CEO_Briefing_Skill using Ralph_Wiggum_Loop_Skill to perform the
full 4-phase audit and compile the executive summary.

## Audit Phases (Ralph Loop)

- [ ] **Phase 1 — Financial Audit:** Read bank tasks, query Odoo get_report
- [ ] **Phase 2 — Project Audit:** Scan Needs_Action, Pending_Approval, Done
- [ ] **Phase 3 — Social Audit:** Read latest Social_Summary from Plans
- [ ] **Phase 4 — Compile Briefing:** Generate CEO_Briefing_{date_stamp}.md, create delivery task

## Delivery

After briefing is compiled, create a delivery task with:
- `approval_needed: true`
- `mcp_action: ["send_email"]`
- Route through Approval_Check_Skill before sending

## Notes

- **Triggered by:** Scheduler (weekly, {CEO_BRIEFING_DAY} {CEO_BRIEFING_TIME})
- **Detected at:** {timestamp}
- **Skill:** CEO_Briefing_Skill.md
- **Loop:** Ralph_Wiggum_Loop_Skill (4 iterations, max 8)
- Briefing compilation is read-only (no approval needed)
- Only the delivery (email/LinkedIn) requires approval
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except Exception as e:
        log_error(f"Error creating CEO briefing task: {e}")
        return None


def scheduled_ceo_briefing():
    """
    Weekly CEO briefing job. Creates a briefing trigger task if this week's
    briefing hasn't been generated yet and no trigger task is pending.
    Runs every Monday at 09:00 via schedule library.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[{timestamp}] Running weekly CEO briefing check...")

    try:
        # Check if briefing already exists for this week
        if ceo_briefing_exists_this_week():
            print("  -> CEO briefing already generated this week. Skipping.")
            return

        # Check if a trigger task already exists
        if ceo_briefing_task_exists():
            print("  -> CEO briefing task already pending. Skipping.")
            log_to_system_log("CEO Briefing Check", "Trigger task already exists in Needs_Action")
            return

        # Create the trigger task
        task_path = create_ceo_briefing_task()

        if task_path:
            task_name = os.path.basename(task_path)
            print(f"  -> Created CEO briefing task: {task_name}")
            log_to_system_log("CEO Briefing Triggered", f"Created {task_name} — weekly Monday briefing via scheduler")
        else:
            print("  -> Failed to create CEO briefing task!")
            log_to_system_log("CEO Briefing Error", "Failed to create CEO briefing trigger task")

    except Exception as e:
        log_error(f"Error in CEO briefing check: {e}")


def scheduled_check():
    """
    The main scheduled job that runs every hour.

    This function:
    1. Counts pending tasks in Needs_Action
    2. If tasks exist and no plan task exists, creates a plan task
    3. Logs all activity to System_Log.md
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[{timestamp}] Running scheduled check...")

    try:
        # Count pending tasks
        pending_count = count_pending_tasks()
        print(f"  -> Found {pending_count} pending task(s) in Needs_Action")

        if pending_count == 0:
            # No pending tasks - nothing to do
            print("  -> No tasks to plan. Skipping.")
            log_to_system_log("Scheduler Check", f"No pending tasks found. Next check in {CHECK_INTERVAL_MINUTES} min.")
            return

        # Check if a plan task already exists
        if plan_task_exists():
            # Don't create duplicate
            print("  -> Plan task already exists. Skipping creation.")
            log_to_system_log("Scheduler Check", f"Found {pending_count} tasks, plan task already pending.")
            return

        # Create a plan task
        task_path = create_plan_task()

        if task_path:
            task_name = os.path.basename(task_path)
            print(f"  -> Created plan task: {task_name}")
            log_to_system_log("Scheduler Task Created", f"Created {task_name} for {pending_count} pending tasks")
        else:
            print("  -> Failed to create plan task!")
            log_to_system_log("Scheduler Error", "Failed to create plan task")

    except Exception as e:
        log_error(f"Error in scheduled check: {e}")


def initialize_scheduler():
    """
    Initialize the scheduler by setting up folders and scheduling the job.

    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    print("[SETUP] Initializing scheduler...")

    # Ensure required folders exist
    needs_action_ok = ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    logs_ok = ensure_folder_exists(LOGS_FOLDER, "Logs")

    if not needs_action_ok:
        log_error("Critical folder Needs_Action could not be created.")
        # Continue anyway - maybe it will be created later

    # Schedule the job to run every hour
    # The schedule library uses a simple, readable syntax
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(scheduled_check)

    # Schedule daily bank audit (Gold Tier)
    schedule.every(BANK_AUDIT_INTERVAL_HOURS).hours.do(scheduled_bank_audit)

    # Schedule daily social summary (Gold Tier)
    schedule.every(SOCIAL_SUMMARY_INTERVAL_HOURS).hours.do(scheduled_social_summary)

    # Schedule weekly CEO briefing (Gold Tier) — Monday at 09:00
    schedule.every().monday.at(CEO_BRIEFING_TIME).do(scheduled_ceo_briefing)

    print(f"[SETUP] Scheduled task check every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"[SETUP] Scheduled bank audit every {BANK_AUDIT_INTERVAL_HOURS} hours")
    print(f"[SETUP] Scheduled social summary every {SOCIAL_SUMMARY_INTERVAL_HOURS} hours")
    print(f"[SETUP] Scheduled CEO briefing every {CEO_BRIEFING_DAY} at {CEO_BRIEFING_TIME}")
    print("[SETUP] Initialization complete.")

    return True


def main():
    """
    Main function that runs the scheduler loop.

    This function contains the main scheduling loop wrapped in error handling.
    If an error occurs, it's logged and the loop continues - the script never crashes.
    """
    print("=" * 55)
    print("Gold Tier AI Employee - Task Scheduler")
    print("=" * 55)
    print()

    # Initialize - set up folders and schedule the job
    initialize_scheduler()

    print()
    print(f"Monitoring folder: {NEEDS_ACTION_FOLDER}")
    print(f"System log: {SYSTEM_LOG_FILE}")
    print(f"Error log: {ERROR_LOG_FILE}")
    print(f"Check interval: Every {CHECK_INTERVAL_MINUTES} minutes")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 50)

    # Run an immediate check on startup (don't wait for first interval)
    print("\n[STARTUP] Running initial task check...")
    scheduled_check()

    print("\n[STARTUP] Running initial bank audit check...")
    scheduled_bank_audit()

    print("\n[STARTUP] Running initial social summary check...")
    scheduled_social_summary()

    print("\n[STARTUP] Running initial CEO briefing check...")
    scheduled_ceo_briefing()

    # Log scheduler start
    log_to_system_log("Scheduler Started", f"Task scheduler initialized, checking every {CHECK_INTERVAL_MINUTES} min")

    # Main loop - runs forever until user presses Ctrl+C
    try:
        while True:
            try:
                # Run any pending scheduled jobs
                # This is the schedule library's way of executing scheduled tasks
                schedule.run_pending()

                # Sleep briefly before checking again
                # This keeps CPU usage low while staying responsive
                time.sleep(LOOP_SLEEP_SECONDS)

            except KeyboardInterrupt:
                # Re-raise so outer handler catches it
                raise

            except Exception as e:
                # Something unexpected happened in the loop
                log_error(f"Unexpected error in main loop: {e}")

                # Wait before retrying to avoid spamming errors
                print("[RECOVERING] Waiting 30 seconds before retrying...")
                time.sleep(30)

    except KeyboardInterrupt:
        # User pressed Ctrl+C - this is expected, not an error
        print()
        print("-" * 50)
        print("Scheduler stopped by user.")
        log_to_system_log("Scheduler Stopped", "Task scheduler stopped by user")


# =============================================================================
# ENTRY POINT
# =============================================================================

# This block only runs if you execute this file directly (not when imported)
if __name__ == "__main__":
    main()

"""
Silver Tier AI Employee - Task Scheduler

This script runs periodically (every hour) to check for pending tasks.
When pending tasks are found, it creates a "Generate daily plan" task
to trigger the Plan_Tasks_Skill.

Features:
- Hourly scheduling using the 'schedule' library
- Automatic task creation for planning
- Logging to System_Log.md and scheduler_errors.log
- Error handling that never crashes
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


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    """
    Write an error message to the error log file with a timestamp.

    This function is called whenever something goes wrong. It writes the error
    to a log file so you can review what happened later.

    Args:
        error_message: A string describing what went wrong.

    Why this matters:
        - Errors are recorded even if no one is watching
        - You can review the log file later to diagnose issues
        - The script continues running instead of crashing
    """
    # Get the current time for the log entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format the log entry with timestamp and error message
    log_entry = f"[{timestamp}] ERROR: {error_message}\n"

    try:
        # Ensure the Logs folder exists before writing
        os.makedirs(LOGS_FOLDER, exist_ok=True)

        # Open the log file in "append" mode ('a') so we add to it, not overwrite
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # Also print to console so the user sees it immediately
        print(f"[ERROR LOGGED] {error_message}")

    except Exception as e:
        # If we can't even write to the log file, at least print to console
        print(f"[CRITICAL] Could not write to error log: {e}")
        print(f"[ORIGINAL ERROR] {error_message}")


def log_to_system_log(action, details):
    """
    Write an entry to the System_Log.md file.

    This adds a row to the Activity Log table in System_Log.md,
    following the established format used by other AI Employee components.

    Args:
        action: Short description of the action (e.g., "Scheduler Check")
        details: Longer description of what happened

    Returns:
        bool: True if logging succeeded, False otherwise
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        # Ensure Logs folder exists
        os.makedirs(LOGS_FOLDER, exist_ok=True)

        # Check if System_Log.md exists
        if not os.path.exists(SYSTEM_LOG_FILE):
            # Create a basic System_Log.md if it doesn't exist
            create_system_log()

        # Read the current content
        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the table header row and insert our new entry after it
        # The table format is: | Timestamp | Action | Details |
        table_header = "| Timestamp | Action | Details |"
        separator = "|-----------|--------|---------|"

        # Create the new log entry row
        new_row = f"| {timestamp} | {action} | {details} |"

        # Find where to insert (after the separator line)
        if separator in content:
            # Insert new row right after the separator
            parts = content.split(separator, 1)
            if len(parts) == 2:
                # Add newline + new row after separator
                new_content = parts[0] + separator + "\n" + new_row + parts[1]

                with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(new_content)

                return True

        # If we couldn't find the expected format, log error
        log_error("System_Log.md format not recognized, could not add entry")
        return False

    except Exception as e:
        log_error(f"Failed to write to System_Log.md: {e}")
        return False


def create_system_log():
    """
    Create a new System_Log.md file with the correct structure.

    This is called if System_Log.md doesn't exist when we try to log.
    """
    content = """# System Log

Central log for all AI Employee activity and system events.

---

## Activity Log

| Timestamp | Action | Details |
|-----------|--------|---------|
| _System initialized_ | Setup | Scheduler created System_Log.md |

---

_New entries should be added at the top of the Activity Log table._
"""

    try:
        with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[SETUP] Created System_Log.md")
    except Exception as e:
        log_error(f"Failed to create System_Log.md: {e}")


def ensure_folder_exists(folder_path, folder_name):
    """
    Check if a folder exists, and create it if it doesn't.

    Args:
        folder_path: The full path to the folder.
        folder_name: A friendly name for the folder (used in messages).

    Returns:
        bool: True if the folder exists (or was created), False if creation failed.
    """
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True

    except PermissionError:
        log_error(f"Permission denied when creating {folder_name} folder at {folder_path}")
        return False

    except Exception as e:
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


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

    print(f"[SETUP] Scheduled task check every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"[SETUP] Scheduled bank audit every {BANK_AUDIT_INTERVAL_HOURS} hours")
    print(f"[SETUP] Scheduled social summary every {SOCIAL_SUMMARY_INTERVAL_HOURS} hours")
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

"""
Gold Tier AI Employee - Centralized Log Manager

This module provides shared logging utilities for all watchers, the
scheduler, and any other component. Import from here instead of
duplicating log_error / log_to_system_log / ensure_folder_exists in
every file.

Features:
- Auto-rotation when any log file exceeds MAX_SIZE_BYTES (1 MB)
- Error backtrace capture (full traceback logged automatically)
- Centralized System_Log.md writing
- Shared ensure_folder_exists helper
- Monitors ALL log files: System_Log, plus every watcher error log
- Safe to call from any module — never crashes the caller

Usage (in watchers / scheduler):
    from log_manager import log_error, log_to_system_log, ensure_folder_exists

    # log_error auto-captures the active exception traceback
    try:
        risky_call()
    except Exception as e:
        log_error(f"risky_call failed: {e}", error_log_file=MY_ERROR_LOG)

    # Or let it fall back to the default error log:
    log_error("something broke")

    # System log (table row in Logs/System_Log.md)
    log_to_system_log("Watcher Started", "Mode: DEMO, checking every 10s")

Run directly to force a rotation check on all known log files:
    python log_manager.py
"""

import os
import sys
import traceback
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

# Maximum log file size in bytes before rotation (1 MB)
MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

# Folder paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")
DEFAULT_ERROR_LOG = os.path.join(LOGS_FOLDER, "watcher_errors.log")

# All log files to monitor for rotation.
# Each entry: (file_path, header_content_for_fresh_file)
SYSTEM_LOG_HEADER = """# System Log

Central log for all AI Employee activity and system events.

---

## Activity Log

| Timestamp | Action | Details |
|-----------|--------|---------|

---

_New entries should be added at the top of the Activity Log table._
"""

LOG_FILES = [
    (SYSTEM_LOG_FILE, SYSTEM_LOG_HEADER),
    (os.path.join(LOGS_FOLDER, "watcher_errors.log"),
     "# Watcher Error Log\n# Errors from file_watcher.py\n\n"),
    (os.path.join(LOGS_FOLDER, "gmail_watcher_errors.log"),
     "# Gmail Watcher Error Log\n# Errors from gmail_watcher.py\n\n"),
    (os.path.join(LOGS_FOLDER, "bank_watcher_errors.log"),
     "# Bank Watcher Error Log\n# Errors from bank_watcher.py\n\n"),
    (os.path.join(LOGS_FOLDER, "social_watcher_errors.log"),
     "# Social Watcher Error Log\n# Errors from social_watcher.py\n\n"),
    (os.path.join(LOGS_FOLDER, "scheduler_errors.log"),
     "# Scheduler Error Log\n# Errors from scheduler.py\n\n"),
]


# =============================================================================
# SIZE HELPERS
# =============================================================================

def get_file_size(file_path):
    """Return file size in bytes, or 0 if the file doesn't exist."""
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
    except Exception:
        return 0


def format_size(size_bytes):
    """Convert bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


# =============================================================================
# AUTO-ROTATION
# =============================================================================

def _generate_archive_name(file_path):
    """
    Build an archive filename with today's date.

    Example: System_Log.md -> System_Log_2026-02-10.md
    Handles collisions by appending _1, _2, etc.
    """
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        ext = "." + ext
    else:
        name = filename
        ext = ""

    date_stamp = datetime.now().strftime("%Y-%m-%d")
    new_filename = f"{name}_{date_stamp}{ext}"
    new_path = os.path.join(directory, new_filename)

    counter = 1
    while os.path.exists(new_path):
        new_filename = f"{name}_{date_stamp}_{counter}{ext}"
        new_path = os.path.join(directory, new_filename)
        counter += 1

    return new_path


def check_and_rotate(file_path, header_content=""):
    """
    Rotate a log file if it exceeds MAX_SIZE_BYTES.

    Steps:
        1. Check size.
        2. Rename old file with a date suffix (archive).
        3. Create a fresh file with the header content.

    Args:
        file_path:       Absolute path to the log file.
        header_content:  Content to write into the new empty file.

    Returns:
        bool: True if rotation happened, False otherwise.
    """
    try:
        if not os.path.exists(file_path):
            return False

        current_size = get_file_size(file_path)
        if current_size < MAX_SIZE_BYTES:
            return False

        # Rotate
        archive_path = _generate_archive_name(file_path)
        os.rename(file_path, archive_path)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(header_content)

        archive_name = os.path.basename(archive_path)
        print(f"[LOG ROTATION] {os.path.basename(file_path)} -> {archive_name} "
              f"({format_size(current_size)})")
        return True

    except Exception as e:
        # Last-resort: print but never crash
        print(f"[LOG ROTATION ERROR] Could not rotate {file_path}: {e}")
        return False


def rotate_all():
    """Check all known log files and rotate any that exceed the size limit."""
    rotated = 0
    for file_path, header in LOG_FILES:
        if check_and_rotate(file_path, header):
            rotated += 1
    return rotated


# =============================================================================
# CORE: log_error
# =============================================================================

def log_error(error_message, error_log_file=None, exc=None):
    """
    Write an error message (with optional traceback) to an error log file.

    If called inside an ``except`` block and *exc* is not provided, the
    current exception's traceback is captured automatically via
    ``sys.exc_info()``.

    After writing, the target file is checked for auto-rotation.

    Args:
        error_message:  Human-readable description of the error.
        error_log_file: Path to the error log.  Falls back to
                        DEFAULT_ERROR_LOG if not specified.
        exc:            Optional exception object.  If None, the active
                        exception (if any) is used.
    """
    target = error_log_file or DEFAULT_ERROR_LOG
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Build the log entry ---
    lines = [f"[{timestamp}] ERROR: {error_message}"]

    # Auto-capture traceback
    if exc is None:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            exc = exc_info[1]

    if exc is not None:
        try:
            tb_lines = traceback.format_exception(type(exc), exc,
                                                  exc.__traceback__)
            lines.append("  Traceback:")
            for tb_line in tb_lines:
                for sub in tb_line.rstrip().split("\n"):
                    lines.append(f"    {sub}")
        except Exception:
            lines.append(f"  (could not format traceback)")

    log_entry = "\n".join(lines) + "\n\n"

    # --- Write ---
    try:
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"[ERROR LOGGED] {error_message}")
    except Exception as e:
        print(f"[CRITICAL] Could not write to error log: {e}")
        print(f"[ORIGINAL ERROR] {error_message}")

    # --- Auto-rotate if the file just exceeded the limit ---
    # Look up the matching header, or use a generic one
    header = ""
    for path, hdr in LOG_FILES:
        if os.path.abspath(path) == os.path.abspath(target):
            header = hdr
            break
    check_and_rotate(target, header)


# =============================================================================
# CORE: log_to_system_log
# =============================================================================

def log_to_system_log(action, details):
    """
    Add a row to the Activity Log table in Logs/System_Log.md.

    The row is inserted immediately after the separator line so that
    the newest entry is always at the top of the table.

    Auto-rotates System_Log.md if it exceeds MAX_SIZE_BYTES after
    writing.

    Args:
        action:  Short label (e.g. "Scheduler Check").
        details: Longer description of what happened.

    Returns:
        bool: True if the entry was written, False otherwise.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_row = f"| {timestamp} | {action} | {details} |"

    try:
        os.makedirs(LOGS_FOLDER, exist_ok=True)

        if not os.path.exists(SYSTEM_LOG_FILE):
            with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(SYSTEM_LOG_HEADER)

        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        separator = "|-----------|--------|---------|"
        if separator in content:
            parts = content.split(separator, 1)
            if len(parts) == 2:
                new_content = parts[0] + separator + "\n" + new_row + parts[1]
                with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Auto-rotate after write
                check_and_rotate(SYSTEM_LOG_FILE, SYSTEM_LOG_HEADER)
                return True

        log_error("System_Log.md format not recognized, could not add entry")
        return False

    except Exception as e:
        # Avoid infinite recursion: don't call log_error -> log_to_system_log
        timestamp_err = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(DEFAULT_ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp_err}] ERROR: Failed to write to "
                        f"System_Log.md: {e}\n")
        except Exception:
            pass
        print(f"[ERROR] Failed to write to System_Log.md: {e}")
        return False


# =============================================================================
# CORE: ensure_folder_exists
# =============================================================================

def ensure_folder_exists(folder_path, folder_name):
    """
    Create *folder_path* if it doesn't already exist.

    Args:
        folder_path: Absolute path to the folder.
        folder_name: Friendly name for console output.

    Returns:
        bool: True if the folder exists (or was created), False on error.
    """
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True

    except PermissionError:
        log_error(f"Permission denied when creating {folder_name} folder "
                  f"at {folder_path}")
        return False

    except Exception as e:
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


# =============================================================================
# CLI: Run directly to force rotation check
# =============================================================================

def run_log_rotation():
    """Check all configured log files and rotate any that exceed the limit."""
    print("=" * 55)
    print("Gold Tier AI Employee - Log Manager")
    print("=" * 55)
    print()
    print(f"Size limit: {format_size(MAX_SIZE_BYTES)}")
    print(f"Checking {len(LOG_FILES)} log file(s)...")
    print()

    rotated_count = 0

    for file_path, header_content in LOG_FILES:
        filename = os.path.basename(file_path)
        current_size = get_file_size(file_path)

        if not os.path.exists(file_path):
            print(f"[SKIP] {filename}: does not exist")
        else:
            print(f"[CHECK] {filename}: {format_size(current_size)}")
            if check_and_rotate(file_path, header_content):
                rotated_count += 1
            else:
                print(f"  -> OK (limit: {format_size(MAX_SIZE_BYTES)})")
        print()

    print("-" * 55)
    if rotated_count > 0:
        print(f"Done! Rotated {rotated_count} file(s).")
    else:
        print("Done! No rotation needed.")


if __name__ == "__main__":
    run_log_rotation()

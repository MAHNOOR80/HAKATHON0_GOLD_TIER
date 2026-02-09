"""
Gold Tier AI Employee - Bank Transaction Watcher

This script monitors the /Bank_Drops folder for new CSV files containing
bank transactions. When a new CSV is detected, it parses every transaction
and creates structured task files in /Needs_Action.

Transactions above the ANOMALY_THRESHOLD ($500) are flagged for human
approval via the Approval_Check_Skill gate.

This is the THIRD watcher (alongside file_watcher.py and gmail_watcher.py),
fulfilling the Gold Tier "Financial Perception" requirement.

Features:
- Monitors /Bank_Drops for .csv files
- Parses transactions via pandas (date, amount, description)
- Auto-categorises as revenue (positive) or expense (negative)
- Flags anomalies (> $500 absolute value) with approval_needed: true
- Demo mode that works without real bank data
- Duplicate prevention via processed-file tracking
- Logging to System_Log.md and bank_watcher_errors.log
- Error handling that never crashes

CSV Format Expected:
    date,description,amount
    2026-02-01,Client payment - Acme Corp,1500.00
    2026-02-01,AWS hosting fee,-249.99
    (header row required; amount positive = revenue, negative = expense)

Requirements:
    pip install pandas

Usage:
    Demo:  python bank_watcher.py
    Live:  Drop a .csv into /Bank_Drops and the watcher picks it up

Press Ctrl+C to stop the watcher.
"""

import os
import sys
import time
import csv
import hashlib
from datetime import datetime

# Try to import pandas; fall back to stdlib csv if unavailable
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("[WARN] pandas not installed — using stdlib csv parser (pip install pandas for full support)")


# =============================================================================
# CONFIGURATION
# =============================================================================

# How often to check for new CSV files (in seconds)
CHECK_INTERVAL = 10

# Dollar threshold — anything above this absolute value is an anomaly
ANOMALY_THRESHOLD = 500.00

# Folder paths (relative to where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_DROPS_FOLDER = os.path.join(SCRIPT_DIR, "Bank_Drops")
NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
DONE_FOLDER = os.path.join(SCRIPT_DIR, "Done")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "bank_watcher_errors.log")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")

# Track which CSV files have already been processed
processed_files = set()

# Demo mode flag — set True to generate a sample CSV on first run
DEMO_MODE = True
demo_generated = False


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    """
    Write an error message to the error log file with a timestamp.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] ERROR: {error_message}\n"

    try:
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"[ERROR LOGGED] {error_message}")
    except Exception as e:
        print(f"[CRITICAL] Could not write to error log: {e}")
        print(f"[ORIGINAL ERROR] {error_message}")


def log_to_system_log(action, details):
    """
    Add an entry to the System_Log.md activity table.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_row = f"| {timestamp} | {action} | {details} |"

    try:
        if not os.path.exists(SYSTEM_LOG_FILE):
            return

        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        marker = "|-----------|--------|---------|"
        if marker in content:
            content = content.replace(marker, f"{marker}\n{new_row}")
            with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        log_error(f"Could not update System_Log: {e}")


def ensure_folder_exists(folder_path, folder_name):
    """
    Check if a folder exists, and create it if it doesn't.
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
# CSV PARSING
# =============================================================================

def generate_transaction_id(date_str, description, amount, row_index):
    """
    Generate a deterministic, unique transaction ID from row data.
    """
    raw = f"{date_str}|{description}|{amount}|{row_index}"
    return "txn_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def classify_transaction(amount):
    """
    Classify a transaction as revenue or expense based on sign.

    Returns:
        tuple: (category, is_anomaly)
            category  — 'revenue' if amount >= 0, 'expense' if amount < 0
            is_anomaly — True if abs(amount) > ANOMALY_THRESHOLD
    """
    category = "revenue" if amount >= 0 else "expense"
    is_anomaly = abs(amount) > ANOMALY_THRESHOLD
    return category, is_anomaly


def parse_csv_pandas(filepath):
    """
    Parse a bank CSV using pandas.

    Expected columns (case-insensitive): date, description, amount
    Extra columns are ignored.

    Returns:
        list[dict]: List of transaction dicts, or empty list on error.
    """
    try:
        df = pd.read_csv(filepath, dtype=str)

        # Normalise column names to lowercase, strip whitespace
        df.columns = [c.strip().lower() for c in df.columns]

        # Validate required columns
        required = {"date", "description", "amount"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            log_error(f"CSV {filepath} missing columns: {missing}. Found: {list(df.columns)}")
            return []

        transactions = []
        for idx, row in df.iterrows():
            try:
                date_str = str(row["date"]).strip()
                description = str(row["description"]).strip()
                amount = float(str(row["amount"]).strip().replace(",", ""))
            except (ValueError, TypeError) as e:
                log_error(f"Row {idx} in {filepath} has bad data: {e}")
                continue

            txn_id = generate_transaction_id(date_str, description, amount, idx)
            category, is_anomaly = classify_transaction(amount)

            transactions.append({
                "transaction_id": txn_id,
                "date": date_str,
                "description": description,
                "amount": amount,
                "category": category,
                "is_anomaly": is_anomaly,
            })

        return transactions

    except Exception as e:
        log_error(f"pandas failed to parse {filepath}: {e}")
        return []


def parse_csv_stdlib(filepath):
    """
    Fallback CSV parser using Python's built-in csv module.
    Same interface as parse_csv_pandas.
    """
    transactions = []

    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # Normalise headers
            if reader.fieldnames is None:
                log_error(f"CSV {filepath} has no header row")
                return []

            # Build a lowercase mapping
            header_map = {h.strip().lower(): h for h in reader.fieldnames}
            required = {"date", "description", "amount"}
            if not required.issubset(set(header_map.keys())):
                missing = required - set(header_map.keys())
                log_error(f"CSV {filepath} missing columns: {missing}")
                return []

            for idx, row in enumerate(reader):
                try:
                    date_str = row[header_map["date"]].strip()
                    description = row[header_map["description"]].strip()
                    amount = float(row[header_map["amount"]].strip().replace(",", ""))
                except (ValueError, TypeError, KeyError) as e:
                    log_error(f"Row {idx} in {filepath} has bad data: {e}")
                    continue

                txn_id = generate_transaction_id(date_str, description, amount, idx)
                category, is_anomaly = classify_transaction(amount)

                transactions.append({
                    "transaction_id": txn_id,
                    "date": date_str,
                    "description": description,
                    "amount": amount,
                    "category": category,
                    "is_anomaly": is_anomaly,
                })

    except Exception as e:
        log_error(f"stdlib csv failed to parse {filepath}: {e}")

    return transactions


def parse_csv(filepath):
    """
    Parse a bank CSV file. Uses pandas if available, otherwise stdlib csv.
    """
    if HAS_PANDAS:
        return parse_csv_pandas(filepath)
    return parse_csv_stdlib(filepath)


# =============================================================================
# TASK CREATION
# =============================================================================

def create_transaction_task(csv_filename, transactions):
    """
    Create a single task file in /Needs_Action summarising all transactions
    from a CSV file. If any transaction is an anomaly, the entire task is
    flagged for approval.

    Args:
        csv_filename: Name of the source CSV file.
        transactions: List of transaction dicts from parse_csv().

    Returns:
        str: Path to the created task file, or None on failure.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        has_anomaly = any(t["is_anomaly"] for t in transactions)

        # Compute summary stats
        total_revenue = sum(t["amount"] for t in transactions if t["category"] == "revenue")
        total_expense = sum(t["amount"] for t in transactions if t["category"] == "expense")
        net = total_revenue + total_expense  # expense amounts are negative
        anomaly_count = sum(1 for t in transactions if t["is_anomaly"])

        # Safe filename
        safe_name = csv_filename.replace(".csv", "").replace(" ", "_")
        task_filename = f"task_bank_{safe_name}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        # Avoid overwriting
        counter = 1
        while os.path.exists(task_path):
            task_filename = f"task_bank_{safe_name}_{counter}.md"
            task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)
            counter += 1

        # Build the transaction table
        txn_rows = []
        for t in transactions:
            flag = " **ANOMALY**" if t["is_anomaly"] else ""
            txn_rows.append(
                f"| {t['transaction_id']} | {t['date']} | {t['description']} "
                f"| ${t['amount']:,.2f} | {t['category']} |{flag}"
            )
        txn_table = "\n".join(txn_rows)

        # Build anomaly detail section
        anomaly_section = ""
        if has_anomaly:
            anomaly_lines = []
            for t in transactions:
                if t["is_anomaly"]:
                    anomaly_lines.append(
                        f"- **{t['transaction_id']}**: {t['description']} — "
                        f"${t['amount']:,.2f} ({t['category']}) — exceeds ${ANOMALY_THRESHOLD:,.2f} threshold"
                    )
            anomaly_section = (
                "## Anomalies Detected\n\n"
                + "\n".join(anomaly_lines)
                + "\n\nThese transactions exceed the anomaly threshold and require human review.\n"
            )

        # Determine approval fields
        approval_needed = "true" if has_anomaly else "false"
        mcp_action = "['send_email']" if has_anomaly else "[]"

        task_content = f"""---
type: bank_transaction
status: pending
priority: {"high" if has_anomaly else "medium"}
created_at: {timestamp}
related_files: ["Bank_Drops/{csv_filename}"]
approval_needed: {approval_needed}
approved: false
mcp_action: {mcp_action}
source: bank_watcher
csv_file: "{csv_filename}"
transaction_count: {len(transactions)}
total_revenue: {total_revenue:.2f}
total_expenses: {total_expense:.2f}
net_amount: {net:.2f}
anomaly_count: {anomaly_count}
anomaly_threshold: {ANOMALY_THRESHOLD:.2f}
---

# Bank Transactions: {csv_filename}

## Summary

- **Source CSV:** Bank_Drops/{csv_filename}
- **Transactions:** {len(transactions)}
- **Total Revenue:** ${total_revenue:,.2f}
- **Total Expenses:** ${total_expense:,.2f}
- **Net:** ${net:,.2f}
- **Anomalies:** {anomaly_count} (threshold: ${ANOMALY_THRESHOLD:,.2f})

## Transaction Detail

| Transaction ID | Date | Description | Amount | Category |
|----------------|------|-------------|--------|----------|
{txn_table}

{anomaly_section}
## Steps

- [ ] Review transaction summary and verify totals
- [ ] Investigate any flagged anomalies
- [ ] {"**APPROVAL REQUIRED** — anomalies exceed $" + f"{ANOMALY_THRESHOLD:,.2f}" + " threshold" if has_anomaly else "No anomalies — routine review"}
- [ ] Categorise and archive transactions
- [ ] Mark this task as completed

## Notes

- **Source:** Bank Watcher (automatic detection)
- **Detected at:** {timestamp}
- **Parser:** {"pandas" if HAS_PANDAS else "stdlib csv"}
- This task was auto-generated by the Bank Watcher system.
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except Exception as e:
        log_error(f"Error creating bank task for '{csv_filename}': {e}")
        return None


# =============================================================================
# CSV FILE MONITORING
# =============================================================================

def get_csv_files():
    """
    Get a set of .csv filenames currently in /Bank_Drops.
    """
    try:
        if not os.path.exists(BANK_DROPS_FOLDER):
            return set()

        files = set()
        for item in os.listdir(BANK_DROPS_FOLDER):
            if item.lower().endswith(".csv") and os.path.isfile(
                os.path.join(BANK_DROPS_FOLDER, item)
            ):
                files.add(item)
        return files

    except Exception as e:
        log_error(f"Error reading Bank_Drops folder: {e}")
        return set()


def check_for_new_csvs():
    """
    Check /Bank_Drops for new CSV files that haven't been processed yet.
    For each new CSV, parse transactions and create task files.

    Returns:
        int: Number of new CSV files processed.
    """
    try:
        current_files = get_csv_files()
        new_files = current_files - processed_files

        count = 0
        for csv_filename in sorted(new_files):
            filepath = os.path.join(BANK_DROPS_FOLDER, csv_filename)
            print(f"[NEW CSV] {csv_filename}")

            # Parse transactions
            transactions = parse_csv(filepath)

            if not transactions:
                print(f"  -> No valid transactions found in {csv_filename} (skipping)")
                processed_files.add(csv_filename)
                continue

            anomaly_count = sum(1 for t in transactions if t["is_anomaly"])
            print(f"  -> Parsed {len(transactions)} transaction(s), {anomaly_count} anomaly(ies)")

            # Create task file
            task_path = create_transaction_task(csv_filename, transactions)

            if task_path:
                print(f"  -> Created task: {os.path.basename(task_path)}")
                processed_files.add(csv_filename)

                # Log to System_Log
                anomaly_note = f", {anomaly_count} anomalies flagged" if anomaly_count else ""
                log_to_system_log(
                    "Bank Watcher",
                    f"Processed {csv_filename}: {len(transactions)} txns{anomaly_note}"
                )
                count += 1
            else:
                print(f"  -> Failed to create task for {csv_filename}")

        return count

    except Exception as e:
        log_error(f"Error during CSV check: {e}")
        return 0


# =============================================================================
# DEMO MODE
# =============================================================================

DEMO_CSV_CONTENT = """date,description,amount
2026-02-01,Client payment - Acme Corp,1500.00
2026-02-01,AWS hosting fee,-249.99
2026-02-02,Freelance invoice - Widget Co,3200.00
2026-02-03,Office supplies - Staples,-87.50
2026-02-03,Stripe payout - SaaS subscriptions,4750.00
2026-02-04,Contractor payment - Jane Doe,-2800.00
2026-02-05,Suspicious transfer - Unknown LLC,-6500.00
2026-02-05,Refund from vendor,125.00
2026-02-06,Client retainer - Beta Inc,950.00
2026-02-07,Software license - JetBrains,-189.00
"""


def generate_demo_csv():
    """
    Create a sample CSV in /Bank_Drops for demo/testing purposes.
    Includes a mix of normal transactions and anomalies.

    Returns:
        str: Path to the generated CSV, or None on failure.
    """
    try:
        date_stamp = datetime.now().strftime("%Y-%m-%d")
        demo_filename = f"demo_bank_statement_{date_stamp}.csv"
        demo_path = os.path.join(BANK_DROPS_FOLDER, demo_filename)

        # Don't overwrite if it already exists
        if os.path.exists(demo_path):
            print(f"[DEMO] Demo CSV already exists: {demo_filename}")
            return demo_path

        with open(demo_path, "w", encoding="utf-8", newline="") as f:
            f.write(DEMO_CSV_CONTENT.strip() + "\n")

        print(f"[DEMO] Generated sample CSV: {demo_filename}")
        print(f"[DEMO] Contains 10 transactions (3 anomalies > ${ANOMALY_THRESHOLD:,.2f})")
        return demo_path

    except Exception as e:
        log_error(f"Failed to generate demo CSV: {e}")
        return None


# =============================================================================
# INITIALIZATION AND MAIN LOOP
# =============================================================================

def initialize_watcher():
    """
    Initialize the Bank Watcher by setting up folders and recording
    existing CSV files (so they aren't re-processed on restart).

    Returns:
        bool: True if initialization was successful.
    """
    global processed_files, demo_generated

    print("[SETUP] Initializing Bank Watcher...")

    bank_ok = ensure_folder_exists(BANK_DROPS_FOLDER, "Bank_Drops")
    needs_action_ok = ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    logs_ok = ensure_folder_exists(LOGS_FOLDER, "Logs")
    done_ok = ensure_folder_exists(DONE_FOLDER, "Done")

    if not bank_ok or not needs_action_ok:
        log_error("Critical folders could not be created. Watcher may not function correctly.")

    # In demo mode, generate a sample CSV if /Bank_Drops is empty
    if DEMO_MODE and not demo_generated:
        existing = get_csv_files()
        if not existing:
            generate_demo_csv()
            demo_generated = True
        else:
            print(f"[SETUP] Found {len(existing)} existing CSV(s) in Bank_Drops")

    # Record already-existing files to avoid re-processing on restart
    # Comment out the next line to reprocess existing files on restart
    # processed_files = get_csv_files()
    # NOTE: We intentionally do NOT pre-populate processed_files so the
    #       demo CSV (or any existing CSVs) gets processed on first run.

    print(f"[SETUP] Anomaly threshold: ${ANOMALY_THRESHOLD:,.2f}")
    print(f"[SETUP] Parser: {'pandas' if HAS_PANDAS else 'stdlib csv'}")
    print("[SETUP] Initialization complete.")
    return True


def main():
    """
    Main function that runs the Bank Watcher loop.
    """
    print("=" * 55)
    print("Gold Tier AI Employee - Bank Transaction Watcher")
    print("=" * 55)
    print()

    initialize_watcher()

    print()
    print(f"Monitoring folder: {BANK_DROPS_FOLDER}")
    print(f"Tasks will be created in: {NEEDS_ACTION_FOLDER}")
    print(f"Errors will be logged to: {ERROR_LOG_FILE}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    mode_label = "DEMO" if DEMO_MODE else "LIVE"
    print(f"Mode: {mode_label}")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 55)

    # Log startup
    log_to_system_log(
        "Bank Watcher Started",
        f"Mode: {mode_label}, threshold: ${ANOMALY_THRESHOLD:,.2f}, checking every {CHECK_INTERVAL}s"
    )

    try:
        while True:
            try:
                new_count = check_for_new_csvs()

                if new_count > 0:
                    print(f"[BANK] Processed {new_count} new CSV file(s)")

                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                raise

            except Exception as e:
                log_error(f"Unexpected error in main loop: {e}")
                print("[RECOVERING] Waiting 10 seconds before retrying...")
                time.sleep(10)

    except KeyboardInterrupt:
        print()
        print("-" * 55)
        print("Bank Watcher stopped by user.")
        print(f"Total CSV files processed this session: {len(processed_files)}")
        log_to_system_log(
            "Bank Watcher Stopped",
            f"Processed {len(processed_files)} CSV file(s)"
        )


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()

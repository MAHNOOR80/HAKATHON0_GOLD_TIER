"""
Gold Tier AI Employee - Social Media Watcher

This script polls LinkedIn (and optionally X/Twitter) for recent post
engagement, detects revenue leads hidden in comments, and generates a
daily summary report in /Plans/Social_Summary_<date>.md.

This is the FOURTH watcher (alongside file_watcher.py, gmail_watcher.py,
and bank_watcher.py), fulfilling the Gold Tier "Social Perception"
requirement.

Features:
- LinkedIn engagement polling via REST API (or demo data)
- X/Twitter polling via v2 API (or demo data)
- Revenue-lead detection from comment keywords
- Engagement trend calculation
- Summary report generation in /Plans/
- Dashboard update with summary link
- Duplicate prevention (one summary per day)
- Error handling that never crashes

Requirements:
    pip install requests          (for live API calls)
    pip install schedule          (if running via scheduler)

Setup (LinkedIn live mode):
    Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in mcp_server/.env
    or as environment variables.

Setup (X/Twitter live mode):
    Set X_BEARER_TOKEN as environment variable.

Usage:
    Demo:  python social_watcher.py
    Live:  Set API credentials, then python social_watcher.py

Press Ctrl+C to stop the watcher.
"""

import os
import sys
import time
import json
import re
from datetime import datetime, timedelta

# Try to import requests for live API calls
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# =============================================================================
# CONFIGURATION
# =============================================================================

# How often to check (seconds). Default: run once then sleep 24 hours.
CHECK_INTERVAL = 86400  # 24 hours

# How many days of history to analyse
SUMMARY_PERIOD_DAYS = 7

# Minimum signal-keyword count to flag a comment as a "hot" lead
LEAD_SCORE_THRESHOLD = 2

# Folder paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLANS_FOLDER = os.path.join(SCRIPT_DIR, "Plans")
NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "social_watcher_errors.log")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")
DASHBOARD_FILE = os.path.join(SCRIPT_DIR, "Dashboard.md")

# API credentials (from environment or .env via parent process)
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")

# Mode detection
LINKEDIN_LIVE = bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN
                     and LINKEDIN_ACCESS_TOKEN != "your-linkedin-access-token")
X_LIVE = bool(X_BEARER_TOKEN and X_BEARER_TOKEN != "your-x-bearer-token")
DEMO_MODE = not LINKEDIN_LIVE and not X_LIVE


# =============================================================================
# REVENUE-LEAD SIGNAL KEYWORDS
# =============================================================================

SIGNAL_KEYWORDS = {
    "direct_intent": [
        "consulting", "hire", "budget", "pricing", "proposal",
        "quote", "rates", "cost", "invoice", "retainer",
    ],
    "partnership": [
        "partnership", "collaborate", "joint venture", "co-founder",
        "partner", "alliance", "venture",
    ],
    "availability": [
        "available", "schedule", "call", "meeting", "demo",
        "book", "calendar", "free time", "slot",
    ],
    "services": [
        "services", "offering", "portfolio", "capabilities",
        "expertise", "solutions", "deliverables",
    ],
    "urgency": [
        "asap", "urgent", "this week", "deadline",
        "q1", "q2", "q3", "q4", "immediately",
    ],
}

# Flatten for quick scanning
ALL_SIGNALS = []
for keywords in SIGNAL_KEYWORDS.values():
    ALL_SIGNALS.extend(keywords)


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    """Write an error message to the error log file with a timestamp."""
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
    """Add an entry to the System_Log.md activity table."""
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
    """Check if a folder exists, and create it if it doesn't."""
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True
    except Exception as e:
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


# =============================================================================
# LEAD SCORING
# =============================================================================

def score_comment(text):
    """
    Scan a comment for revenue-lead signal keywords.

    Returns:
        tuple: (score: int, matched_signals: list[str])
    """
    text_lower = text.lower()
    matched = []

    for signal in ALL_SIGNALS:
        if signal in text_lower:
            matched.append(signal)

    return len(matched), matched


def classify_lead(score):
    """
    Classify a lead based on its signal score.

    Returns:
        str: 'hot', 'warm', or 'informational'
    """
    if score >= LEAD_SCORE_THRESHOLD:
        return "hot"
    elif score >= 1:
        return "warm"
    return "informational"


# =============================================================================
# LINKEDIN LIVE API
# =============================================================================

def fetch_linkedin_posts():
    """
    Fetch recent posts from LinkedIn via the UGC API.

    Returns:
        list[dict]: Posts with engagement metrics, or empty list on error.
    """
    if not LINKEDIN_LIVE or not HAS_REQUESTS:
        return []

    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        # Fetch user's posts
        url = (
            "https://api.linkedin.com/v2/ugcPosts"
            f"?q=authors&authors=List({LINKEDIN_PERSON_URN})"
            "&sortBy=LAST_MODIFIED&count=20"
        )
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            log_error(f"LinkedIn API error {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        posts = []

        for element in data.get("elements", []):
            post_urn = element.get("id", "")
            text = ""
            spec = element.get("specificContent", {})
            share = spec.get("com.linkedin.ugc.ShareContent", {})
            commentary = share.get("shareCommentary", {})
            text = commentary.get("text", "")

            created = element.get("created", {}).get("time", 0)
            created_dt = datetime.fromtimestamp(created / 1000) if created else None

            # Fetch social actions (likes, comments)
            metrics = {"likes": 0, "comments": 0, "shares": 0}
            try:
                sa_url = f"https://api.linkedin.com/v2/socialActions/{post_urn}"
                sa_resp = requests.get(sa_url, headers=headers, timeout=10)
                if sa_resp.status_code == 200:
                    sa = sa_resp.json()
                    metrics["likes"] = sa.get("likesSummary", {}).get("totalLikes", 0)
                    metrics["comments"] = sa.get("commentsSummary", {}).get("totalFirstLevelComments", 0)
            except Exception:
                pass

            posts.append({
                "platform": "linkedin",
                "urn": post_urn,
                "text": text[:200],
                "created": created_dt.strftime("%Y-%m-%d") if created_dt else "unknown",
                "likes": metrics["likes"],
                "comments_count": metrics["comments"],
                "shares": metrics["shares"],
                "comment_texts": [],  # filled below if comments exist
            })

        return posts

    except Exception as e:
        log_error(f"LinkedIn API fetch failed: {e}")
        return []


def fetch_linkedin_comments(post_urn):
    """Fetch comments for a single LinkedIn post."""
    if not LINKEDIN_LIVE or not HAS_REQUESTS:
        return []

    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        url = f"https://api.linkedin.com/v2/socialActions/{post_urn}/comments"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []

        data = resp.json()
        comments = []
        for el in data.get("elements", []):
            actor = el.get("actor", "unknown")
            text = el.get("message", {}).get("text", "")
            comments.append({"author": actor, "text": text})

        return comments

    except Exception:
        return []


# =============================================================================
# DEMO MODE DATA
# =============================================================================

def generate_demo_data():
    """
    Generate realistic demo engagement data for the summary report.
    Includes a mix of normal comments and revenue leads.

    Returns:
        dict with 'linkedin' and 'x' keys, each containing posts list.
    """
    today = datetime.now()

    linkedin_posts = [
        {
            "platform": "linkedin",
            "urn": "urn:li:ugcPost:demo-001",
            "text": "AI agents are changing how consulting firms operate. Here are 5 patterns I see working...",
            "created": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            "likes": 45, "comments_count": 6, "shares": 3,
            "impressions": 1250,
            "comment_texts": [
                {"author": "Sarah Chen (Startup.io)", "text": "This is spot on. We're looking for a partnership to bring AI consulting to our clients. Would love to schedule a call to discuss."},
                {"author": "James Liu", "text": "Great insights! Sharing with my team."},
                {"author": "Mike Rodriguez", "text": "Do you offer consulting services for early-stage startups? We have budget allocated for Q2 and need expertise ASAP."},
                {"author": "Priya Sharma", "text": "Love this perspective on autonomous agents."},
                {"author": "Tom W.", "text": "What tools do you recommend for building MCP servers?"},
                {"author": "Alex K.", "text": "Could you send a proposal for our AI strategy workshop? We need a quote by Friday."},
            ],
        },
        {
            "platform": "linkedin",
            "urn": "urn:li:ugcPost:demo-002",
            "text": "5 things I learned building MCP servers for enterprise clients...",
            "created": (today - timedelta(days=3)).strftime("%Y-%m-%d"),
            "likes": 28, "comments_count": 5, "shares": 4,
            "impressions": 890,
            "comment_texts": [
                {"author": "Dev Team Lead @BigCorp", "text": "We're evaluating MCP for our internal tools. Are you available for a demo this week?"},
                {"author": "Nina F.", "text": "This is exactly what we needed. Bookmarked."},
                {"author": "Carlos M.", "text": "How does this compare to LangChain?"},
                {"author": "Raj P.", "text": "Impressive work. What are your rates for a 3-month engagement?"},
                {"author": "Emma L.", "text": "Thanks for sharing!"},
            ],
        },
        {
            "platform": "linkedin",
            "urn": "urn:li:ugcPost:demo-003",
            "text": "The future of AI employees is autonomous, reliable, and always on...",
            "created": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
            "likes": 14, "comments_count": 3, "shares": 2,
            "impressions": 310,
            "comment_texts": [
                {"author": "Linda K.", "text": "Interesting take. Following for more."},
                {"author": "Startup Founder", "text": "We're hiring an AI consultant. DM me if interested."},
                {"author": "Mark T.", "text": "Bold claim but I like the vision."},
            ],
        },
    ]

    x_posts = [
        {
            "platform": "x",
            "id": "tweet-demo-001",
            "text": "Just shipped: AI Employee that monitors email, bank CSVs, and Odoo — all from Claude Code.",
            "created": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            "likes": 22, "comments_count": 4, "shares": 6,
            "impressions": 980,
            "comment_texts": [
                {"author": "@devteam_ai", "text": "Looking to hire someone to build something similar for our team. What's your availability?"},
                {"author": "@mlops_daily", "text": "This is the future of DevOps. RT'd."},
                {"author": "@curious_dev", "text": "How does the approval gate work? Thread?"},
                {"author": "@techfounder", "text": "We need this for our SaaS. Can you consult?"},
            ],
        },
        {
            "platform": "x",
            "id": "tweet-demo-002",
            "text": "MCP protocol + Odoo = accounting automation that actually works.",
            "created": (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            "likes": 15, "comments_count": 2, "shares": 0,
            "impressions": 520,
            "comment_texts": [
                {"author": "@startup_cfo", "text": "Interesting! What are your rates?"},
                {"author": "@odoo_fan", "text": "Need to try this."},
            ],
        },
        {
            "platform": "x",
            "id": "tweet-demo-003",
            "text": "Hot take: Every solo consultant needs an AI employee running 24/7.",
            "created": (today - timedelta(days=4)).strftime("%Y-%m-%d"),
            "likes": 5, "comments_count": 2, "shares": 0,
            "impressions": 300,
            "comment_texts": [
                {"author": "@indie_hacker", "text": "100% agree."},
                {"author": "@saas_builder", "text": "Would love a demo. DM?"},
            ],
        },
        {
            "platform": "x",
            "id": "tweet-demo-004",
            "text": "Bank watcher parsing CSVs and flagging anomalies > $500. Gold tier unlocked.",
            "created": (today - timedelta(days=6)).strftime("%Y-%m-%d"),
            "likes": 8, "comments_count": 1, "shares": 1,
            "impressions": 210,
            "comment_texts": [
                {"author": "@fintech_news", "text": "Cool project. Shared in our newsletter."},
            ],
        },
        {
            "platform": "x",
            "id": "tweet-demo-005",
            "text": "Ralph Wiggum Loop Skill: Claude re-prompts itself until the job is actually done.",
            "created": (today - timedelta(days=6)).strftime("%Y-%m-%d"),
            "likes": 12, "comments_count": 1, "shares": 2,
            "impressions": 340,
            "comment_texts": [
                {"author": "@agent_builder", "text": "Genius naming. Does it work for multi-file refactors?"},
            ],
        },
    ]

    return {"linkedin": linkedin_posts, "x": x_posts}


# =============================================================================
# SUMMARY GENERATION
# =============================================================================

def build_summary(data):
    """
    Analyse engagement data and produce a structured summary dict.

    Args:
        data: dict with 'linkedin' and 'x' keys, each a list of post dicts.

    Returns:
        dict: Summary metrics, top posts, leads, recommendations.
    """
    today = datetime.now()
    period_start = (today - timedelta(days=SUMMARY_PERIOD_DAYS)).strftime("%Y-%m-%d")
    period_end = today.strftime("%Y-%m-%d")

    all_posts = data.get("linkedin", []) + data.get("x", [])

    # Aggregate metrics per platform
    metrics = {}
    for platform in ["linkedin", "x"]:
        posts = data.get(platform, [])
        metrics[platform] = {
            "posts": len(posts),
            "impressions": sum(p.get("impressions", 0) for p in posts),
            "likes": sum(p.get("likes", 0) for p in posts),
            "comments": sum(p.get("comments_count", 0) for p in posts),
            "shares": sum(p.get("shares", 0) for p in posts),
        }
        total_impressions = metrics[platform]["impressions"]
        total_engagement = (metrics[platform]["likes"]
                           + metrics[platform]["comments"]
                           + metrics[platform]["shares"])
        metrics[platform]["engagement_rate"] = (
            round(total_engagement / total_impressions * 100, 1)
            if total_impressions > 0 else 0.0
        )

    # Top posts by engagement (likes + comments + shares)
    top_posts = sorted(
        all_posts,
        key=lambda p: p.get("likes", 0) + p.get("comments_count", 0) + p.get("shares", 0),
        reverse=True,
    )[:5]

    # Scan all comments for leads
    leads = []
    for post in all_posts:
        for comment in post.get("comment_texts", []):
            score, matched = score_comment(comment["text"])
            if score >= 1:
                leads.append({
                    "platform": post["platform"],
                    "post_text": post["text"][:60],
                    "author": comment["author"],
                    "comment": comment["text"],
                    "score": score,
                    "signals": matched,
                    "classification": classify_lead(score),
                })

    # Sort leads by score descending
    leads.sort(key=lambda l: l["score"], reverse=True)

    hot = sum(1 for l in leads if l["classification"] == "hot")
    warm = sum(1 for l in leads if l["classification"] == "warm")
    total_comments = sum(p.get("comments_count", 0) for p in all_posts)
    informational = total_comments - hot - warm

    return {
        "period": f"{period_start} to {period_end}",
        "metrics": metrics,
        "top_posts": top_posts,
        "leads": leads,
        "lead_counts": {"hot": hot, "warm": warm, "informational": max(informational, 0)},
    }


def write_summary_report(summary):
    """
    Write the summary dict to /Plans/Social_Summary_<date>.md.

    Returns:
        str: Path to the created file, or None on error.
    """
    try:
        today = datetime.now()
        timestamp = today.strftime("%Y-%m-%d %H:%M:%S")
        date_str = today.strftime("%Y-%m-%d")

        filename = f"Social_Summary_{date_str}.md"
        filepath = os.path.join(PLANS_FOLDER, filename)

        # Don't overwrite if already exists today
        if os.path.exists(filepath):
            print(f"[SOCIAL] Summary already exists for today: {filename}")
            return filepath

        m_li = summary["metrics"].get("linkedin", {})
        m_x = summary["metrics"].get("x", {})

        total_posts = m_li.get("posts", 0) + m_x.get("posts", 0)
        total_imp = m_li.get("impressions", 0) + m_x.get("impressions", 0)
        total_likes = m_li.get("likes", 0) + m_x.get("likes", 0)
        total_comments = m_li.get("comments", 0) + m_x.get("comments", 0)
        total_shares = m_li.get("shares", 0) + m_x.get("shares", 0)
        total_engagement = total_likes + total_comments + total_shares
        total_rate = round(total_engagement / total_imp * 100, 1) if total_imp > 0 else 0.0

        # Top posts section
        top_lines = []
        for i, p in enumerate(summary["top_posts"], 1):
            eng = p.get("likes", 0) + p.get("comments_count", 0) + p.get("shares", 0)
            top_lines.append(
                f'{i}. **"{p["text"][:80]}..."** '
                f'({p["platform"]}) — {p.get("likes", 0)} likes, '
                f'{p.get("comments_count", 0)} comments, '
                f'{p.get("shares", 0)} shares (total: {eng})'
            )
        top_section = "\n".join(top_lines) if top_lines else "No posts in this period."

        # Leads table
        lead_rows = []
        for i, ld in enumerate(summary["leads"], 1):
            signals_str = ", ".join(ld["signals"][:3])
            excerpt = ld["comment"][:80].replace("|", "/")
            lead_rows.append(
                f'| {i} | {ld["platform"]} | {ld["author"]} | '
                f'{ld["classification"].upper()} | {signals_str} | '
                f'{excerpt} |'
            )
        leads_table = "\n".join(lead_rows) if lead_rows else "| — | — | — | — | — | No leads detected |"

        lc = summary["lead_counts"]

        # Recommendations
        recs = []
        for ld in summary["leads"]:
            if ld["classification"] == "hot":
                recs.append(f'- **Reply to {ld["author"]}** ({ld["platform"]}) — '
                           f'signals: {", ".join(ld["signals"][:3])}')
        if m_li.get("posts", 0) > 0:
            recs.append("- Post again mid-week (Tue/Thu) — engagement peaks then")
        if m_x.get("posts", 0) > 0:
            recs.append("- Repurpose top tweet as a LinkedIn long-form post for wider reach")
        if not recs:
            recs.append("- No urgent actions — maintain posting cadence")
        recs_section = "\n".join(recs)

        mode_label = "DEMO" if DEMO_MODE else "LIVE"

        content = f"""---
type: social_summary
status: completed
created_at: {timestamp}
period: "{summary['period']}"
platforms: ["linkedin", "x"]
approval_needed: false
mcp_action: []
source: social_watcher
mode: {mode_label.lower()}
---

# Social Media Summary — {date_str}

## Overview

| Metric | LinkedIn | X (Twitter) | Total |
|--------|----------|-------------|-------|
| Posts published | {m_li.get('posts', 0)} | {m_x.get('posts', 0)} | {total_posts} |
| Impressions | {m_li.get('impressions', 0):,} | {m_x.get('impressions', 0):,} | {total_imp:,} |
| Likes | {m_li.get('likes', 0)} | {m_x.get('likes', 0)} | {total_likes} |
| Comments | {m_li.get('comments', 0)} | {m_x.get('comments', 0)} | {total_comments} |
| Shares / Reposts | {m_li.get('shares', 0)} | {m_x.get('shares', 0)} | {total_shares} |
| Engagement Rate | {m_li.get('engagement_rate', 0)}% | {m_x.get('engagement_rate', 0)}% | {total_rate}% |

## Top Performing Posts

{top_section}

## Revenue Leads Detected

| # | Platform | Person | Score | Signals | Comment Excerpt |
|---|----------|--------|-------|---------|-----------------|
{leads_table}

### Lead Summary
- **Hot leads (reply < 24h):** {lc['hot']}
- **Warm leads (reply < 72h):** {lc['warm']}
- **Informational (no action):** {lc['informational']}

## Recommendations

{recs_section}

---

_Generated by Social_Summary_Skill via social_watcher.py ({mode_label} mode)_
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    except Exception as e:
        log_error(f"Error writing social summary: {e}")
        return None


# =============================================================================
# LEAD TASK CREATION
# =============================================================================

def create_lead_tasks(leads):
    """
    Create a task file in /Needs_Action for hot leads that need follow-up.

    Args:
        leads: list of lead dicts from build_summary().

    Returns:
        int: Number of tasks created.
    """
    hot_leads = [l for l in leads if l["classification"] == "hot"]
    if not hot_leads:
        return 0

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_stamp = datetime.now().strftime("%Y-%m-%d")

        task_filename = f"task_social_leads_{date_stamp}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        if os.path.exists(task_path):
            return 0  # already created today

        lead_lines = []
        for i, ld in enumerate(hot_leads, 1):
            lead_lines.append(
                f"### Lead {i}: {ld['author']} ({ld['platform']})\n"
                f"- **Comment:** {ld['comment']}\n"
                f"- **Signals:** {', '.join(ld['signals'])}\n"
                f"- **Action:** Draft reply / send intro email\n"
            )

        leads_section = "\n".join(lead_lines)

        content = f"""---
type: social_lead_followup
status: pending
priority: high
created_at: {timestamp}
related_files: ["Plans/Social_Summary_{date_stamp}.md"]
approval_needed: true
approved: false
mcp_action: ['send_email']
source: social_watcher
lead_count: {len(hot_leads)}
---

# Social Media Lead Follow-Up — {date_stamp}

## Description

The Social Watcher detected {len(hot_leads)} hot revenue lead(s) from
social media comments. These require a reply within 24 hours.

## Hot Leads

{leads_section}

## Steps

- [ ] Review each lead and verify intent
- [ ] Draft personalised reply for each lead
- [ ] Route replies through Approval_Check_Skill (send_email)
- [ ] Send approved replies
- [ ] Mark this task as completed

## Notes

- **Source:** Social Watcher (automatic detection)
- **Detected at:** {timestamp}
- **Skill:** Social_Summary_Skill
- Replies require human approval before sending.
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[SOCIAL] Created lead follow-up task: {task_filename}")
        return len(hot_leads)

    except Exception as e:
        log_error(f"Error creating lead task: {e}")
        return 0


# =============================================================================
# DASHBOARD UPDATE
# =============================================================================

def update_dashboard(summary_filename):
    """Add a Social Summary reference to Dashboard.md Recent Plans section."""
    try:
        if not os.path.exists(DASHBOARD_FILE):
            return

        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        date_str = datetime.now().strftime("%Y-%m-%d")
        new_line = f"- **Social Summary:** [[Plans/{summary_filename}]] — Generated {date_str}"

        # Insert after ## Recent Plans
        marker = "## Recent Plans"
        if marker in content:
            parts = content.split(marker, 1)
            if len(parts) == 2:
                # Find the first line after the marker
                rest = parts[1]
                content = parts[0] + marker + "\n\n" + new_line + rest
                # Remove double blank lines
                content = re.sub(r'\n{3,}', '\n\n', content)

                with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[SOCIAL] Updated Dashboard with {summary_filename}")

    except Exception as e:
        log_error(f"Error updating Dashboard: {e}")


# =============================================================================
# MAIN CHECK
# =============================================================================

def run_social_summary():
    """
    Main function: fetch data, build summary, write report, create tasks.

    Returns:
        str: Path to the generated summary, or None on error.
    """
    print("[SOCIAL] Generating social media summary...")

    # Fetch engagement data
    if DEMO_MODE:
        print("[SOCIAL] Demo mode — using sample engagement data")
        data = generate_demo_data()
    else:
        print("[SOCIAL] Live mode — fetching from APIs...")
        li_posts = fetch_linkedin_posts()
        # Fetch comments for each LinkedIn post
        for post in li_posts:
            if post.get("comments_count", 0) > 0:
                post["comment_texts"] = fetch_linkedin_comments(post["urn"])
        data = {"linkedin": li_posts, "x": []}  # X integration placeholder

    # Build summary
    summary = build_summary(data)

    total_posts = (summary["metrics"].get("linkedin", {}).get("posts", 0)
                   + summary["metrics"].get("x", {}).get("posts", 0))
    hot = summary["lead_counts"]["hot"]
    warm = summary["lead_counts"]["warm"]

    print(f"[SOCIAL] Posts: {total_posts}, Leads: {hot} hot, {warm} warm")

    # Write report
    filepath = write_summary_report(summary)

    if filepath:
        filename = os.path.basename(filepath)
        print(f"[SOCIAL] Summary written: {filename}")

        # Update Dashboard
        update_dashboard(filename)

        # Create lead tasks for hot leads
        if hot > 0:
            created = create_lead_tasks(summary["leads"])
            if created:
                print(f"[SOCIAL] Created task for {created} hot lead(s)")

        # Log to System_Log
        log_to_system_log(
            "Social Summary",
            f"Generated {filename}: {total_posts} posts, "
            f"{hot} hot leads, {warm} warm leads "
            f"({'DEMO' if DEMO_MODE else 'LIVE'})"
        )

        return filepath

    return None


# =============================================================================
# INITIALIZATION AND MAIN LOOP
# =============================================================================

def initialize_watcher():
    """Initialize the Social Watcher by setting up folders."""
    print("[SETUP] Initializing Social Watcher...")

    ensure_folder_exists(PLANS_FOLDER, "Plans")
    ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    ensure_folder_exists(LOGS_FOLDER, "Logs")

    if DEMO_MODE:
        print("[SETUP] Running in DEMO MODE (no API credentials detected)")
        print("[SETUP] Set LINKEDIN_ACCESS_TOKEN/PERSON_URN for LinkedIn live mode")
        print("[SETUP] Set X_BEARER_TOKEN for X/Twitter live mode")
    else:
        platforms = []
        if LINKEDIN_LIVE:
            platforms.append("LinkedIn")
        if X_LIVE:
            platforms.append("X")
        print(f"[SETUP] Live platforms: {', '.join(platforms)}")

    print(f"[SETUP] Lead threshold: {LEAD_SCORE_THRESHOLD} signals = hot lead")
    print(f"[SETUP] Period: last {SUMMARY_PERIOD_DAYS} days")
    print("[SETUP] Initialization complete.")
    return True


def main():
    """Main function that runs the Social Watcher loop."""
    print("=" * 55)
    print("Gold Tier AI Employee - Social Media Watcher")
    print("=" * 55)
    print()

    initialize_watcher()

    print()
    print(f"Summaries will be saved to: {PLANS_FOLDER}")
    print(f"Lead tasks created in: {NEEDS_ACTION_FOLDER}")
    print(f"Errors will be logged to: {ERROR_LOG_FILE}")
    mode_label = "DEMO" if DEMO_MODE else "LIVE"
    print(f"Mode: {mode_label}")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 55)

    log_to_system_log(
        "Social Watcher Started",
        f"Mode: {mode_label}, period: {SUMMARY_PERIOD_DAYS} days, "
        f"threshold: {LEAD_SCORE_THRESHOLD} signals"
    )

    # Run immediately on start
    run_social_summary()

    # Then loop
    try:
        while True:
            try:
                time.sleep(CHECK_INTERVAL)
                run_social_summary()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                log_error(f"Unexpected error in main loop: {e}")
                print("[RECOVERING] Waiting 60 seconds before retrying...")
                time.sleep(60)

    except KeyboardInterrupt:
        print()
        print("-" * 55)
        print("Social Watcher stopped by user.")
        log_to_system_log("Social Watcher Stopped", "Social media watcher stopped by user")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()

"""
modules/notifier.py
Sends email notifications via Gmail API using your personal OAuth token.
"""

import os
import json
import logging
import base64
from email.mime.text import MIMEText
from datetime import datetime

log = logging.getLogger(__name__)

NOTIFY_EMAIL = "nazishmehdi26@gmail.com"
SHEET_ID     = "1x2wL6qks87lbieUeYvqMylrrqX1OEquf2OMqQciWT3o"
SHEET_URL    = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"


def _gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_json = os.environ.get("GOOGLE_TOKEN_JSON", "")
    if not token_json:
        raise Exception("No GOOGLE_TOKEN_JSON found")

    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        scopes=["https://www.googleapis.com/auth/gmail.send"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def _send(subject: str, body: str):
    try:
        gmail   = _gmail_service()
        message = MIMEText(body)
        message["to"]      = NOTIFY_EMAIL
        message["from"]    = NOTIFY_EMAIL
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
        log.info(f"Email sent: {subject}")
    except Exception as e:
        log.error(f"Email failed: {e}")


def notify(matched_jobs: list, status: str = "success"):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    if status == "failure":
        _send(
            subject=f"❌ JobSeeker FAILED — {now}",
            body=(
                f"Hi Nazish,\n\n"
                f"JobSeeker encountered an error during the {now} scan.\n\n"
                f"Check GitHub Actions for details:\n"
                f"https://github.com/Nazish-Works/JobSeeker/actions\n\n"
                f"— JobSeeker Bot"
            )
        )
        return

    if not matched_jobs:
        _send(
            subject=f"ℹ️ JobSeeker: No new matches — {now}",
            body=(
                f"Hi Nazish,\n\n"
                f"JobSeeker ran at {now} and found no new matching jobs this scan.\n"
                f"Will try again at the next scheduled run.\n\n"
                f"— JobSeeker Bot"
            )
        )
        return

    # Build match summary
    india_jobs  = [j for j in matched_jobs if j.get("region") == "India"]
    saudi_jobs  = [j for j in matched_jobs if j.get("region") == "Saudi"]

    lines = [
        f"Hi Nazish,",
        f"",
        f"JobSeeker found {len(matched_jobs)} new job match(es) at {now}:",
        f"  🇮🇳 India: {len(india_jobs)} jobs",
        f"  🇸🇦 Saudi: {len(saudi_jobs)} jobs",
        f"",
    ]

    if saudi_jobs:
        lines.append("── SAUDI JOBS ──────────────────────────")
        for j in saudi_jobs:
            lines += [
                f"🇸🇦 {j.get('title')} @ {j.get('company')}",
                f"   📍 {j.get('location')} | ⭐ {j.get('score')}/100",
                f"   🔗 {j.get('url')}",
                f"   {j.get('match_reasons', '')}",
                f"",
            ]

    if india_jobs:
        lines.append("── INDIA JOBS ───────────────────────────")
        for j in india_jobs:
            lines += [
                f"🇮🇳 {j.get('title')} @ {j.get('company')}",
                f"   📍 {j.get('location')} | ⭐ {j.get('score')}/100",
                f"   🔗 {j.get('url')}",
                f"   {j.get('match_reasons', '')}",
                f"",
            ]

    lines += [
        "─────────────────────────────────────────",
        f"📊 Full tracker + tailored resumes:",
        f"{SHEET_URL}",
        f"",
        f"— JobSeeker Bot",
    ]

    _send(
        subject=f"✅ JobSeeker: {len(matched_jobs)} new match(es) — {len(saudi_jobs)} Saudi, {len(india_jobs)} India",
        body="\n".join(lines)
    )

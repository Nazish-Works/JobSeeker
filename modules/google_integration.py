"""
modules/google_integration.py
Uses YOUR Google account token (not service account) to:
  - Save tailored resumes as PDFs to your Google Drive folder
  - Log jobs to Google Sheets with daily tabs
"""

import os
import io
import json
import logging
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

DRIVE_FOLDER_ID = "1x1xBlIHRfaRgBPEhtATuggXC0RjBxGMR"
SHEET_ID        = "1x2wL6qks87lbieUeYvqMylrrqX1OEquf2OMqQciWT3o"
NOTIFY_EMAIL    = "nazishmehdi26@gmail.com"

SHEET_HEADERS = [
    "Time", "Job ID", "Portal", "Region", "Job Title", "Company",
    "Location", "Score", "Match Reason", "Job URL",
    "Resume (Drive)", "Cover Note", "Status", "Applied Date", "Notes"
]


def _get_creds():
    token_json = os.environ.get("GOOGLE_TOKEN_JSON", "")
    if not token_json:
        if os.path.exists("token.json"):
            with open("token.json") as f:
                token_json = f.read()
        else:
            raise Exception("No GOOGLE_TOKEN_JSON secret found!")

    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        log.info("Google token refreshed successfully")

    return creds


def _drive_service():
    return build("drive", "v3", credentials=_get_creds())

def _sheets_service():
    return build("sheets", "v4", credentials=_get_creds())


# ── Google Drive — save as PDF ────────────────────────────────────────────────

def save_resume_to_drive(job_id: str, company: str, title: str,
                          region: str, resume_text: str) -> str:
    try:
        drive = _drive_service()

        date_str   = datetime.utcnow().strftime("%d %b %Y")
        safe_co    = company.replace("/", "-").replace("\\", "-").strip()[:40]
        safe_title = title.replace("/", "-").replace("\\", "-").strip()[:50]
        filename   = f"{date_str} — {safe_title} — {safe_co} [{region}].txt"

        # Upload as plain text (can be opened and copy-pasted into Word/PDF)
        file_bytes = resume_text.encode("utf-8")
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype="text/plain",
            resumable=False
        )
        file_meta = {
            "name": filename,
            "parents": [DRIVE_FOLDER_ID]
        }
        created = drive.files().create(
            body=file_meta,
            media_body=media,
            fields="id,webViewLink"
        ).execute()

        url = created.get("webViewLink", "")
        log.info(f"Resume saved to Drive: {filename} → {url}")
        return url
    except Exception as e:
        log.error(f"Drive upload failed: {e}")
        return ""


# ── Google Sheets — one tab per day ──────────────────────────────────────────

def _get_or_create_tab(sheets, tab_name: str) -> int:
    meta = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == tab_name:
            return sheet["properties"]["sheetId"]

    result = sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
    ).execute()
    new_sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]}
    ).execute()

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"requests": [{
            "repeatCell": {
                "range": {"sheetId": new_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold"
            }
        }]}
    ).execute()

    log.info(f"Created new tab: {tab_name}")
    return new_sheet_id


def log_job_to_sheet(job, relevance_data: dict, drive_url: str, cover_note: str):
    try:
        sheets = _sheets_service()
        tab_name = datetime.utcnow().strftime("%-d %b %Y")
        _get_or_create_tab(sheets, tab_name)

        row = [
            datetime.utcnow().strftime("%H:%M UTC"),
            job.job_id,
            job.portal,
            job.region,
            job.title,
            job.company,
            job.location,
            relevance_data.get("score", ""),
            relevance_data.get("match_reasons", ""),
            job.url,
            drive_url if drive_url else "",
            cover_note[:300] if cover_note else "",
            "New",
            "",
            "",
        ]

        sheets.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A:A",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
        log.info(f"Logged [{tab_name}]: {job.title} @ {job.company}")
    except Exception as e:
        log.error(f"Sheets logging failed: {e}")


def send_notification_email(new_jobs: list, recipient: str):
    if not new_jobs:
        return
    log.info(f"=== {len(new_jobs)} NEW JOB MATCHES ===")
    for j in new_jobs:
        log.info(
            f"[{j.get('region','?')}] {j.get('title','?')} @ "
            f"{j.get('company','?')} — Score: {j.get('score','?')}/100"
        )
    log.info(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")

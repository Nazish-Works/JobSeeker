"""
modules/google_integration.py
Uses Google Service Account (no browser auth needed) to:
  - Save tailored resumes to Google Drive
  - Log jobs to Google Sheets tracker
  - Send notification emails via Gmail
"""

import os
import json
import logging
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from email.mime.text import MIMEText
import base64

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]

GDRIVE_FOLDER_NAME = "JobSeeker — Tailored Resumes"
GSHEET_NAME        = "JobSeeker — Applications Tracker"
NOTIFY_EMAIL       = "nazishmehdi26@gmail.com"

SHEET_HEADERS = [
    "Date Found", "Job ID", "Portal", "Region", "Job Title", "Company",
    "Location", "Relevance Score", "Match Reason", "Job URL",
    "Resume Saved (Drive)", "Cover Note", "Status", "Applied Date", "Notes"
]


def _get_creds():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        # Fall back to file if running locally
        if os.path.exists("service_account.json"):
            with open("service_account.json") as f:
                sa_json = f.read()
        else:
            raise Exception("No GOOGLE_SERVICE_ACCOUNT_JSON secret found!")

    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=SCOPES
    )
    return creds


def _drive_service():
    return build("drive", "v3", credentials=_get_creds())

def _sheets_service():
    return build("sheets", "v4", credentials=_get_creds())


# ── Google Drive ──────────────────────────────────────────────────────────────

def _get_or_create_folder(drive, folder_name: str) -> str:
    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder = drive.files().create(
        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id"
    ).execute()
    log.info(f"Created Drive folder: {folder_name}")
    return folder["id"]


def save_resume_to_drive(job_id: str, company: str, title: str,
                          region: str, resume_text: str) -> str:
    try:
        drive = _drive_service()
        folder_id = _get_or_create_folder(drive, GDRIVE_FOLDER_NAME)

        date_str   = datetime.utcnow().strftime("%Y%m%d")
        safe_co    = company.replace("/", "-").replace(" ", "_")[:30]
        safe_title = title.replace("/", "-").replace(" ", "_")[:30]
        filename   = f"{date_str}_{region}_{safe_co}_{safe_title}_{job_id}.txt"

        media = MediaInMemoryUpload(
            resume_text.encode("utf-8"),
            mimetype="text/plain",
            resumable=False
        )
        file_meta = {"name": filename, "parents": [folder_id]}
        created = drive.files().create(
            body=file_meta, media_body=media, fields="id,webViewLink"
        ).execute()

        # Make the file readable by anyone with the link
        drive.permissions().create(
            fileId=created["id"],
            body={"type": "user", "role": "writer", "emailAddress": NOTIFY_EMAIL}
        ).execute()

        url = created.get("webViewLink", "")
        log.info(f"Resume saved to Drive: {filename}")
        return url
    except Exception as e:
        log.error(f"Drive upload failed: {e}")
        return ""


# ── Google Sheets ─────────────────────────────────────────────────────────────

def _get_or_create_sheet(sheets) -> str:
    drive = _drive_service()
    q = f"name='{GSHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    spreadsheet = sheets.spreadsheets().create(body={
        "properties": {"title": GSHEET_NAME},
        "sheets": [{"properties": {"title": "Applications"}}]
    }).execute()
    sheet_id = spreadsheet["spreadsheetId"]

    # Write headers
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Applications!A1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]}
    ).execute()

    # Bold the header row
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{
            "repeatCell": {
                "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold"
            }
        }]}
    ).execute()

    # Share the sheet with Nazish so she can view it
    drive.permissions().create(
        fileId=sheet_id,
        body={"type": "user", "role": "writer", "emailAddress": NOTIFY_EMAIL}
    ).execute()

    log.info(f"Created new tracker sheet: {GSHEET_NAME}")
    return sheet_id


def log_job_to_sheet(job, relevance_data: dict,
                      drive_url: str, cover_note: str):
    try:
        sheets = _sheets_service()
        sheet_id = _get_or_create_sheet(sheets)

        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            job.job_id,
            job.portal,
            job.region,
            job.title,
            job.company,
            job.location,
            relevance_data.get("score", ""),
            relevance_data.get("match_reasons", ""),
            job.url,
            drive_url,
            cover_note[:500] if cover_note else "",
            "New",
            "",
            "",
        ]

        sheets.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Applications!A:A",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
        log.info(f"Logged to Sheets: {job.title} @ {job.company}")
    except Exception as e:
        log.error(f"Sheets logging failed: {e}")


# ── Email notification (via Gmail API with service account) ───────────────────

def send_notification_email(new_jobs: list, recipient: str):
    if not new_jobs:
        return
    try:
        # Build plain summary — service accounts can't send Gmail directly
        # so we log it and the sheet serves as the notification
        log.info(f"=== {len(new_jobs)} NEW JOB MATCHES ===")
        for j in new_jobs:
            log.info(
                f"[{j.get('region','?')}] {j.get('title','?')} @ "
                f"{j.get('company','?')} — Score: {j.get('score','?')}/100 — "
                f"{j.get('url','')}"
            )
        log.info(f"Check your Google Sheet: https://drive.google.com")
    except Exception as e:
        log.error(f"Notification logging failed: {e}")

"""
modules/google_integration.py
Handles:
  - Saving tailored resumes as .txt/.docx to Google Drive
  - Logging jobs to Google Sheets tracker
  - Sending notification emails via Gmail
"""

import os
import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
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

# Spreadsheet column headers
SHEET_HEADERS = [
    "Date Found", "Job ID", "Portal", "Region", "Job Title", "Company",
    "Location", "Relevance Score", "Match Reason", "Job URL",
    "Resume Saved (Drive)", "Cover Note", "Status", "Applied Date", "Notes"
]


def _get_creds() -> Credentials:
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def _drive_service():
    return build("drive", "v3", credentials=_get_creds())

def _sheets_service():
    return build("sheets", "v4", credentials=_get_creds())

def _gmail_service():
    return build("gmail", "v1", credentials=_get_creds())


# ── Google Drive ──────────────────────────────────────────────────────────────

def _get_or_create_folder(drive, folder_name: str) -> str:
    """Returns Drive folder ID, creating it if it doesn't exist."""
    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder = drive.files().create(
        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id"
    ).execute()
    return folder["id"]


def save_resume_to_drive(job_id: str, company: str, title: str,
                          region: str, resume_text: str) -> str:
    """
    Saves the tailored resume as a plain-text file in Google Drive.
    Returns the shareable file URL.
    """
    try:
        drive = _drive_service()
        folder_id = _get_or_create_folder(drive, GDRIVE_FOLDER_NAME)

        date_str  = datetime.utcnow().strftime("%Y%m%d")
        safe_co   = company.replace("/", "-").replace(" ", "_")[:30]
        safe_title= title.replace("/", "-").replace(" ", "_")[:30]
        filename  = f"{date_str}_{region}_{safe_co}_{safe_title}_{job_id}.txt"

        media = MediaInMemoryUpload(
            resume_text.encode("utf-8"),
            mimetype="text/plain",
            resumable=False
        )
        file_meta = {"name": filename, "parents": [folder_id]}
        created = drive.files().create(
            body=file_meta, media_body=media, fields="id,webViewLink"
        ).execute()
        url = created.get("webViewLink", "")
        log.info(f"Resume saved to Drive: {filename}")
        return url
    except Exception as e:
        log.error(f"Drive upload failed: {e}")
        return ""


# ── Google Sheets ─────────────────────────────────────────────────────────────

def _get_or_create_sheet(sheets) -> str:
    """Returns spreadsheet ID, creating the tracker sheet if needed."""
    drive = _drive_service()
    q = f"name='{GSHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        sheet_id = files[0]["id"]
    else:
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
        # Format header row bold
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
        log.info(f"Created new tracker sheet: {GSHEET_NAME}")

    return sheet_id


def log_job_to_sheet(job, relevance_data: dict,
                      drive_url: str, cover_note: str):
    """Appends a row to the Applications tracker sheet."""
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
            "New",          # Status — you update this manually
            "",             # Applied Date
            "",             # Notes
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


# ── Gmail Notification ────────────────────────────────────────────────────────

def send_notification_email(new_jobs: list, recipient: str):
    """Sends a digest email listing all new matched jobs."""
    if not new_jobs:
        return
    try:
        gmail = _gmail_service()

        lines = [f"JobSeeker found {len(new_jobs)} new matching job(s):\n"]
        for j in new_jobs:
            score = j.get("score", "?")
            lines.append(
                f"[{j['region']}] {j['title']} @ {j['company']} — {j['location']}\n"
                f"  Relevance: {score}/100\n"
                f"  URL: {j['url']}\n"
                f"  Resume on Drive: {j.get('drive_url', 'N/A')}\n"
            )
        lines.append("\nOpen your tracker: https://docs.google.com/spreadsheets")

        body = "\n".join(lines)
        message = MIMEText(body)
        message["to"]      = recipient
        message["from"]    = recipient
        message["subject"] = f"JobSeeker: {len(new_jobs)} new match(es) — {datetime.utcnow().strftime('%d %b %Y')}"

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        log.info(f"Notification email sent to {recipient}")
    except Exception as e:
        log.error(f"Email notification failed: {e}")

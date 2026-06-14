"""
main.py — JobSeeker Orchestrator
Nazish Mehdi | Senior Data Analyst Job Hunt Automation

Run manually:     python main.py
Run via cron:     see .github/workflows/job_scan.yml for GitHub Actions setup

Flow:
  1. Scrape all portals (India + Saudi)
  2. Deduplicate against seen_jobs.json
  3. Filter out Saudi-nationals-only roles
  4. Score each new job via Claude AI
  5. Skip jobs below MIN_RELEVANCE_SCORE
  6. Tailor resume + generate cover note for matches
  7. Save resume to Google Drive
  8. Log to Google Sheets tracker
  9. Send email digest
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from config.config import (
    CANDIDATE_PROFILE, SEARCH_KEYWORDS,
    INDIA_PREFERRED_CITIES, SAUDI_CITIES,
    SAUDI_SKIP_NATIONALS_ONLY, MIN_RELEVANCE_SCORE,
    NOTIFY_EMAIL, SEEN_JOBS_DB, APPLICATIONS_LOG,
    INDIA_ACCEPT_REMOTE, SAUDI_ACCEPT_REMOTE,
)
from modules.scraper        import run_all_scrapers, Job
from modules.deduplicator   import SeenJobsStore
from modules.ai_processor   import score_relevance, tailor_resume, generate_cover_note
from modules.google_integration import (
    save_resume_to_drive, log_job_to_sheet, send_notification_email
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/jobseeker.log"),
    ]
)
log = logging.getLogger(__name__)

os.makedirs("data",    exist_ok=True)
os.makedirs("resumes", exist_ok=True)


def location_filter(job: Job) -> bool:
    """
    India: accept if city is in preferred list OR if remote.
    Saudi: accept onsite only (no remote).
    """
    loc_lower = job.location.lower()

    if job.region == "India":
        preferred = [c.lower() for c in INDIA_PREFERRED_CITIES]
        in_preferred_city = any(city in loc_lower for city in preferred)
        is_remote = "remote" in loc_lower
        return in_preferred_city or (INDIA_ACCEPT_REMOTE and is_remote)

    if job.region == "Saudi":
        is_remote = "remote" in loc_lower
        if SAUDI_ACCEPT_REMOTE is False and is_remote:
            return False   # Skip remote Saudi roles
        return True        # Any onsite Saudi city is fine

    return True


def load_applications_log() -> list:
    if os.path.exists(APPLICATIONS_LOG):
        with open(APPLICATIONS_LOG) as f:
            return json.load(f)
    return []


def save_applications_log(apps: list):
    with open(APPLICATIONS_LOG, "w") as f:
        json.dump(apps, f, indent=2)


def run():
    log.info("=" * 60)
    log.info(f"JobSeeker scan started at {datetime.utcnow().isoformat()} UTC")
    log.info("=" * 60)

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
    raw_jobs = run_all_scrapers(
        keywords=SEARCH_KEYWORDS,
        india_cities=INDIA_PREFERRED_CITIES,
        saudi_cities=SAUDI_CITIES,
    )

    # ── Step 2: Deduplicate ───────────────────────────────────────────────────
    store    = SeenJobsStore(SEEN_JOBS_DB)
    new_jobs = store.filter_new(raw_jobs)

    # ── Step 3: Location + nationals filter ───────────────────────────────────
    filtered = []
    for job in new_jobs:
        if SAUDI_SKIP_NATIONALS_ONLY and job.is_nationals_only:
            log.info(f"SKIP (nationals only): {job.title} @ {job.company}")
            store.mark_seen(job)   # mark so we don't revisit
            continue
        if not location_filter(job):
            log.info(f"SKIP (location): {job.title} @ {job.company} — {job.location}")
            store.mark_seen(job)
            continue
        filtered.append(job)

    log.info(f"After filters: {len(filtered)} jobs to score")

    # Limit to 100 per run — 5 scans/day means up to 500 jobs processed daily
    if len(filtered) > 100:
        log.info(f"Limiting to 100 jobs this run (will process rest next scan)")
        filtered = filtered[:100]

    if not filtered:
        log.info("No new qualifying jobs this run. Exiting.")
        return

    # ── Steps 4–8: Score → Tailor → Save ─────────────────────────────────────
    apps_log   = load_applications_log()
    notif_list = []

    for job in filtered:
        log.info(f"Processing: {job.title} @ {job.company} [{job.region}]")

        # Score
        rel = score_relevance(job)
        score = rel.get("score", 0)
        log.info(f"  Relevance score: {score}/100")

        # Mark seen regardless of score (so we don't rescore same job)
        store.mark_seen(job)

        if score < MIN_RELEVANCE_SCORE:
            log.info(f"  SKIP (score {score} < threshold {MIN_RELEVANCE_SCORE})")
            continue

        log.info(f"  MATCH! Tailoring resume...")

        # Tailor resume
        tailored = tailor_resume(job, rel)
        cover    = generate_cover_note(job, rel)

        # Save to Drive
        drive_url = ""
        if tailored:
            drive_url = save_resume_to_drive(
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                region=job.region,
                resume_text=tailored,
            )

        # Log to Sheets
        log_job_to_sheet(job, rel, drive_url, cover)

        # Build notification entry
        notif_entry = {
            **job.to_dict(),
            "score": score,
            "match_reasons": rel.get("match_reasons", ""),
            "drive_url": drive_url,
        }
        notif_list.append(notif_entry)
        apps_log.append(notif_entry)

        log.info(f"  Done → Drive: {drive_url[:60]}...")

    # ── Step 9: Notify ────────────────────────────────────────────────────────
    if notif_list:
        send_notification_email(notif_list, NOTIFY_EMAIL)
        log.info(f"Scan complete. {len(notif_list)} matches found and saved.")
    else:
        log.info("Scan complete. No new matches above threshold.")

    save_applications_log(apps_log)
    log.info("=" * 60)


if __name__ == "__main__":
    run()

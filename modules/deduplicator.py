"""
modules/deduplicator.py
Tracks seen job IDs in a local JSON file so we never process the same
listing twice across runs.
"""

import json
import os
import logging
from datetime import datetime
from modules.scraper import Job

log = logging.getLogger(__name__)


class SeenJobsStore:
    def __init__(self, db_path: str = "data/seen_jobs.json"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._store: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.db_path):
            with open(self.db_path) as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump(self._store, f, indent=2)

    def is_new(self, job: Job) -> bool:
        return job.job_id not in self._store

    def mark_seen(self, job: Job):
        self._store[job.job_id] = {
            "title": job.title,
            "company": job.company,
            "portal": job.portal,
            "seen_at": datetime.utcnow().isoformat(),
        }
        self._save()

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        new_jobs = [j for j in jobs if self.is_new(j)]
        log.info(f"Dedup: {len(jobs)} total → {len(new_jobs)} new")
        return new_jobs

    def mark_all_seen(self, jobs: list[Job]):
        for job in jobs:
            self.mark_seen(job)

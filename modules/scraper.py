"""
modules/scraper.py
Clean, no-duplicate job scraper.
- India: Adzuna API (Bengaluru, Mumbai, Pune, Hyderabad) + Naukri
- Saudi: Adzuna UK with Gulf keyword filtering + GulfTalent scrape
- Deduplication: within-run set prevents same job being scored twice
"""

import os
import time
import logging
import hashlib
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

log = logging.getLogger(__name__)

ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    location: str
    region: str
    portal: str
    url: str
    description: str
    posted_date: str
    salary: Optional[str]
    is_nationals_only: bool
    scraped_at: str

    def to_dict(self):
        return asdict(self)


def _make_id(title: str, company: str) -> str:
    """ID based on title + company only — location wording varies across portals."""
    raw = f"{title.lower().strip()}|{company.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _check_nationals_only(text: str) -> bool:
    flags = ["saudi nationals only", "saudi national only", "saudi citizen",
             "saudization", "must be a saudi national"]
    return any(f in text.lower() for f in flags)


# ── Adzuna India ──────────────────────────────────────────────────────────────

def scrape_adzuna_india(keyword: str, location: str, seen: set) -> list:
    jobs = []
    if not ADZUNA_APP_ID:
        return jobs
    try:
        r = requests.get(
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "results_per_page": 50,
                "what": keyword,
                "where": location,
                "sort_by": "date",
                "max_days_old": 3,
            },
            timeout=15
        )
        r.raise_for_status()
        for item in r.json().get("results", []):
            title   = item.get("title", "N/A")
            company = item.get("company", {}).get("display_name", "N/A")
            jid     = _make_id(title, company)
            if jid in seen:
                continue
            seen.add(jid)
            loc    = item.get("location", {}).get("display_name", location)
            jobs.append(Job(
                job_id=jid, title=title, company=company, location=loc,
                region="India", portal="adzuna_india",
                url=item.get("redirect_url", ""),
                description=item.get("description", "")[:3000],
                posted_date=item.get("created", "")[:10],
                salary=None, is_nationals_only=False,
                scraped_at=datetime.utcnow().isoformat(),
            ))
        log.info(f"Adzuna India [{location}] '{keyword}': {len(jobs)} new jobs")
    except Exception as e:
        log.error(f"Adzuna India [{location}] error: {e}")
    return jobs


# ── Naukri India ──────────────────────────────────────────────────────────────

def scrape_naukri(keyword: str, location: str, seen: set) -> list:
    jobs = []
    slug_kw  = keyword.replace(" ", "-").lower()
    slug_loc = location.replace(" ", "-").lower()
    try:
        r = requests.get(
            f"https://www.naukri.com/{slug_kw}-jobs-in-{slug_loc}",
            headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        soup  = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article.jobTuple, div[class*='jobTuple']")
        for card in cards[:15]:
            title_el = card.select_one("a.title, a[class*='title']")
            comp_el  = card.select_one("a.subTitle, a[class*='comp']")
            if not title_el:
                continue
            title   = title_el.get_text(strip=True)
            company = comp_el.get_text(strip=True) if comp_el else "N/A"
            jid     = _make_id(title, company)
            if jid in seen:
                continue
            seen.add(jid)
            jobs.append(Job(
                job_id=jid, title=title, company=company, location=location,
                region="India", portal="naukri",
                url=title_el.get("href", ""),
                description="",
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=None, is_nationals_only=False,
                scraped_at=datetime.utcnow().isoformat(),
            ))
        log.info(f"Naukri [{location}] '{keyword}': {len(jobs)} new jobs")
    except Exception as e:
        log.error(f"Naukri [{location}] error: {e}")
    return jobs


# ── Saudi / Gulf ──────────────────────────────────────────────────────────────

def scrape_saudi_jobs(keyword: str, seen: set) -> list:
    """
    Three approaches for Saudi jobs:
    1. Adzuna UK — international recruiters post Gulf roles on UK boards
    2. GulfTalent direct scrape
    3. Bayt.com direct scrape
    All results filtered to only keep genuine Saudi/Gulf jobs.
    """
    jobs = []
    gulf_terms = ["saudi", "riyadh", "jeddah", "dammam", "ksa",
                  "gulf", "middle east", "neom", "khobar", "dhahran", "aramco"]

    # 1. Adzuna UK — search "keyword + Saudi Arabia"
    if ADZUNA_APP_ID:
        for search in [f"{keyword} Saudi Arabia", f"{keyword} Riyadh"]:
            try:
                r = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/gb/search/1",
                    params={
                        "app_id": ADZUNA_APP_ID,
                        "app_key": ADZUNA_APP_KEY,
                        "results_per_page": 20,
                        "what": search,
                        "sort_by": "date",
                        "max_days_old": 7,
                    },
                    timeout=15
                )
                r.raise_for_status()
                count = 0
                for item in r.json().get("results", []):
                    title   = item.get("title", "N/A")
                    company = item.get("company", {}).get("display_name", "N/A")
                    desc    = item.get("description", "")[:3000]
                    loc     = item.get("location", {}).get("display_name", "Saudi Arabia")
                    combined = (title + desc + loc).lower()
                    if not any(t in combined for t in gulf_terms):
                        continue
                    jid = _make_id(title, company)
                    if jid in seen:
                        continue
                    seen.add(jid)
                    jobs.append(Job(
                        job_id=jid, title=title, company=company, location=loc,
                        region="Saudi", portal="adzuna_gulf",
                        url=item.get("redirect_url", ""),
                        description=desc,
                        posted_date=item.get("created", "")[:10],
                        salary=None,
                        is_nationals_only=_check_nationals_only(desc + title),
                        scraped_at=datetime.utcnow().isoformat(),
                    ))
                    count += 1
                log.info(f"Adzuna Gulf '{search}': {count} new jobs")
            except Exception as e:
                log.error(f"Adzuna Gulf error: {e}")
            time.sleep(0.5)

    # 2. GulfTalent scrape
    try:
        slug = keyword.replace(" ", "-").lower()
        r = requests.get(
            f"https://www.gulftalent.com/saudi-arabia/jobs/{slug}",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            soup  = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("div.job_listing, article.job-listing, li.job")
            count = 0
            for card in cards[:15]:
                title_el = card.select_one("h3 a, h2 a, a[class*='title']")
                comp_el  = card.select_one("span.company, div.company-name, span[class*='company']")
                if not title_el:
                    continue
                title   = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True) if comp_el else "N/A"
                jid     = _make_id(title, company)
                if jid in seen:
                    continue
                seen.add(jid)
                href = title_el.get("href", "")
                jobs.append(Job(
                    job_id=jid, title=title, company=company,
                    location="Saudi Arabia", region="Saudi",
                    portal="gulftalent", url=href, description="",
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=None, is_nationals_only=False,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
                count += 1
            log.info(f"GulfTalent '{keyword}': {count} new jobs")
    except Exception as e:
        log.error(f"GulfTalent error: {e}")

    # 3. Bayt scrape
    try:
        slug = keyword.replace(" ", "-").lower()
        r = requests.get(
            f"https://www.bayt.com/en/saudi-arabia/jobs/{slug}-jobs/",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            soup  = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li[data-js-job], div.has-pointer-d")
            count = 0
            for card in cards[:15]:
                title_el = card.select_one("h2.jb-title a, a[data-automation-id='job-title']")
                comp_el  = card.select_one("span[data-automation-id='company-name'], b.jb-company")
                if not title_el:
                    continue
                title   = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True) if comp_el else "N/A"
                jid     = _make_id(title, company)
                if jid in seen:
                    continue
                seen.add(jid)
                href = title_el.get("href", "")
                if href.startswith("/"):
                    href = "https://www.bayt.com" + href
                jobs.append(Job(
                    job_id=jid, title=title, company=company,
                    location="Saudi Arabia", region="Saudi",
                    portal="bayt", url=href, description="",
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=None, is_nationals_only=False,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
                count += 1
            log.info(f"Bayt '{keyword}': {count} new jobs")
    except Exception as e:
        log.error(f"Bayt error: {e}")

    return jobs


# ── Main entry point ──────────────────────────────────────────────────────────

def run_all_scrapers(keywords: list, india_cities: list, saudi_cities: list) -> list:
    all_jobs  = []
    seen_ids  = set()   # ← within-run dedup: same job_id never added twice

    for keyword in keywords:
        log.info(f"Scanning: '{keyword}'")

        # Saudi FIRST — prioritised
        saudi = scrape_saudi_jobs(keyword, seen_ids)
        all_jobs += saudi
        log.info(f"  Saudi total so far: {len([j for j in all_jobs if j.region=='Saudi'])}")
        time.sleep(1)

        # India — Adzuna (one search per city, no duplicate cities)
        for city in india_cities:
            all_jobs += scrape_adzuna_india(keyword, city, seen_ids)
            time.sleep(0.5)

        # India — Naukri (only Bengaluru + Hyderabad — highest density)
        for city in ["Bengaluru", "Hyderabad"]:
            all_jobs += scrape_naukri(keyword, city, seen_ids)
            time.sleep(0.5)

        time.sleep(1)

    log.info(f"Total scraped (no duplicates): {len(all_jobs)}")
    log.info(f"  India: {len([j for j in all_jobs if j.region=='India'])}")
    log.info(f"  Saudi: {len([j for j in all_jobs if j.region=='Saudi'])}")
    return all_jobs

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

# LinkedIn Saudi Arabia geoId
LINKEDIN_SAUDI_GEOID = "102713980"

def scrape_linkedin_saudi(keyword: str, seen: set) -> list:
    """
    Uses LinkedIn's public jobs guest API — no login, no API key needed.
    This is the same endpoint LinkedIn uses internally to load job listings.
    Specifically targets Saudi Arabia using LinkedIn's geoId.
    """
    jobs = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.linkedin.com/",
    }

    for start in [0, 25]:
        try:
            url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            params = {
                "keywords": keyword,
                "location": "Saudi Arabia",
                "geoId": LINKEDIN_SAUDI_GEOID,
                "f_TPR": "r604800",  # last 7 days
                "start": start,
            }
            r = requests.get(url, headers=headers, params=params, timeout=15)
            if r.status_code != 200:
                log.warning(f"LinkedIn Saudi returned {r.status_code} for '{keyword}' start={start}")
                break

            soup  = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li")
            count = 0
            for card in cards:
                title_el = card.select_one("h3.base-search-card__title, h3")
                comp_el  = card.select_one("h4.base-search-card__subtitle, h4")
                loc_el   = card.select_one("span.job-search-card__location, span.base-search-card__metadata")
                link_el  = card.select_one("a.base-card__full-link, a")

                if not title_el or not link_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True)   if comp_el  else "N/A"
                loc     = loc_el.get_text(strip=True)    if loc_el   else "Saudi Arabia"
                href    = link_el.get("href", "").split("?")[0]

                jid = _make_id(title, company)
                if jid in seen:
                    continue
                seen.add(jid)

                jobs.append(Job(
                    job_id=jid, title=title, company=company,
                    location=loc, region="Saudi",
                    portal="linkedin_saudi",
                    url=href, description="",
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=None,
                    is_nationals_only=_check_nationals_only(title + loc),
                    scraped_at=datetime.utcnow().isoformat(),
                ))
                count += 1

            log.info(f"LinkedIn Saudi '{keyword}' start={start}: {count} new jobs")
            time.sleep(1)

        except Exception as e:
            log.error(f"LinkedIn Saudi error: {e}")
            break

    return jobs


def scrape_naukrigulf(keyword: str, seen: set) -> list:
    """Scrapes NaukriGulf for Saudi Arabia jobs."""
    jobs = []
    slug = keyword.replace(" ", "-").lower()
    try:
        r = requests.get(
            f"https://www.naukrigulf.com/{slug}-jobs-in-saudi-arabia",
            headers=HEADERS, timeout=20
        )
        if r.status_code == 200:
            soup  = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("div.ni-job-tuple, li.jobTuple, div[class*='jobTuple']")
            count = 0
            for card in cards[:20]:
                title_el = card.select_one("a.designation, a.jobTitle, a[class*='title']")
                comp_el  = card.select_one("a.company-name, span.comp-name, a[class*='comp']")
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
                    href = "https://www.naukrigulf.com" + href
                jobs.append(Job(
                    job_id=jid, title=title, company=company,
                    location="Saudi Arabia", region="Saudi",
                    portal="naukrigulf", url=href, description="",
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=None, is_nationals_only=False,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
                count += 1
            log.info(f"NaukriGulf '{keyword}': {count} new jobs")
    except Exception as e:
        log.error(f"NaukriGulf error: {e}")
    return jobs


def scrape_saudi_jobs(keyword: str, seen: set) -> list:
    """Combines LinkedIn Saudi + NaukriGulf for maximum Saudi coverage."""
    jobs = []
    jobs += scrape_linkedin_saudi(keyword, seen)
    time.sleep(1)
    jobs += scrape_naukrigulf(keyword, seen)
    time.sleep(1)
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

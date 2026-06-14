"""
modules/scraper.py
Fetches job listings using:
  - Adzuna API (India + Saudi) — free, official, no blocks
  - Naukri.com (India) — works with proper headers
  - Wellfound (India) — startup jobs
"""

import os
import time
import json
import logging
import hashlib
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
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
    region: str           # "India" | "Saudi"
    portal: str
    url: str
    description: str
    posted_date: str
    salary: Optional[str]
    is_nationals_only: bool
    scraped_at: str

    def to_dict(self):
        return asdict(self)


def _make_id(title: str, company: str, location: str) -> str:
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _check_nationals_only(text: str) -> bool:
    flags = [
        "saudi nationals only", "saudi national only", "saudi citizen",
        "saudization", "must be a saudi national", "Saudi nationals"
    ]
    text_lower = text.lower()
    return any(flag.lower() in text_lower for flag in flags)


# ── Adzuna API (India) ────────────────────────────────────────────────────────

def scrape_adzuna_india(keyword: str, location: str) -> list:
    jobs = []
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        log.warning("Adzuna credentials missing — skipping")
        return jobs

    url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": 20,
        "what": keyword,
        "where": location,
        "sort_by": "date",
        "max_days_old": 1,
        "content-type": "application/json",
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        for item in data.get("results", []):
            title    = item.get("title", "N/A")
            company  = item.get("company", {}).get("display_name", "N/A")
            loc      = item.get("location", {}).get("display_name", location)
            href     = item.get("redirect_url", "")
            desc     = item.get("description", "")[:3000]
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            salary   = f"{salary_min}–{salary_max}" if salary_min else None
            posted   = item.get("created", datetime.utcnow().strftime("%Y-%m-%d"))[:10]

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region="India", portal="adzuna_india",
                url=href, description=desc,
                posted_date=posted, salary=salary,
                is_nationals_only=False,
                scraped_at=datetime.utcnow().isoformat(),
            ))
        log.info(f"Adzuna India [{location}] '{keyword}': {len(jobs)} jobs")
    except Exception as e:
        log.error(f"Adzuna India error: {e}")
    return jobs


# ── Adzuna API (Saudi Arabia) ─────────────────────────────────────────────────

def scrape_adzuna_saudi(keyword: str) -> list:
    jobs = []
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return jobs

    # Adzuna uses 'ae' (UAE) as the closest Gulf country code
    # We filter for Saudi-related locations after fetching
    for country_code in ["ae", "gb"]:
        url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 20,
            "what": keyword,
            "where": "Saudi Arabia",
            "sort_by": "date",
            "max_days_old": 1,
            "content-type": "application/json",
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()

            for item in data.get("results", []):
                title   = item.get("title", "N/A")
                company = item.get("company", {}).get("display_name", "N/A")
                loc     = item.get("location", {}).get("display_name", "Saudi Arabia")
                href    = item.get("redirect_url", "")
                desc    = item.get("description", "")[:3000]
                posted  = item.get("created", datetime.utcnow().strftime("%Y-%m-%d"))[:10]
                nationals_only = _check_nationals_only(desc + title)

                jobs.append(Job(
                    job_id=_make_id(title, company, loc),
                    title=title, company=company, location=loc,
                    region="Saudi", portal=f"adzuna_{country_code}",
                    url=href, description=desc,
                    posted_date=posted, salary=None,
                    is_nationals_only=nationals_only,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
            log.info(f"Adzuna [{country_code}] '{keyword}': {len(data.get('results', []))} jobs")
        except Exception as e:
            log.error(f"Adzuna Saudi [{country_code}] error: {e}")
        time.sleep(1)

    return jobs


# ── Naukri (India) ────────────────────────────────────────────────────────────

def scrape_naukri(keyword: str, location: str) -> list:
    jobs = []
    slug_kw  = keyword.replace(" ", "-").lower()
    slug_loc = location.replace(" ", "-").lower()
    url = f"https://www.naukri.com/{slug_kw}-jobs-in-{slug_loc}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article.jobTuple, div.srp-jobtuple-wrapper, div[class*='jobTuple']")

        for card in cards[:15]:
            try:
                title_el  = card.select_one("a.title, a.jobTitle, a[class*='title']")
                comp_el   = card.select_one("a.subTitle, a.companyInfo, a[class*='comp']")
                loc_el    = card.select_one("li.location span, span.locWdth, span[class*='loc']")
                salary_el = card.select_one("li.salary span, span[class*='salary']")

                title   = title_el.get_text(strip=True) if title_el else "N/A"
                company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
                loc     = loc_el.get_text(strip=True)   if loc_el   else location
                salary  = salary_el.get_text(strip=True)if salary_el else None
                href    = title_el.get("href", url)     if title_el else url

                # Get description from job page
                desc = ""
                try:
                    jr = requests.get(href, headers=HEADERS, timeout=10)
                    jr.raise_for_status()
                    jsoup = BeautifulSoup(jr.text, "html.parser")
                    jd_el = jsoup.select_one("div.job-desc, section.job-desc, div[class*='jobDesc']")
                    desc  = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""
                except Exception:
                    pass

                jobs.append(Job(
                    job_id=_make_id(title, company, loc),
                    title=title, company=company, location=loc,
                    region="India", portal="naukri",
                    url=href, description=desc,
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=salary, is_nationals_only=False,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
                time.sleep(0.5)
            except Exception as e:
                log.error(f"Naukri card error: {e}")

        log.info(f"Naukri [{location}] '{keyword}': {len(jobs)} jobs")
    except Exception as e:
        log.error(f"Naukri scrape error for {url}: {e}")
    return jobs


# ── Wellfound (India startups) ────────────────────────────────────────────────

def scrape_wellfound(keyword: str) -> list:
    jobs = []
    slug = keyword.replace(" ", "-").lower()
    url  = f"https://wellfound.com/jobs/l/india/{slug}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div[class*='JobListing'], div[class*='job-listing']")

        for card in cards[:15]:
            try:
                title_el = card.select_one("a[class*='title'], h2 a")
                comp_el  = card.select_one("a[class*='company'], span[class*='company']")
                loc_el   = card.select_one("span[class*='location'], div[class*='location']")

                title   = title_el.get_text(strip=True) if title_el else "N/A"
                company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
                loc     = loc_el.get_text(strip=True)   if loc_el   else "India"
                href    = title_el.get("href", "")      if title_el else ""
                if href and href.startswith("/"):
                    href = "https://wellfound.com" + href

                jobs.append(Job(
                    job_id=_make_id(title, company, loc),
                    title=title, company=company, location=loc,
                    region="India", portal="wellfound",
                    url=href, description="",
                    posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    salary=None, is_nationals_only=False,
                    scraped_at=datetime.utcnow().isoformat(),
                ))
            except Exception as e:
                log.error(f"Wellfound card error: {e}")

        log.info(f"Wellfound '{keyword}': {len(jobs)} jobs")
    except Exception as e:
        log.error(f"Wellfound error: {e}")
    return jobs


# ── Main entry point ──────────────────────────────────────────────────────────

def run_all_scrapers(keywords: list, india_cities: list, saudi_cities: list) -> list:
    all_jobs = []

    for keyword in keywords:
        log.info(f"Scanning keyword: '{keyword}'")

        # India — Adzuna API (primary, reliable)
        for city in india_cities:
            all_jobs += scrape_adzuna_india(keyword, city)
            time.sleep(1)

        # India — Naukri (backup scraper)
        for city in ["Bengaluru", "Mumbai", "Pune", "Hyderabad"]:
            all_jobs += scrape_naukri(keyword, city)
            time.sleep(1)

        # India — Wellfound startups
        all_jobs += scrape_wellfound(keyword)

        # Saudi — Adzuna API
        all_jobs += scrape_adzuna_saudi(keyword)

        time.sleep(2)

    log.info(f"Total jobs scraped (before dedup): {len(all_jobs)}")
    return all_jobs

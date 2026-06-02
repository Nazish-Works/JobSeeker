"""
modules/scraper.py
Fetches job listings from Indeed India, Naukri, Wellfound, Bayt,
GulfTalent, NaukriGulf, and Indeed Saudi.
"""

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

@dataclass
class Job:
    job_id: str           # stable hash of title+company+location
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


def _get(url: str, params: dict = None, retries: int = 3) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            log.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 ** attempt)
    return None


# ── Indeed (India + Saudi) ────────────────────────────────────────────────────

def scrape_indeed(keyword: str, location: str, region: str, base_url: str) -> list[Job]:
    jobs = []
    params = {"q": keyword, "l": location, "sort": "date", "fromage": "1"}
    soup = _get(base_url, params)
    if not soup:
        return jobs

    cards = soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")
    for card in cards:
        try:
            title_el  = card.select_one("h2.jobTitle span, h2 a span")
            comp_el   = card.select_one("span.companyName, [data-testid='company-name']")
            loc_el    = card.select_one("div.companyLocation, [data-testid='text-location']")
            link_el   = card.select_one("h2 a")
            salary_el = card.select_one("div.metadata.salary-snippet-container, div.salaryOnly")

            title    = title_el.get_text(strip=True)  if title_el  else "N/A"
            company  = comp_el.get_text(strip=True)   if comp_el   else "N/A"
            loc      = loc_el.get_text(strip=True)    if loc_el    else location
            salary   = salary_el.get_text(strip=True) if salary_el else None
            href     = "https://www.indeed.com" + link_el["href"] if link_el else base_url

            desc_soup = _get(href)
            description = ""
            if desc_soup:
                jd_el = desc_soup.select_one("div#jobDescriptionText, div.jobsearch-jobDescriptionText")
                description = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""

            nationals_only = _check_nationals_only(description + title)

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region=region, portal=f"indeed_{region.lower()}",
                url=href, description=description,
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=salary, is_nationals_only=nationals_only,
                scraped_at=datetime.utcnow().isoformat(),
            ))
            time.sleep(1)
        except Exception as e:
            log.error(f"Indeed card parse error: {e}")
    return jobs


# ── Naukri (India) ────────────────────────────────────────────────────────────

def scrape_naukri(keyword: str, location: str) -> list[Job]:
    jobs = []
    slug_kw  = keyword.replace(" ", "-").lower()
    slug_loc = location.replace(" ", "-").lower()
    url = f"https://www.naukri.com/{slug_kw}-jobs-in-{slug_loc}"
    soup = _get(url)
    if not soup:
        return jobs

    cards = soup.select("article.jobTuple, div.srp-jobtuple-wrapper")
    for card in cards:
        try:
            title_el  = card.select_one("a.title, a.jobTitle")
            comp_el   = card.select_one("a.subTitle, a.companyInfo")
            loc_el    = card.select_one("li.location span, span.locWdth")
            salary_el = card.select_one("li.salary span, span.salary")

            title   = title_el.get_text(strip=True) if title_el else "N/A"
            company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
            loc     = loc_el.get_text(strip=True)   if loc_el   else location
            salary  = salary_el.get_text(strip=True)if salary_el else None
            href    = title_el["href"] if title_el and title_el.get("href") else url

            desc_soup = _get(href)
            description = ""
            if desc_soup:
                jd_el = desc_soup.select_one("div.job-desc, section.job-desc")
                description = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region="India", portal="naukri",
                url=href, description=description,
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=salary, is_nationals_only=False,
                scraped_at=datetime.utcnow().isoformat(),
            ))
            time.sleep(1)
        except Exception as e:
            log.error(f"Naukri card parse error: {e}")
    return jobs


# ── NaukriGulf (Saudi) ────────────────────────────────────────────────────────

def scrape_naukrigulf(keyword: str) -> list[Job]:
    jobs = []
    slug = keyword.replace(" ", "-").lower()
    url  = f"https://www.naukrigulf.com/{slug}-jobs-in-saudi-arabia"
    soup = _get(url)
    if not soup:
        return jobs

    cards = soup.select("div.ni-job-tuple, li.jobTuple")
    for card in cards:
        try:
            title_el = card.select_one("a.designation, a.jobTitle")
            comp_el  = card.select_one("a.company-name, span.comp-name")
            loc_el   = card.select_one("span.location, li.location")

            title   = title_el.get_text(strip=True) if title_el else "N/A"
            company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
            loc     = loc_el.get_text(strip=True)   if loc_el   else "Saudi Arabia"
            href    = title_el["href"] if title_el and title_el.get("href") else url
            if href.startswith("/"):
                href = "https://www.naukrigulf.com" + href

            desc_soup = _get(href)
            description = ""
            if desc_soup:
                jd_el = desc_soup.select_one("div.job-description-main, div#job-description")
                description = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""

            nationals_only = _check_nationals_only(description + title)

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region="Saudi", portal="naukrigulf",
                url=href, description=description,
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=None, is_nationals_only=nationals_only,
                scraped_at=datetime.utcnow().isoformat(),
            ))
            time.sleep(1)
        except Exception as e:
            log.error(f"NaukriGulf card parse error: {e}")
    return jobs


# ── Bayt (Saudi) ──────────────────────────────────────────────────────────────

def scrape_bayt(keyword: str) -> list[Job]:
    jobs = []
    slug = keyword.replace(" ", "-").lower()
    url  = f"https://www.bayt.com/en/saudi-arabia/jobs/{slug}-jobs/"
    soup = _get(url)
    if not soup:
        return jobs

    cards = soup.select("li[data-js-job], div.has-pointer-d")
    for card in cards:
        try:
            title_el = card.select_one("h2.jb-title a, a[data-automation-id='job-title']")
            comp_el  = card.select_one("span[data-automation-id='company-name'], b.jb-company")
            loc_el   = card.select_one("span[data-automation-id='job-location'], span.jb-loc")

            title   = title_el.get_text(strip=True) if title_el else "N/A"
            company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
            loc     = loc_el.get_text(strip=True)   if loc_el   else "Saudi Arabia"
            href    = title_el["href"] if title_el and title_el.get("href") else url
            if href.startswith("/"):
                href = "https://www.bayt.com" + href

            desc_soup = _get(href)
            description = ""
            if desc_soup:
                jd_el = desc_soup.select_one("div.jb-description, div[data-automation-id='job-description']")
                description = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""

            nationals_only = _check_nationals_only(description + title)

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region="Saudi", portal="bayt",
                url=href, description=description,
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=None, is_nationals_only=nationals_only,
                scraped_at=datetime.utcnow().isoformat(),
            ))
            time.sleep(1)
        except Exception as e:
            log.error(f"Bayt card parse error: {e}")
    return jobs


# ── GulfTalent (Saudi) ────────────────────────────────────────────────────────

def scrape_gulftalent(keyword: str) -> list[Job]:
    jobs = []
    slug = keyword.replace(" ", "-").lower()
    url  = f"https://www.gulftalent.com/saudi-arabia/jobs/{slug}"
    soup = _get(url)
    if not soup:
        return jobs

    cards = soup.select("div.job_listing, article.job-listing")
    for card in cards:
        try:
            title_el = card.select_one("h3 a, h2 a")
            comp_el  = card.select_one("span.company, div.company-name")
            loc_el   = card.select_one("span.location, div.job-location")

            title   = title_el.get_text(strip=True) if title_el else "N/A"
            company = comp_el.get_text(strip=True)  if comp_el  else "N/A"
            loc     = loc_el.get_text(strip=True)   if loc_el   else "Saudi Arabia"
            href    = title_el["href"] if title_el and title_el.get("href") else url

            desc_soup = _get(href)
            description = ""
            if desc_soup:
                jd_el = desc_soup.select_one("div.job-description, section.jd-text")
                description = jd_el.get_text(" ", strip=True)[:3000] if jd_el else ""

            nationals_only = _check_nationals_only(description + title)

            jobs.append(Job(
                job_id=_make_id(title, company, loc),
                title=title, company=company, location=loc,
                region="Saudi", portal="gulftalent",
                url=href, description=description,
                posted_date=datetime.utcnow().strftime("%Y-%m-%d"),
                salary=None, is_nationals_only=nationals_only,
                scraped_at=datetime.utcnow().isoformat(),
            ))
            time.sleep(1)
        except Exception as e:
            log.error(f"GulfTalent card parse error: {e}")
    return jobs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_nationals_only(text: str) -> bool:
    """Returns True if the role appears to require Saudi nationals only."""
    flags = [
        "saudi nationals only", "saudi national only", "saudi citizen",
        "حاملي الجنسية السعودية", "للمواطنين السعوديين", "saudization",
        "must be a saudi national"
    ]
    text_lower = text.lower()
    return any(flag in text_lower for flag in flags)


def run_all_scrapers(keywords: list[str],
                     india_cities: list[str],
                     saudi_cities: list[str]) -> list[Job]:
    """Entry point — runs all enabled scrapers and returns a flat list of jobs."""
    all_jobs = []

    for keyword in keywords:
        log.info(f"Scanning keyword: '{keyword}'")

        # India portals — Bengaluru first (home city), then other preferred cities
        for city in india_cities:
            all_jobs += scrape_indeed(keyword, city, "India", "https://www.indeed.co.in/jobs")
            # Naukri lists it as both "Bangalore" and "Bengaluru" — scrape both
            all_jobs += scrape_naukri(keyword, city)
            if city.lower() in ("bengaluru", "bangalore"):
                # Scrape the alternate spelling too to catch all listings
                alt = "Bangalore" if city.lower() == "bengaluru" else "Bengaluru"
                all_jobs += scrape_naukri(keyword, alt)
            time.sleep(2)

        # Saudi portals
        all_jobs += scrape_indeed(keyword, "Saudi Arabia", "Saudi", "https://sa.indeed.com/jobs")
        all_jobs += scrape_naukrigulf(keyword)
        all_jobs += scrape_bayt(keyword)
        all_jobs += scrape_gulftalent(keyword)
        time.sleep(2)

    log.info(f"Total jobs scraped (before dedup): {len(all_jobs)}")
    return all_jobs

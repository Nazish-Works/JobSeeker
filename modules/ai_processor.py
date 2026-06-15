"""
modules/ai_processor.py
Uses Claude to:
  1. Score job relevance (0–100) against Nazish's profile
  2. Tailor the resume bullet points for matched jobs
  3. Generate a short cover note
"""

import os
import json
import logging
import requests
from modules.scraper import Job

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


def _call_gemini(prompt: str, max_tokens: int = 1000) -> str:
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY is not set! Add it to GitHub Secrets.")
        return ""
    try:
        if GEMINI_API_KEY.startswith("AIza"):
            url     = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
        else:
            url     = GEMINI_URL
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GEMINI_API_KEY}"}

        r = requests.post(
            url,
            headers=headers,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error(f"Gemini API error: {e}")
        return ""

# ── Nazish's profile snapshot (used in prompts) ───────────────────────────────
PROFILE_SUMMARY = """
Name: Nazish Mehdi
Current Role: Senior Solutions Analyst @ ThoughtSpot (Aug 2024–Present)
Previous: Data Analyst @ SagasIT Analytics / AIMLEAP (Mar 2021–Apr 2023)
Total Experience: ~5 years
Current Location: Bengaluru, India (prefers Bengaluru onsite roles; open to Mumbai, Pune, Hyderabad onsite; open to remote if no onsite match)
Education: B.E. Electronics & Communications, 2020

Core Skills:
- Python (Selenium, Pandas), SQL (Advanced), Java/Scala (exposure)
- Data Engineering & ETL: Matillion ETL, dbt, Fivetran, BigQuery, Snowflake, Postgres, S3
- Cloud: Azure VM, AWS (EC2, S3), GCP (BigQuery), Docker/Kubernetes exposure
- Analytics & BI: ThoughtSpot (Architect/Professional certified), Power BI, Looker
- Tools: Git, UiPath, Airflow

Key Achievements:
- Designed scalable data models for 50+ enterprise customers (up to 100B rows)
- Query performance optimization on Snowflake, Databricks, Redshift, Oracle
- Led Tableau-to-ThoughtSpot migrations
- Built Python ETL pipelines, real-time fleet tracking, Selenium scrapers on AWS EC2
- Implemented RLS and PII data masking
- Converted customer from Essentials to higher TCV within 3 months

Certifications: ThoughtSpot (6 certs), Snowflake (5 certs), Power BI, Advanced SQL

Nationality: Indian | Currently in Bengaluru | Notice: 30 days
"""

BASE_RESUME_BULLETS = """
ThoughtSpot | Senior Solutions Analyst | Aug 2024–Present
- Design and implement unique data models for 50+ enterprise customers, optimizing performance for workloads up to 100 billion rows.
- Provide technical consultancy on query performance optimization for Snowflake, Databricks, Redshift, and Oracle.
- Lead technical migrations from legacy systems (Tableau) to ThoughtSpot.
- Implemented Git-based version control for data assets with CI/CD-like workflows.
- Developed complex aggregated formulas and data masking strategies for PII use cases using Row Level Security (RLS).
- Trained customer data models to use Spotter and NLP to generate automated insights.

SagasIT Analytics / AIMLEAP | Data Analyst | Mar 2021–Apr 2023
- Built Python-based automated ETL pipeline extracting via Semrush API, loading into BigQuery.
- Engineered real-time fleet tracking system with Python and SQL Server, automated hourly data ingestion and Power BI refreshes.
- Developed high-scale bots using Selenium and AWS EC2 to bypass anti-bot tools, storing PDF datasets in S3.
- Deployed web scraping bots using Selenium and Python on Amazon WorkSpace.
- Built data pipelines linking scraped content to PostgreSQL using SQL (pgAdmin).
- Automated data extraction with UiPath, automated cleaning, appended results to Excel.

AI Powered Personal Projects
- Designed and shipped a production-grade personal finance app using Claude AI as a full-stack development assistant. Defined requirements, reviewed outputs, debugged issues, and iterated through 50+ development cycles entirely through natural language prompts.
- Built Multi-user system with PIN authentication and admin/user role separation. Real-time cloud sync via Supabase REST API with PostgreSQL backend.
- It demonstrates Ability to translate business requirements into technical specifications for AI tools , Iterative product thinking — identifying edge cases, UX gaps, and data flow issues and  Full-stack understanding — frontend rendering, REST APIs, database schema, auth, hosting
"""


# ── 1. Relevance Scoring ─────────────────────────────────────────────────────

def score_relevance(job: Job) -> dict:
    """
    Returns {"score": int, "reasons": str, "missing_skills": list}
    score 0–100. Jobs below config threshold are skipped.
    """
    prompt = f"""
You are a senior recruiter evaluating candidate fit. Return ONLY valid JSON,
no markdown, no explanation, no code fences.

Return exactly this structure:
{{
  "score": <integer 0-100>,
  "match_reasons": "<2-3 specific sentences about fit — mention actual skills/tools that match>",
  "missing_skills": ["only list genuine gaps, not minor ones"],
  "recommended_highlights": ["specific experience or achievement to lead with for THIS job"]
}}

Scoring:
- 80–100: Strong match (title, stack, seniority all align well)
- 65–79: Good match (most skills match, minor gaps)
- 40–64: Partial match (some relevant experience, notable gaps)
- Below 40: Poor fit — don't waste her time

Be honest and specific. If the JD asks for Tableau and she has ThoughtSpot,
note it but don't penalise heavily (transferable). If it asks for 10 years and
she has 5, note the gap.

CANDIDATE PROFILE:
{PROFILE_SUMMARY}

JOB TITLE: {job.title}
COMPANY: {job.company}
LOCATION: {job.location}
REGION: {job.region}
JOB DESCRIPTION:
{job.description[:2500]}
"""
    try:
        text = _call_gemini(prompt, max_tokens=600)
        # Strip markdown json fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        log.error(f"Relevance scoring failed for {job.job_id}: {e}")
        return {"score": 0, "match_reasons": "Error", "missing_skills": [], "recommended_highlights": []}


# ── 2. Resume Tailoring ───────────────────────────────────────────────────────

def tailor_resume(job: Job, relevance_data: dict) -> str:
    """
    Returns a full tailored resume as plain text, customised for this specific JD.
    """
    highlights = "\n".join(f"- {h}" for h in relevance_data.get("recommended_highlights", []))
    missing    = ", ".join(relevance_data.get("missing_skills", []))

    # For Saudi jobs: add relocation note, omit photo recommendation, add passport
    region_note = ""
    if job.region == "Saudi":
        region_note = """
IMPORTANT FOR SAUDI ROLE:
- Mention availability to relocate to Saudi Arabia immediately (30-day notice)
- Include passport number Z6029437 in personal details
- Do NOT include photo recommendation (not required in Saudi)
- Emphasise experience with large-scale enterprise clients (aligns with Saudi Aramco, STC, NEOM culture)
"""
    else:
        region_note = """
IMPORTANT FOR INDIA ROLE:
- Based in Bengaluru — highlight this for Bengaluru onsite roles (no relocation needed)
- For Mumbai/Pune/Hyderabad roles, mention willingness to relocate within India (30-day notice)
- For remote roles, mention current Bengaluru base and full remote availability
"""

    prompt = f"""
You are a professional resume writer with 15 years of experience. Your task is to tailor
Nazish Mehdi's resume for a specific job. Write like a human expert, not an AI.

STRICT RULES — FOLLOW THESE EXACTLY:
1. NEVER use these overused AI words: "spearheaded", "leveraged", "orchestrated",
   "synergized", "utilized", "robust", "cutting-edge", "dynamic", "streamlined",
   "transformative", "innovative", "passionate", "results-driven"
2. Use SIMPLE, DIRECT language — write how a confident professional talks
3. Keep ALL real numbers and achievements (100B rows, 50+ customers, etc.) — these are gold
4. Only reorder and rephrase — NEVER invent skills or experience she doesn't have
5. Mirror the JD's language naturally — if the JD says "data pipeline", use "data pipeline"
6. Make changes SUBTLE — it should read like SHE wrote it, not a resume bot
7. Start bullet points with strong past-tense verbs: Built, Designed, Led, Reduced, Improved

OUTPUT FORMAT: Plain text resume in this order:
Professional Summary (3 lines max, punchy) → Technical Skills → Professional Experience
→ Core Competencies → Certifications → Education

JOB DETAILS:
Title: {job.title}
Company: {job.company}
Location: {job.location}, {job.region}
Description: {job.description[:2500]}

PRIORITISE THESE SKILLS FOR THIS ROLE:
{highlights if highlights else "Python, SQL, cloud data platforms"}

GAPS TO ACKNOWLEDGE HONESTLY:
{missing if missing else "None — strong match"}

{region_note}

NAZISH'S ACTUAL EXPERIENCE (use this as the base — do not change facts):
{BASE_RESUME_BULLETS}

CONTACT:
Nazish Mehdi | nazishmehdi26@gmail.com | +917349328590
LinkedIn: https://www.linkedin.com/in/nazishmehdi-80b0a5188/
Notice Period: 30 days
"""
    try:
        return _call_gemini(prompt, max_tokens=2000)
    except Exception as e:
        log.error(f"Resume tailoring failed for {job.job_id}: {e}")
        return ""


# ── 3. Cover Note ─────────────────────────────────────────────────────────────

def generate_cover_note(job: Job, relevance_data: dict) -> str:
    """Generates a short 3-paragraph cover note for the application."""
    prompt = f"""
Write a short, human cover note (3 paragraphs) for Nazish Mehdi applying to this role.

TONE GUIDE:
- Write like a real person, not a corporate robot
- Confident but not arrogant
- Specific — mention the company by name, reference something real from the JD
- NO clichés: "I am writing to express my interest", "I am a passionate professional",
  "I would be a great fit", "Please find attached", "I look forward to hearing from you"
- DO NOT start with "I" — start with something engaging

STRUCTURE:
Para 1: Lead with your strongest match point — make them want to read on
Para 2: One specific achievement from her experience that directly maps to their need
Para 3: One sentence on why THIS company specifically, then a confident close

JOB: {job.title} at {job.company}, {job.location}
WHY SHE FITS: {relevance_data.get('match_reasons', '')}
KEY JD REQUIREMENTS: {job.description[:800]}

Nazish's background: 5 years in data engineering and analytics,
ThoughtSpot certified architect, built data models for 50+ enterprise clients
handling up to 100 billion rows. Currently at ThoughtSpot as Senior Solutions Analyst.
"""
    try:
        return _call_gemini(prompt, max_tokens=500)
    except Exception as e:
        log.error(f"Cover note generation failed: {e}")
        return ""

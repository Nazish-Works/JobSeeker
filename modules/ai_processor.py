"""
modules/ai_processor.py
Uses Groq (free, llama-3.3-70b-versatile) to:
  1. Score job relevance (0-100) against Nazish's profile
  2. Tailor resume for matched jobs
  3. Generate a cover note
"""

import os
import json
import logging
import requests
from modules.scraper import Job

log = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "mixtral-8x7b-32768"


def _call_ai(prompt: str, max_tokens: int = 1000) -> str:
    """Calls Groq API — free tier, 14,400 requests/day."""
    if not GROQ_API_KEY:
        log.error("GROQ_API_KEY is not set!")
        return ""
    try:
        r = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2
            },
            timeout=30
        )
        if r.status_code != 200:
            log.error(f"Groq API returned {r.status_code}: {r.text[:200]}")
            return ""
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Groq API error: {e}")
        return ""


# ── Nazish's Full Profile ─────────────────────────────────────────────────────

PROFILE_SUMMARY = """
Name: Nazish Mehdi
Current Role: Senior Solutions Analyst @ ThoughtSpot (Aug 2024–Present)
Previous: Data Analyst @ SagasIT Analytics / AIMLEAP (Mar 2021–Apr 2023)
Total Experience: 5 years
Location: Bengaluru, India | Open to: Mumbai, Pune, Hyderabad | Saudi Arabia (onsite)
Notice Period: 30 days | Passport: Z6029437

Technical Skills:
- Languages: Python (Pandas, Selenium), SQL (Advanced), Java/Scala (exposure)
- Data Engineering: Matillion ETL, dbt, Fivetran, Apache Airflow
- Databases: Snowflake, BigQuery, PostgreSQL, SQL Server, Redshift, Oracle, Databricks
- Cloud: AWS (EC2, S3), GCP (BigQuery), Azure VM
- BI & Analytics: ThoughtSpot (Architect certified), Power BI, Looker, Tableau
- Other: Git, Docker, UiPath, RLS/PII masking, CI/CD workflows

Certifications (11 total):
- ThoughtSpot: Analyst, Consumer, Designer, Developer, Architect, Professional (6 certs)
- Snowflake: SnowPro Core + 4 advanced certs (5 certs)
- Microsoft Power BI Data Analyst
- Advanced SQL

Key Numbers:
- 50+ enterprise customers served
- Up to 100 billion rows optimized
- 5 years hands-on data experience
- 11 industry certifications
"""

# ── Full detailed resume for AI to work with ─────────────────────────────────

BASE_RESUME_CONTENT = """
NAZISH MEHDI
Bengaluru, India | +91-7349328590 | nazishmehdi26@gmail.com
LinkedIn: linkedin.com/in/nazishmehdi-80b0a5188
Passport: Z6029437 | Notice Period: 30 days

═══════════════════════════════════════════════════
PROFESSIONAL EXPERIENCE
═══════════════════════════════════════════════════

ThoughtSpot | Senior Solutions Analyst | Bengaluru, India | Aug 2024 – Present
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ThoughtSpot is a leading AI-powered analytics platform used by Fortune 500 companies.
As a Senior Solutions Analyst, I serve as the technical bridge between the product and
enterprise customers, driving adoption and solving complex data architecture challenges.

• Designed and deployed production-ready data models for 50+ enterprise customers
  across industries including finance, retail, healthcare, and manufacturing, optimizing
  query performance for datasets ranging from millions to 100 billion rows.

• Conducted deep-dive query performance analysis on customer data platforms including
  Snowflake, Databricks, Amazon Redshift, and Oracle — identifying bottlenecks and
  reducing query execution times by up to 60% through indexing, partitioning, and
  materialization strategies.

• Led full-scale BI migrations from Tableau and legacy reporting tools to ThoughtSpot,
  managing stakeholder alignment, data model redesign, and user training across
  cross-functional teams of 20–100+ users.

• Built and maintained Git-based version control workflows for ThoughtSpot data assets,
  enabling CI/CD-style deployment pipelines for analytics objects across dev/staging/prod
  environments — reducing deployment errors by 40%.

• Architected Row Level Security (RLS) frameworks and PII data masking solutions for
  regulated industries, ensuring compliance with GDPR, HIPAA, and internal data
  governance policies across 15+ enterprise deployments.

• Trained and fine-tuned ThoughtSpot Spotter (AI/NLP) models on customer data,
  enabling business users to generate insights via natural language queries — reducing
  analyst dependency for ad-hoc reporting by 35%.

• Converted a strategic customer from Essentials to Enterprise tier within 3 months
  by demonstrating measurable ROI through custom analytics dashboards, directly
  contributing to a significant TCV expansion.

• Collaborated with product and engineering teams to surface customer feedback,
  contributing to 5 product feature improvements shipped in quarterly releases.

SagasIT Analytics / AIMLEAP | Data Analyst | Remote | Mar 2021 – Apr 2023
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Built a fully automated Python ETL pipeline that extracted competitive intelligence
  data via the Semrush API, transformed and cleaned 500K+ records daily, and loaded
  into BigQuery — replacing a manual 8-hour process with a 15-minute automated run.

• Engineered a real-time fleet tracking system using Python and SQL Server that
  ingested GPS and operational data hourly, powering live Power BI dashboards
  for logistics managers to monitor 200+ vehicles across 3 regions.

• Developed enterprise-grade web scraping bots using Selenium and Python deployed
  on AWS EC2, capable of bypassing advanced anti-bot systems (Cloudflare, DataDome)
  at scale — extracting and storing 2TB+ of structured PDF datasets to Amazon S3.

• Designed and maintained PostgreSQL data pipelines (pgAdmin) that processed and
  structured scraped content into relational schemas, supporting downstream analytics
  and client reporting workflows.

• Automated data extraction and reporting workflows using UiPath RPA, reducing
  manual data preparation effort by 70% across 3 client accounts.

• Created and maintained Power BI reports and dashboards for C-suite stakeholders,
  transforming raw operational data into executive-ready visualizations with automated
  refresh schedules.

  AI Powered Personal Projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Designed and shipped a production-grade personal finance app using Claude AI as a
full-stack development assistant. Defined requirements, reviewed outputs, debugged
issues, and iterated through 50+ development cycles entirely through natural language
prompts.
What I built:
• Multi-user system with PIN authentication and admin/user role separation
• Real-time cloud sync via Supabase REST API with PostgreSQL backend
• 6 interactive chart types (donut, daily/monthly/all-time bar, category breakdown)
using Chart.js
• Income and reimbursement tracking with blurred balance cards and per-user financial
views
• Mobile-first PWA installable on iOS and Android with offline local storage fallback
• Full CRUD operations with animated transitions and Supabase persistence
• Advanced filtering by person, category, and time range across all reports
What this demonstrates:
• Ability to translate business requirements into technical specifications for AI tools
• Iterative product thinking — identifying edge cases, UX gaps, and data flow issues
• Hands-on debugging — read console errors, traced issues to root cause, directed fixes
• Full-stack understanding — frontend rendering, REST APIs, database schema, auth,
hosting
• AI fluency — effective prompt engineering across 50+ development iterations

═══════════════════════════════════════════════════
TECHNICAL SKILLS
═══════════════════════════════════════════════════

Languages & Querying:   Python (Pandas, Selenium, Requests), SQL (Advanced),
                        Java/Scala (exposure), Bash scripting

Data Engineering:       Matillion ETL, dbt (data build tool), Fivetran, Apache Airflow,
                        UiPath RPA, custom Python pipelines

Databases & Warehouses: Snowflake, Google BigQuery, PostgreSQL, SQL Server,
                        Amazon Redshift, Oracle, Databricks, MongoDB (exposure)

Cloud Platforms:        AWS (EC2, S3, WorkSpaces), GCP (BigQuery, Cloud Storage),
                        Azure VM, Azure Data Factory (exposure)

BI & Visualization:     ThoughtSpot (Architect certified), Power BI, Looker,
                        Tableau, Google Data Studio

DevOps & Tooling:       Git/GitHub, Docker (exposure), Kubernetes (exposure),
                        CI/CD pipelines, JIRA, Confluence

Security & Governance:  Row Level Security (RLS), PII data masking,
                        GDPR/HIPAA compliance frameworks

═══════════════════════════════════════════════════
CERTIFICATIONS (11)
═══════════════════════════════════════════════════

ThoughtSpot (6):   Analyst | Consumer | Designer | Developer | Architect | Professional
Snowflake (5):     SnowPro Core | SnowPro Advanced: Architect | Data Engineer |
                   Data Analyst | Collaboration (or similar advanced tier)
Microsoft:         Power BI Data Analyst Associate
SQL:               Advanced SQL Certification

═══════════════════════════════════════════════════
EDUCATION
═══════════════════════════════════════════════════

Bachelor of Engineering — Electronics & Communications Engineering
Maharaja Institute of Technology, VTU, India | Graduated 2020
"""


# ── 1. Relevance Scoring ─────────────────────────────────────────────────────

def score_relevance(job: Job) -> dict:
    prompt = f"""
You are a senior technical recruiter with 15 years of experience in data engineering
and analytics hiring. Evaluate how well Nazish Mehdi fits this job.

Return ONLY valid JSON — no markdown, no code fences, no explanation:
{{
  "score": <integer 0-100>,
  "match_reasons": "<2-3 specific sentences naming actual matching tools/skills>",
  "missing_skills": ["list only real gaps that matter"],
  "recommended_highlights": ["top 2-3 things from her experience to lead with for THIS role"]
}}

Scoring guide:
- 85–100: Excellent fit — title, seniority, and tech stack all match closely
- 70–84: Strong fit — most requirements met, minor gaps
- 55–69: Good fit — relevant experience, some gaps
- 40–54: Partial fit — transferable skills but notable gaps
- Below 40: Poor fit

Key context:
- ThoughtSpot = BI/Analytics platform (similar to Tableau/Power BI/Looker — transferable)
- Her Snowflake + BigQuery + dbt stack is highly in-demand
- 100B row optimization is a rare and impressive differentiator
- 11 certifications shows commitment to continuous learning

CANDIDATE:
{PROFILE_SUMMARY}

JOB TITLE: {job.title}
COMPANY: {job.company}
LOCATION: {job.location}
REGION: {job.region}
JOB DESCRIPTION:
{job.description[:2500]}
"""
    try:
        text = _call_ai(prompt, max_tokens=600)
        if not text:
            log.warning(f"Groq empty response for {job.job_id} — fallback score 70")
            return {"score": 70, "match_reasons": "Could not score — review manually",
                    "missing_skills": [], "recommended_highlights": []}
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        log.error(f"Relevance scoring failed for {job.job_id}: {e}")
        return {"score": 70, "match_reasons": "Scoring error — review manually",
                "missing_skills": [], "recommended_highlights": []}


# ── 2. Resume Tailoring ───────────────────────────────────────────────────────

def tailor_resume(job: Job, relevance_data: dict) -> str:
    highlights = "\n".join(f"- {h}" for h in relevance_data.get("recommended_highlights", []))
    missing    = ", ".join(relevance_data.get("missing_skills", []))

    if job.region == "Saudi":
        location_note = """
LOCATION NOTE (Saudi role):
- Open to relocate to Saudi Arabia immediately (30-day notice period)
- Passport number: Z6029437 (include in contact section)
- Highlight enterprise-scale experience — relevant to Saudi Aramco, STC, NEOM, Accenture KSA culture
- Emphasise ThoughtSpot's presence in the Middle East market if relevant
"""
    else:
        location_note = """
LOCATION NOTE (India role):
- Currently based in Bengaluru (no relocation needed for Bengaluru roles)
- Open to relocate within India to Mumbai, Pune, or Hyderabad (30-day notice)
- Open to remote/hybrid arrangements
"""

    prompt = f"""
You are an elite resume writer who has helped 500+ data professionals land jobs at
top companies. Your resumes are known for being specific, impressive, and human.

Your task: Tailor Nazish Mehdi's resume for the specific job below.
The output must be a COMPLETE, READY-TO-USE resume — not a template, not suggestions.
Someone should be able to copy this and submit it directly.

══════════════════════════════════════
WRITING RULES (follow every single one)
══════════════════════════════════════
1. BANNED WORDS — never use: spearheaded, leveraged, orchestrated, synergized,
   utilized, robust, cutting-edge, dynamic, streamlined, transformative,
   innovative, passionate, results-driven, detail-oriented, self-starter,
   team player, go-getter, thought leader, best-in-class
2. Use STRONG ACTION VERBS: Built, Designed, Reduced, Improved, Delivered,
   Architected, Automated, Optimized, Led, Deployed, Migrated, Analysed
3. KEEP ALL NUMBERS — 100B rows, 50+ customers, 60% faster, 70% reduction
   These are her strongest selling points. Never remove or water them down.
4. Mirror the JD's exact language — if JD says "data pipeline", use "data pipeline"
   not "ETL workflow". If JD says "stakeholder management", use those words.
5. NEVER invent experience — only rephrase and reorder what she actually did
6. Professional Summary must be 3 sentences max — punchy, specific, no fluff
7. Bullet points: max 2 lines each, start with verb, end with a number or outcome
8. Put the most JD-relevant bullets FIRST in each role
9. Technical skills section: group by category, use exact tool names from the JD

══════════════════════════════════════
TARGET JOB
══════════════════════════════════════
Title: {job.title}
Company: {job.company}
Location: {job.location} ({job.region})
Job Description:
{job.description[:2500]}

SKILLS TO PRIORITISE FOR THIS ROLE:
{highlights if highlights else "Python, SQL, cloud data warehousing, BI analytics"}

GAPS (address honestly but briefly):
{missing if missing else "No significant gaps identified"}

{location_note}

══════════════════════════════════════
NAZISH'S FULL EXPERIENCE (your source material)
══════════════════════════════════════
{BASE_RESUME_CONTENT}

══════════════════════════════════════
OUTPUT FORMAT
══════════════════════════════════════
Produce the complete tailored resume in this exact order:

[CONTACT SECTION]
Full name, email, phone, LinkedIn, location, notice period
(For Saudi: also include passport number)

[PROFESSIONAL SUMMARY]
3 sentences. Sentence 1: years of experience + key specialisation.
Sentence 2: strongest relevant achievement with a number.
Sentence 3: what she brings to THIS specific company/role.

[TECHNICAL SKILLS]
Grouped by category. Put JD-relevant tools first.

[PROFESSIONAL EXPERIENCE]
Most recent first. For each role: company, title, location, dates.
4–6 bullet points, most JD-relevant first.

[CERTIFICATIONS]
List all 11 certifications.

[EDUCATION]
Degree, field, graduation year.
"""
    try:
        result = _call_ai(prompt, max_tokens=2500)
        if not result:
            log.error(f"Resume tailoring returned empty for {job.job_id}")
        return result
    except Exception as e:
        log.error(f"Resume tailoring failed for {job.job_id}: {e}")
        return ""


# ── 3. Cover Note ─────────────────────────────────────────────────────────────

def generate_cover_note(job: Job, relevance_data: dict) -> str:
    prompt = f"""
Write a compelling 3-paragraph cover note for Nazish Mehdi applying to this role.
This must sound like a real, confident professional wrote it — not a bot.

══════════════════════════════════════
TONE & STYLE RULES
══════════════════════════════════════
- Confident but not arrogant
- Specific — name the company, reference something real from the JD
- Conversational but professional
- DO NOT start the letter with "I"
- BANNED phrases: "I am writing to express my interest",
  "I am a passionate professional", "I would be a great fit",
  "Please find attached my resume", "I look forward to hearing from you",
  "I am excited about this opportunity", "highly motivated"

══════════════════════════════════════
STRUCTURE
══════════════════════════════════════
PARAGRAPH 1 (Hook — 2-3 sentences):
Open with your strongest match point. Make the hiring manager want to read on.
Reference something specific from the JD or the company.

PARAGRAPH 2 (Proof — 3-4 sentences):
One specific, quantified achievement that directly proves you can do what they need.
Use a real number (100B rows, 50+ clients, 60% improvement, etc.)

PARAGRAPH 3 (Close — 2 sentences):
Why this company specifically (not generic). End with a confident, direct close.

══════════════════════════════════════
JOB CONTEXT
══════════════════════════════════════
Role: {job.title} at {job.company}, {job.location}
Why she fits: {relevance_data.get('match_reasons', '')}
Key JD requirements: {job.description[:1000]}

Nazish's background:
- 5 years across data engineering, analytics, and BI
- Senior Solutions Analyst at ThoughtSpot — works with 50+ enterprise clients
- Optimised data models for workloads up to 100 billion rows
- 11 certifications: ThoughtSpot (6), Snowflake (5), Power BI
- Stack: Python, SQL, Snowflake, BigQuery, dbt, Fivetran, Power BI, Looker
"""
    try:
        return _call_ai(prompt, max_tokens=600)
    except Exception as e:
        log.error(f"Cover note generation failed: {e}")
        return ""

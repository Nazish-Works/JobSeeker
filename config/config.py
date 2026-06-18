# =============================================================================
# JobSeeker Configuration — Nazish Mehdi
# =============================================================================

# --- Your Profile --------------------------------------------------------
CANDIDATE_PROFILE = {
    "name": "Nazish Mehdi",
    "email": "nazishmehdi26@gmail.com",
    "phone": "+917349328590",
    "linkedin": "https://www.linkedin.com/in/nazishmehdi-80b0a5188/",
    "current_title": "Senior Data Analyst / Senior Solutions Analyst",
    "years_experience": 5,
    "current_location": "Bengaluru, India",  # Primary preference for onsite roles
    "notice_period_days": 30,
    "nationality": "Indian",
    "passport": "Z6029437",

    "core_skills": [
        "Python", "SQL", "Snowflake", "BigQuery", "dbt", "Fivetran",
        "Matillion ETL", "Power BI", "Looker", "ThoughtSpot",
        "AWS (EC2, S3)", "Azure VM", "Google Cloud Platform",
        "Selenium", "Pandas", "Airflow", "Docker", "PostgreSQL",
        "Data Modeling", "ETL Pipeline Development", "Web Scraping",
        "Row Level Security", "Data Masking", "NLP", "UiPath"
    ],

    "certifications": [
        "ThoughtSpot Professional", "ThoughtSpot Architect",
        "ThoughtSpot Cloud Architect", "Snowflake Data Engineering",
        "Snowflake Data Warehouse", "Power BI", "Advanced SQL"
    ],
}

# --- Job Search Keywords -------------------------------------------------
SEARCH_KEYWORDS = [
    "Senior Data Analyst",
    "Data Analyst",
    "Data Engineer",
    "Analytics Engineer",
    "BI Developer",
]

# --- Location Preferences ------------------------------------------------
# India: open to onsite in these cities + remote
INDIA_PREFERRED_CITIES = [
    "Bengaluru", "Bangalore", "bengaluru", "bangalore", "karnataka",
    "Mumbai", "Pune", "Hyderabad",
]
INDIA_ACCEPT_REMOTE = True   # remote accepted if no onsite match in preferred cities

# Saudi Arabia: onsite only
SAUDI_CITIES = ["Riyadh", "Jeddah", "Dhahran", "NEOM", "Dammam", "Khobar"]
SAUDI_ACCEPT_REMOTE = False  # onsite only for Saudi
SAUDI_SKIP_NATIONALS_ONLY = True  # skip roles requiring Saudi nationals

# --- Portals to scan -----------------------------------------------------
PORTALS = {
    # India
    "indeed_india": {
        "enabled": True,
        "region": "India",
        "base_url": "https://www.indeed.co.in/jobs",
        "location_param": "l",
        "query_param": "q",
    },
    "naukri": {
        "enabled": True,
        "region": "India",
        "base_url": "https://www.naukri.com",
        "search_path": "/{keyword}-jobs-in-{location}",
    },
    "wellfound": {
        "enabled": True,
        "region": "India",
        "base_url": "https://wellfound.com/jobs",
    },

    # Saudi Arabia / Gulf
    "bayt": {
        "enabled": True,
        "region": "Saudi",
        "base_url": "https://www.bayt.com/en/saudi-arabia/jobs",
        "location": "Saudi-Arabia",
    },
    "gulftalent": {
        "enabled": True,
        "region": "Saudi",
        "base_url": "https://www.gulftalent.com/saudi-arabia/jobs",
    },
    "naukrigulf": {
        "enabled": True,
        "region": "Saudi",
        "base_url": "https://www.naukrigulf.com",
        "location": "Saudi-Arabia",
    },
    "indeed_saudi": {
        "enabled": True,
        "region": "Saudi",
        "base_url": "https://sa.indeed.com/jobs",
    },
}

# --- Scheduling ----------------------------------------------------------
SCAN_TIMES_UTC = ["03:00", "07:00", "11:00", "15:00", "19:00"]  # 5×/day
# Converts to IST: 08:30, 12:30, 16:30, 20:30, 00:30

# --- AI Relevance Settings -----------------------------------------------
MIN_RELEVANCE_SCORE = 65      # 0–100; jobs below this are skipped
ANTHROPIC_MODEL    = "claude-sonnet-4-20250514"

# --- Google Integration --------------------------------------------------
GDRIVE_FOLDER_NAME   = "JobSeeker — Tailored Resumes"
GSHEET_NAME          = "JobSeeker — Applications Tracker"

# --- Notifications -------------------------------------------------------
NOTIFY_EMAIL         = "nazishmehdi26@gmail.com"
NOTIFY_ON_NEW_MATCH  = True
NOTIFY_DIGEST_HOUR   = 8    # IST: morning digest email with day's matches

# --- Paths ---------------------------------------------------------------
BASE_RESUME_PATH     = "resumes/Nazish_Mehdi_Resume_2026.pdf"
SEEN_JOBS_DB         = "data/seen_jobs.json"
APPLICATIONS_LOG     = "data/applications.json"

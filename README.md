# JobSeeker — Automated Job Hunt Pipeline
### Nazish Mehdi | Senior Data Analyst

Scans 7 job portals across India and Saudi Arabia, scores each role via Claude AI,
tailors your resume per JD, saves to Google Drive, logs to Google Sheets, and
emails you a digest — 5 times a day, automatically via GitHub Actions.

---

## What It Does

| Step | Action |
|------|--------|
| 1 | Scrapes Indeed India, Naukri, Wellfound (India) + Bayt, GulfTalent, NaukriGulf, Indeed Saudi |
| 2 | Deduplicates — never scores the same job twice |
| 3 | Filters: India → Mumbai/Pune/Hyderabad or remote. Saudi → onsite only, skips nationals-only |
| 4 | Claude scores each job 0–100 for relevance to your profile |
| 5 | Jobs ≥ 65/100 get a tailored resume + cover note |
| 6 | Tailored resume saved as `.txt` in Google Drive folder |
| 7 | Row added to Google Sheets tracker (title, company, score, URL, Drive link, status) |
| 8 | Email digest sent to nazishmehdi26@gmail.com |

---

## One-Time Setup (do this once)

### Step 1 — Clone your repo
```bash
git clone https://github.com/Nazish-Works/JobSeeker
cd JobSeeker
pip install -r requirements.txt
```

### Step 2 — Get your Anthropic API Key
1. Go to https://console.anthropic.com
2. Create an API key
3. Save it — you'll add it to GitHub Secrets in Step 5

### Step 3 — Set up Google OAuth (for Drive + Sheets + Gmail)
1. Go to https://console.cloud.google.com
2. Create a new project called "JobSeeker"
3. Enable these 3 APIs:
   - Google Drive API
   - Google Sheets API
   - Gmail API
4. Go to "OAuth consent screen" → External → fill in app name "JobSeeker"
5. Go to "Credentials" → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Name: JobSeeker
6. Download the JSON → save as `credentials.json` in the project root
7. Run this once locally to generate `token.json`:
   ```bash
   python -c "from modules.google_integration import _get_creds; _get_creds()"
   ```
   A browser window will open → sign in with your Google account → allow permissions
8. A `token.json` file is created. **Keep this safe — it's your login token.**

### Step 4 — Copy your resume PDF
```bash
cp /path/to/Nazish_Mehdi_Resume_2026.pdf resumes/
```

### Step 5 — Add GitHub Secrets (so Actions can run without exposing keys)
Go to your repo → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key from Step 2 |
| `GOOGLE_CREDENTIALS_JSON` | Paste the full contents of `credentials.json` |

Also commit `token.json` to the repo (it's needed for Actions to auth with Google):
```bash
git add token.json
git commit -m "Add Google auth token"
git push
```
> Note: `token.json` contains your Google auth — don't share the repo publicly.
> If your repo is public, instead add `token.json` contents as a GitHub Secret
> and write it to disk in the workflow (same pattern as `credentials.json`).

### Step 6 — Push everything and enable Actions
```bash
git add .
git commit -m "Initial JobSeeker setup"
git push
```
Go to your repo → Actions tab → enable workflows if prompted.

### Step 7 — Test it manually
In GitHub Actions → "JobSeeker — Auto Scan" → "Run workflow" → Run.
Check the logs, then check your Google Sheets and Drive.

---

## Running Locally (anytime)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python main.py
```

---

## Customising

**Change relevance threshold:** Edit `MIN_RELEVANCE_SCORE` in `config/config.py` (default: 65)

**Add/remove keywords:** Edit `SEARCH_KEYWORDS` in `config/config.py`

**Add a new portal:** Add a scraper function in `modules/scraper.py` and call it in `run_all_scrapers()`

**Change scan frequency:** Edit the cron expressions in `.github/workflows/job_scan.yml`

---

## Your Google Sheets Tracker Columns

| Column | Description |
|--------|-------------|
| Date Found | When the job was found |
| Portal | Which site (bayt, naukri, indeed_india, etc.) |
| Region | India or Saudi |
| Job Title | As listed |
| Company | As listed |
| Location | City / Remote |
| Relevance Score | 0–100 from Claude |
| Match Reason | Why Claude thinks it fits |
| Job URL | Direct link to apply |
| Resume (Drive) | Link to your tailored resume |
| Cover Note | Short cover note |
| **Status** | **You update this: New → Applied → Interview → Rejected → Offer** |
| Applied Date | Fill in when you apply |
| Notes | Your personal notes |

---

## Troubleshooting

**"Scraper returns 0 jobs"** — Portal HTML structure may have changed. Run the scraper for one portal and inspect the raw HTML to update selectors in `modules/scraper.py`.

**"Google auth error"** — Your `token.json` may have expired. Delete it and re-run the local auth step.

**"Claude API error"** — Check your `ANTHROPIC_API_KEY` secret is set correctly in GitHub.

**LinkedIn not included?** — LinkedIn blocks scrapers. Use LinkedIn Job Alerts (set up email alerts for your search) and forward them to your Gmail. The pipeline can be extended to read those emails via Gmail API.

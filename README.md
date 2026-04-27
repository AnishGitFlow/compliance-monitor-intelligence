# BFSI Compliance Intelligence Monitor

## 1. Overview
The **BFSI Compliance Intelligence Monitor** is an automated intelligence pipeline designed to track, extract, and analyze LinkedIn posts related to regulatory and compliance topics from senior leaders within India's Banking, Financial Services, and Insurance (BFSI) ecosystem. 

**Key Features:**
- **Automated Discovery:** Queries Google Search (via Serper API) daily to find relevant LinkedIn posts published in the last 24 hours.
- **Intelligent Deduplication:** Maintains a local history to ensure you never receive the same post twice, even if it's re-shared.
- **AI-Powered Enrichment:** Leverages Google Gemini to automatically categorize posts, extract regulatory keywords, determine tone, and generate concise summaries. Includes a robust rule-based fallback.
- **Premium Reporting:** Generates a visually appealing, responsive HTML "Executive Dashboard" email detailing the daily insights.
- **Cloud-Ready:** Designed to run seamlessly as a scheduled GitHub Action.

**Target Users:**
Compliance Officers, Risk Managers, RegTech Founders, and BFSI Executives who need a curated, daily digest of market sentiment and regulatory updates without manually scrolling through LinkedIn.

---

## 2. Architecture
The system follows a linear, modular **Extract, Transform, Load (ETL)** pipeline pattern.

1. **Extract (`scraper.py`)**: Uses Serper API to query Google for recent LinkedIn posts matching specific compliance and BFSI keywords.
2. **Filter & Deduplicate (`deduplicator.py`)**: Checks the extracted URLs and content hashes against a persistent JSON database to drop duplicates.
3. **Enrich (`enricher.py`)**: Passes the raw text to Google Gemini for structural analysis (Category, Tone, Regulators, Summary).
4. **Report (`reporter.py`)**: Compiles the enriched data into an HTML template and dispatches it via SMTP.
5. **Orchestrate (`main.py`)**: Ties the modules together and manages execution flow.

---

## 3. Folder & File Structure

```text
/
├── main.py               # Main entry point and orchestration script
├── config.py             # Centralized settings (Queries, Keywords, APIs)
├── scraper.py            # Serper API integration and Google result parsing
├── deduplicator.py       # Logic for tracking URLs and preventing duplicates
├── enricher.py           # Google Gemini AI integration and fallback logic
├── reporter.py           # HTML generation and SMTP email dispatch
├── test_pipeline.py      # Diagnostic tool to verify API keys and connections
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (API Keys, Passwords)
├── .gitignore            # Git exclusion rules
├── .github/
│   └── workflows/
│       └── daily_report.yml # GitHub Actions configuration for automation
└── data/
    ├── history.json      # Persistent storage for deduplication (tracked by Git)
    └── reports/          # Locally saved JSON/HTML reports (ignored by Git)
```

---

## 4. Setup & Installation

### Prerequisites
- Python 3.10+
- A [Serper API](https://serper.dev/) Account (for Google Search scraping)
- A [Google AI Studio](https://aistudio.google.com/) Account (for Gemini API)
- A Gmail Account with an "App Password" (for sending emails)

### Step-by-Step Setup
1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and populate it:
   ```env
   SERPER_API_KEY=your_serper_key_here
   GEMINI_API_KEY=your_gemini_key_here
   GEMINI_MODEL=gemini-2.0-flash-lite
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   REPORT_TO=recipient1@example.com, recipient2@example.com
   REPORT_FROM=your_email@gmail.com
   ```

---

## 5. Usage

### Diagnostics
Before running the main pipeline, verify your environment and API keys:
```bash
python test_pipeline.py
```

### Running Locally
To run a single execution of the pipeline immediately:
```bash
python main.py
```

### Running as a Local Service
To run the script continuously and have it trigger daily at the time specified in `config.py` (e.g., `08:00`):
```bash
python main.py --schedule
```

### Cloud Automation (GitHub Actions)
The repository includes a GitHub Action (`.github/workflows/daily_report.yml`) that automatically runs the pipeline from Monday to Friday at 02:30 UTC (08:00 AM IST). 
To enable this:
1. Push the code to GitHub.
2. Add your `.env` variables to **GitHub Repository Settings > Secrets and variables > Actions**.

---

## 6. Core Components Explanation

### `config.py`
The brain of the operation's parameters. It defines the search queries sent to Google, the strict compliance keywords required to pass the filter, and lists of BFSI/Startup indicators.

### `scraper.py`
- Calls `https://google.serper.dev/search` using the `site:linkedin.com/posts` operator.
- Iterates through a configured list of search queries to maximize the discovery of relevant posts.
- Enforces a strict 24-hour time window (`tbs=qdr:d`) and performs a best-effort `og:meta` tag scrape on the LinkedIn URL to extract the full post content.

### `enricher.py`
- Constructs a prompt for `gemini-2.0-flash-lite` asking for JSON output.
- **Fallback Mechanism:** If the Gemini API is exhausted (429 error) or fails, the `_fallback_enrich` function uses regular expressions and keyword matching to categorize the post and extract regulators, ensuring the pipeline never breaks.

### `reporter.py`
- Constructs a high-fidelity, responsive HTML email ("Executive Dashboard").
- Uses `smtplib` to dispatch the email to the configured recipients.
- Saves local copies of the reports in `data/reports/` for auditing.

---

## 7. Dependencies

| Library | Purpose |
|---|---|
| `requests` | Making HTTP calls to Serper API and LinkedIn |
| `beautifulsoup4` | Parsing `og:meta` tags from LinkedIn HTML |
| `google-genai` | Official Google SDK for accessing Gemini AI |
| `python-dotenv` | Loading API keys from the `.env` file |
| `schedule` | Handling local daily chron scheduling |
| `lxml` | Fast HTML parsing engine used by BeautifulSoup |

---

## 8. Testing
The project includes a robust diagnostic script: `test_pipeline.py`.
- **What it tests:** 
  1. Validates presence of `.env` variables.
  2. Pings Serper API to verify authentication.
  3. Runs a live Google Search test.
  4. Pings the Gemini API to verify quota and model availability.
  5. Attempts an SMTP login to verify email credentials.

**To test:** Run `python test_pipeline.py`.

---

## 9. Contribution Guide
- **Adding Keywords/Queries:** Modify `config.py`. No logic changes are needed.
- **Changing Email Design:** Modify the HTML string inside the `_build_html` function in `reporter.py`.
- **Stateless Operation:** Ensure that any new tracking mechanisms utilize `data/history.json` so they can be persisted by GitHub Actions.

---

## 10. Known Issues / Limitations
- **LinkedIn Scraping Limits:** The script relies on Google Search snippets and basic `og:meta` tags because scraping LinkedIn directly requires a logged-in session, which is prone to bans. Consequently, exact metrics like "Likes" or "Comments" cannot be accurately extracted.
- **Search Result Overlap:** Because multiple queries are used, the raw fetch volume is high, but the unique post yield is smaller due to Google returning the same viral posts across different keywords.

---

## 11. Future Improvements
- **Alternative Data Sources:** Integrate official LinkedIn API or premium data providers if deeper metrics (engagement stats, full author profiles) are required.
- **Multi-Channel Delivery:** Expand `reporter.py` to send alerts via Slack or Microsoft Teams webhooks for high-priority "Risk Alert" posts.
- **Database Migration:** If the `history.json` file grows too large, migrate deduplication tracking to a lightweight cloud database (e.g., Firebase, Supabase, or AWS DynamoDB).

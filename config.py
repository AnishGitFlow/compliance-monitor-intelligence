"""
config.py - Central configuration for the Indian AMC/AIF/PMS Compliance Signal Monitor
Updated to use OpenRouter instead of Gemini for LLM enrichment.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ─────────────────────────────────────────────────────────────────────
SERPER_API_KEY      = os.getenv("SERPER_API_KEY", "")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free-model fallback chain (tried in order via OpenRouter's route=fallback)
OPENROUTER_MODELS = [
    os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free"),
    "deepseek/deepseek-v4-flash:free",
    "z-ai/glm-4.5-air:free",
    "openrouter/free",
]

# ── Email Delivery (Microsoft 365 / Outlook) ─────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
REPORT_TO     = os.getenv("REPORT_TO", "")
REPORT_FROM   = os.getenv("REPORT_FROM", SMTP_USER)

# ── Scheduler ─────────────────────────────────────────────────────────────────────
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "08:00")  # 24-hr IST

# ── API Usage Settings ────────────────────────────────────────────────────────────
# Set to None to process ALL search queries every run.
# If you later want throttling again, set a numeric value like 5 or 10.
DAILY_QUERY_LIMIT = None

# LLM processing limits
TOP_POSTS_FOR_LLM = 5
MAX_CHARS_FOR_LLM = 700

# ── Semantic Engine Settings ──────────────────────────────────────────────────────
# Cosine similarity threshold (0.0–1.0). Posts below this are discarded.
# 0.35 = permissive (more posts pass), 0.50 = strict (only high-match posts pass)
# Increased slightly to reduce noisy posts.
# Recommended range:
# 0.40 = balanced
# 0.45 = strict high-intent filtering
SEMANTIC_THRESHOLD = 0.42

# ==============================================================================
# TARGET CONCEPTS
# ==============================================================================

TARGET_CONCEPTS = {

    "Compliance Pain": (
        "A company or professional discussing manual compliance processes, spreadsheet-based "
        "tracking, operational bottlenecks, delays in regulatory filings, errors in audit "
        "reporting, or scaling challenges in compliance workflows inside an Indian fund or "
        "wealth management firm."
    ),

    "Regulatory Pressure": (
        "A SEBI circular, new regulation, compliance update, or governance requirement "
        "impacting Indian AMC, AIF, PMS, or wealth management companies. Includes posts "
        "about increased scrutiny, audits, disclosure requirements, or firms adapting to "
        "new regulatory changes in India."
    ),

    "Audit and Risk": (
        "Concerns about audit readiness, internal or external audits, gaps in compliance "
        "frameworks, risk controls, exception management, or operational risk in Indian "
        "investment management firms including AMC, AIF, PMS."
    ),

    "Transformation and Modernization": (
        "A firm pursuing digital transformation, automation, regtech adoption, or replacing "
        "legacy systems in their compliance or operations function. Includes posts about "
        "process improvement, scaling operations, or adopting compliance technology in "
        "Indian fund management or wealth management."
    ),

    "Business Growth Trigger": (
        "An Indian AMC, AIF, PMS, or wealth management firm announcing a new fund launch, "
        "significant AUM growth, entry into a new regulatory category, new product lines, "
        "or business expansion that would trigger new compliance requirements."
    ),
}

# ==============================================================================
# HARD FILTERS
# ==============================================================================

# More permissive India relevance filter.
# Avoids dropping useful operational posts that don't explicitly mention India.
INDIA_HARD_SIGNALS = [
    "india", "indian", "sebi", "amfi", "rbi", "pmla", "dpdp",
    "aif", "pms", "amc", "mutual fund", "wealth management",
    "asset management", "fund house", "investment management",
    "nse", "bse", "compliance", "audit", "regulatory",
]

EXCLUDE_KEYWORDS = [

    # Non-India regulations
    "us sec",
    "sec filing",
    "finra",
    "mifid",
    "european union",
    "us regulation",

    # Generic low-signal events
    "conference",
    "podcast",
    "webinar",
    "panel discussion",
    "speaking at",
    "register now",

    # Generic engagement bait
    "like and share",
    "subscribe now",
]

# ==============================================================================
# COMPANY PRIORITY
# ==============================================================================

HIGH_PRIORITY_COMPANIES = [
    "amc", "aif", "pms", "asset management", "investment management",
    "mutual fund", "fund house", "wealth management",
]

MEDIUM_PRIORITY_COMPANIES = [
    "fintech", "investment advisory", "wealthtech", "capital markets",
]

# ==============================================================================
# SEARCH QUERIES
# Tailored specifically for operational compliance pain, audit readiness,
# SEBI workflow pressure, and BFSI compliance modernization.
# ==============================================================================

SEARCH_QUERIES = [

    # --------------------------------------------------------------------------
    # Manual Compliance Operations Pain
    # --------------------------------------------------------------------------
    "manual compliance tracking AMC India",
    "manual circular tracking AIF India",
    "spreadsheet based compliance PMS",
    "compliance workflow challenges wealth management",
    "compliance operations struggling India",
    "manual audit tracking AMC",
    "compliance submissions operational pressure",
    "SEBI reporting taking too much time",
    "compliance team overwhelmed reporting",
    "legacy compliance workflows BFSI",

    # --------------------------------------------------------------------------
    # Audit Readiness + Regulatory Pressure
    # --------------------------------------------------------------------------
    "SEBI circular implementation challenges",
    "SEBI compliance pressure AMC",
    "audit readiness investment management India",
    "regulatory submission tracking India",
    "internal audit compliance gaps BFSI",
    "compliance evidence tracking fund management",
    "governance and compliance challenges AMC",
    "risk and compliance operations India",
    "compliance exceptions management AIF",
    "regulatory operations bottlenecks India",

    # --------------------------------------------------------------------------
    # Transformation + Modernization
    # --------------------------------------------------------------------------
    "automating compliance operations India",
    "regtech adoption AMC India",
    "digital transformation compliance workflows",
    "replacing spreadsheets in compliance",
    "compliance automation wealth management",
    "scaling compliance operations AIF",
    "modernizing compliance infrastructure India",
    "AI for compliance operations BFSI",
    "operational efficiency compliance teams",
    "compliance process automation PMS",

    # --------------------------------------------------------------------------
    # Business Growth Triggers
    # --------------------------------------------------------------------------
    "new fund launch AIF India",
    "AUM growth wealth management firm",
    "new PMS launch India",
    "AMC expansion India compliance",
    "new compliance requirements SEBI",
    "investment firm operational scaling India",

    # --------------------------------------------------------------------------
    # High-Intent Conversational Queries
    # --------------------------------------------------------------------------
    "still managing compliance manually",
    "compliance workflows are broken",
    "compliance chaos before audit",
    "tracking SEBI circulars manually",
    "audit preparation taking weeks",
    "compliance process needs automation",
    "manual regulatory tracking problems",
    "difficulty managing compliance deadlines",
]

# ==============================================================================
# OPTIONAL HELPER FUNCTION
# ==============================================================================

def get_active_queries():
    """
    Returns all search queries if DAILY_QUERY_LIMIT is None.
    Otherwise returns a limited subset.
    """

    if DAILY_QUERY_LIMIT is None:
        return SEARCH_QUERIES

    return SEARCH_QUERIES[:DAILY_QUERY_LIMIT]


# ==============================================================================
# BACKWARD-COMPATIBLE QUERY ROTATION FUNCTION
# ==============================================================================

def get_daily_queries(day=0):
    """
    Returns active search queries.

    If DAILY_QUERY_LIMIT is None:
        returns ALL queries.

    Otherwise:
        rotates queries daily to reduce SERPER usage.
    """

    if DAILY_QUERY_LIMIT is None:
        return SEARCH_QUERIES

    start = (day * DAILY_QUERY_LIMIT) % len(SEARCH_QUERIES)
    end = start + DAILY_QUERY_LIMIT

    if end <= len(SEARCH_QUERIES):
        return SEARCH_QUERIES[start:end]

    return SEARCH_QUERIES[start:] + SEARCH_QUERIES[: end - len(SEARCH_QUERIES)]

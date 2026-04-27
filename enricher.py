"""
enricher.py - Optimised AI enrichment using Google Gemini with rule-based fallback.

Token-saving pipeline:
  1. Sort posts by signal score (highest first)
  2. Only top TOP_POSTS_FOR_LLM posts are eligible for Gemini
  3. Each post must score >= MIN_SIGNAL_SCORE to reach Gemini
  4. Post content is truncated to MAX_CHARS_FOR_LLM before the Gemini call
  5. Minimal JSON prompt is used (< 50 tokens of instructions)
  6. 5-second delay between Gemini calls to respect free-tier rate limits
  7. All other posts fall back to fast rule-based enrichment
"""
import json
import re
import time

from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    TOP_POSTS_FOR_LLM, MAX_CHARS_FOR_LLM, SEMANTIC_THRESHOLD,
)

# ── Gemini client (optional) ────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    _client = (
        genai.Client(api_key=GEMINI_API_KEY)
        if GEMINI_API_KEY and GEMINI_API_KEY not in ("", "your_gemini_api_key_here")
        else None
    )
except Exception:
    _client = None
    genai_types = None

# ── Constants ────────────────────────────────────────────────────────────────────
POST_CATEGORIES = [
    "Regulatory Update",
    "Opinion / Commentary",
    "Risk Alert",
    "Product / Solution Insight",
    "Hiring / Talent",
    "Thought Leadership",
    "Case Study",
    "Event / Webinar",
]

TONE_LABELS = ["Positive", "Neutral", "Concerned", "Critical"]

REGULATOR_ENTITIES = [
    "RBI", "SEBI", "IRDAI", "PFRDA", "FIU-IND", "MCA", "IT Ministry",
    "FATF", "BIS", "Basel Committee", "DPDP", "PMLA", "NHB", "IFSCA", "AMFI",
]

# ── Minimal Gemini prompt (keeps token usage extremely low) ──────────────────────
_GEMINI_PROMPT = """\
Classify this LinkedIn post from India's AMC/AIF/PMS/wealth sector.

Return ONLY valid JSON, no markdown:
{{
  "category": "<one of: {categories}>",
  "tone": "<one of: {tones}>",
  "regulators_mentioned": [],
  "summary": "<1-2 sentences, compliance angle only>"
}}

POST:
{content}"""


# ── Gemini enrichment ────────────────────────────────────────────────────────────

def _gemini_enrich(content: str) -> dict | None:
    """Call Gemini with a truncated post and minimal prompt. Returns None on failure."""
    if not _client:
        return None

    clean_text = content[:MAX_CHARS_FOR_LLM]
    prompt = _GEMINI_PROMPT.format(
        categories=", ".join(POST_CATEGORIES),
        tones=", ".join(TONE_LABELS),
        content=clean_text,
    )
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(temperature=0.1),
        )
        text = response.text.strip()
        # Strip code fences if present
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"```$", "", text).strip()
        data = json.loads(text)
        # Validate expected keys
        required = {"category", "tone", "regulators_mentioned", "summary"}
        if required.issubset(data.keys()):
            return data
    except Exception as e:
        print(f"  [Enricher] Gemini failed: {e}")
    return None


# ── Rule-based fallback ──────────────────────────────────────────────────────────

def _rule_based_enrich(content: str) -> dict:
    low = content.lower()

    # Category
    category = "Thought Leadership"
    if any(k in low for k in ("hiring", "looking for", "join our team", "open role")):
        category = "Hiring / Talent"
    elif any(k in low for k in ("webinar", "event", "conference", "summit", "register")):
        category = "Event / Webinar"
    elif any(k in low for k in ("case study", "success story", "how we helped")):
        category = "Case Study"
    elif any(k in low for k in ("launched", "announcing", "product", "solution", "platform")):
        category = "Product / Solution Insight"
    elif any(k in low for k in ("alert", "fraud", "breach", "scam", "attack", "cyber")):
        category = "Risk Alert"
    elif any(k in low for k in ("circular", "notification", "rbi directive", "sebi order", "gazette")):
        category = "Regulatory Update"
    elif any(k in low for k in ("opinion", "i think", "my view", "perspective", "thoughts on")):
        category = "Opinion / Commentary"

    # Tone
    tone = "Neutral"
    if any(k in low for k in ("excited", "proud", "happy", "thrilled", "amazing", "great news")):
        tone = "Positive"
    elif any(k in low for k in ("concern", "worried", "threat", "risk", "beware", "caution")):
        tone = "Concerned"
    elif any(k in low for k in ("wrong", "fail", "terrible", "breach", "violation", "penalty")):
        tone = "Critical"

    # Regulators
    regulators = [r for r in REGULATOR_ENTITIES if r.lower() in low]

    # Summary (first 3 sentences, capped at 400 chars)
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    summary = " ".join(sentences[:3])
    if len(summary) > 400:
        summary = summary[:397] + "..."

    return {
        "category":             category,
        "tone":                 tone,
        "regulators_mentioned": regulators,
        "summary":              summary,
    }


# ── Public API ───────────────────────────────────────────────────────────────────

def enrich_post(post: dict, use_gemini: bool = False) -> dict:
    """
    Enrich a single post.
    If use_gemini=True, attempt Gemini first; fall back to rule-based on failure.
    If use_gemini=False, use rule-based only (no API call).
    """
    content = post.get("content", "")
    if use_gemini:
        data = _gemini_enrich(content) or _rule_based_enrich(content)
    else:
        data = _rule_based_enrich(content)
    return {**post, **data}


def enrich_batch(posts: list[dict]) -> list[dict]:
    """
    Token-optimised batch enrichment:
      1. Sort by signal score (desc)
      2. Top TOP_POSTS_FOR_LLM posts scoring >= MIN_SIGNAL_SCORE go to Gemini
         (with 5-second rate-limit delay between calls)
      3. All remaining posts are rule-based only
    """
    if not posts:
        return []

    # Sort highest-signal posts first
    sorted_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)

    # Posts with semantic score >= SEMANTIC_THRESHOLD qualify for Gemini
    # (score is 0.0–1.0 from the embedding model)
    gemini_candidates = [
        p for p in sorted_posts
        if p.get("score", 0.0) >= SEMANTIC_THRESHOLD
    ][:TOP_POSTS_FOR_LLM]

    gemini_ids = {p["id"] for p in gemini_candidates}

    gemini_count  = len(gemini_candidates)
    fallback_count = len(posts) - gemini_count

    print(f"[Enricher] {gemini_count} posts → Gemini  |  {fallback_count} posts → rule-based")
    if gemini_count == 0:
        print(f"[Enricher] No posts met SEMANTIC_THRESHOLD={SEMANTIC_THRESHOLD}. All rule-based.")

    enriched: list[dict] = []
    gemini_call_n = 0

    for post in sorted_posts:
        use_gemini = post["id"] in gemini_ids

        try:
            name = post.get("author_name", "Unknown")
            tag  = "Gemini" if use_gemini else "rule"
            score = post.get("score", 0)
            print(f"  [Enricher] [{tag}] score={score}  {name}")
        except UnicodeEncodeError:
            print(f"  [Enricher] [{'Gemini' if use_gemini else 'rule'}] [Non-ASCII Name]")

        if use_gemini:
            gemini_call_n += 1
            if gemini_call_n > 1:
                # Rate-limit: 5-second pause between Gemini calls
                print(f"  [Enricher] Sleeping 5s (rate limit)...")
                time.sleep(5)

        enriched.append(enrich_post(post, use_gemini=use_gemini))

    return enriched

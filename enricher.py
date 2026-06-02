"""
enricher.py - AI enrichment using OpenRouter (OpenAI-compatible) with rule-based fallback.

Token-saving pipeline:
  1. Sort posts by signal score (highest first)
  2. Only top TOP_POSTS_FOR_LLM posts are eligible for LLM enrichment
  3. Each post must score >= MIN_SIGNAL_SCORE to reach the LLM
  4. Post content is truncated to MAX_CHARS_FOR_LLM before the LLM call
  5. Minimal JSON prompt is used (< 50 tokens of instructions)
  6. 5-second delay between LLM calls to respect free-tier rate limits
  7. All other posts fall back to fast rule-based enrichment
  8. Model fallback chain: tries each free model in order if one fails
"""
import json
import re
import time

from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODELS,
    TOP_POSTS_FOR_LLM, MAX_CHARS_FOR_LLM, SEMANTIC_THRESHOLD,
)

# ── OpenRouter client (optional) ────────────────────────────────────────────────
try:
    from openai import OpenAI
    _client = (
        OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
        if OPENROUTER_API_KEY and OPENROUTER_API_KEY not in ("", "your_openrouter_api_key_here")
        else None
    )
except Exception:
    _client = None

# ── Constants ────────────────────────────────────────────────────────────────────
POST_CATEGORIES = [
    "Regulatory Update",
    "Opinion / Commentary",
    "Risk Alert",
    "Product / Solution Insight",
    "Thought Leadership",
    "Case Study",
    "Event / Webinar",
]

TONE_LABELS = ["Positive", "Neutral", "Concerned", "Critical"]

REGULATOR_ENTITIES = [
    "RBI", "SEBI", "IRDAI", "PFRDA", "FIU-IND", "MCA", "IT Ministry",
    "FATF", "BIS", "Basel Committee", "DPDP", "PMLA", "NHB", "IFSCA", "AMFI",
]

# ── Minimal LLM prompt (keeps token usage extremely low) ─────────────────────────
_LLM_PROMPT = """\
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


# ── OpenRouter LLM enrichment ────────────────────────────────────────────────────

def _llm_enrich(content: str) -> dict | None:
    """
    Call OpenRouter with a truncated post and minimal prompt.
    Uses a free-model fallback chain: tries each model in OPENROUTER_MODELS
    in order, returning the first successful result.
    Returns None if all models fail.
    """
    if not _client:
        return None

    clean_text = content[:MAX_CHARS_FOR_LLM]
    prompt = _LLM_PROMPT.format(
        categories=", ".join(POST_CATEGORIES),
        tones=", ".join(TONE_LABELS),
        content=clean_text,
    )

    for model in OPENROUTER_MODELS:
        try:
            response = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            text = response.choices[0].message.content.strip()
            # Strip code fences if present
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"```$", "", text).strip()
            data = json.loads(text)
            # Validate expected keys
            required = {"category", "tone", "regulators_mentioned", "summary"}
            if required.issubset(data.keys()):
                used_model = getattr(response, "model", model)
                print(f"    [LLM] Model used: {used_model}")
                return data
        except Exception as e:
            print(f"  [LLM] Model {model!r} failed: {e}")
            continue  # try next model in fallback chain

    print("  [LLM] All models in fallback chain failed — using rule-based.")
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

def enrich_post(post: dict, use_llm: bool = False) -> dict:
    """
    Enrich a single post.
    If use_llm=True, attempt OpenRouter LLM first; fall back to rule-based on failure.
    If use_llm=False, use rule-based only (no API call).
    """
    content = post.get("content", "")
    if use_llm:
        data = _llm_enrich(content) or _rule_based_enrich(content)
    else:
        data = _rule_based_enrich(content)
    return {**post, **data}


def enrich_batch(posts: list[dict]) -> list[dict]:
    """
    Token-optimised batch enrichment:
      1. Sort by signal score (desc)
      2. Top TOP_POSTS_FOR_LLM posts scoring >= SEMANTIC_THRESHOLD go to LLM
         (with 5-second rate-limit delay between calls)
      3. All remaining posts are rule-based only
    """
    if not posts:
        return []

    # Sort highest-signal posts first
    sorted_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)

    # Posts with semantic score >= SEMANTIC_THRESHOLD qualify for LLM
    # (score is 0.0–1.0 from the embedding model)
    llm_candidates = [
        p for p in sorted_posts
        if p.get("score", 0.0) >= SEMANTIC_THRESHOLD
    ][:TOP_POSTS_FOR_LLM]

    llm_ids = {p["id"] for p in llm_candidates}

    llm_count      = len(llm_candidates)
    fallback_count = len(posts) - llm_count

    print(f"[Enricher] {llm_count} posts → LLM  |  {fallback_count} posts → rule-based")
    if llm_count == 0:
        print(f"[Enricher] No posts met SEMANTIC_THRESHOLD={SEMANTIC_THRESHOLD}. All rule-based.")

    enriched: list[dict] = []
    llm_call_n = 0

    for post in sorted_posts:
        use_llm = post["id"] in llm_ids

        try:
            name  = post.get("author_name", "Unknown")
            tag   = "LLM" if use_llm else "rule"
            score = post.get("score", 0)
            print(f"  [Enricher] [{tag}] score={score}  {name}")
        except UnicodeEncodeError:
            print(f"  [Enricher] [{'LLM' if use_llm else 'rule'}] [Non-ASCII Name]")

        if use_llm:
            llm_call_n += 1
            if llm_call_n > 1:
                # Rate-limit: 5-second pause between LLM calls
                print(f"  [Enricher] Sleeping 5s (rate limit)...")
                time.sleep(5)

        enriched.append(enrich_post(post, use_llm=use_llm))

    return enriched

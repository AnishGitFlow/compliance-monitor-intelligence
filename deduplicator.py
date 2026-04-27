"""
deduplicator.py - Persistent de-duplication layer.

Maintains a JSON history log at data/history.json that stores:
  - post URL hash (post ID)  → prevents reprocessing same post
  - content hash             → detects reposts with different URLs

On each run:
  1. Load history
  2. For each new post: check if ID or content_hash already seen
  3. Tag posts as is_duplicate or is_repost
  4. Save updated history (only non-duplicates are written back)
"""
import json
import os
from datetime import datetime, timedelta, timezone

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "history.json")
HISTORY_TTL_DAYS = 30  # entries older than this are pruned automatically


def _load_history() -> dict:
    """Load the history log; returns empty structure if missing or corrupt."""
    if not os.path.exists(HISTORY_FILE):
        return {"url_hashes": {}, "content_hashes": {}}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure both keys exist (backward compat)
            data.setdefault("url_hashes", {})
            data.setdefault("content_hashes", {})
            return data
    except (json.JSONDecodeError, OSError):
        return {"url_hashes": {}, "content_hashes": {}}


def _save_history(history: dict) -> None:
    """Persist history to disk, pruning entries older than TTL."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_TTL_DAYS)).isoformat()

    # Prune stale URL hash entries
    history["url_hashes"] = {
        k: v for k, v in history["url_hashes"].items()
        if v.get("seen_at", "") >= cutoff
    }
    # Prune stale content hash entries
    history["content_hashes"] = {
        k: v for k, v in history["content_hashes"].items()
        if v.get("seen_at", "") >= cutoff
    }

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def deduplicate(posts: list[dict]) -> list[dict]:
    """
    Tag and filter posts using the persistent history log.

    Rules:
      - If post ID (URL hash) already in history → mark is_duplicate=True, skip
      - If content_hash already in history but different URL → mark is_repost=True, keep
      - New posts → add to history and return

    Returns only non-duplicate posts (reposts are included but tagged).
    """
    history = _load_history()
    now_str = datetime.now(timezone.utc).isoformat()

    fresh_posts: list[dict] = []

    for post in posts:
        pid  = post.get("id", "")
        chash = post.get("content_hash", "")

        # ── Exact URL duplicate ─────────────────────────────────────────────────
        if pid and pid in history["url_hashes"]:
            print(f"  [Dedup] Skipping duplicate post: {post.get('post_url', pid[:12])}")
            post["is_duplicate"] = True
            continue  # drop entirely

        # ── Repost (same content, different URL) ───────────────────────────────
        if chash and chash in history["content_hashes"]:
            original_url = history["content_hashes"][chash].get("url", "")
            print(f"  [Dedup] Repost detected (original: {original_url[:60]})")
            post["is_repost"] = True

        # ── Register in history ────────────────────────────────────────────────
        if pid:
            history["url_hashes"][pid] = {
                "url":     post.get("post_url", ""),
                "seen_at": now_str,
            }
        if chash and chash not in history["content_hashes"]:
            history["content_hashes"][chash] = {
                "url":     post.get("post_url", ""),
                "seen_at": now_str,
            }

        fresh_posts.append(post)

    _save_history(history)
    print(f"[Dedup] {len(fresh_posts)} posts passed deduplication ({len(posts) - len(fresh_posts)} dropped).")
    return fresh_posts

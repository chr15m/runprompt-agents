"""Reddit tools for listing posts in a subreddit."""

import urllib.parse
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone

MAX_ITEMS = 25
TIMEOUT = 30


def _fetch_json(url, headers=None):
    """Fetch URL and parse as JSON."""
    req_headers = {"User-Agent": "research-tool/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.reason)}
    except urllib.error.URLError as e:
        return {"error": "URL error: %s" % str(e.reason)}
    except Exception as e:
        return {"error": str(e)}


def _to_iso8601(created_utc):
    if created_utc is None:
        return ""
    try:
        dt = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def reddit_list(subreddit: str,
                sort: str = "hot",
                t: str = "day",
                limit: int = MAX_ITEMS):
    """List posts in a subreddit by sort and (optionally) time window.

    Uses Reddit's listing endpoints:
    - /r/<subreddit>/hot.json
    - /r/<subreddit>/new.json
    - /r/<subreddit>/top.json?t=day|week|month|year|all
    - /r/<subreddit>/rising.json

    Args:
      subreddit: Subreddit name, with or without "r/" prefix.
      sort: One of "hot", "new", "top", "rising".
      t: Time window for "top" sort: "hour", "day", "week", "month",
         "year", "all". Ignored for other sorts.
      limit: Number of posts to return (max 100).

    Returns:
      LLM-friendly Markdown containing the existing fields for each post:
      title, subreddit, author, score, comments, created, url, permalink,
      and truncated selftext.
    """
    subreddit = (subreddit or "").strip()
    if subreddit.lower().startswith("r/"):
        subreddit = subreddit[2:]
    subreddit = subreddit.strip("/")

    if not subreddit:
        return {"error": "subreddit is required"}

    sort = (sort or "hot").strip().lower()
    allowed_sorts = {"hot", "new", "top", "rising"}
    if sort not in allowed_sorts:
        return {"error": "Invalid sort: %s" % sort}

    t = (t or "day").strip().lower()
    allowed_t = {"hour", "day", "week", "month", "year", "all"}
    if t not in allowed_t:
        return {"error": "Invalid time window t: %s" % t}

    limit = int(limit) if limit is not None else MAX_ITEMS
    limit = max(1, min(limit, 100))

    base_url = "https://www.reddit.com/r/%s/%s.json" % (
        urllib.parse.quote(subreddit),
        urllib.parse.quote(sort),
    )
    qs = {"limit": str(limit)}
    if sort == "top":
        qs["t"] = t
    url = base_url + "?" + urllib.parse.urlencode(qs)

    data = _fetch_json(url)
    if "error" in data:
        return data

    children = data.get("data", {}).get("children", [])
    posts = []
    for child in children[:limit]:
        post = (child or {}).get("data", {}) or {}
        title = post.get("title", "") or ""
        permalink = post.get("permalink", "") or ""
        selftext = post.get("selftext", "") or ""
        if len(selftext) > 500:
            selftext = selftext[:500] + "…"

        posts.append({
            "title": title,
            "subreddit": post.get("subreddit", subreddit) or subreddit,
            "author": post.get("author", "") or "",
            "score": post.get("score", 0),
            "comments": post.get("num_comments", 0),
            "created": _to_iso8601(post.get("created_utc")),
            "url": post.get("url", "") or "",
            "permalink": "https://reddit.com%s" % permalink if permalink else "",
            "selftext": selftext,
        })

    lines = [
        "# Reddit listing",
        "",
        "Subreddit: `r/%s`" % subreddit,
        "Sort: `%s`" % sort,
        "Time window: `%s`" % t if sort == "top" else "Time window: ``",
        "Limit: %d" % limit,
        "",
        "URL: %s" % url,
        "",
    ]

    if not posts:
        lines.append("_No posts._")
        return "\n".join(lines).rstrip()

    lines.append("Posts:")
    lines.append("")

    for i, post in enumerate(posts, 1):
        title = post.get("title", "") or ""
        author = post.get("author", "") or ""
        score = post.get("score", 0)
        comments = post.get("comments", 0)
        created = post.get("created", "") or ""
        post_url = post.get("url", "") or ""
        permalink = post.get("permalink", "") or ""
        selftext = post.get("selftext", "") or ""

        lines.append("%d. **%s**" % (i, title))
        lines.append(
            "   Author: u/%s | Score: %s | Comments: %s"
            % (author, score, comments)
        )
        if created:
            lines.append("   Created: %s" % created)
        if post_url:
            lines.append("   URL: %s" % post_url)
        if permalink:
            lines.append("   Permalink: %s" % permalink)
        if selftext:
            lines.append("   Selftext: %s" % selftext.replace("\n", " "))
        lines.append("")

    return "\n".join(lines).rstrip()


reddit_list.safe = True

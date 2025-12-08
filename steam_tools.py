"""Steam tools for fetching game information and reviews."""

import urllib.request
import urllib.parse
import json
import re

MAX_ITEMS = 10
TIMEOUT = 30


def _fetch_json(url, headers=None):
    """Fetch URL and parse as JSON."""
    req_headers = {"User-Agent": "steam-tool/1.0"}
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


def steam_search(query: str):
    """Search Steam store for games by name.
    
    Returns matching games with app IDs, names, and prices.
    Use this to find a game's app ID when you only have the name.
    """
    url = "https://store.steampowered.com/api/storesearch/?term=%s&cc=us&l=en" % (
        urllib.parse.quote(query))
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for item in data.get("items", [])[:MAX_ITEMS]:
        result = {
            "app_id": item.get("id"),
            "name": item.get("name", ""),
            "url": "https://store.steampowered.com/app/%s" % item.get("id")
        }
        if item.get("price"):
            price = item["price"]
            if price.get("final"):
                result["price"] = "$%.2f" % (price["final"] / 100)
            if price.get("discount_percent"):
                result["discount"] = "%d%%" % price["discount_percent"]
        results.append(result)
    return {"query": query, "total": data.get("total", 0), "results": results}


def steam_reviews(app_id: str, num_reviews: int = 100):
    """Fetch Steam reviews for a game by app ID.
    
    Returns recent reviews with text, recommendation, playtime, and vote counts.
    Use steam_search() first if you need to find the app ID from a game name.
    """
    app_id = str(app_id).strip()
    url = "https://store.steampowered.com/appreviews/%s?json=1&language=english&num_per_page=%d&purchase_type=all" % (
        urllib.parse.quote(app_id), min(num_reviews, 100))
    data = _fetch_json(url)
    if "error" in data:
        return data
    if not data.get("success"):
        return {"error": "Failed to fetch reviews for app ID: %s" % app_id}
    summary = data.get("query_summary", {})
    result = {
        "app_id": app_id,
        "total_reviews": summary.get("total_reviews", 0),
        "total_positive": summary.get("total_positive", 0),
        "total_negative": summary.get("total_negative", 0),
        "review_score_desc": summary.get("review_score_desc", ""),
        "reviews": []
    }
    if result["total_reviews"] > 0:
        result["positive_percent"] = round(
            100 * result["total_positive"] / result["total_reviews"], 1)
    for review in data.get("reviews", []):
        author = review.get("author", {})
        playtime_hours = round(author.get("playtime_forever", 0) / 60, 1)
        review_text = review.get("review", "")
        review_text = re.sub(r'\[/?[^\]]+\]', '', review_text)
        # Truncate to ~5000 words (approx 30000 chars)
        if len(review_text) > 30000:
            review_text = review_text[:30000] + "\n\n[... truncated ...]"
        result["reviews"].append({
            "recommended": review.get("voted_up", False),
            "playtime_hours": playtime_hours,
            "votes_up": review.get("votes_up", 0),
            "votes_funny": review.get("votes_funny", 0),
            "text": review_text
        })
    return result

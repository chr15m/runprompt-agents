"""GitHub tools for fetching issues and comments."""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

MAX_ITEMS = 100
TIMEOUT = 30
RATE_LIMIT_RESERVE = 3


def _fetch_json(url, headers=None):
    """Fetch URL and parse as JSON, returning data and rate limit info."""
    req_headers = {"User-Agent": "github-research-tool/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rate_limit = {
                "limit": resp.headers.get("X-RateLimit-Limit"),
                "remaining": resp.headers.get("X-RateLimit-Remaining"),
                "reset": resp.headers.get("X-RateLimit-Reset"),
            }
            return {"data": data, "rate_limit": rate_limit}
    except urllib.error.HTTPError as e:
        rate_limit = {
            "limit": e.headers.get("X-RateLimit-Limit"),
            "remaining": e.headers.get("X-RateLimit-Remaining"),
            "reset": e.headers.get("X-RateLimit-Reset"),
        }
        return {
            "error": "HTTP %d: %s" % (e.code, e.reason),
            "rate_limit": rate_limit,
        }
    except urllib.error.URLError as e:
        return {"error": "URL error: %s" % str(e.reason)}
    except Exception as e:
        return {"error": str(e)}


def _check_rate_limit(rate_limit, reserve=RATE_LIMIT_RESERVE):
    """Check if we have enough rate limit remaining."""
    remaining = rate_limit.get("remaining")
    reset = rate_limit.get("reset")
    
    if remaining is None:
        return {"ok": True}
    
    remaining = int(remaining)
    if remaining <= reserve:
        if reset:
            reset_time = datetime.fromtimestamp(int(reset))
            now = datetime.now()
            wait_seconds = (reset_time - now).total_seconds()
            msg = (
                "Rate limit nearly exhausted (%d/%s requests remaining, "
                "reserving %d for deep research). "
                "Resets at %s (in ~%d seconds)."
            ) % (
                remaining,
                rate_limit.get("limit", "?"),
                reserve,
                reset_time.strftime("%Y-%m-%d %H:%M:%S"),
                max(0, int(wait_seconds)),
            )
        else:
            msg = (
                "Rate limit nearly exhausted (%d/%s requests remaining, "
                "reserving %d for deep research)."
            ) % (remaining, rate_limit.get("limit", "?"), reserve)
        
        print("WARNING: " + msg, file=sys.stderr)
        return {"ok": False, "message": msg, "remaining": remaining}
    
    return {"ok": True, "remaining": remaining}


def _truncate(text, max_len=2000):
    """Truncate text to max length."""
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len] + "…"


def github_issues_list(
    owner: str,
    repo: str,
    state: str = "all",
    sort: str = "updated",
    direction: str = "desc",
    per_page: int = 100,
    max_pages: int = 5,
):
    """List issues from a GitHub repository with pagination and rate limit awareness.

    Args:
      owner: Repository owner (username or org)
      repo: Repository name
      state: Issue state - "open", "closed", or "all" (default: "all")
      sort: Sort by "created", "updated", or "comments" (default: "updated")
      direction: Sort direction - "asc" or "desc" (default: "desc")
      per_page: Items per page, max 100 (default: 100)
      max_pages: Maximum pages to fetch (default: 5)

    Returns:
      Markdown-formatted text with issues and rate limit info.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        return "Error: owner and repo are required"

    state = (state or "all").strip().lower()
    if state not in ("open", "closed", "all"):
        return "Error: state must be 'open', 'closed', or 'all'"

    sort = (sort or "updated").strip().lower()
    if sort not in ("created", "updated", "comments"):
        return "Error: sort must be 'created', 'updated', or 'comments'"

    direction = (direction or "desc").strip().lower()
    if direction not in ("asc", "desc"):
        return "Error: direction must be 'asc' or 'desc'"

    per_page = min(max(1, int(per_page or 100)), 100)
    max_pages = max(1, int(max_pages or 5))

    all_issues = []
    page = 1
    rate_limit_info = None
    stopped_early = False

    while page <= max_pages:
        url = "https://api.github.com/repos/%s/%s/issues?%s" % (
            urllib.parse.quote(owner),
            urllib.parse.quote(repo),
            urllib.parse.urlencode({
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": str(per_page),
                "page": str(page),
            }),
        )

        result = _fetch_json(url)
        rate_limit_info = result.get("rate_limit", {})

        if "error" in result:
            lines = [
                "# GitHub Issues - Error",
                "",
                "Repository: `%s/%s`" % (owner, repo),
                "Error: %s" % result["error"],
                "",
            ]
            if rate_limit_info:
                limit_check = _check_rate_limit(rate_limit_info, reserve=0)
                if not limit_check["ok"]:
                    lines.append("Rate limit: %s" % limit_check.get("message", ""))
            return "\n".join(lines)

        issues = result.get("data", [])
        if not issues:
            break

        all_issues.extend(issues)

        limit_check = _check_rate_limit(rate_limit_info)
        if not limit_check["ok"]:
            stopped_early = True
            break

        if len(issues) < per_page:
            break

        page += 1

    lines = [
        "# GitHub Issues",
        "",
        "Repository: `%s/%s`" % (owner, repo),
        "State: `%s` | Sort: `%s` (%s)" % (state, sort, direction),
        "Fetched: %d issues across %d page(s)" % (len(all_issues), page - 1),
    ]

    if rate_limit_info and rate_limit_info.get("remaining") is not None:
        lines.append(
            "Rate limit: %s/%s remaining"
            % (rate_limit_info["remaining"], rate_limit_info.get("limit", "?"))
        )

    if stopped_early:
        lines.append("")
        lines.append(
            "⚠️ Stopped early due to rate limit. "
            "Reserved %d requests for deep research." % RATE_LIMIT_RESERVE
        )

    lines.append("")

    if not all_issues:
        lines.append("_No issues found._")
        return "\n".join(lines)

    lines.append("Issues:")
    lines.append("")

    for i, issue in enumerate(all_issues, 1):
        number = issue.get("number", 0)
        title = issue.get("title", "") or ""
        state_val = issue.get("state", "")
        user = (issue.get("user") or {}).get("login", "") or ""
        labels = [
            (lbl.get("name") or "") for lbl in (issue.get("labels") or [])
        ]
        comments = issue.get("comments", 0)
        created = (issue.get("created_at") or "")[:10]
        updated = (issue.get("updated_at") or "")[:10]
        body = _truncate(issue.get("body") or "", 300)

        lines.append("%d. **#%d** - %s" % (i, number, title))
        lines.append(
            "   State: `%s` | Author: @%s | Comments: %d"
            % (state_val, user, comments)
        )
        lines.append("   Created: %s | Updated: %s" % (created, updated))
        if labels:
            lines.append("   Labels: %s" % ", ".join("`%s`" % l for l in labels[:5]))
        lines.append(
            "   URL: https://github.com/%s/%s/issues/%d" % (owner, repo, number)
        )
        if body:
            lines.append("   Body: %s" % body.replace("\n", " "))
        lines.append("")

    return "\n".join(lines).rstrip()


github_issues_list.safe = True


def github_issues_search(
    owner: str,
    repo: str,
    query: str,
    sort: str = "updated",
    order: str = "desc",
    per_page: int = 100,
):
    """Search issues in a GitHub repository.

    Args:
      owner: Repository owner (username or org)
      repo: Repository name
      query: Search query (will be combined with repo filter)
      sort: Sort by "created", "updated", or "comments" (default: "updated")
      order: Sort order - "asc" or "desc" (default: "desc")
      per_page: Items per page, max 100 (default: 100)

    Returns:
      Markdown-formatted text with matching issues and rate limit info.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    query = (query or "").strip()

    if not owner or not repo:
        return "Error: owner and repo are required"
    if not query:
        return "Error: query is required"

    sort = (sort or "updated").strip().lower()
    if sort not in ("created", "updated", "comments"):
        return "Error: sort must be 'created', 'updated', or 'comments'"

    order = (order or "desc").strip().lower()
    if order not in ("asc", "desc"):
        return "Error: order must be 'asc' or 'desc'"

    per_page = min(max(1, int(per_page or 100)), 100)

    full_query = "repo:%s/%s %s" % (owner, repo, query)
    url = "https://api.github.com/search/issues?%s" % urllib.parse.urlencode({
        "q": full_query,
        "sort": sort,
        "order": order,
        "per_page": str(per_page),
    })

    result = _fetch_json(url)
    rate_limit_info = result.get("rate_limit", {})

    if "error" in result:
        lines = [
            "# GitHub Issues Search - Error",
            "",
            "Repository: `%s/%s`" % (owner, repo),
            "Query: `%s`" % query,
            "Error: %s" % result["error"],
            "",
        ]
        if rate_limit_info:
            limit_check = _check_rate_limit(rate_limit_info, reserve=0)
            if not limit_check["ok"]:
                lines.append("Rate limit: %s" % limit_check.get("message", ""))
        return "\n".join(lines)

    data = result.get("data", {})
    total_count = data.get("total_count", 0)
    items = data.get("items", [])

    lines = [
        "# GitHub Issues Search",
        "",
        "Repository: `%s/%s`" % (owner, repo),
        "Query: `%s`" % query,
        "Total matches: %d | Showing: %d" % (total_count, len(items)),
        "Sort: `%s` (%s)" % (sort, order),
    ]

    if rate_limit_info and rate_limit_info.get("remaining") is not None:
        lines.append(
            "Rate limit: %s/%s remaining"
            % (rate_limit_info["remaining"], rate_limit_info.get("limit", "?"))
        )

    lines.append("")

    if not items:
        lines.append("_No matching issues found._")
        return "\n".join(lines)

    lines.append("Issues:")
    lines.append("")

    for i, issue in enumerate(items, 1):
        number = issue.get("number", 0)
        title = issue.get("title", "") or ""
        state_val = issue.get("state", "")
        user = (issue.get("user") or {}).get("login", "") or ""
        labels = [
            (lbl.get("name") or "") for lbl in (issue.get("labels") or [])
        ]
        comments = issue.get("comments", 0)
        created = (issue.get("created_at") or "")[:10]
        updated = (issue.get("updated_at") or "")[:10]
        body = _truncate(issue.get("body") or "", 300)

        lines.append("%d. **#%d** - %s" % (i, number, title))
        lines.append(
            "   State: `%s` | Author: @%s | Comments: %d"
            % (state_val, user, comments)
        )
        lines.append("   Created: %s | Updated: %s" % (created, updated))
        if labels:
            lines.append("   Labels: %s" % ", ".join("`%s`" % l for l in labels[:5]))
        lines.append(
            "   URL: https://github.com/%s/%s/issues/%d" % (owner, repo, number)
        )
        if body:
            lines.append("   Body: %s" % body.replace("\n", " "))
        lines.append("")

    return "\n".join(lines).rstrip()


github_issues_search.safe = True


def github_issue_comments(owner: str, repo: str, issue_number: int):
    """Fetch all comments for a specific GitHub issue.

    Args:
      owner: Repository owner (username or org)
      repo: Repository name
      issue_number: Issue number

    Returns:
      Markdown-formatted text with issue details and all comments.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    issue_number = int(issue_number or 0)

    if not owner or not repo or not issue_number:
        return "Error: owner, repo, and issue_number are required"

    issue_url = "https://api.github.com/repos/%s/%s/issues/%d" % (
        urllib.parse.quote(owner),
        urllib.parse.quote(repo),
        issue_number,
    )

    issue_result = _fetch_json(issue_url)
    rate_limit_info = issue_result.get("rate_limit", {})

    if "error" in issue_result:
        lines = [
            "# GitHub Issue Comments - Error",
            "",
            "Repository: `%s/%s`" % (owner, repo),
            "Issue: #%d" % issue_number,
            "Error: %s" % issue_result["error"],
            "",
        ]
        if rate_limit_info:
            limit_check = _check_rate_limit(rate_limit_info, reserve=0)
            if not limit_check["ok"]:
                lines.append("Rate limit: %s" % limit_check.get("message", ""))
        return "\n".join(lines)

    issue = issue_result.get("data", {})
    title = issue.get("title", "") or ""
    state_val = issue.get("state", "")
    user = (issue.get("user") or {}).get("login", "") or ""
    labels = [(lbl.get("name") or "") for lbl in (issue.get("labels") or [])]
    created = (issue.get("created_at") or "")[:10]
    updated = (issue.get("updated_at") or "")[:10]
    body = issue.get("body") or ""
    num_comments = issue.get("comments", 0)

    lines = [
        "# GitHub Issue #%d" % issue_number,
        "",
        "Repository: `%s/%s`" % (owner, repo),
        "Title: **%s**" % title,
        "State: `%s` | Author: @%s" % (state_val, user),
        "Created: %s | Updated: %s" % (created, updated),
    ]

    if labels:
        lines.append("Labels: %s" % ", ".join("`%s`" % l for l in labels))

    lines.append(
        "URL: https://github.com/%s/%s/issues/%d" % (owner, repo, issue_number)
    )
    lines.append("")
    lines.append("## Issue Body")
    lines.append("")
    lines.append(body if body else "_No description provided._")
    lines.append("")

    if num_comments == 0:
        lines.append("## Comments")
        lines.append("")
        lines.append("_No comments._")
        return "\n".join(lines)

    comments_url = "https://api.github.com/repos/%s/%s/issues/%d/comments?per_page=100" % (
        urllib.parse.quote(owner),
        urllib.parse.quote(repo),
        issue_number,
    )

    all_comments = []
    page = 1

    while True:
        paginated_url = comments_url + "&page=%d" % page
        comments_result = _fetch_json(paginated_url)
        rate_limit_info = comments_result.get("rate_limit", {})

        if "error" in comments_result:
            lines.append("## Comments - Error")
            lines.append("")
            lines.append("Error fetching comments: %s" % comments_result["error"])
            if rate_limit_info:
                limit_check = _check_rate_limit(rate_limit_info, reserve=0)
                if not limit_check["ok"]:
                    lines.append("")
                    lines.append("Rate limit: %s" % limit_check.get("message", ""))
            return "\n".join(lines)

        comments = comments_result.get("data", [])
        if not comments:
            break

        all_comments.extend(comments)

        limit_check = _check_rate_limit(rate_limit_info)
        if not limit_check["ok"]:
            lines.append("## Comments (partial - rate limited)")
            lines.append("")
            lines.append(
                "⚠️ Fetched %d of %d comments before hitting rate limit."
                % (len(all_comments), num_comments)
            )
            lines.append("")
            break

        if len(comments) < 100:
            break

        page += 1

    if not all_comments:
        lines.append("## Comments")
        lines.append("")
        lines.append("_No comments found._")
        return "\n".join(lines)

    lines.append("## Comments (%d)" % len(all_comments))
    lines.append("")

    for i, comment in enumerate(all_comments, 1):
        author = (comment.get("user") or {}).get("login", "") or ""
        created_at = (comment.get("created_at") or "")[:10]
        comment_body = comment.get("body") or ""

        lines.append("### Comment %d - @%s (%s)" % (i, author, created_at))
        lines.append("")
        lines.append(comment_body if comment_body else "_Empty comment._")
        lines.append("")

    if rate_limit_info and rate_limit_info.get("remaining") is not None:
        lines.append("---")
        lines.append(
            "Rate limit: %s/%s remaining"
            % (rate_limit_info["remaining"], rate_limit_info.get("limit", "?"))
        )

    return "\n".join(lines).rstrip()


github_issue_comments.safe = True

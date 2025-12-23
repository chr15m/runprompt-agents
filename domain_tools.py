import json
import urllib.error
import urllib.request

TIMEOUT = 30
MAX_CONTENT_LENGTH = 50000


def _truncate(text: str, max_len: int = MAX_CONTENT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... (truncated to {max_len} chars)"


def _normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.removeprefix("https://")
    domain = domain.removeprefix("http://")
    domain = domain.split("/")[0]
    return domain


def rdap_domain(domain: str):
    """Look up a domain via RDAP and infer availability from the response.

    Returns a dict with:
      - status: "taken" | "available" | "unknown"
      - http_status: int | None
      - rdap: parsed JSON (when available and small enough)
      - error: string (when an error occurs)
    """
    domain = _normalize_domain(domain)
    url = f"https://rdap.org/domain/{domain}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/rdap+json, application/json, */*",
            "User-Agent": "runprompt-domain-research/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = getattr(resp, "status", None)
            raw = resp.read(MAX_CONTENT_LENGTH + 1)
            text = raw.decode("utf-8", errors="replace")
            text = _truncate(text)

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"raw": text}

            if isinstance(parsed, dict) and parsed.get("objectClassName") == "domain":
                return {
                    "domain": domain,
                    "url": url,
                    "status": "taken",
                    "http_status": status,
                    "rdap": parsed,
                }

            return {
                "domain": domain,
                "url": url,
                "status": "unknown",
                "http_status": status,
                "rdap": parsed,
            }

    except urllib.error.HTTPError as e:
        # RDAP servers typically return 404 for not-registered domains.
        if e.code == 404:
            return {
                "domain": domain,
                "url": url,
                "status": "available",
                "http_status": e.code,
            }

        body = ""
        try:
            body = e.read(MAX_CONTENT_LENGTH + 1).decode("utf-8", errors="replace")
            body = _truncate(body)
        except Exception:
            body = ""

        return {
            "domain": domain,
            "url": url,
            "status": "unknown",
            "http_status": e.code,
            "error": f"HTTPError: {e.code} {e.reason}",
            "body": body,
        }

    except Exception as e:
        return {
            "domain": domain,
            "url": url,
            "status": "unknown",
            "http_status": None,
            "error": repr(e),
        }


rdap_domain.safe = True

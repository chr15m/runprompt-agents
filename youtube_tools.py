import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _extract_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()

    if _ID_RE.match(s):
        return s

    # Some users paste extra text; grab the first URL-looking token.
    token = s.split()[0]

    parsed = urlparse(token)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    # https://www.youtube.com/watch?v=VIDEO_ID
    if "youtube.com" in host:
        qs = parse_qs(parsed.query or "")
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            if _ID_RE.match(vid):
                return vid

        # /shorts/VIDEO_ID, /embed/VIDEO_ID, /live/VIDEO_ID
        parts = [p for p in path.split("/") if p]
        for prefix in ("shorts", "embed", "live"):
            if prefix in parts:
                idx = parts.index(prefix)
                if idx + 1 < len(parts) and _ID_RE.match(parts[idx + 1]):
                    return parts[idx + 1]

    # https://youtu.be/VIDEO_ID
    if "youtu.be" in host:
        vid = path.lstrip("/").split("/")[0]
        if _ID_RE.match(vid):
            return vid

    # Fallback: find an 11-char id-like substring anywhere in the input.
    m = re.search(
        r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])",
        s,
    )
    if m:
        return m.group(1)

    raise ValueError("Could not extract a YouTube video id from input")


def _truncate(text: str, max_len: int) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def youtube_feed_xml(
    user: str = "",
    channel_id: str = "",
    limit: int = 25,
) -> dict:
    """Fetch YouTube's public Atom feed (videos.xml) and return a concise list.

    Args:
      user: Legacy YouTube username (e.g. "mccormix").
      channel_id: YouTube channel id (typically "UC..." style).
      limit: Maximum number of entries to return.

    Returns:
      A dict with:
        - url: the feed URL requested
        - feed: metadata (id, channel_id, title, author)
        - videos: list of entries with video_id, title, url, published, updated,
          views, thumbnail, description (truncated)
        - error: string (when an error occurs)
    """
    user = (user or "").strip()
    channel_id = (channel_id or "").strip()
    if bool(user) == bool(channel_id):
        return {"error": "Provide exactly one of: user, channel_id"}

    limit = int(limit) if limit is not None else 25
    limit = max(1, min(limit, 100))

    params = {"user": user} if user else {"channel_id": channel_id}
    url = "https://www.youtube.com/feeds/videos.xml?%s" % (
        urllib.parse.urlencode(params),
    )

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/atom+xml, application/xml, text/xml, */*",
            "User-Agent": "runprompt-youtube-tools/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        return {"url": url, "error": "HTTPError: %s %s" % (e.code, e.reason)}
    except urllib.error.URLError as e:
        return {"url": url, "error": "URLError: %s" % str(e.reason)}
    except Exception as e:
        return {"url": url, "error": repr(e)}

    xml_text = raw.decode("utf-8", errors="replace")

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        return {"url": url, "error": "XML parse error: %s" % repr(e)}

    def _text(path: str) -> str:
        el = root.find(path, ns)
        if el is None or el.text is None:
            return ""
        return unescape(el.text.strip())

    feed = {
        "id": _text("atom:id"),
        "channel_id": _text("yt:channelId"),
        "title": _text("atom:title"),
        "author": _text("atom:author/atom:name"),
    }

    feed_link_el = root.find('atom:link[@rel="alternate"]', ns)
    if feed_link_el is not None:
        channel_url = feed_link_el.attrib.get("href", "") or ""
        feed["channel_url"] = channel_url
        parsed = urlparse(channel_url)
        parts = [p for p in (parsed.path or "").split("/") if p]
        if len(parts) >= 2 and parts[-2] == "channel":
            feed["channel_id_uc"] = parts[-1]

    videos = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        published = (
            entry.findtext("atom:published", default="", namespaces=ns) or ""
        ).strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=ns) or "").strip()

        link_el = entry.find('atom:link[@rel="alternate"]', ns)
        video_url = link_el.attrib.get("href", "") if link_el is not None else ""

        desc = (entry.findtext("media:group/media:description", default="", namespaces=ns) or "").strip()
        thumb_el = entry.find("media:group/media:thumbnail", ns)
        thumbnail = thumb_el.attrib.get("url", "") if thumb_el is not None else ""
        stats_el = entry.find("media:group/media:community/media:statistics", ns)
        views = stats_el.attrib.get("views", "") if stats_el is not None else ""

        videos.append(
            {
                "video_id": video_id,
                "title": unescape(title),
                "url": video_url,
                "published": published,
                "updated": updated,
                "views": views,
                "thumbnail": thumbnail,
                "description": _truncate(unescape(desc), 280),
            }
        )

    return {"url": url, "feed": feed, "videos": videos}


youtube_feed_xml.safe = True


def youtube_channel_videos(
    channel_id: str = "",
    user: str = "",
    limit: int = 200,
) -> dict:
    """List a channel's uploaded videos using scrapetube (no API key).

    Args:
      channel_id: A YouTube channel id (typically "UC...").
      user: Legacy username. If provided, resolves a channel id via
        youtube_feed_xml() and then uses that for scraping.
      limit: Maximum number of videos to return (max 2000).

    Returns:
      A dict with:
        - channel_id: the channel id used for scraping
        - source: "scrapetube"
        - videos: list of {video_id, url, title}
        - error: string (when an error occurs)
    """
    channel_id = (channel_id or "").strip()
    user = (user or "").strip()
    if bool(channel_id) == bool(user):
        return {"error": "Provide exactly one of: channel_id, user"}

    limit = int(limit) if limit is not None else 200
    limit = max(1, min(limit, 2000))

    if user:
        feed = youtube_feed_xml(user=user, limit=1)
        if isinstance(feed, dict) and feed.get("error"):
            return {"error": feed.get("error", "Failed to fetch feed")}
        channel_id = (
            ((feed.get("feed") or {}).get("channel_id_uc") or "").strip()
            or ((feed.get("feed") or {}).get("channel_id") or "").strip()
        )
        if not channel_id:
            return {"error": "Could not resolve channel_id from feed"}

    try:
        import scrapetube
    except Exception as e:
        return {"error": "Failed to import scrapetube: %s" % repr(e)}

    videos = []
    try:
        for v in scrapetube.get_channel(channel_id):
            video_id = (v.get("videoId") or v.get("video_id") or "").strip()
            if not video_id:
                continue

            raw_title = v.get("title") or ""
            if isinstance(raw_title, dict):
                runs = raw_title.get("runs")
                if isinstance(runs, list) and runs:
                    raw_title = "".join((r.get("text") or "") for r in runs)
                else:
                    raw_title = raw_title.get("simpleText") or ""
            elif isinstance(raw_title, list):
                raw_title = "".join(str(x) for x in raw_title)
            title = str(raw_title).strip()

            videos.append(
                {
                    "video_id": video_id,
                    "url": "https://www.youtube.com/watch?v=%s" % video_id,
                    "title": _truncate(title, 200),
                }
            )
            if len(videos) >= limit:
                break
    except Exception as e:
        return {
            "channel_id": channel_id,
            "source": "scrapetube",
            "error": repr(e),
        }

    return {"channel_id": channel_id, "source": "scrapetube", "videos": videos}


youtube_channel_videos.safe = True


def _youtube_watch_url(video_id: str) -> str:
    return "https://www.youtube.com/watch?v=%s" % video_id


def _to_iso_date(value) -> str:
    if value is None:
        return ""
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def youtube_oembed(url_or_id: str) -> dict:
    """Fetch YouTube metadata via the public oEmbed endpoint (no API key).

    Args:
      url_or_id: A YouTube URL (watch/youtu.be/shorts/embed) or a raw
        11-character video id.

    Returns:
      A dict with:
        - video_id: The extracted id
        - video_url: Normalized watch URL
        - oembed_url: The requested oEmbed URL
        - oembed: Parsed oEmbed JSON response (when successful)
        - error: string (when an error occurs)
    """
    video_id = _extract_video_id(url_or_id)
    video_url = _youtube_watch_url(video_id)

    qs = urllib.parse.urlencode({"url": video_url, "format": "json"})
    oembed_url = "https://www.youtube.com/oembed?%s" % qs

    req = urllib.request.Request(
        oembed_url,
        headers={
            "Accept": "application/json, */*",
            "User-Agent": "runprompt-youtube-tools/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        return {
            "video_id": video_id,
            "video_url": video_url,
            "oembed_url": oembed_url,
            "error": "HTTPError: %s %s" % (e.code, e.reason),
        }
    except urllib.error.URLError as e:
        return {
            "video_id": video_id,
            "video_url": video_url,
            "oembed_url": oembed_url,
            "error": "URLError: %s" % str(e.reason),
        }
    except Exception as e:
        return {
            "video_id": video_id,
            "video_url": video_url,
            "oembed_url": oembed_url,
            "error": repr(e),
        }

    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except Exception as e:
        return {
            "video_id": video_id,
            "video_url": video_url,
            "oembed_url": oembed_url,
            "error": "JSON parse error: %s" % repr(e),
            "raw": _truncate(text, 2000),
        }

    return {
        "video_id": video_id,
        "video_url": video_url,
        "oembed_url": oembed_url,
        "oembed": parsed,
    }


youtube_oembed.safe = True


def youtube_metadata_pytube(url_or_id: str) -> dict:
    """Fetch YouTube metadata via pytube (no API key).

    Args:
      url_or_id: A YouTube URL (watch/youtu.be/shorts/embed) or a raw
        11-character video id.

    Returns:
      A dict with:
        - video_id: The extracted id
        - video_url: Normalized watch URL
        - metadata: A small subset of fields from pytube's YouTube object
        - error: string (when an error occurs)
    """
    video_id = _extract_video_id(url_or_id)
    video_url = _youtube_watch_url(video_id)

    try:
        from pytube import YouTube
    except Exception as e:
        return {"error": "Failed to import pytube: %s" % repr(e)}

    try:
        yt = YouTube(video_url)
    except Exception as e:
        return {
            "video_id": video_id,
            "video_url": video_url,
            "error": repr(e),
        }

    metadata = {
        "title": getattr(yt, "title", "") or "",
        "author": getattr(yt, "author", "") or "",
        "channel_id": getattr(yt, "channel_id", "") or "",
        "channel_url": getattr(yt, "channel_url", "") or "",
        "thumbnail_url": getattr(yt, "thumbnail_url", "") or "",
        "length_seconds": getattr(yt, "length", None),
        "views": getattr(yt, "views", None),
        "publish_date": _to_iso_date(getattr(yt, "publish_date", None)),
        "description": getattr(yt, "description", "") or "",
        "keywords": getattr(yt, "keywords", None),
    }

    if isinstance(metadata.get("description"), str):
        metadata["description"] = _truncate(metadata["description"], 2000)

    return {
        "video_id": video_id,
        "video_url": video_url,
        "metadata": metadata,
    }


youtube_metadata_pytube.safe = True


def youtube_transcript(url_or_id: str) -> dict:
    """Fetch a YouTube transcript via youtube-transcript-api.

    Args:
      url_or_id: A YouTube URL (watch/youtu.be/shorts/embed) or a raw
        11-character video id.

    Returns:
      A dict with:
        - video_id: The extracted id
        - transcript: Plain text transcript with lightweight line breaks
    """
    video_id = _extract_video_id(url_or_id)

    # Support multiple youtube_transcript_api versions.
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        items = YouTubeTranscriptApi.get_transcript(
            video_id,
            preserve_formatting=True,
        )
    else:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            try:
                items = api.fetch(video_id, preserve_formatting=True)
            except TypeError:
                items = api.fetch(video_id)
        elif hasattr(YouTubeTranscriptApi, "fetch"):
            try:
                items = YouTubeTranscriptApi.fetch(
                    video_id,
                    preserve_formatting=True,
                )
            except TypeError:
                items = YouTubeTranscriptApi.fetch(video_id)
        else:
            raise AttributeError("Unsupported youtube_transcript_api API")

    lines = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("text", "")
        else:
            text = getattr(item, "text", "")
        text = (text or "").strip()
        if text:
            lines.append(text)

    return {"video_id": video_id, "transcript": "\n".join(lines)}


youtube_transcript.safe = True

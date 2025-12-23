import re
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
    m = re.search(r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", s)
    if m:
        return m.group(1)

    raise ValueError("Could not extract a YouTube video id from input")


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

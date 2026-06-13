import re
from typing import Optional
from urllib.parse import quote_plus
from core.schemas import ActionResponse

def _normalize_spotify_query(raw_query: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw_query or "").strip().lower())
    if not text:
        return None

    corrections = {
        "roberry": "robbery",
        "robary": "robbery",
        "robbary": "robbery",
        "jews world": "juice wrld",
        "use world": "juice wrld",
        "juice world": "juice wrld",
        "juicewrld": "juice wrld",
    }
    for src, dst in corrections.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)

    generic_values = {"", "some", "any", "something", "anything", "random", "song", "songs", "track", "tracks", "music", "playlist", "playlists"}

    def _clean_segment(segment: str, drop_media_words: bool) -> str:
        value = re.sub(r"\s+", " ", (segment or "").strip().lower())
        value = re.sub(r"^(?:please\s+)?(?:some|any|a|an|the)\s+", "", value)
        if drop_media_words:
            value = re.sub(r"\b(?:song|songs|track|tracks|music|playlist|playlists)\b", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" ,.-")
        return value

    by_match = re.match(r"^(.+?)\s+by\s+(.+)$", text)
    if by_match:
        left_raw, artist_raw = by_match.group(1), by_match.group(2)
        title = _clean_segment(left_raw, drop_media_words=True)
        artist = _clean_segment(artist_raw, drop_media_words=False)
        if not artist:
            return title or None
        if not title or title in generic_values:
            return artist
        return f"{title} {artist}".strip()

    text = _clean_segment(text, drop_media_words=True)
    if text in generic_values:
        return None
    return text or None

def _normalize_media_query(raw_query: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw_query or "").strip().lower())
    if not text:
        return None

    text = re.sub(r"^(?:please\s+)?(?:play|put on|listen to|search|find)\s+", "", text).strip()
    text = re.sub(r"\b(?:song|songs|music|track|tracks|video|videos)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    if text in {"", "some", "any", "something", "anything", "random"}:
        return None
    return text

def _youtube_search_action(query: str, default_target: str) -> ActionResponse:
    cleaned = _normalize_media_query(query) or query.strip()
    return ActionResponse(
        action="open_website",
        url=f"https://www.youtube.com/results?search_query={quote_plus(cleaned)}",
        target=default_target,
        response=f"Playing {cleaned} on YouTube.",
    )

def _extract_spotify_query(normalized: str) -> Optional[str]:
    text = normalized.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(?:in|on)\s+spotify(?:\s+app)?\b", "", text).strip()
    text = re.sub(r"^(?:please\s+)?(?:play|put on|listen to|search|find)\s+", "", text).strip()
    return _normalize_spotify_query(text)

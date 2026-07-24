from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

from s2a.normalize.models import MediaReference, UnresolvedMediaReference

VIMEO_URL_RE = re.compile(
    r"(?P<url>(?:https?:)?//(?:www\.)?(?:player\.)?vimeo\.com/"
    r"(?:(?:video|channels/[^/\s\"'<>]+|groups/[^/\s\"'<>]+/videos)/)?"
    r"(?P<id>\d{5,12})(?P<tail>[^\s\"'<>\\]*))",
    re.IGNORECASE,
)
YOUTUBE_URL_RE = re.compile(
    r"(?P<url>(?:https?:)?//(?:"
    r"(?:www\.)?youtube(?:-nocookie)?\.com/"
    r"(?:(?:watch\?(?:[^\s\"'<>]*?&)?v=)|(?:embed|shorts|live)/)"
    r"|youtu\.be/)"
    r"(?P<id>[A-Za-z0-9_-]{11})(?P<tail>[^\s\"'<>\\]*))",
    re.IGNORECASE,
)
PROVIDER_VIDEO_ID_PATTERNS = (
    re.compile(
        r'"(?:providerName|provider|service)"\s*:\s*"(?P<provider>Vimeo|YouTube)"'
        r'.{0,1500}?"(?:videoId|video_id)"\s*:\s*"?(?P<id>[A-Za-z0-9_-]{5,16})"?',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'"(?:videoId|video_id)"\s*:\s*"?(?P<id>[A-Za-z0-9_-]{5,16})"?'
        r'.{0,1500}?"(?:providerName|provider|service)"\s*:\s*"(?P<provider>Vimeo|YouTube)"',
        re.IGNORECASE | re.DOTALL,
    ),
)

PROVIDER_KEYS = ("providerName", "provider", "service", "source")
VIDEO_ID_KEYS = ("videoId", "video_id", "assetId", "asset_id")
URL_KEYS = (
    "url",
    "embedUrl",
    "embed_url",
    "videoUrl",
    "video_url",
    "src",
    "html",
)


@dataclass(slots=True)
class MediaExtractionResult:
    references: list[MediaReference]
    unresolved: list[UnresolvedMediaReference]


@dataclass(frozen=True, slots=True)
class _Candidate:
    provider: str
    video_id: str
    source_url: str
    embed_url: str
    privacy_token: str
    source_kind: str
    detection_method: str
    confidence: str


def normalise_media_text(value: str) -> str:
    result = html.unescape(value)
    result = result.replace("\\/", "/")
    replacements = {
        "\\u002F": "/",
        "\\u002f": "/",
        "\\u003A": ":",
        "\\u003a": ":",
        "\\u0026": "&",
    }
    for encoded, decoded in replacements.items():
        result = result.replace(encoded, decoded)
    for _ in range(2):
        decoded = unquote(result)
        if decoded == result:
            break
        result = decoded
    return result


def extract_media_references(
    html_text: str | None,
    json_payload: Any | None,
) -> MediaExtractionResult:
    candidates: list[_Candidate] = []
    mentions: dict[str, set[str]] = {}

    if html_text:
        candidates.extend(_scan_text(html_text, source_kind="html"))
        _record_provider_mentions(html_text, "html", mentions)

    if json_payload is not None:
        serialized = json.dumps(json_payload, ensure_ascii=False, sort_keys=True)
        candidates.extend(_scan_text(serialized, source_kind="json"))
        candidates.extend(_scan_json_object(json_payload))
        _record_provider_mentions(serialized, "json", mentions)

    references = _merge_candidates(candidates)
    resolved_providers = {reference.provider for reference in references}
    unresolved = [
        UnresolvedMediaReference(
            provider=provider,
            reason="provider mentioned but no stable video ID was extracted",
            source_kinds=sorted(source_kinds),
        )
        for provider, source_kinds in sorted(mentions.items())
        if provider not in resolved_providers
    ]
    return MediaExtractionResult(references=references, unresolved=unresolved)


def build_media_manifest(snapshot: Any) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    provider_counts: dict[str, int] = {}
    page_count = 0

    for page in snapshot.pages:
        owner_url = page.final_url or page.requested_url
        owner_route = urlsplit(owner_url).path or "/"
        if page.media:
            page_count += 1
        for reference in page.media:
            provider_counts[reference.provider] = provider_counts.get(reference.provider, 0) + 1
            items.append(
                {
                    "owner_url": owner_url,
                    "owner_route": owner_route,
                    "provider": reference.provider,
                    "video_id": reference.video_id,
                    "privacy_token": reference.privacy_token,
                    "source_url": reference.source_url,
                    "embed_url": reference.embed_url,
                    "source_kinds": reference.source_kinds,
                    "detection_methods": reference.detection_methods,
                    "confidence": reference.confidence,
                    "occurrences": reference.occurrences,
                }
            )
        for reference in page.unresolved_media:
            unresolved.append(
                {
                    "owner_url": owner_url,
                    "owner_route": owner_route,
                    "provider": reference.provider,
                    "reason": reference.reason,
                    "source_kinds": reference.source_kinds,
                }
            )

    items.sort(key=lambda item: (item["owner_route"], item["provider"], item["video_id"]))
    unresolved.sort(key=lambda item: (item["owner_route"], item["provider"]))
    return {
        "generated_at": snapshot.generated_at,
        "target_url": snapshot.target_url,
        "counts": {
            "media_references": len(items),
            "pages_with_media": page_count,
            "unresolved_provider_mentions": len(unresolved),
            "by_provider": dict(sorted(provider_counts.items())),
        },
        "items": items,
        "unresolved": unresolved,
    }


def _scan_text(text: str, *, source_kind: str) -> list[_Candidate]:
    normalised = normalise_media_text(text)
    candidates: list[_Candidate] = []

    for match in VIMEO_URL_RE.finditer(normalised):
        source_url = _absolute_media_url(match.group("url"))
        video_id = match.group("id")
        token = _vimeo_privacy_token(source_url, match.group("tail"))
        candidates.append(
            _Candidate(
                provider="vimeo",
                video_id=video_id,
                privacy_token=token,
                source_url=source_url,
                embed_url=_canonical_embed_url("vimeo", video_id, token),
                source_kind=source_kind,
                detection_method="url",
                confidence="high",
            )
        )

    for match in YOUTUBE_URL_RE.finditer(normalised):
        source_url = _absolute_media_url(match.group("url"))
        video_id = match.group("id")
        candidates.append(
            _Candidate(
                provider="youtube",
                video_id=video_id,
                privacy_token="",
                source_url=source_url,
                embed_url=_canonical_embed_url("youtube", video_id),
                source_kind=source_kind,
                detection_method="url",
                confidence="high",
            )
        )

    for pattern in PROVIDER_VIDEO_ID_PATTERNS:
        for match in pattern.finditer(normalised):
            provider = match.group("provider").lower()
            video_id = match.group("id")
            if not _valid_video_id(provider, video_id):
                continue
            canonical = _canonical_embed_url(provider, video_id)
            candidates.append(
                _Candidate(
                    provider=provider,
                    video_id=video_id,
                    privacy_token="",
                    source_url=canonical,
                    embed_url=canonical,
                    source_kind=source_kind,
                    detection_method="provider-video-id-pair",
                    confidence="medium",
                )
            )
    return candidates


def _scan_json_object(value: Any) -> list[_Candidate]:
    candidates: list[_Candidate] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            provider = _provider_from_mapping(node)
            video_id = _first_string(node, VIDEO_ID_KEYS)
            if provider and video_id and _valid_video_id(provider, video_id):
                candidates.extend(_candidate_from_structured_mapping(node, provider, video_id))

            for child in node.values():
                if isinstance(child, (dict, list)):
                    visit(child)
                elif isinstance(child, str):
                    candidates.extend(_scan_text(child, source_kind="json"))
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return candidates


def _candidate_from_structured_mapping(
    mapping: dict[str, Any],
    provider: str,
    video_id: str,
) -> list[_Candidate]:
    url_value = _first_string(mapping, URL_KEYS)
    if url_value:
        matching = [
            candidate
            for candidate in _scan_text(url_value, source_kind="json")
            if candidate.provider == provider and candidate.video_id == video_id
        ]
        if matching:
            return matching

    canonical = _canonical_embed_url(provider, video_id)
    return [
        _Candidate(
            provider=provider,
            video_id=video_id,
            privacy_token="",
            source_url=canonical,
            embed_url=canonical,
            source_kind="json",
            detection_method="structured-provider-video-id",
            confidence="high",
        )
    ]


def _merge_candidates(candidates: Iterable[_Candidate]) -> list[MediaReference]:
    merged: dict[tuple[str, str], MediaReference] = {}
    for candidate in candidates:
        key = (candidate.provider, candidate.video_id)
        existing = merged.get(key)
        if existing is None:
            merged[key] = MediaReference(
                provider=candidate.provider,
                video_id=candidate.video_id,
                source_url=candidate.source_url,
                embed_url=candidate.embed_url,
                privacy_token=candidate.privacy_token,
                source_kinds=[candidate.source_kind],
                detection_methods=[candidate.detection_method],
                confidence=candidate.confidence,
                occurrences=1,
            )
            continue

        existing.occurrences += 1
        if candidate.source_kind not in existing.source_kinds:
            existing.source_kinds.append(candidate.source_kind)
            existing.source_kinds.sort()
        if candidate.detection_method not in existing.detection_methods:
            existing.detection_methods.append(candidate.detection_method)
            existing.detection_methods.sort()
        if existing.confidence == "medium" and candidate.confidence == "high":
            existing.confidence = "high"
            existing.source_url = candidate.source_url
            existing.embed_url = candidate.embed_url
        if candidate.privacy_token and not existing.privacy_token:
            existing.privacy_token = candidate.privacy_token
            existing.source_url = candidate.source_url
            existing.embed_url = candidate.embed_url

    return sorted(merged.values(), key=lambda item: (item.provider, item.video_id))


def _record_provider_mentions(
    text: str,
    source_kind: str,
    mentions: dict[str, set[str]],
) -> None:
    lowered = normalise_media_text(text).lower()
    if "vimeo" in lowered:
        mentions.setdefault("vimeo", set()).add(source_kind)
    if "youtube" in lowered or "youtu.be" in lowered:
        mentions.setdefault("youtube", set()).add(source_kind)


def _provider_from_mapping(mapping: dict[str, Any]) -> str:
    value = _first_string(mapping, PROVIDER_KEYS).lower()
    if "vimeo" in value:
        return "vimeo"
    if "youtube" in value or "youtu.be" in value:
        return "youtube"
    return ""


def _first_string(mapping: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, (str, int)):
            return str(value)
    return ""


def _valid_video_id(provider: str, video_id: str) -> bool:
    if provider == "vimeo":
        return video_id.isdigit() and 5 <= len(video_id) <= 12
    if provider == "youtube":
        return len(video_id) == 11 and bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id))
    return False


def _absolute_media_url(url: str) -> str:
    return f"https:{url}" if url.startswith("//") else url


def _vimeo_privacy_token(url: str, tail: str) -> str:
    parsed = urlsplit(url)
    query_token = parse_qs(parsed.query).get("h", [""])[0]
    if query_token:
        return query_token
    clean_tail = tail.split("?", 1)[0].strip("/")
    if clean_tail and re.fullmatch(r"[A-Za-z0-9]+", clean_tail):
        return clean_tail
    return ""


def _canonical_embed_url(provider: str, video_id: str, privacy_token: str = "") -> str:
    if provider == "vimeo":
        base = f"https://player.vimeo.com/video/{video_id}"
        return f"{base}?h={privacy_token}" if privacy_token else base
    return f"https://www.youtube-nocookie.com/embed/{video_id}"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Callable, Iterable
from urllib.parse import parse_qsl, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from s2a.normalize.models import AssetManifest, AssetReference, CrawlSnapshot, DownloadedAsset
from s2a.url_utils import make_absolute_url


DOWNLOADABLE_FILE_SUFFIXES = {
    ".pdf",
    ".zip",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".rtf",
    ".pages",
    ".key",
    ".numbers",
}
SQUARESPACE_HOST_MARKERS = (
    "squarespace.com",
    "squarespace-cdn.com",
    "static1.squarespace.com",
    "static2.squarespace.com",
    "images.squarespace-cdn.com",
)
BACKGROUND_URL_PATTERN = re.compile(r"url\((['\"]?)(?P<url>[^)'\"]+)\1\)")
VARIANT_KEYWORDS = ("thumb", "thumbnail", "small", "medium", "large", "xl", "xlarge", "original")
EXTENSION_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "application/pdf": ".pdf",
}
PLACEHOLDER_ASSET_PREFIXES = ("data:", "about:", "javascript:")
GENERIC_DESCRIPTOR_STEMS = {
    "asset",
    "audio",
    "content",
    "download",
    "file",
    "image",
    "img",
    "media",
    "original",
    "photo",
    "video",
}

ProgressCallback = Callable[[int, int, str | None], None]


@dataclass(slots=True)
class AssetDownloadEstimate:
    assets: list[AssetReference]
    estimated_size_bytes: int
    unknown_size_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def asset_count(self) -> int:
        return len(self.assets)


@dataclass(slots=True)
class ResolvedAssetDownload:
    asset: AssetReference
    final_url: str
    asset_subdir: str
    extension: str
    content_type: str | None
    size_bytes: int
    sha256: str
    content: bytes


def extract_asset_references(soup: BeautifulSoup, base_url: str, owner_route: str) -> list[AssetReference]:
    references: list[AssetReference] = []
    seen: set[tuple[str, str, str, str | None]] = set()

    for index, tag in enumerate(soup.find_all(True), start=1):
        group_key = asset_group_key(tag, index)

        if tag.name == "img":
            src_attribute, src_value = preferred_attribute_value(
                tag, "src", "data-src", "data-image")
            add_reference(
                references,
                seen,
                url=src_value,
                base_url=base_url,
                asset_type="image",
                attribute=src_attribute or "src",
                owner_route=owner_route,
                group_key=group_key,
                source_tag="img",
                alt_text=tag.get("alt"),
                caption=caption_for_tag(tag),
                variant_hint=infer_variant_hint(src_value, None, "image", src_attribute or "src"),
            )
            srcset_attribute, srcset_value = first_present_attribute(tag, "srcset", "data-srcset")
            add_srcset_references(
                references,
                seen,
                srcset=srcset_value,
                base_url=base_url,
                asset_type="image",
                attribute=srcset_attribute or "srcset",
                owner_route=owner_route,
                group_key=group_key,
                source_tag="img",
                alt_text=tag.get("alt"),
                caption=caption_for_tag(tag),
            )

        if tag.name == "source":
            parent_name = tag.parent.name if isinstance(tag.parent, Tag) else None
            if parent_name in {"video", "audio", "picture"}:
                asset_type = "image" if parent_name == "picture" else parent_name
                src_attribute, src_value = preferred_attribute_value(tag, "src", "data-src")
                add_reference(
                    references,
                    seen,
                    url=src_value,
                    base_url=base_url,
                    asset_type=asset_type,
                    attribute=src_attribute or "src",
                    owner_route=owner_route,
                    group_key=group_key,
                    source_tag="source",
                    caption=caption_for_tag(tag),
                    variant_hint=infer_variant_hint(
                        src_value, None, asset_type, src_attribute or "src"),
                )
                srcset_attribute, srcset_value = first_present_attribute(
                    tag, "srcset", "data-srcset")
                add_srcset_references(
                    references,
                    seen,
                    srcset=srcset_value,
                    base_url=base_url,
                    asset_type=asset_type,
                    attribute=srcset_attribute or "srcset",
                    owner_route=owner_route,
                    group_key=group_key,
                    source_tag="source",
                    caption=caption_for_tag(tag),
                )

        if tag.name == "video":
            src_attribute, src_value = preferred_attribute_value(tag, "src", "data-src")
            add_reference(
                references,
                seen,
                url=src_value,
                base_url=base_url,
                asset_type="video",
                attribute=src_attribute or "src",
                owner_route=owner_route,
                group_key=group_key,
                source_tag="video",
                caption=caption_for_tag(tag),
                variant_hint=infer_variant_hint(src_value, None, "video", src_attribute or "src"),
            )
            poster_attribute, poster_value = preferred_attribute_value(tag, "poster", "data-poster")
            add_reference(
                references,
                seen,
                url=poster_value,
                base_url=base_url,
                asset_type="image",
                attribute=poster_attribute or "poster",
                owner_route=owner_route,
                group_key=group_key,
                source_tag="video",
                caption=caption_for_tag(tag),
                variant_hint="poster",
            )

        if tag.name == "audio":
            src_attribute, src_value = preferred_attribute_value(tag, "src", "data-src")
            add_reference(
                references,
                seen,
                url=src_value,
                base_url=base_url,
                asset_type="audio",
                attribute=src_attribute or "src",
                owner_route=owner_route,
                group_key=group_key,
                source_tag="audio",
                caption=caption_for_tag(tag),
                variant_hint=infer_variant_hint(src_value, None, "audio", src_attribute or "src"),
            )

        if tag.name == "a" and tag.get("href"):
            href = make_absolute_url(base_url, tag["href"])
            if is_downloadable_asset_url(href) or tag.get("download") is not None:
                add_reference(
                    references,
                    seen,
                    url=href,
                    base_url=base_url,
                    asset_type="file",
                    attribute="href",
                    owner_route=owner_route,
                    group_key=group_key,
                    source_tag="a",
                    link_text=tag.get_text(" ", strip=True) or None,
                    variant_hint="file",
                )

        style_value = tag.get("style")
        if style_value:
            for background_url in extract_background_urls(style_value):
                add_reference(
                    references,
                    seen,
                    url=background_url,
                    base_url=base_url,
                    asset_type="image",
                    attribute="style",
                    owner_route=owner_route,
                    group_key=group_key,
                    source_tag=tag.name,
                    caption=caption_for_tag(tag),
                    variant_hint=infer_variant_hint(background_url, None, "image", "style"),
                )

    return references


def collect_unique_squarespace_assets(snapshot: CrawlSnapshot) -> list[AssetReference]:
    unique_assets: list[AssetReference] = []
    seen_urls: set[str] = set()

    for page in snapshot.pages:
        for asset in page.assets:
            if not is_squarespace_asset_url(asset.source_url):
                continue
            if asset.source_url in seen_urls:
                continue
            seen_urls.add(asset.source_url)
            unique_assets.append(asset)

    return unique_assets


def estimate_snapshot_asset_download(
    client: httpx.Client,
    snapshot: CrawlSnapshot,
    progress_callback: ProgressCallback | None = None,
) -> AssetDownloadEstimate:
    return estimate_asset_download(
        client,
        collect_unique_squarespace_assets(snapshot),
        progress_callback=progress_callback,
    )


def estimate_asset_download(
    client: httpx.Client,
    assets: list[AssetReference],
    progress_callback: ProgressCallback | None = None,
) -> AssetDownloadEstimate:
    estimated_size_bytes = 0
    unknown_size_count = 0
    warnings: list[str] = []
    total_assets = len(assets)

    if progress_callback is not None:
        progress_callback(0, total_assets, None)

    for index, asset in enumerate(assets, start=1):
        size_bytes, warning = estimate_asset_size_bytes(client, asset.source_url)
        if size_bytes is None:
            unknown_size_count += 1
            if warning:
                warnings.append(f"Could not estimate size for asset {asset.source_url}: {warning}")
        else:
            estimated_size_bytes += size_bytes

        if progress_callback is not None:
            progress_callback(index, total_assets, None)

    return AssetDownloadEstimate(
        assets=list(assets),
        estimated_size_bytes=estimated_size_bytes,
        unknown_size_count=unknown_size_count,
        warnings=list(dict.fromkeys(warnings)),
    )


def download_snapshot_assets(
    client: httpx.Client,
    snapshot: CrawlSnapshot,
    output_dir: Path,
    *,
    estimate: AssetDownloadEstimate | None = None,
    progress_callback: ProgressCallback | None = None,
) -> AssetManifest:
    warnings: list[str] = []
    resolved_assets: list[ResolvedAssetDownload] = []
    assets = estimate.assets if estimate is not None else collect_unique_squarespace_assets(
        snapshot)
    total_assets = len(assets)

    if progress_callback is not None:
        progress_callback(0, total_assets, None)

    for index, asset in enumerate(assets, start=1):
        try:
            response = client.get(asset.source_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            warnings.append(f"Failed to download asset {asset.source_url}: {exc}")
        else:
            content = response.content
            content_type = response.headers.get("content-type")
            extension = extension_for_asset(str(response.url), content_type)
            asset_subdir = asset_subdirectory(asset.asset_type)
            resolved_assets.append(
                ResolvedAssetDownload(
                    asset=asset,
                    final_url=str(response.url),
                    asset_subdir=asset_subdir,
                    extension=extension,
                    content_type=content_type,
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    content=content,
                )
            )

        if progress_callback is not None:
            progress_callback(index, total_assets, None)

    items: list[DownloadedAsset] = []
    grouped_assets = group_downloaded_assets(resolved_assets)
    route_labels = build_route_label_lookup(
        representative_for_group(group).asset.owner_route for group in grouped_assets
    )
    media_group_indices: dict[str, dict[str, int]] = {}
    file_group_indices: dict[str, dict[str, int]] = {}
    used_relative_paths: set[str] = set()

    for group in sorted(grouped_assets, key=download_group_sort_key):
        representative = representative_for_group(group)
        canonical_id = representative.sha256
        route_label = route_labels.get(
            representative.asset.owner_route,
            slugify_fragment(representative.asset.owner_route.strip("/") or "home"),
        )
        if representative.asset.asset_type == "file":
            sequence = route_group_sequence(
                file_group_indices, route_label, representative.asset.group_key)
        else:
            sequence = route_group_sequence(
                media_group_indices, route_label, representative.asset.group_key)

        filename = uniquify_download_filename(
            representative.asset_subdir,
            build_download_filename(
                representative.asset,
                representative.extension,
                route_label,
                sequence,
            ),
            used_relative_paths,
            disambiguators=filename_collision_disambiguators(representative),
        )
        local_relative_path = Path("downloaded-assets") / representative.asset_subdir / filename
        public_relative_path = Path("assets") / representative.asset_subdir / filename
        full_path = output_dir / local_relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(representative.content)

        source_urls = sorted({entry.asset.source_url for entry in group})
        final_urls = sorted({entry.final_url for entry in group})
        item = DownloadedAsset(
            source_url=representative.asset.source_url,
            final_url=representative.final_url,
            asset_type=representative.asset.asset_type,
            owner_route=representative.asset.owner_route,
            group_key=representative.asset.group_key,
            filename=filename,
            local_path=local_relative_path.as_posix(),
            public_path=f"/{public_relative_path.as_posix()}",
            content_type=representative.content_type,
            size_bytes=representative.size_bytes,
            sha256=representative.sha256,
            canonical_id=canonical_id,
            alt_text=representative.asset.alt_text,
            caption=representative.asset.caption,
            link_text=representative.asset.link_text,
            variant_hint=representative.asset.variant_hint,
            alias_source_urls=[url for url in source_urls if url !=
                               representative.asset.source_url],
            alias_final_urls=[url for url in final_urls if url != representative.final_url],
            deduplicated_from_count=len(group),
        )
        items.append(item)

    items.sort(key=lambda item: (item.public_path, item.source_url))

    return AssetManifest(
        generated_at=datetime.now(UTC).isoformat(),
        items=items,
        source_asset_count=len(resolved_assets),
        deduplicated_asset_count=max(0, len(resolved_assets) - len(items)),
        warnings=warnings,
    )


def estimate_asset_size_bytes(client: httpx.Client, source_url: str) -> tuple[int | None, str | None]:
    last_error: str | None = None

    try:
        response = client.head(source_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        last_error = str(exc)
    else:
        content_length = parse_content_length(response.headers.get("content-length"))
        if content_length is not None:
            return content_length, None

    try:
        with client.stream("GET", source_url) as response:
            response.raise_for_status()
            content_length = parse_content_length(response.headers.get("content-length"))
            if content_length is not None:
                return content_length, None
    except httpx.HTTPError as exc:
        last_error = str(exc)

    return None, last_error


def parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped.isdigit():
        return None

    return int(stripped)


def add_srcset_references(
    references: list[AssetReference],
    seen: set[tuple[str, str, str, str | None]],
    *,
    srcset: str | None,
    base_url: str,
    asset_type: str,
    attribute: str,
    owner_route: str,
    group_key: str,
    source_tag: str,
    alt_text: str | None = None,
    caption: str | None = None,
) -> None:
    for url, descriptor in parse_srcset(srcset):
        add_reference(
            references,
            seen,
            url=url,
            base_url=base_url,
            asset_type=asset_type,
            attribute=attribute,
            owner_route=owner_route,
            group_key=group_key,
            source_tag=source_tag,
            alt_text=alt_text,
            caption=caption,
            variant_hint=infer_variant_hint(url, descriptor, asset_type, attribute),
        )


def add_reference(
    references: list[AssetReference],
    seen: set[tuple[str, str, str, str | None]],
    *,
    url: str | None,
    base_url: str,
    asset_type: str,
    attribute: str,
    owner_route: str,
    group_key: str,
    source_tag: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    link_text: str | None = None,
    variant_hint: str | None = None,
) -> None:
    if not url:
        return

    absolute_url = make_absolute_url(base_url, url)
    key = (absolute_url, attribute, group_key, variant_hint)
    if key in seen:
        return
    seen.add(key)
    references.append(
        AssetReference(
            source_url=absolute_url,
            asset_type=asset_type,
            attribute=attribute,
            owner_route=owner_route,
            group_key=group_key,
            source_tag=source_tag,
            alt_text=alt_text,
            caption=caption,
            link_text=link_text,
            variant_hint=variant_hint,
        )
    )


def asset_group_key(tag: Tag, index: int) -> str:
    parent = tag.parent if isinstance(tag.parent, Tag) else None
    if parent and parent.name in {"picture", "video", "audio", "figure", "a"}:
        return f"{parent.name}-{index}"
    return f"{tag.name}-{index}"


def caption_for_tag(tag: Tag) -> str | None:
    figure = tag.find_parent("figure")
    if not figure:
        return None
    caption = figure.find("figcaption")
    if not caption:
        return None
    text = caption.get_text(" ", strip=True)
    return text or None


def preferred_attribute_value(tag: Tag, *attributes: str) -> tuple[str | None, str | None]:
    fallback: tuple[str, str] | None = None

    for attribute in attributes:
        value = tag.get(attribute)
        if not value:
            continue
        if fallback is None:
            fallback = (attribute, value)
        if not is_placeholder_asset_value(value):
            return attribute, value

    if fallback is None:
        return None, None
    return fallback


def first_present_attribute(tag: Tag, *attributes: str) -> tuple[str | None, str | None]:
    for attribute in attributes:
        value = tag.get(attribute)
        if value:
            return attribute, value
    return None, None


def is_placeholder_asset_value(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered in {"#", "about:blank"}:
        return True
    return lowered.startswith(PLACEHOLDER_ASSET_PREFIXES)


def parse_srcset(value: str | None) -> list[tuple[str, str | None]]:
    if not value:
        return []

    entries: list[tuple[str, str | None]] = []
    for candidate in value.split(","):
        cleaned = candidate.strip()
        if not cleaned:
            continue
        parts = cleaned.split()
        url = parts[0]
        descriptor = parts[1] if len(parts) > 1 else None
        entries.append((url, descriptor))
    return entries


def extract_background_urls(style_value: str) -> list[str]:
    return [match.group("url") for match in BACKGROUND_URL_PATTERN.finditer(style_value)]


def is_downloadable_asset_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(path.endswith(suffix) for suffix in DOWNLOADABLE_FILE_SUFFIXES)


def is_squarespace_asset_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(marker in host for marker in SQUARESPACE_HOST_MARKERS)


def group_downloaded_assets(
    resolved_assets: list[ResolvedAssetDownload],
) -> list[list[ResolvedAssetDownload]]:
    groups: dict[tuple[str, str], list[ResolvedAssetDownload]] = {}

    for resolved in resolved_assets:
        key = (resolved.asset_subdir, resolved.sha256)
        groups.setdefault(key, []).append(resolved)

    return list(groups.values())


def representative_for_group(group: list[ResolvedAssetDownload]) -> ResolvedAssetDownload:
    return min(group, key=canonical_asset_sort_key)


def download_group_sort_key(group: list[ResolvedAssetDownload]) -> tuple[tuple[str, ...], tuple[str, int, str], int, str, str]:
    representative = representative_for_group(group)
    return (
        route_sort_key(representative.asset.owner_route),
        asset_group_sort_key(representative.asset.group_key),
        asset_variant_sort_key(representative.asset.variant_hint),
        representative.asset.asset_type,
        representative.final_url or representative.asset.source_url,
    )


def canonical_asset_sort_key(resolved: ResolvedAssetDownload) -> tuple[bool, str, str, str, str, str, str]:
    descriptor = asset_descriptor_stem(resolved.asset)
    variant = canonical_variant_hint(resolved.asset)
    route = slugify_fragment(resolved.asset.owner_route.strip("/") or "home")
    url_identity = resolved.final_url or resolved.asset.source_url
    return (
        is_generic_descriptor_stem(descriptor),
        descriptor,
        variant,
        route,
        url_identity,
        resolved.asset.attribute,
        resolved.asset.group_key,
    )


def build_download_filename(asset: AssetReference, extension: str, route_label: str, sequence: int) -> str:
    if asset.asset_type == "file":
        stem = asset_descriptor_stem(asset)
        if is_generic_descriptor_stem(stem):
            stem = f"{route_label}-file-{sequence}"
        return f"{stem}{extension}"

    stem = f"{route_label}-{sequence}"
    variant = canonical_variant_hint(asset)

    if variant not in {"", "file", "original"}:
        stem = f"{stem}-{variant}"

    return f"{stem}{extension}"


def uniquify_download_filename(
    asset_subdir: str,
    filename: str,
    used_relative_paths: set[str],
    *,
    disambiguators: Iterable[str] = (),
) -> str:
    path_key = f"{asset_subdir}/{filename}"
    if path_key not in used_relative_paths:
        used_relative_paths.add(path_key)
        return filename

    path = Path(filename)
    stem = path.stem
    suffix = path.suffix

    for disambiguator in normalized_collision_disambiguators(disambiguators):
        if stem.endswith(f"-{disambiguator}"):
            continue
        candidate = f"{stem}-{disambiguator}{suffix}"
        candidate_key = f"{asset_subdir}/{candidate}"
        if candidate_key not in used_relative_paths:
            used_relative_paths.add(candidate_key)
            return candidate

    index = 2
    while True:
        candidate = f"{stem}-{index}{suffix}"
        candidate_key = f"{asset_subdir}/{candidate}"
        if candidate_key not in used_relative_paths:
            used_relative_paths.add(candidate_key)
            return candidate
        index += 1


def normalized_collision_disambiguators(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        slug = slugify_fragment(value)
        if slug and slug not in normalized:
            normalized.append(slug)
    return normalized


def filename_collision_disambiguators(resolved: ResolvedAssetDownload) -> list[str]:
    disambiguators: list[str] = []
    for candidate_url in (resolved.final_url, resolved.asset.source_url):
        token = variant_width_token_from_url(candidate_url)
        if token and token not in disambiguators:
            disambiguators.append(token)

    descriptor = asset_descriptor_stem(resolved.asset)
    if descriptor and not is_generic_descriptor_stem(descriptor) and descriptor not in disambiguators:
        disambiguators.append(descriptor)

    return disambiguators


def canonical_variant_hint(asset: AssetReference) -> str:
    return slugify_fragment(asset.variant_hint or "original")


def asset_descriptor_stem(asset: AssetReference) -> str:
    candidates: list[str | None]

    if asset.asset_type == "file":
        candidates = [
            asset.link_text,
            filename_stem_from_url(asset.source_url),
            asset.owner_route.strip("/") or "file",
        ]
    else:
        candidates = [
            filename_stem_from_url(asset.source_url),
            asset.alt_text,
            asset.caption,
            asset.link_text,
            asset.owner_route.strip("/") or asset.asset_type,
        ]

    normalized: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        slug = slugify_fragment(candidate)
        if slug and slug not in normalized:
            normalized.append(slug)

    for slug in normalized:
        if slug not in GENERIC_DESCRIPTOR_STEMS:
            return slug

    if normalized:
        return normalized[0]

    return slugify_fragment(asset.asset_type or "asset")


def is_generic_descriptor_stem(value: str) -> bool:
    parts = [part for part in re.split(r"[-_]+", value.lower()) if part]
    if not parts:
        return True

    textual_parts = [part for part in parts if not part.isdigit()]
    if not textual_parts:
        return True

    return all(part in GENERIC_DESCRIPTOR_STEMS for part in textual_parts)


def build_route_label_lookup(owner_routes: Iterable[str]) -> dict[str, str]:
    unique_routes = sorted(set(owner_routes), key=route_sort_key)
    if not unique_routes:
        return {}

    segment_lookup = {route: route_label_segments(route) for route in unique_routes}
    suffix_widths = {route: 1 for route in unique_routes}

    while True:
        labels = {
            route: "-".join(segment_lookup[route][-suffix_widths[route]:])
            for route in unique_routes
        }
        collisions: dict[str, list[str]] = {}
        for route, label in labels.items():
            collisions.setdefault(label, []).append(route)

        changed = False
        for routes in collisions.values():
            if len(routes) < 2:
                continue
            expandable = [route for route in routes if suffix_widths[route]
                          < len(segment_lookup[route])]
            if not expandable:
                continue
            for route in expandable:
                suffix_widths[route] += 1
                changed = True

        if not changed:
            return labels


def route_label_segments(owner_route: str) -> list[str]:
    segments = [slugify_fragment(part)
                for part in owner_route.strip("/").split("/") if part.strip()]
    return segments or ["home"]


def route_sort_key(owner_route: str) -> tuple[str, ...]:
    return tuple(route_label_segments(owner_route))


def route_group_sequence(
    route_group_indices: dict[str, dict[str, int]],
    route_label: str,
    group_key: str,
) -> int:
    route_map = route_group_indices.setdefault(route_label, {})
    if group_key not in route_map:
        route_map[group_key] = len(route_map) + 1
    return route_map[group_key]


def asset_group_sort_key(group_key: str) -> tuple[str, int, str]:
    prefix, separator, suffix = group_key.partition("-")
    if separator and suffix.isdigit():
        return prefix, int(suffix), group_key
    return prefix, 0, group_key


def asset_variant_sort_key(variant_hint: str | None) -> int:
    variant = slugify_fragment(variant_hint or "original")
    order = {
        "original": 0,
        "poster": 1,
        "small": 2,
        "medium": 3,
        "large": 4,
    }
    return order.get(variant, 10)


def extension_for_asset(url: str, content_type: str | None) -> str:
    lowered_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if lowered_content_type in EXTENSION_OVERRIDES:
        return EXTENSION_OVERRIDES[lowered_content_type]

    path = Path(urlsplit(url).path)
    if path.suffix:
        return normalize_extension(path.suffix)

    guessed = mimetypes.guess_extension(lowered_content_type) if lowered_content_type else None
    return normalize_extension(guessed or ".bin")


def normalize_extension(extension: str) -> str:
    normalized = extension.lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized == ".jpe":
        return ".jpg"
    return normalized


def asset_subdirectory(asset_type: str) -> str:
    return {
        "image": "images",
        "video": "videos",
        "audio": "audio",
        "file": "files",
    }.get(asset_type, "assets")


def filename_stem_from_url(url: str) -> str:
    path = Path(urlsplit(url).path)
    if path.stem:
        return path.stem
    return "asset"


def variant_width_token_from_url(url: str | None) -> str | None:
    if not url:
        return None

    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    for key in ("format", "w", "width", "h", "height"):
        token = dimension_token(query.get(key))
        if token:
            return token

    return None


def dimension_token(value: str | None) -> str | None:
    if not value:
        return None

    stripped = value.strip().lower()
    if not stripped:
        return None
    if stripped.isdigit():
        return f"{stripped}w"

    match = re.fullmatch(r"(\d+)(w|h|x)", stripped)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    return None


def infer_variant_hint(
    url: str | None,
    descriptor: str | None,
    asset_type: str,
    attribute: str,
) -> str:
    if attribute == "poster":
        return "poster"
    if asset_type == "file":
        return "file"

    if descriptor:
        stripped = descriptor.strip().lower()
        if stripped.endswith("w") and stripped[:-1].isdigit():
            return width_to_variant_label(int(stripped[:-1]))
        if stripped.endswith("x") and stripped[:-1].replace(".", "", 1).isdigit():
            return f"{stripped[:-1].replace('.', '-')}x"

    if url:
        parts = urlsplit(url)
        lowered_path = parts.path.lower()
        for keyword in VARIANT_KEYWORDS:
            if keyword in lowered_path:
                return keyword
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        width = query.get("w") or query.get("width")
        if width and width.isdigit():
            return width_to_variant_label(int(width))

    return "original"


def width_to_variant_label(width: int) -> str:
    if width <= 480:
        return "small"
    if width <= 960:
        return "medium"
    if width <= 1600:
        return "large"
    return "original"


def slugify_fragment(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "asset"

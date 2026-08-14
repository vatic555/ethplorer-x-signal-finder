"""Deterministic, network-free helpers for downstream reads of stored X content."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


SAFE_UNAVAILABLE_REFERENCE_REASONS = frozenset(
    {
        "not_found",
        "protected_or_inaccessible",
        "api_unavailable",
        "unknown",
    }
)


@dataclass(frozen=True)
class ResolvedXUrl:
    """One stored X URL entity and its best already-returned destination."""

    original_url: str
    resolved_url: str
    resolution_source: str
    expanded_url: str | None
    unwound_url: str | None


def resolve_x_url_entity(entity: Mapping[str, Any]) -> ResolvedXUrl | None:
    """Resolve one entity as unwound_url, expanded_url, then url without I/O."""
    original = entity.get("url")
    if not isinstance(original, str) or not original:
        return None
    unwound = entity.get("unwound_url")
    expanded = entity.get("expanded_url")
    safe_unwound = unwound if isinstance(unwound, str) and unwound else None
    safe_expanded = expanded if isinstance(expanded, str) and expanded else None
    if safe_unwound is not None:
        resolved, source = safe_unwound, "unwound_url"
    elif safe_expanded is not None:
        resolved, source = safe_expanded, "expanded_url"
    else:
        resolved, source = original, "url"
    return ResolvedXUrl(
        original_url=original,
        resolved_url=resolved,
        resolution_source=source,
        expanded_url=safe_expanded,
        unwound_url=safe_unwound,
    )


def _url_entities(entities: object) -> Iterable[Mapping[str, Any]]:
    if not isinstance(entities, Mapping):
        return ()
    urls = entities.get("urls", [])
    if not isinstance(urls, list):
        return ()
    return (item for item in urls if isinstance(item, Mapping))


def resolved_x_urls_from_stored_post(
    *,
    entities: object,
    raw_json: object | None = None,
) -> tuple[ResolvedXUrl, ...]:
    """Read resolved URLs from stored main and note_tweet entities without requests."""
    entity_sets: list[object] = [entities]
    if isinstance(raw_json, Mapping):
        note_tweet = raw_json.get("note_tweet")
        if isinstance(note_tweet, Mapping):
            entity_sets.append(note_tweet.get("entities"))

    results: list[ResolvedXUrl] = []
    seen: set[tuple[str, str, str]] = set()
    for entity_set in entity_sets:
        for entity in _url_entities(entity_set):
            resolved = resolve_x_url_entity(entity)
            if resolved is None:
                continue
            fingerprint = (
                resolved.original_url,
                resolved.resolved_url,
                resolved.resolution_source,
            )
            if fingerprint not in seen:
                seen.add(fingerprint)
                results.append(resolved)
    return tuple(results)


def is_tco_url(value: str) -> bool:
    hostname = (urlparse(value).hostname or "").lower()
    return hostname == "t.co"


def first_party_site(value: str) -> str | None:
    hostname = (urlparse(value).hostname or "").lower().rstrip(".")
    for site in ("ethplorer.io", "binplorer.com"):
        if hostname == site or hostname.endswith(f".{site}"):
            return site
    return None


def unavailable_reference_reason(relationship: Mapping[str, Any]) -> str | None:
    """Read a safe reason, treating old unavailable records as unknown."""
    if relationship.get("context_state") != "unavailable":
        return None
    reason = relationship.get("unavailable_reason")
    if isinstance(reason, str) and reason in SAFE_UNAVAILABLE_REFERENCE_REASONS:
        return reason
    return "unknown"


def summarize_stored_x_urls(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Return content-safe aggregate URL counts for stored first-party rows."""
    posts_with_urls = 0
    url_entities = 0
    with_expanded_url = 0
    with_unwound_url = 0
    tco_only = 0
    ethplorer_urls = 0
    binplorer_urls = 0
    for post in posts:
        urls = resolved_x_urls_from_stored_post(
            entities=post.get("entities"),
            raw_json=post.get("raw_json"),
        )
        if urls:
            posts_with_urls += 1
        for url in urls:
            url_entities += 1
            with_expanded_url += url.expanded_url is not None
            with_unwound_url += url.unwound_url is not None
            tco_only += is_tco_url(url.resolved_url)
            site = first_party_site(url.resolved_url)
            ethplorer_urls += site == "ethplorer.io"
            binplorer_urls += site == "binplorer.com"
    return {
        "posts_with_url_entities": posts_with_urls,
        "url_entities": url_entities,
        "url_entities_with_expanded_url": with_expanded_url,
        "url_entities_with_unwound_url": with_unwound_url,
        "urls_remaining_tco_only": tco_only,
        "ethplorer_site_urls": ethplorer_urls,
        "binplorer_site_urls": binplorer_urls,
        "first_party_site_urls": ethplorer_urls + binplorer_urls,
    }

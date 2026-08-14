"""Auditable first-party Ethplorer and Binplorer X corpus synchronization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
import time
from typing import Any, Literal, Protocol
from uuid import UUID

from x_signal_finder.collector import (
    _PageRequestFailed,
    _request_page_with_retry,
)
from x_signal_finder.x_api.client import XApiClient


FirstPartySource = Literal["ethplorer", "binplorer"]


@dataclass(frozen=True)
class FirstPartyAccount:
    source: FirstPartySource
    user_id: str
    inventory_reference: int


ACCOUNTS: dict[FirstPartySource, FirstPartyAccount] = {
    "ethplorer": FirstPartyAccount(
        source="ethplorer",
        user_id="866192511038922753",
        inventory_reference=352,
    ),
    "binplorer": FirstPartyAccount(
        source="binplorer",
        user_id="1565037191214030853",
        inventory_reference=39,
    ),
}

SOURCE_KEYS: dict[FirstPartySource, str] = {
    "ethplorer": "first_party_x_ethplorer",
    "binplorer": "first_party_x_binplorer",
}

TWEET_FIELDS = (
    "attachments,author_id,conversation_id,created_at,edit_history_tweet_ids,"
    "entities,in_reply_to_user_id,lang,note_tweet,public_metrics,"
    "referenced_tweets,text"
)
EXPANSIONS = (
    "attachments.media_keys,author_id,in_reply_to_user_id,"
    "referenced_tweets.id,referenced_tweets.id.author_id,"
    "referenced_tweets.id.attachments.media_keys"
)
USER_FIELDS = "created_at,id,name,protected,public_metrics,username,verified"
MEDIA_FIELDS = (
    "alt_text,duration_ms,height,media_key,preview_image_url,public_metrics,"
    "type,url,width"
)

BLOCKING_WARNINGS = frozenset(
    {
        "cost_guard_reached",
        "duplicate_post_ids_detected",
        "invalid_post_shape_present",
        "page_limit_reached",
        "pagination_metadata_missing",
        "request_failed_after_partial_fetch",
        "usage_recording_failed",
    }
)


class FirstPartyXError(RuntimeError):
    """Content-safe corpus error that never embeds Post text or response bodies."""


class FirstPartyRepository(Protocol):
    def get_existing_first_party_x_post_ids(self, post_ids) -> frozenset[str]: ...

    def upsert_first_party_x_posts(self, posts) -> None: ...

    def update_sync_state(self, **values) -> None: ...

    def record_usage_event(self, event) -> None: ...


@dataclass(frozen=True, repr=False)
class FetchedFirstPartySource:
    source: FirstPartySource
    source_key: str
    source_user_id: str
    requests_count: int
    timeline_requests_count: int
    reference_lookup_requests_count: int
    primary_posts_received: int
    expanded_posts_received: int
    reference_completion_posts_received: int
    distinct_post_resources_received: int
    media_resources_received: int
    records: tuple[dict[str, Any], ...]
    newest_post_id: str | None
    oldest_post_id: str | None
    newest_created_at: datetime | None
    oldest_created_at: datetime | None
    checkpoint_before: str | None
    checkpoint_candidate: str | None
    checkpoint_can_advance: bool
    completion_state: str
    inventory_tweet_count: int | None
    inventory_reference: int
    unit_cost_usd: Decimal
    estimated_cost_usd: Decimal
    warnings: tuple[str, ...]
    terminal_error_category: str | None = None
    terminal_http_status: int | None = None

    def __repr__(self) -> str:
        return (
            "FetchedFirstPartySource(source="
            f"{self.source!r}, requests_count={self.requests_count}, "
            f"primary_posts_received={self.primary_posts_received}, "
            f"record_count={len(self.records)}, "
            f"completion_state={self.completion_state!r})"
        )

    __str__ = __repr__

    def with_warning(self, warning: str) -> FetchedFirstPartySource:
        return replace(
            self,
            checkpoint_can_advance=False,
            completion_state="incomplete",
            warnings=tuple(sorted(set(self.warnings) | {warning})),
        )


@dataclass(frozen=True, repr=False)
class FirstPartySyncSummary:
    source: FirstPartySource
    source_key: str
    requests_count: int
    timeline_requests_count: int
    reference_lookup_requests_count: int
    primary_posts_received: int
    posts_saved: int
    new_posts: int
    existing_posts_updated: int
    originals: int
    replies: int
    quotes: int
    reposts: int
    unique_referenced_post_ids: int
    referenced_contexts_available: int
    referenced_contexts_unavailable: int
    media_resources_received: int
    newest_post_id: str | None
    oldest_post_id: str | None
    newest_created_at: datetime | None
    oldest_created_at: datetime | None
    inventory_tweet_count: int | None
    inventory_reference: int
    retrieval_difference: int | None
    checkpoint_before: str | None
    checkpoint_after: str | None
    completion_state: str
    unit_cost_usd: Decimal
    estimated_cost_usd: Decimal
    warnings: tuple[str, ...]

    @property
    def has_blocking_warning(self) -> bool:
        return self.completion_state != "complete" or bool(
            BLOCKING_WARNINGS.intersection(self.warnings)
        )

    def safe_diagnostic(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_key": self.source_key,
            "requests_count": self.requests_count,
            "timeline_requests_count": self.timeline_requests_count,
            "reference_lookup_requests_count": self.reference_lookup_requests_count,
            "primary_posts_received": self.primary_posts_received,
            "posts_saved": self.posts_saved,
            "new_posts": self.new_posts,
            "existing_posts_updated": self.existing_posts_updated,
            "originals": self.originals,
            "replies": self.replies,
            "quotes": self.quotes,
            "reposts": self.reposts,
            "unique_referenced_post_ids": self.unique_referenced_post_ids,
            "referenced_contexts_available": self.referenced_contexts_available,
            "referenced_contexts_unavailable": self.referenced_contexts_unavailable,
            "media_resources_received": self.media_resources_received,
            "oldest_post_id": self.oldest_post_id,
            "newest_post_id": self.newest_post_id,
            "oldest_created_at": (
                self.oldest_created_at.isoformat() if self.oldest_created_at else None
            ),
            "newest_created_at": (
                self.newest_created_at.isoformat() if self.newest_created_at else None
            ),
            "inventory_tweet_count": self.inventory_tweet_count,
            "previous_inventory_reference": self.inventory_reference,
            "retrieval_difference": self.retrieval_difference,
            "checkpoint_before": self.checkpoint_before,
            "checkpoint_after": self.checkpoint_after,
            "completion_state": self.completion_state,
            "unit_cost_usd": format(self.unit_cost_usd, "f"),
            "estimated_x_cost_usd": format(self.estimated_cost_usd, "f"),
            "warnings": list(self.warnings),
            "errors": [],
        }

    def __repr__(self) -> str:
        return f"FirstPartySyncSummary({self.safe_diagnostic()!r})"

    __str__ = __repr__


def source_key_for(source: FirstPartySource) -> str:
    return SOURCE_KEYS[source]


def endpoint_for(source: FirstPartySource) -> str:
    return f"/users/{ACCOUNTS[source].user_id}/tweets"


def _full_text(post: Mapping[str, Any]) -> tuple[str, str]:
    note_tweet = post.get("note_tweet")
    if note_tweet is not None and not isinstance(note_tweet, Mapping):
        raise FirstPartyXError("X Post contains invalid note_tweet data.")
    note_text = note_tweet.get("text") if note_tweet is not None else None
    if note_text is not None and not isinstance(note_text, str):
        raise FirstPartyXError("X Post contains invalid note_tweet text data.")
    if note_text:
        return note_text, "note_tweet"
    text = post.get("text")
    if not isinstance(text, str):
        raise FirstPartyXError("X Post is missing a required text field.")
    return text, "text"


def _datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise FirstPartyXError(f"X Post is missing the requested {field} field.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FirstPartyXError(f"X Post contains an invalid {field} field.") from error
    if parsed.tzinfo is None:
        raise FirstPartyXError(f"X Post {field} must include a timezone.")
    return parsed


def _optional_string(post: Mapping[str, Any], field: str) -> str | None:
    value = post.get(field)
    if value is not None and not isinstance(value, str):
        raise FirstPartyXError(f"X Post contains invalid {field} data.")
    return value


def _json_object(post: Mapping[str, Any], field: str) -> dict[str, Any]:
    value = post.get(field)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FirstPartyXError(f"X Post contains invalid {field} data.")
    return dict(value)


def _media_keys(post: Mapping[str, Any]) -> tuple[str, ...]:
    attachments = post.get("attachments")
    if attachments is None:
        return ()
    if not isinstance(attachments, Mapping):
        raise FirstPartyXError("X Post contains invalid attachments data.")
    keys = attachments.get("media_keys", [])
    if keys is None:
        return ()
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        raise FirstPartyXError("X Post contains invalid media_keys data.")
    return tuple(keys)


def _media_for(
    post: Mapping[str, Any],
    media_by_key: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        dict(media_by_key[key])
        for key in _media_keys(post)
        if key in media_by_key and isinstance(media_by_key[key], Mapping)
    ]


def _raw_references(post: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = post.get("referenced_tweets", [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise FirstPartyXError("X Post contains invalid referenced_tweets data.")
    references = [dict(item) for item in value]
    for reference in references:
        if reference.get("type") not in {"replied_to", "quoted", "retweeted"}:
            raise FirstPartyXError("X Post contains an unknown reference type.")
        if not isinstance(reference.get("id"), str):
            raise FirstPartyXError("X Post reference is missing a valid id.")
    return references


def _post_type(post: Mapping[str, Any], references: list[dict[str, Any]]) -> str:
    types = {str(reference["type"]) for reference in references}
    if "retweeted" in types:
        return "repost"
    if "quoted" in types:
        return "quote"
    if "replied_to" in types or post.get("in_reply_to_user_id") is not None:
        return "reply"
    return "original"


def map_first_party_x_post(
    post: Mapping[str, Any],
    *,
    source: FirstPartySource,
    users_by_id: Mapping[str, Mapping[str, Any]],
    expanded_posts_by_id: Mapping[str, Mapping[str, Any]],
    media_by_key: Mapping[str, Mapping[str, Any]],
    run_id: UUID,
    collected_at: datetime,
) -> dict[str, Any]:
    """Map one Post and every direct returned relationship without truncation."""
    post_id = post.get("id")
    if not isinstance(post_id, str):
        raise FirstPartyXError("X Post is missing a required id field.")
    text, full_text_source = _full_text(post)
    created_at = _datetime(post.get("created_at"), field="created_at")
    references = _raw_references(post)
    author_id = _optional_string(post, "author_id")
    author = users_by_id.get(author_id, {}) if author_id else {}
    raw_username = author.get("username") if isinstance(author, Mapping) else None
    if raw_username is not None and not isinstance(raw_username, str):
        raise FirstPartyXError("Expanded X User contains invalid username data.")
    author_username = raw_username or source
    main_media = _media_for(post, media_by_key)

    relationship_records: list[dict[str, Any]] = []
    expanded_relationships: list[dict[str, Any]] = []
    for index, relationship in enumerate(references):
        referenced_id = str(relationship["id"])
        expanded_post = expanded_posts_by_id.get(referenced_id)
        context_state = "available" if expanded_post is not None else "unavailable"
        reference_record: dict[str, Any] = {
            "relationship_index": index,
            "relationship_type": str(relationship["type"]),
            "referenced_post_id": referenced_id,
            "context_state": context_state,
            "raw_relationship": dict(relationship),
        }
        expanded_context: dict[str, Any] = {
            "relationship": dict(relationship),
            "context_state": context_state,
        }
        if expanded_post is not None:
            if not isinstance(expanded_post, Mapping):
                raise FirstPartyXError("X Post contains invalid expanded Post data.")
            referenced_text, referenced_text_source = _full_text(expanded_post)
            referenced_author_id = _optional_string(expanded_post, "author_id")
            referenced_author = (
                users_by_id.get(referenced_author_id, {})
                if referenced_author_id
                else {}
            )
            referenced_username = (
                referenced_author.get("username")
                if isinstance(referenced_author, Mapping)
                else None
            )
            if referenced_username is not None and not isinstance(
                referenced_username, str
            ):
                raise FirstPartyXError(
                    "Expanded referenced author contains invalid username data."
                )
            referenced_created_at = _datetime(
                expanded_post.get("created_at"),
                field="created_at",
            )
            referenced_media = _media_for(expanded_post, media_by_key)
            referenced_media_key_count = len(_media_keys(expanded_post))
            referenced_entities = _json_object(expanded_post, "entities")
            reference_record.update(
                {
                    "referenced_text": referenced_text,
                    "referenced_author_id": referenced_author_id,
                    "referenced_author_username": referenced_username,
                    "referenced_created_at": referenced_created_at,
                    "referenced_entities": referenced_entities,
                    "referenced_media_metadata": referenced_media,
                    "expanded_raw_json": dict(expanded_post),
                }
            )
            expanded_context.update(
                {
                    "full_text_source": referenced_text_source,
                    "referenced_post": dict(expanded_post),
                    "referenced_author": {
                        key: value
                        for key, value in {
                            "id": referenced_author_id,
                            "username": referenced_username,
                        }.items()
                        if value is not None
                    },
                    "media": referenced_media,
                }
            )
            if referenced_media_key_count > len(referenced_media):
                expanded_context["media_expansion_incomplete"] = True
                expanded_context["missing_media_count"] = (
                    referenced_media_key_count - len(referenced_media)
                )
        relationship_records.append(reference_record)
        expanded_relationships.append(expanded_context)

    if not references:
        context_state = "not_applicable"
    elif any(item["context_state"] == "unavailable" for item in relationship_records):
        context_state = "unavailable"
    else:
        context_state = "available"

    raw_json = dict(post)
    raw_json["_expanded"] = {
        "relationships": expanded_relationships,
        "media": main_media,
    }
    collector_metadata: dict[str, Any] = {
        "full_text_source": full_text_source,
        "referenced_context_state": context_state,
    }
    main_media_key_count = len(_media_keys(post))
    if main_media_key_count > len(main_media):
        collector_metadata["media_expansion_incomplete"] = True
        collector_metadata["missing_media_count"] = main_media_key_count - len(main_media)
    raw_json["_collector"] = collector_metadata
    post_url = f"https://x.com/{author_username}/status/{post_id}"
    return {
        "post_id": post_id,
        "source_account": source,
        "source_user_id": ACCOUNTS[source].user_id,
        "author_id": author_id,
        "author_username": author_username,
        "post_url": post_url,
        "created_at": created_at,
        "conversation_id": _optional_string(post, "conversation_id"),
        "in_reply_to_user_id": _optional_string(post, "in_reply_to_user_id"),
        "post_type": _post_type(post, references),
        "text": text,
        "lang": _optional_string(post, "lang"),
        "entities": _json_object(post, "entities"),
        "public_metrics": _json_object(post, "public_metrics"),
        "media_metadata": main_media,
        "referenced_relationships": expanded_relationships,
        "referenced_context_state": context_state,
        "raw_json": raw_json,
        "publication_origin": "unknown",
        "opportunity_id": None,
        "first_seen_run_id": run_id,
        "last_seen_run_id": run_id,
        "first_collected_at": collected_at,
        "last_collected_at": collected_at,
        "references": relationship_records,
    }


def _reference_ids(posts: tuple[Mapping[str, Any], ...]) -> set[str]:
    return {
        str(reference["id"])
        for post in posts
        for reference in _raw_references(post)
    }


def _chunks(values: list[str], size: int = 100):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def fetch_first_party_source(
    *,
    client: XApiClient,
    source: FirstPartySource,
    run_id: UUID,
    collected_at: datetime,
    checkpoint_before: str | None,
    max_pages: int,
    max_estimated_cost_usd: Decimal,
    estimated_cost_before_usd: Decimal = Decimal("0"),
    unit_cost_usd: Decimal = Decimal("0.005"),
    inventory_tweet_count: int | None = None,
    max_attempts: int = 3,
    max_retry_wait_seconds: float = 60,
    sleep=time.sleep,
    now_timestamp=time.time,
) -> FetchedFirstPartySource:
    """Fetch a complete historical or incremental source within explicit guards."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if max_estimated_cost_usd <= 0 or unit_cost_usd <= 0:
        raise ValueError("cost limits and unit cost must be positive")
    if estimated_cost_before_usd >= max_estimated_cost_usd:
        raise FirstPartyXError("Estimated-cost guard prevents the first request.")

    endpoint = endpoint_for(source)
    base_params: dict[str, object] = {
        "max_results": 100,
        "tweet.fields": TWEET_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
        "since_id": checkpoint_before,
    }
    pages = []
    users_by_id: dict[str, Mapping[str, Any]] = {}
    expanded_posts_by_id: dict[str, Mapping[str, Any]] = {}
    media_by_key: dict[str, Mapping[str, Any]] = {}
    primary_ids: set[str] = set()
    expanded_ids: set[str] = set()
    completion_ids: set[str] = set()
    timeline_requests = 0
    reference_requests = 0
    warnings: set[str] = set()
    pagination_token: str | None = None
    terminal_error = None

    while len(pages) < max_pages:
        params = dict(base_params)
        if pagination_token:
            params["pagination_token"] = pagination_token
        try:
            result = _request_page_with_retry(
                client=client,
                endpoint=endpoint,
                params=params,
                max_attempts=max_attempts,
                max_retry_wait_seconds=max_retry_wait_seconds,
                sleep=sleep,
                now_timestamp=now_timestamp,
            )
        except _PageRequestFailed as failure:
            timeline_requests += failure.attempts
            if not pages:
                raise failure.error
            terminal_error = failure.error
            warnings.add("request_failed_after_partial_fetch")
            break
        page = result.page
        timeline_requests += result.attempts
        pages.append(page)
        users_by_id.update(page.users_by_id)
        expanded_posts_by_id.update(page.expanded_posts_by_id)
        media_by_key.update(page.media_by_key)
        primary_ids.update(str(post["id"]) for post in page.posts)
        expanded_ids.update(page.expanded_posts_by_id)
        pagination_token = page.next_token
        if page.partial_error_count:
            warnings.add("partial_resources_unavailable")
        if not page.meta_present:
            warnings.add("pagination_metadata_missing")
            break
        if not pagination_token:
            break
        current_cost = unit_cost_usd * len(primary_ids | expanded_ids)
        if estimated_cost_before_usd + current_cost >= max_estimated_cost_usd:
            warnings.add("cost_guard_reached")
            break

    if not pages:
        raise FirstPartyXError("First-party X sync produced no response page.")
    if pagination_token and len(pages) >= max_pages:
        warnings.add("page_limit_reached")

    raw_posts = tuple(post for page in pages for post in page.posts)
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    unique_posts: list[Mapping[str, Any]] = []
    for post in raw_posts:
        post_id = str(post["id"])
        if post_id in seen:
            duplicate_ids.add(post_id)
            continue
        seen.add(post_id)
        unique_posts.append(post)
    if duplicate_ids:
        warnings.add("duplicate_post_ids_detected")

    direct_reference_ids = _reference_ids(tuple(unique_posts))
    missing_reference_ids = sorted(direct_reference_ids - set(expanded_posts_by_id))
    lookup_endpoint = "/tweets"
    for batch in _chunks(missing_reference_ids):
        current_cost = unit_cost_usd * len(primary_ids | expanded_ids | completion_ids)
        if estimated_cost_before_usd + current_cost >= max_estimated_cost_usd:
            warnings.add("reference_completion_cost_guard_reached")
            break
        try:
            result = _request_page_with_retry(
                client=client,
                endpoint=lookup_endpoint,
                params={
                    "ids": ",".join(batch),
                    "tweet.fields": TWEET_FIELDS,
                    "expansions": EXPANSIONS,
                    "user.fields": USER_FIELDS,
                    "media.fields": MEDIA_FIELDS,
                },
                max_attempts=max_attempts,
                max_retry_wait_seconds=max_retry_wait_seconds,
                sleep=sleep,
                now_timestamp=now_timestamp,
            )
        except _PageRequestFailed as failure:
            reference_requests += failure.attempts
            warnings.add("reference_completion_request_failed")
            break
        page = result.page
        reference_requests += result.attempts
        users_by_id.update(page.users_by_id)
        media_by_key.update(page.media_by_key)
        expanded_posts_by_id.update({str(post["id"]): post for post in page.posts})
        expanded_posts_by_id.update(page.expanded_posts_by_id)
        completion_ids.update(str(post["id"]) for post in page.posts)
        completion_ids.update(page.expanded_posts_by_id)
        if page.partial_error_count:
            warnings.add("reference_completion_partial_errors")

    records: list[dict[str, Any]] = []
    for post in unique_posts:
        try:
            records.append(
                map_first_party_x_post(
                    post,
                    source=source,
                    users_by_id=users_by_id,
                    expanded_posts_by_id=expanded_posts_by_id,
                    media_by_key=media_by_key,
                    run_id=run_id,
                    collected_at=collected_at,
                )
            )
        except FirstPartyXError:
            warnings.add("invalid_post_shape_present")

    blocking = bool(BLOCKING_WARNINGS.intersection(warnings))
    completion_state = "incomplete" if blocking else "complete"
    first_page = pages[0]
    last_page = pages[-1]
    created_times = [record["created_at"] for record in records]
    all_resource_ids = primary_ids | expanded_ids | completion_ids
    return FetchedFirstPartySource(
        source=source,
        source_key=source_key_for(source),
        source_user_id=ACCOUNTS[source].user_id,
        requests_count=timeline_requests + reference_requests,
        timeline_requests_count=timeline_requests,
        reference_lookup_requests_count=reference_requests,
        primary_posts_received=len(raw_posts),
        expanded_posts_received=len(expanded_ids),
        reference_completion_posts_received=len(completion_ids),
        distinct_post_resources_received=len(all_resource_ids),
        media_resources_received=len(media_by_key),
        records=tuple(records),
        newest_post_id=first_page.newest_id,
        oldest_post_id=last_page.oldest_id,
        newest_created_at=max(created_times) if created_times else None,
        oldest_created_at=min(created_times) if created_times else None,
        checkpoint_before=checkpoint_before,
        checkpoint_candidate=first_page.newest_id or checkpoint_before,
        checkpoint_can_advance=not blocking,
        completion_state=completion_state,
        inventory_tweet_count=inventory_tweet_count,
        inventory_reference=ACCOUNTS[source].inventory_reference,
        unit_cost_usd=unit_cost_usd,
        estimated_cost_usd=unit_cost_usd * len(all_resource_ids),
        warnings=tuple(sorted(warnings)),
        terminal_error_category=(terminal_error.category if terminal_error else None),
        terminal_http_status=(terminal_error.status if terminal_error else None),
    )


def save_first_party_source(
    *,
    repository: FirstPartyRepository,
    fetched: FetchedFirstPartySource,
    previous_state: Mapping[str, Any] | None,
    run_id: UUID,
    collected_at: datetime,
    max_pages: int,
) -> FirstPartySyncSummary:
    post_ids = tuple(str(record["post_id"]) for record in fetched.records)
    existing_ids = repository.get_existing_first_party_x_post_ids(post_ids)
    repository.upsert_first_party_x_posts(fetched.records)
    checkpoint_after = (
        fetched.checkpoint_candidate
        if fetched.checkpoint_can_advance
        else fetched.checkpoint_before
    )
    previous_success_at = previous_state.get("last_successful_at") if previous_state else None
    previous_success_run = (
        previous_state.get("last_successful_run_id") if previous_state else None
    )
    type_counts = {
        post_type: sum(record["post_type"] == post_type for record in fetched.records)
        for post_type in ("original", "reply", "quote", "repost")
    }
    references = [
        reference
        for record in fetched.records
        for reference in record.get("references", [])
    ]
    previous_metadata = (
        previous_state.get("checkpoint_metadata") if previous_state else None
    )
    preserved_inventory_count = fetched.inventory_tweet_count
    if preserved_inventory_count is None and isinstance(previous_metadata, Mapping):
        raw_inventory_count = previous_metadata.get("inventory_tweet_count")
        if isinstance(raw_inventory_count, int) and not isinstance(
            raw_inventory_count, bool
        ):
            preserved_inventory_count = raw_inventory_count
    metadata = {
        "source": fetched.source,
        "source_user_id": fetched.source_user_id,
        "collection_run_id": str(run_id),
        "max_pages": max_pages,
        "requests_count": fetched.requests_count,
        "timeline_requests_count": fetched.timeline_requests_count,
        "reference_lookup_requests_count": fetched.reference_lookup_requests_count,
        "primary_posts_received": fetched.primary_posts_received,
        "posts_saved": len(post_ids),
        "inventory_tweet_count": preserved_inventory_count,
        "previous_inventory_reference": fetched.inventory_reference,
        "completion_state": fetched.completion_state,
        "newest_post_id": fetched.newest_post_id,
        "oldest_post_id": fetched.oldest_post_id,
        "estimated_x_cost_usd": format(fetched.estimated_cost_usd, "f"),
        "warnings": list(fetched.warnings),
    }
    repository.update_sync_state(
        source_key=fetched.source_key,
        checkpoint_value=checkpoint_after,
        checkpoint_metadata=metadata,
        last_attempt_at=collected_at,
        last_successful_at=(
            collected_at if fetched.checkpoint_can_advance else previous_success_at
        ),
        last_successful_run_id=(
            run_id if fetched.checkpoint_can_advance else previous_success_run
        ),
        last_warning_code=fetched.warnings[0] if fetched.warnings else None,
        updated_at=collected_at,
    )
    inventory_count = preserved_inventory_count
    retrieval_difference = (
        len(post_ids) - inventory_count
        if inventory_count is not None and fetched.checkpoint_before is None
        else None
    )
    return FirstPartySyncSummary(
        source=fetched.source,
        source_key=fetched.source_key,
        requests_count=fetched.requests_count,
        timeline_requests_count=fetched.timeline_requests_count,
        reference_lookup_requests_count=fetched.reference_lookup_requests_count,
        primary_posts_received=fetched.primary_posts_received,
        posts_saved=len(post_ids),
        new_posts=len(post_ids) - len(existing_ids),
        existing_posts_updated=len(existing_ids),
        originals=type_counts["original"],
        replies=type_counts["reply"],
        quotes=type_counts["quote"],
        reposts=type_counts["repost"],
        unique_referenced_post_ids=len(
            {reference["referenced_post_id"] for reference in references}
        ),
        referenced_contexts_available=sum(
            reference["context_state"] == "available" for reference in references
        ),
        referenced_contexts_unavailable=sum(
            reference["context_state"] == "unavailable" for reference in references
        ),
        media_resources_received=fetched.media_resources_received,
        newest_post_id=fetched.newest_post_id,
        oldest_post_id=fetched.oldest_post_id,
        newest_created_at=fetched.newest_created_at,
        oldest_created_at=fetched.oldest_created_at,
        inventory_tweet_count=inventory_count,
        inventory_reference=fetched.inventory_reference,
        retrieval_difference=retrieval_difference,
        checkpoint_before=fetched.checkpoint_before,
        checkpoint_after=checkpoint_after,
        completion_state=fetched.completion_state,
        unit_cost_usd=fetched.unit_cost_usd,
        estimated_cost_usd=fetched.estimated_cost_usd,
        warnings=fetched.warnings,
    )


def record_first_party_usage(
    *,
    repository: FirstPartyRepository,
    fetched: FetchedFirstPartySource,
    run_id: UUID,
    usage_event_id: UUID,
    collected_at: datetime,
) -> None:
    repository.record_usage_event(
        {
            "usage_event_id": usage_event_id,
            "run_id": run_id,
            "provider": "x",
            "operation": f"first_party_x_sync_{fetched.source}",
            "request_count": fetched.requests_count,
            "input_units": fetched.distinct_post_resources_received,
            "reported_cost": None,
            "estimated_cost": fetched.estimated_cost_usd,
            "currency": "USD",
            "created_at": collected_at,
            "metadata": {
                "source": fetched.source,
                "source_key": fetched.source_key,
                "source_run_id": str(run_id),
                "primary_post_resources": fetched.primary_posts_received,
                "expanded_post_resources": fetched.expanded_posts_received,
                "reference_completion_post_resources": (
                    fetched.reference_completion_posts_received
                ),
                "distinct_post_resources": fetched.distinct_post_resources_received,
                "media_resources": fetched.media_resources_received,
                "timeline_requests": fetched.timeline_requests_count,
                "reference_lookup_requests": fetched.reference_lookup_requests_count,
                "pricing_basis": "estimated_distinct_post_resources",
                "unit_cost_usd": format(fetched.unit_cost_usd, "f"),
                "completion_state": fetched.completion_state,
                "warnings": list(fetched.warnings),
            },
        }
    )


def record_inventory_usage(
    *,
    repository: FirstPartyRepository,
    run_id: UUID,
    usage_event_id: UUID,
    collected_at: datetime,
    request_count: int,
    user_count: int,
    unit_cost_usd: Decimal,
    inventory_counts: Mapping[str, int | None] | None = None,
) -> Decimal:
    estimated_cost = unit_cost_usd * user_count
    repository.record_usage_event(
        {
            "usage_event_id": usage_event_id,
            "run_id": run_id,
            "provider": "x",
            "operation": "first_party_x_inventory_lookup",
            "request_count": request_count,
            "input_units": user_count,
            "reported_cost": None,
            "estimated_cost": estimated_cost,
            "currency": "USD",
            "created_at": collected_at,
            "metadata": {
                "user_resources": user_count,
                "pricing_basis": "estimated_user_reads",
                "unit_cost_usd": format(unit_cost_usd, "f"),
                "inventory_tweet_counts": dict(inventory_counts or {}),
            },
        }
    )
    return estimated_cost

"""Bounded X collection and PostgreSQL persistence for Task 004A."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from x_signal_finder.x_api.client import XApiClient
from x_signal_finder.x_api.probe import (
    EXPANSIONS,
    MEDIA_FIELDS,
    TWEET_FIELDS,
    USER_FIELDS,
    Source,
    endpoint_for,
)


SOURCE_KEYS: dict[Source, str] = {
    "home": "x_home_timeline",
    "mentions": "x_ethplorer_mentions",
}
POST_READ_COST_USD = Decimal("0.005")


class CollectionError(RuntimeError):
    """Safe collection failure that contains no Post text or credentials."""


class CollectorRepository(Protocol):
    def get_existing_post_ids(self, post_ids) -> frozenset[str]: ...

    def upsert_posts(self, posts) -> None: ...

    def update_sync_state(self, **values) -> None: ...

    def record_usage_event(self, event) -> None: ...


@dataclass(frozen=True, repr=False)
class FetchedSource:
    source: Source
    source_key: str
    endpoint: str
    requests_count: int
    fetched_posts: int
    reposts_excluded: int
    records: tuple[dict[str, Any], ...]
    newest_post_id: str | None
    oldest_post_id: str | None
    checkpoint_before: str | None
    checkpoint_candidate: str | None
    checkpoint_can_advance: bool
    estimated_cost_usd: Decimal
    warnings: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "FetchedSource(source="
            f"{self.source!r}, requests_count={self.requests_count}, "
            f"fetched_posts={self.fetched_posts}, "
            f"saved_candidates={len(self.records)}, "
            f"reposts_excluded={self.reposts_excluded})"
        )

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class SourceCollectionSummary:
    source: Source
    source_key: str
    requests_count: int
    fetched_posts: int
    new_posts: int
    existing_posts: int
    saved_posts: int
    reposts_excluded: int
    newest_post_id: str | None
    oldest_post_id: str | None
    checkpoint_before: str | None
    checkpoint_after: str | None
    estimated_cost_usd: Decimal
    warnings: tuple[str, ...]

    @property
    def has_blocking_warning(self) -> bool:
        return any(
            warning
            in {
                "duplicate_post_ids_detected",
                "incremental_page_limit_reached",
                "pagination_metadata_missing",
                "partial_errors_present",
            }
            for warning in self.warnings
        )

    def safe_diagnostic(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_key": self.source_key,
            "requests_count": self.requests_count,
            "fetched_posts": self.fetched_posts,
            "new_posts": self.new_posts,
            "existing_posts": self.existing_posts,
            "saved_posts": self.saved_posts,
            "reposts_excluded": self.reposts_excluded,
            "newest_post_id": self.newest_post_id,
            "oldest_post_id": self.oldest_post_id,
            "checkpoint_before": self.checkpoint_before,
            "checkpoint_after": self.checkpoint_after,
            "estimated_x_cost_usd": format(self.estimated_cost_usd, "f"),
            "errors": [],
            "warnings": list(self.warnings),
        }

    def __repr__(self) -> str:
        return f"SourceCollectionSummary({self.safe_diagnostic()!r})"

    __str__ = __repr__


def source_key_for(source: Source) -> str:
    return SOURCE_KEYS[source]


def _post_relationship(post: Mapping[str, Any]) -> tuple[str, str | None]:
    raw_references = post.get("referenced_tweets", [])
    if raw_references is None:
        raw_references = []
    if not isinstance(raw_references, list) or not all(
        isinstance(reference, dict) for reference in raw_references
    ):
        raise CollectionError("X Post contains invalid referenced_tweets data.")

    references = [dict(reference) for reference in raw_references]
    for relationship in ("retweeted", "quoted", "replied_to"):
        reference = next(
            (
                item
                for item in references
                if item.get("type") == relationship
                and isinstance(item.get("id"), str)
            ),
            None,
        )
        if reference is not None:
            post_type = {
                "retweeted": "repost",
                "quoted": "quote",
                "replied_to": "reply",
            }[relationship]
            return post_type, str(reference["id"])
    if post.get("in_reply_to_user_id") is not None:
        return "reply", None
    return "original", None


def map_x_post(
    post: Mapping[str, Any],
    *,
    users_by_id: Mapping[str, Mapping[str, Any]],
    source: Source,
    run_id: UUID,
    collected_at: datetime,
) -> dict[str, Any] | None:
    """Map one X Post to the existing schema, excluding simple reposts."""
    post_id = post.get("id")
    text = post.get("text")
    created_at_raw = post.get("created_at")
    if not isinstance(post_id, str) or not isinstance(text, str):
        raise CollectionError("X Post is missing a required id or text field.")
    if not isinstance(created_at_raw, str):
        raise CollectionError("X Post is missing the requested created_at field.")
    try:
        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise CollectionError("X Post contains an invalid created_at field.") from error
    if created_at.tzinfo is None:
        raise CollectionError("X Post created_at must include a timezone.")

    post_type, referenced_post_id = _post_relationship(post)
    if post_type == "repost":
        return None

    author_id = post.get("author_id")
    if author_id is not None and not isinstance(author_id, str):
        raise CollectionError("X Post contains an invalid author_id field.")
    author = users_by_id.get(author_id, {}) if author_id else {}
    username = author.get("username") if isinstance(author, Mapping) else None
    author_username = username if isinstance(username, str) else None

    conversation_id = post.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise CollectionError("X Post contains an invalid conversation_id field.")

    return {
        "post_id": post_id,
        "author_id": author_id,
        "author_username": author_username,
        "created_at": created_at,
        "conversation_id": conversation_id,
        "referenced_post_id": referenced_post_id,
        "post_type": post_type,
        "source_key": source_key_for(source),
        "text": text,
        "raw_json": dict(post),
        "first_seen_run_id": run_id,
        "last_seen_run_id": run_id,
        "first_collected_at": collected_at,
        "last_collected_at": collected_at,
        "processing_status": "unprocessed",
        "availability_status": "available",
        "last_verified_at": collected_at,
    }


def fetch_source(
    *,
    client: XApiClient,
    source: Source,
    user_id: str,
    run_id: UUID,
    collected_at: datetime,
    checkpoint_before: str | None,
    max_pages: int,
    max_results: int,
) -> FetchedSource:
    """Fetch a bounded source window and prepare schema-compatible records."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    minimum = 1 if source == "home" else 5
    if not minimum <= max_results <= 100:
        raise ValueError(f"max_results for {source} must be between {minimum} and 100")

    endpoint = endpoint_for(source, user_id)
    base_params: dict[str, object] = {
        "max_results": max_results,
        "tweet.fields": TWEET_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
        "since_id": checkpoint_before,
    }
    if source == "home":
        base_params["exclude"] = "retweets"

    pages = []
    users_by_id: dict[str, Mapping[str, Any]] = {}
    pagination_token: str | None = None
    while len(pages) < max_pages:
        params = dict(base_params)
        if pagination_token:
            params["pagination_token"] = pagination_token
        page = client.get_content_page(endpoint, params)
        pages.append(page)
        users_by_id.update(page.users_by_id)
        pagination_token = page.next_token
        if not pagination_token:
            break

    raw_posts = tuple(post for page in pages for post in page.posts)
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    reposts_excluded = 0
    for post in raw_posts:
        post_id = str(post["id"])
        if post_id in seen_ids:
            duplicate_ids.add(post_id)
            continue
        seen_ids.add(post_id)
        record = map_x_post(
            post,
            users_by_id=users_by_id,
            source=source,
            run_id=run_id,
            collected_at=collected_at,
        )
        if record is None:
            reposts_excluded += 1
        else:
            records.append(record)

    first_page = pages[0]
    last_page = pages[-1]
    warnings: set[str] = set()
    if any(page.partial_error_count for page in pages):
        warnings.add("partial_errors_present")
    if any(not page.meta_present for page in pages):
        warnings.add("pagination_metadata_missing")
    if duplicate_ids:
        warnings.add("duplicate_post_ids_detected")
    if last_page.next_token:
        if checkpoint_before is None:
            warnings.add("initial_history_not_backfilled")
        else:
            warnings.add("incremental_page_limit_reached")

    checkpoint_can_advance = not warnings.intersection(
        {
            "partial_errors_present",
            "pagination_metadata_missing",
            "duplicate_post_ids_detected",
            "incremental_page_limit_reached",
        }
    )
    checkpoint_candidate = first_page.newest_id or checkpoint_before
    return FetchedSource(
        source=source,
        source_key=source_key_for(source),
        endpoint=endpoint,
        requests_count=len(pages),
        fetched_posts=len(raw_posts),
        reposts_excluded=reposts_excluded,
        records=tuple(records),
        newest_post_id=first_page.newest_id,
        oldest_post_id=last_page.oldest_id,
        checkpoint_before=checkpoint_before,
        checkpoint_candidate=checkpoint_candidate,
        checkpoint_can_advance=checkpoint_can_advance,
        estimated_cost_usd=POST_READ_COST_USD * len(raw_posts),
        warnings=tuple(sorted(warnings)),
    )


def save_source_collection(
    *,
    repository: CollectorRepository,
    fetched: FetchedSource,
    previous_state: Mapping[str, Any] | None,
    run_id: UUID,
    usage_event_id: UUID,
    collected_at: datetime,
    max_pages: int,
    max_results: int,
) -> SourceCollectionSummary:
    """Persist posts, usage, and a safe source checkpoint in caller transaction."""
    post_ids = tuple(str(record["post_id"]) for record in fetched.records)
    existing_ids = repository.get_existing_post_ids(post_ids)
    repository.upsert_posts(fetched.records)

    checkpoint_after = (
        fetched.checkpoint_candidate
        if fetched.checkpoint_can_advance
        else fetched.checkpoint_before
    )
    previous_success_at = (
        previous_state.get("last_successful_at") if previous_state else None
    )
    previous_success_run = (
        previous_state.get("last_successful_run_id") if previous_state else None
    )
    repository.update_sync_state(
        source_key=fetched.source_key,
        checkpoint_value=checkpoint_after,
        checkpoint_metadata={
            "source": fetched.source,
            "requests_count": fetched.requests_count,
            "fetched_posts": fetched.fetched_posts,
            "max_pages": max_pages,
            "max_results": max_results,
            "warnings": list(fetched.warnings),
        },
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
    repository.record_usage_event(
        {
            "usage_event_id": usage_event_id,
            "run_id": run_id,
            "provider": "x",
            "operation": f"collect_{fetched.source}",
            "request_count": fetched.requests_count,
            "input_units": fetched.fetched_posts,
            "estimated_cost": fetched.estimated_cost_usd,
            "currency": "USD",
            "created_at": collected_at,
            "metadata": {
                "source_key": fetched.source_key,
                "pricing_basis": "public_post_read_estimate",
                "unit_cost_usd": format(POST_READ_COST_USD, "f"),
            },
        }
    )
    existing_count = len(existing_ids)
    saved_count = len(post_ids)
    return SourceCollectionSummary(
        source=fetched.source,
        source_key=fetched.source_key,
        requests_count=fetched.requests_count,
        fetched_posts=fetched.fetched_posts,
        new_posts=saved_count - existing_count,
        existing_posts=existing_count,
        saved_posts=saved_count,
        reposts_excluded=fetched.reposts_excluded,
        newest_post_id=fetched.newest_post_id,
        oldest_post_id=fetched.oldest_post_id,
        checkpoint_before=fetched.checkpoint_before,
        checkpoint_after=checkpoint_after,
        estimated_cost_usd=fetched.estimated_cost_usd,
        warnings=fetched.warnings,
    )


def record_failed_source_attempt(
    *,
    repository: CollectorRepository,
    source: Source,
    previous_state: Mapping[str, Any] | None,
    attempted_at: datetime,
    warning_code: str,
) -> None:
    """Record a failed attempt without advancing or replacing its checkpoint."""
    checkpoint = previous_state.get("checkpoint_value") if previous_state else None
    metadata = dict(previous_state.get("checkpoint_metadata") or {}) if previous_state else {}
    metadata["last_attempt_status"] = "failed"
    repository.update_sync_state(
        source_key=source_key_for(source),
        checkpoint_value=checkpoint,
        checkpoint_metadata=metadata,
        last_attempt_at=attempted_at,
        last_successful_at=(
            previous_state.get("last_successful_at") if previous_state else None
        ),
        last_successful_run_id=(
            previous_state.get("last_successful_run_id") if previous_state else None
        ),
        last_warning_code=warning_code,
        updated_at=attempted_at,
    )

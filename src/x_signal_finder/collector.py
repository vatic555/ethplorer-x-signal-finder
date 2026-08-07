"""Bounded X collection and PostgreSQL persistence for Stage 3."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import time
from typing import Any, Protocol
from uuid import UUID

from x_signal_finder.x_api.client import XApiClient, XApiRequestError
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
DEFAULT_POST_READ_COST_USD = Decimal("0.005")

BLOCKING_WARNINGS = frozenset(
    {
        "cost_guard_reached",
        "duplicate_post_ids_detected",
        "invalid_post_shape_present",
        "page_limit_reached",
        "pagination_metadata_missing",
        "partial_errors_present",
        "primary_post_limit_reached",
        "request_failed_after_partial_fetch",
        "usage_recording_failed",
    }
)


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
    expanded_posts_received: int
    distinct_post_resources_received: int
    reposts_excluded: int
    records: tuple[dict[str, Any], ...]
    newest_post_id: str | None
    oldest_post_id: str | None
    checkpoint_before: str | None
    checkpoint_candidate: str | None
    checkpoint_can_advance: bool
    refresh_existing: bool
    completion_state: str
    unit_cost_usd: Decimal
    estimated_cost_usd: Decimal
    warnings: tuple[str, ...]
    terminal_error_category: str | None = None
    terminal_http_status: int | None = None
    terminal_rate_limits: Mapping[str, str] | None = None

    def __repr__(self) -> str:
        return (
            "FetchedSource(source="
            f"{self.source!r}, requests_count={self.requests_count}, "
            f"fetched_posts={self.fetched_posts}, "
            f"expanded_posts_received={self.expanded_posts_received}, "
            f"completion_state={self.completion_state!r}, "
            f"saved_candidates={len(self.records)}, "
            f"reposts_excluded={self.reposts_excluded})"
        )

    __str__ = __repr__

    def with_warning(self, warning: str) -> FetchedSource:
        """Return an incomplete copy with one additional safe warning."""
        return replace(
            self,
            checkpoint_can_advance=False,
            completion_state="incomplete",
            warnings=tuple(sorted(set(self.warnings) | {warning})),
        )


@dataclass(frozen=True, repr=False)
class SourceCollectionSummary:
    source: Source
    source_key: str
    requests_count: int
    fetched_posts: int
    expanded_posts_received: int
    distinct_post_resources_received: int
    new_posts: int
    existing_posts: int
    saved_posts: int
    reposts_excluded: int
    newest_post_id: str | None
    oldest_post_id: str | None
    checkpoint_before: str | None
    checkpoint_after: str | None
    refresh_existing: bool
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
            "fetched_posts": self.fetched_posts,
            "primary_posts_received": self.fetched_posts,
            "expanded_posts_received": self.expanded_posts_received,
            "distinct_post_resources_received": (
                self.distinct_post_resources_received
            ),
            "new_posts": self.new_posts,
            "existing_posts": self.existing_posts,
            "saved_posts": self.saved_posts,
            "reposts_excluded": self.reposts_excluded,
            "newest_post_id": self.newest_post_id,
            "oldest_post_id": self.oldest_post_id,
            "checkpoint_before": self.checkpoint_before,
            "checkpoint_after": self.checkpoint_after,
            "refresh_existing": self.refresh_existing,
            "completion_state": self.completion_state,
            "unit_cost_usd": format(self.unit_cost_usd, "f"),
            "estimated_x_cost_usd": format(self.estimated_cost_usd, "f"),
            "errors": [],
            "warnings": list(self.warnings),
        }

    def __repr__(self) -> str:
        return f"SourceCollectionSummary({self.safe_diagnostic()!r})"

    __str__ = __repr__


def source_key_for(source: Source) -> str:
    return SOURCE_KEYS[source]


def source_minimum_page_size(source: Source) -> int:
    """Return the X endpoint's minimum accepted page size."""
    return 1 if source == "home" else 5


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


def _full_text(post: Mapping[str, Any]) -> tuple[str, str]:
    """Return validated full Post text and its source without truncation."""
    note_tweet = post.get("note_tweet")
    if note_tweet is not None and not isinstance(note_tweet, Mapping):
        raise CollectionError("X Post contains invalid note_tweet data.")
    note_text = note_tweet.get("text") if note_tweet is not None else None
    if note_text is not None and not isinstance(note_text, str):
        raise CollectionError("X Post contains invalid note_tweet text data.")
    if note_text:
        return note_text, "note_tweet"

    text = post.get("text")
    if not isinstance(text, str):
        raise CollectionError("X Post is missing a required text field.")
    return text, "text"


def _media_keys(post: Mapping[str, Any]) -> tuple[str, ...]:
    attachments = post.get("attachments")
    if attachments is None:
        return ()
    if not isinstance(attachments, Mapping):
        raise CollectionError("X Post contains invalid attachments data.")
    raw_keys = attachments.get("media_keys", [])
    if raw_keys is None:
        return ()
    if not isinstance(raw_keys, list) or not all(
        isinstance(media_key, str) for media_key in raw_keys
    ):
        raise CollectionError("X Post contains invalid media_keys data.")
    return tuple(raw_keys)


def map_x_post(
    post: Mapping[str, Any],
    *,
    users_by_id: Mapping[str, Mapping[str, Any]],
    expanded_posts_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    media_by_key: Mapping[str, Mapping[str, Any]] | None = None,
    source: Source,
    run_id: UUID,
    collected_at: datetime,
) -> dict[str, Any] | None:
    """Map one X Post to the existing schema, excluding simple reposts."""
    post_id = post.get("id")
    text, full_text_source = _full_text(post)
    created_at_raw = post.get("created_at")
    if not isinstance(post_id, str):
        raise CollectionError("X Post is missing a required id field.")
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

    raw_json = dict(post)
    collector_metadata: dict[str, object] = {
        "full_text_source": full_text_source,
    }
    expanded_context: dict[str, object] = {}

    expanded_posts = expanded_posts_by_id or {}
    referenced_post = (
        expanded_posts.get(referenced_post_id) if referenced_post_id else None
    )
    if referenced_post is not None:
        if not isinstance(referenced_post, Mapping):
            raise CollectionError("X Post contains invalid expanded Post data.")
        _full_text(referenced_post)
        expanded_context["referenced_post"] = dict(referenced_post)
        referenced_author_id = referenced_post.get("author_id")
        if referenced_author_id is not None and not isinstance(
            referenced_author_id, str
        ):
            raise CollectionError("Expanded X Post contains invalid author_id data.")
        referenced_author = (
            users_by_id.get(referenced_author_id) if referenced_author_id else None
        )
        if isinstance(referenced_author, Mapping):
            referenced_username = referenced_author.get("username")
            author_context: dict[str, str] = {"id": referenced_author_id}
            if isinstance(referenced_username, str):
                author_context["username"] = referenced_username
            expanded_context["referenced_post_author"] = author_context

    media_keys = _media_keys(post)
    media_lookup = media_by_key or {}
    expanded_media = [
        dict(media_lookup[media_key])
        for media_key in media_keys
        if media_key in media_lookup
        and isinstance(media_lookup[media_key], Mapping)
    ]
    if media_keys:
        expanded_context["media"] = expanded_media
        missing_media_count = len(media_keys) - len(expanded_media)
        if missing_media_count:
            collector_metadata["media_expansion_incomplete"] = True
            collector_metadata["missing_media_count"] = missing_media_count

    if expanded_context:
        raw_json["_expanded"] = expanded_context
    raw_json["_collector"] = collector_metadata

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
        "raw_json": raw_json,
        "first_seen_run_id": run_id,
        "last_seen_run_id": run_id,
        "first_collected_at": collected_at,
        "last_collected_at": collected_at,
        "processing_status": "unprocessed",
        "availability_status": "available",
        "last_verified_at": collected_at,
    }


@dataclass(frozen=True)
class _PageResult:
    page: Any
    attempts: int


class _PageRequestFailed(RuntimeError):
    def __init__(self, error: XApiRequestError, attempts: int) -> None:
        self.error = error
        self.attempts = attempts
        super().__init__(str(error))


def _retryable(error: XApiRequestError) -> bool:
    return error.status in {429, 500, 502, 503, 504} or (
        error.status is None and error.category == "connection_error"
    )


def _header_wait_seconds(
    error: XApiRequestError,
    *,
    now_timestamp: Callable[[], float],
) -> float | None:
    retry_after = error.rate_limits.get("retry-after")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return max(0.0, parsed.timestamp() - now_timestamp())
            except (TypeError, ValueError, OverflowError):
                pass

    reset = error.rate_limits.get("x-rate-limit-reset")
    if reset:
        try:
            return max(0.0, float(reset) - now_timestamp())
        except ValueError:
            pass
    return None


def _request_page_with_retry(
    *,
    client: XApiClient,
    endpoint: str,
    params: Mapping[str, object],
    max_attempts: int,
    max_retry_wait_seconds: float,
    sleep: Callable[[float], None],
    now_timestamp: Callable[[], float],
) -> _PageResult:
    attempts = 0
    while True:
        attempts += 1
        try:
            return _PageResult(
                page=client.get_content_page(endpoint, params),
                attempts=attempts,
            )
        except XApiRequestError as error:
            if attempts >= max_attempts or not _retryable(error):
                raise _PageRequestFailed(error, attempts) from error
            wait_seconds = _header_wait_seconds(error, now_timestamp=now_timestamp)
            if wait_seconds is None:
                wait_seconds = float(2 ** (attempts - 1))
            if wait_seconds > max_retry_wait_seconds:
                raise _PageRequestFailed(error, attempts) from error
            sleep(wait_seconds)


def _missed_window_warnings(
    *,
    source: Source,
    previous_successful_at: datetime | None,
    collected_at: datetime,
) -> set[str]:
    if source != "home" or previous_successful_at is None:
        return set()
    successful_at = previous_successful_at
    if successful_at.tzinfo is None:
        successful_at = successful_at.replace(tzinfo=timezone.utc)
    elapsed_days = (collected_at - successful_at).total_seconds() / 86_400
    warnings: set[str] = set()
    if elapsed_days >= 6:
        warnings.add("home_history_window_at_risk")
    if elapsed_days >= 7:
        warnings.add("home_history_window_may_be_lost")
    return warnings


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
    refresh_existing: bool = False,
    max_primary_posts_total: int | None = None,
    max_estimated_cost_usd: Decimal = Decimal("1.00"),
    estimated_cost_before_usd: Decimal = Decimal("0"),
    unit_cost_usd: Decimal = DEFAULT_POST_READ_COST_USD,
    max_attempts: int = 3,
    max_retry_wait_seconds: float = 60,
    previous_successful_at: datetime | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now_timestamp: Callable[[], float] = time.time,
) -> FetchedSource:
    """Fetch one source through completion or an explicit safety guard."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    minimum = source_minimum_page_size(source)
    if not minimum <= max_results <= 100:
        raise ValueError(f"max_results for {source} must be between {minimum} and 100")
    if max_primary_posts_total is not None and max_primary_posts_total < minimum:
        raise ValueError(
            f"remaining primary Post limit for {source} must be at least {minimum}"
        )
    if max_estimated_cost_usd <= 0 or unit_cost_usd <= 0:
        raise ValueError("cost limits and unit cost must be positive")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if max_retry_wait_seconds < 0:
        raise ValueError("max_retry_wait_seconds must not be negative")

    endpoint = endpoint_for(source, user_id)
    base_params: dict[str, object] = {
        "max_results": max_results,
        "tweet.fields": TWEET_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
        "since_id": None if refresh_existing else checkpoint_before,
        "until_id": checkpoint_before if refresh_existing else None,
    }
    if source == "home":
        base_params["exclude"] = "retweets"

    pages = []
    users_by_id: dict[str, Mapping[str, Any]] = {}
    expanded_posts_by_id: dict[str, Mapping[str, Any]] = {}
    media_by_key: dict[str, Mapping[str, Any]] = {}
    resource_ids: set[str] = set()
    expanded_posts_received = 0
    primary_posts_received = 0
    requests_count = 0
    warnings = _missed_window_warnings(
        source=source,
        previous_successful_at=previous_successful_at,
        collected_at=collected_at,
    )
    terminal_error: XApiRequestError | None = None
    pagination_token: str | None = None
    while len(pages) < max_pages:
        params = dict(base_params)
        remaining = (
            None
            if max_primary_posts_total is None
            else max_primary_posts_total - primary_posts_received
        )
        if remaining is not None:
            if remaining < minimum:
                warnings.add("primary_post_limit_reached")
                break
            params["max_results"] = min(max_results, remaining)
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
            requests_count += failure.attempts
            if not pages:
                raise failure.error
            terminal_error = failure.error
            warnings.add("request_failed_after_partial_fetch")
            break
        page = result.page
        requests_count += result.attempts
        pages.append(page)
        users_by_id.update(page.users_by_id)
        expanded_posts_by_id.update(page.expanded_posts_by_id)
        media_by_key.update(page.media_by_key)
        primary_posts_received += len(page.posts)
        expanded_posts_received += len(page.expanded_posts_by_id)
        resource_ids.update(str(post["id"]) for post in page.posts)
        resource_ids.update(page.expanded_posts_by_id)
        pagination_token = page.next_token
        if page.partial_error_count:
            warnings.add("partial_errors_present")
            break
        if not page.meta_present:
            warnings.add("pagination_metadata_missing")
            break
        if not pagination_token:
            break
        current_cost = unit_cost_usd * len(resource_ids)
        if (
            max_primary_posts_total is not None
            and primary_posts_received >= max_primary_posts_total
        ):
            warnings.add("primary_post_limit_reached")
            break
        if estimated_cost_before_usd + current_cost >= max_estimated_cost_usd:
            warnings.add("cost_guard_reached")
            break

    if not pages:
        raise CollectionError("X source collection produced no response page.")

    if pagination_token and len(pages) >= max_pages:
        if checkpoint_before is None and not refresh_existing:
            warnings.add("initial_history_not_backfilled")
        else:
            warnings.add("page_limit_reached")
        if refresh_existing:
            warnings.add("refresh_window_bounded")

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
        try:
            record = map_x_post(
                post,
                users_by_id=users_by_id,
                expanded_posts_by_id=expanded_posts_by_id,
                media_by_key=media_by_key,
                source=source,
                run_id=run_id,
                collected_at=collected_at,
            )
        except CollectionError:
            warnings.add("invalid_post_shape_present")
            continue
        if record is None:
            reposts_excluded += 1
        else:
            records.append(record)

    first_page = pages[0]
    last_page = pages[-1]
    if duplicate_ids:
        warnings.add("duplicate_post_ids_detected")
    if source == "mentions" and BLOCKING_WARNINGS.intersection(warnings):
        warnings.add("mentions_history_may_be_truncated")
    blocking = bool(BLOCKING_WARNINGS.intersection(warnings))
    completion_state = "incomplete" if blocking else "complete"
    checkpoint_can_advance = not refresh_existing and not blocking
    checkpoint_candidate = (
        checkpoint_before
        if refresh_existing
        else first_page.newest_id or checkpoint_before
    )
    return FetchedSource(
        source=source,
        source_key=source_key_for(source),
        endpoint=endpoint,
        requests_count=requests_count,
        fetched_posts=len(raw_posts),
        expanded_posts_received=expanded_posts_received,
        distinct_post_resources_received=len(resource_ids),
        reposts_excluded=reposts_excluded,
        records=tuple(records),
        newest_post_id=first_page.newest_id,
        oldest_post_id=last_page.oldest_id,
        checkpoint_before=checkpoint_before,
        checkpoint_candidate=checkpoint_candidate,
        checkpoint_can_advance=checkpoint_can_advance,
        refresh_existing=refresh_existing,
        completion_state=completion_state,
        unit_cost_usd=unit_cost_usd,
        estimated_cost_usd=unit_cost_usd * len(resource_ids),
        warnings=tuple(sorted(warnings)),
        terminal_error_category=(terminal_error.category if terminal_error else None),
        terminal_http_status=(terminal_error.status if terminal_error else None),
        terminal_rate_limits=(terminal_error.rate_limits if terminal_error else None),
    )


def save_source_collection(
    *,
    repository: CollectorRepository,
    fetched: FetchedSource,
    previous_state: Mapping[str, Any] | None,
    run_id: UUID,
    collected_at: datetime,
    max_pages: int,
    max_results: int,
) -> SourceCollectionSummary:
    """Persist Posts and a safe source checkpoint in caller transaction."""
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
    if not fetched.refresh_existing:
        previous_metadata = (
            previous_state.get("checkpoint_metadata") if previous_state else None
        )
        baseline_acceptance: dict[str, Any] | None = None
        if isinstance(previous_metadata, Mapping):
            nested_acceptance = previous_metadata.get("baseline_acceptance")
            if isinstance(nested_acceptance, Mapping):
                baseline_acceptance = dict(nested_acceptance)
            elif previous_metadata.get("manual_baseline_acceptance") is True:
                baseline_acceptance = dict(previous_metadata)
        checkpoint_metadata: dict[str, Any] = {
            "source": fetched.source,
            "requests_count": fetched.requests_count,
            "fetched_posts": fetched.fetched_posts,
            "primary_posts_received": fetched.fetched_posts,
            "expanded_posts_received": fetched.expanded_posts_received,
            "distinct_post_resources_received": (
                fetched.distinct_post_resources_received
            ),
            "unit_cost_usd": format(fetched.unit_cost_usd, "f"),
            "estimated_x_cost_usd": format(fetched.estimated_cost_usd, "f"),
            "completion_state": fetched.completion_state,
            "newest_post_id": fetched.newest_post_id,
            "oldest_post_id": fetched.oldest_post_id,
            "collection_run_id": str(run_id),
            "max_pages": max_pages,
            "max_results": max_results,
            "warnings": list(fetched.warnings),
        }
        if baseline_acceptance is not None:
            checkpoint_metadata["baseline_acceptance"] = baseline_acceptance
            for key in (
                "manual_baseline_acceptance",
                "source_run_id",
                "previous_checkpoint",
                "accepted_checkpoint",
                "incomplete_reason",
                "incomplete_reasons",
                "older_window_may_have_been_skipped",
                "accepted_at",
            ):
                if key in baseline_acceptance:
                    checkpoint_metadata[key] = baseline_acceptance[key]
        repository.update_sync_state(
            source_key=fetched.source_key,
            checkpoint_value=checkpoint_after,
            checkpoint_metadata=checkpoint_metadata,
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
    existing_count = len(existing_ids)
    saved_count = len(post_ids)
    return SourceCollectionSummary(
        source=fetched.source,
        source_key=fetched.source_key,
        requests_count=fetched.requests_count,
        fetched_posts=fetched.fetched_posts,
        expanded_posts_received=fetched.expanded_posts_received,
        distinct_post_resources_received=fetched.distinct_post_resources_received,
        new_posts=saved_count - existing_count,
        existing_posts=existing_count,
        saved_posts=saved_count,
        reposts_excluded=fetched.reposts_excluded,
        newest_post_id=fetched.newest_post_id,
        oldest_post_id=fetched.oldest_post_id,
        checkpoint_before=fetched.checkpoint_before,
        checkpoint_after=checkpoint_after,
        refresh_existing=fetched.refresh_existing,
        completion_state=fetched.completion_state,
        unit_cost_usd=fetched.unit_cost_usd,
        estimated_cost_usd=fetched.estimated_cost_usd,
        warnings=fetched.warnings,
    )


def record_source_usage(
    *,
    repository: CollectorRepository,
    fetched: FetchedSource,
    run_id: UUID,
    usage_event_id: UUID,
    collected_at: datetime,
) -> None:
    """Record fetched X usage independently from subsequent Post persistence."""
    repository.record_usage_event(
        {
            "usage_event_id": usage_event_id,
            "run_id": run_id,
            "provider": "x",
            "operation": f"collect_{fetched.source}",
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
                "primary_posts_received": fetched.fetched_posts,
                "expanded_posts_received": fetched.expanded_posts_received,
                "distinct_post_resources_received": (
                    fetched.distinct_post_resources_received
                ),
                "pricing_basis": "estimated_distinct_post_resources",
                "unit_cost_usd": format(fetched.unit_cost_usd, "f"),
                "completion_state": fetched.completion_state,
                "newest_post_id": fetched.newest_post_id,
                "oldest_post_id": fetched.oldest_post_id,
                "warnings": list(fetched.warnings),
            },
        }
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

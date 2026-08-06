"""Read-only pagination and checkpoint experiments for Task 003."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from x_signal_finder.x_api.client import XApiClient


Source = Literal["home", "mentions"]

TWEET_FIELDS = (
    "attachments,author_id,conversation_id,created_at,entities,"
    "in_reply_to_user_id,lang,possibly_sensitive,public_metrics,"
    "referenced_tweets,note_tweet,withheld"
)
EXPANSIONS = (
    "attachments.media_keys,author_id,in_reply_to_user_id,"
    "referenced_tweets.id,referenced_tweets.id.author_id"
)
USER_FIELDS = "created_at,id,name,protected,username,verified"
MEDIA_FIELDS = "alt_text,media_key,preview_image_url,type,url"


@dataclass(frozen=True)
class ProbeSummary:
    """Safe diagnostic summary without post bodies or raw responses."""

    source: Source
    endpoint: str
    http_results: tuple[int, ...]
    pages_requested: int
    post_count: int
    next_page_token_present: bool
    newest_post_id: str | None
    oldest_post_id: str | None
    metadata_keys: tuple[str, ...]
    post_field_keys: tuple[str, ...]
    rate_limits: dict[str, str]
    elapsed_seconds: float
    duplicate_ids: tuple[str, ...]
    checkpoint_status: str
    repeated_first_page_matches: bool | None
    limitations: tuple[str, ...]

    def safe_diagnostic(self) -> dict[str, object]:
        return {
            "source": self.source,
            "endpoint": self.endpoint,
            "http_results": list(self.http_results),
            "pages_requested": self.pages_requested,
            "post_count": self.post_count,
            "next_page_token_present": self.next_page_token_present,
            "newest_post_id": self.newest_post_id,
            "oldest_post_id": self.oldest_post_id,
            "metadata_keys": list(self.metadata_keys),
            "post_field_keys": list(self.post_field_keys),
            "rate_limits": self.rate_limits,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "duplicate_ids": list(self.duplicate_ids),
            "checkpoint_status": self.checkpoint_status,
            "repeated_first_page_matches": self.repeated_first_page_matches,
            "limitations": list(self.limitations),
        }


def endpoint_for(source: Source, user_id: str) -> str:
    if source == "home":
        return f"/users/{user_id}/timelines/reverse_chronological"
    return f"/users/{user_id}/mentions"


def classify_checkpoint(
    *,
    checkpoint_id: str | None,
    seen_ids: tuple[str, ...],
    meta_present: bool,
    next_token_present: bool,
    page_limit_reached: bool,
    request_failed: bool = False,
) -> str:
    """Classify an in-memory checkpoint experiment without changing sync state."""
    if checkpoint_id is None:
        return "not_checked"
    if request_failed:
        return "request_failed"
    if checkpoint_id in seen_ids:
        return "checkpoint_reached"
    if not meta_present:
        return "pagination_unavailable"
    if page_limit_reached and next_token_present:
        return "checkpoint_not_reached"
    if not next_token_present:
        return "api_window_exhausted"
    return "checkpoint_not_reached"


def run_probe(
    *,
    client: XApiClient,
    source: Source,
    user_id: str,
    max_pages: int = 2,
    max_results: int = 100,
    checkpoint_id: str | None = None,
    repeat_first_page: bool = False,
) -> ProbeSummary:
    """Probe up to ``max_pages`` without persisting content or checkpoints."""
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
    }
    pages = []
    token: str | None = None
    while len(pages) < max_pages:
        params = dict(base_params)
        if token:
            params["pagination_token"] = token
        page = client.get_page(endpoint, params)
        pages.append(page)
        if checkpoint_id and checkpoint_id in page.post_ids:
            break
        token = page.next_token
        if not token:
            break

    repeated_matches: bool | None = None
    repeated_page = None
    if repeat_first_page:
        repeated_page = client.get_page(endpoint, base_params)
        repeated_matches = repeated_page.post_ids == pages[0].post_ids

    ordered_ids = tuple(post_id for page in pages for post_id in page.post_ids)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for post_id in ordered_ids:
        if post_id in seen:
            duplicates.add(post_id)
        seen.add(post_id)

    last_page = pages[-1]
    page_limit_reached = len(pages) == max_pages
    limitations: set[str] = set()
    if page_limit_reached and last_page.next_token:
        limitations.add("probe_page_limit_reached")
    if any(page.partial_error_count for page in pages):
        limitations.add("partial_errors_present")
    if duplicates:
        limitations.add("duplicate_post_ids_detected")
    if repeat_first_page and repeated_matches is False:
        limitations.add("first_page_changed_between_requests")

    return ProbeSummary(
        source=source,
        endpoint=endpoint,
        http_results=tuple(page.status for page in pages)
        + ((repeated_page.status,) if repeated_page else ()),
        pages_requested=len(pages) + (1 if repeat_first_page else 0),
        post_count=len(ordered_ids),
        next_page_token_present=bool(last_page.next_token),
        newest_post_id=pages[0].newest_id,
        oldest_post_id=last_page.oldest_id,
        metadata_keys=tuple(sorted({key for page in pages for key in page.metadata_keys})),
        post_field_keys=tuple(
            sorted({key for page in pages for key in page.post_field_keys})
        ),
        rate_limits=dict(last_page.rate_limits),
        elapsed_seconds=sum(page.elapsed_seconds for page in pages)
        + (repeated_page.elapsed_seconds if repeated_page else 0.0),
        duplicate_ids=tuple(sorted(duplicates)),
        checkpoint_status=classify_checkpoint(
            checkpoint_id=checkpoint_id,
            seen_ids=ordered_ids,
            meta_present=last_page.meta_present,
            next_token_present=bool(last_page.next_token),
            page_limit_reached=page_limit_reached,
        ),
        repeated_first_page_matches=repeated_matches,
        limitations=tuple(sorted(limitations)),
    )

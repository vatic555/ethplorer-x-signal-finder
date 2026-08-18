"""Isolated read-only X provider quality and cost spike for Task 004D."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
from math import ceil, log2
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import time
from typing import Any, Callable, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import dotenv_values

from x_signal_finder.config import load_database_config
from x_signal_finder.db.connection import connect_database
from x_signal_finder.x_api.client import XApiClient, XApiRequestError, parse_content_page
from x_signal_finder.x_api.config import load_x_api_config, persist_refresh_token
from x_signal_finder.x_api.oauth import refresh_access_token
from x_signal_finder.x_api.probe import TWEET_FIELDS, USER_FIELDS


ProviderName = Literal["official_x", "twitterapi_io", "socialdata"]
PostType = Literal["original", "reply", "quote", "repost"]

TWITTERAPI_IO_UNIT_COST_USD = Decimal("0.00015")
SOCIALDATA_UNIT_COST_USD = Decimal("0.0002")
OFFICIAL_X_POST_READ_COST_USD = Decimal("0.005")
OFFICIAL_X_USER_READ_COST_USD = Decimal("0.010")
OFFICIAL_X_MEDIA_READ_COST_USD = Decimal("0.005")
TRIAL_SPEND_LIMIT_USD = Decimal("0.10")
TWITTERAPI_IO_CREDITS_PER_USD = Decimal("100000")
TWITTERAPI_IO_DOCUMENTED_MAX_PAGE_RESULTS = 20
SOCIALDATA_EXPECTED_PAGE_RESULTS = 20
DIRECT_ID_EXPECTED_BATCH_SIZE = 20
DEFAULT_TWITTERAPI_IO_MINIMUM_SLICE_SECONDS = 60
SHADOW_EXPANSIONS = (
    "attachments.media_keys,author_id,in_reply_to_user_id,"
    "referenced_tweets.id,referenced_tweets.id.author_id,"
    "referenced_tweets.id.attachments.media_keys"
)
SHADOW_MEDIA_FIELDS = (
    "alt_text,duration_ms,height,media_key,preview_image_url,public_metrics,"
    "type,url,width"
)


class ShadowSpikeError(RuntimeError):
    """Content-safe Task 004D failure without response bodies or secrets."""


class ProviderRequestError(ShadowSpikeError):
    def __init__(self, provider: ProviderName, status: int | None, category: str):
        self.provider = provider
        self.status = status
        self.category = category
        rendered_status = str(status) if status is not None else "unavailable"
        super().__init__(
            f"{provider} request failed ({category}, HTTP {rendered_status})."
        )


@dataclass(frozen=True, repr=False)
class NormalizedReference:
    post_id: str
    author: str | None
    created_at: datetime | None
    text: str | None
    media_metadata: tuple[dict[str, Any], ...]

    def __repr__(self) -> str:
        return (
            "NormalizedReference(post_id="
            f"{self.post_id!r}, context_present={bool(self.text)}, "
            f"media_count={len(self.media_metadata)})"
        )


@dataclass(frozen=True, repr=False)
class NormalizedPost:
    post_id: str
    author: str
    author_id: str | None
    created_at: datetime
    text: str
    post_type: PostType
    conversation_id: str | None
    referenced_post_id: str | None
    referenced_context: NormalizedReference | None
    media_metadata: tuple[dict[str, Any], ...]
    provider: ProviderName

    def __repr__(self) -> str:
        return (
            "NormalizedPost(provider="
            f"{self.provider!r}, post_id={self.post_id!r}, "
            f"post_type={self.post_type!r}, text_length={len(self.text)}, "
            f"media_count={len(self.media_metadata)})"
        )


@dataclass(frozen=True)
class SearchTask:
    authors: tuple[str, ...]
    start: datetime
    end: datetime
    depth: int = 0
    cursor: str | None = None
    max_id: str | None = None
    since_id: str | None = None


@dataclass(frozen=True, repr=False)
class ProviderPage:
    posts: tuple[NormalizedPost, ...]
    raw_payload: Mapping[str, Any]
    has_more: bool
    next_cursor: str | None = None
    continuation_max_id: str | None = None
    possible_incomplete: bool = False
    billable_resources_returned: int | None = None

    def __repr__(self) -> str:
        return (
            "ProviderPage(post_count="
            f"{len(self.posts)}, has_more={self.has_more}, "
            f"next_cursor_present={bool(self.next_cursor)})"
        )


@dataclass(frozen=True, repr=False)
class ProviderRun:
    provider: ProviderName
    status: str
    posts: tuple[NormalizedPost, ...]
    requests: int
    pagination_gaps: int
    estimated_spend_usd: Decimal
    actual_spend_usd: Decimal | None
    warnings: tuple[str, ...]
    duplicates_removed: int = 0

    def __repr__(self) -> str:
        return (
            "ProviderRun(provider="
            f"{self.provider!r}, status={self.status!r}, "
            f"post_count={len(self.posts)}, requests={self.requests})"
        )


@dataclass(frozen=True, repr=False)
class ProviderCostPlan:
    provider: ProviderName
    mode: Literal["discovery", "direct_id"]
    benchmark_size: int
    author_count: int
    window_start: datetime | None
    window_end: datetime | None
    strategy: str
    estimated_requests: int
    expected_billable_resources: int
    expected_cost_usd: Decimal
    strategy_worst_case_requests: int
    approved_request_cap: int
    documented_max_page_results: int | None
    expected_page_results: int
    page_size_bound: Literal["documented_maximum", "unknown_unbounded"]
    technical_hard_dollar_cap: bool
    conservative_max_resources: int
    conservative_max_cost_usd: Decimal
    approved_budget_usd: Decimal
    unit_cost_usd: Decimal
    plan_fits_approved_limits: bool
    approval_scope: Mapping[str, object]
    notes: tuple[str, ...]

    def _digest_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "benchmark_size": self.benchmark_size,
            "author_count": self.author_count,
            "window_start": (
                self.window_start.isoformat() if self.window_start else None
            ),
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "strategy": self.strategy,
            "estimated_requests": self.estimated_requests,
            "expected_billable_resources": self.expected_billable_resources,
            "expected_cost_usd": format(self.expected_cost_usd, "f"),
            "strategy_worst_case_requests": self.strategy_worst_case_requests,
            "approved_request_cap": self.approved_request_cap,
            "documented_max_page_results": self.documented_max_page_results,
            "expected_page_results": self.expected_page_results,
            "page_size_bound": self.page_size_bound,
            "technical_hard_dollar_cap": self.technical_hard_dollar_cap,
            "conservative_max_resources": self.conservative_max_resources,
            "conservative_max_cost_usd": format(
                self.conservative_max_cost_usd, "f"
            ),
            "approved_budget_usd": format(self.approved_budget_usd, "f"),
            "unit_cost_usd": format(self.unit_cost_usd, "f"),
            "plan_fits_approved_limits": self.plan_fits_approved_limits,
            "approval_scope": self.approval_scope,
            "notes": list(self.notes),
        }

    @property
    def plan_sha256(self) -> str:
        encoded = json.dumps(
            self._digest_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def safe_summary(self) -> dict[str, object]:
        hard_guard = (
            "documented maximum page reserve plus approved request cap"
            if self.technical_hard_dollar_cap
            else (
                "approved request cap plus conservative expected-page reserve; "
                "page-size worst case is unknown"
            )
        )
        return {
            **self._digest_payload(),
            "plan_sha256": self.plan_sha256,
            "external_requests_during_plan": 0,
            "approval_required": True,
            "execution_authorized": False,
            "hard_guard": hard_guard,
        }

    def __repr__(self) -> str:
        return f"ProviderCostPlan({self.safe_summary()!r})"


@dataclass(frozen=True)
class QualityAcceptanceThresholds:
    minimum_raw_recall_pct: float = 90.0
    target_raw_recall_pct: float = 95.0
    maximum_non_systematic_raw_loss_pct: float = 10.0
    required_content_complete_pct: float = 100.0
    systematic_group_minimum_posts: int = 3
    systematic_group_minimum_missing: int = 2
    systematic_recall_gap_pct: float = 10.0

    def safe_summary(self) -> dict[str, object]:
        return {
            "minimum_raw_recall_pct": self.minimum_raw_recall_pct,
            "target_raw_recall_pct": self.target_raw_recall_pct,
            "maximum_non_systematic_raw_loss_pct": (
                self.maximum_non_systematic_raw_loss_pct
            ),
            "required_content_complete_pct": self.required_content_complete_pct,
            "systematic_group_minimum_posts": self.systematic_group_minimum_posts,
            "systematic_group_minimum_missing": self.systematic_group_minimum_missing,
            "systematic_recall_gap_pct": self.systematic_recall_gap_pct,
        }


class SearchProvider(Protocol):
    name: ProviderName
    unit_cost_usd: Decimal
    minimum_interval_seconds: float

    def search(self, task: SearchTask) -> ProviderPage: ...

    def balance_usd(self) -> Decimal | None: ...


def _required_string(value: object, field: str) -> str:
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or not value.strip():
        raise ShadowSpikeError(f"Provider response is missing required {field}.")
    return value.strip()


def _optional_string(value: object) -> str | None:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_datetime(value: object, field: str = "created_at") -> datetime:
    text = _required_string(value, field)
    parsed: datetime
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError) as error:
            raise ShadowSpikeError(
                f"Provider response contains invalid {field}."
            ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_window_end(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc) - timedelta(seconds=30)
    return _parse_datetime(value, "window_end")


def _full_text(post: Mapping[str, Any], *keys: str) -> str:
    note = post.get("note_tweet")
    if isinstance(note, Mapping):
        note_text = note.get("text")
        if isinstance(note_text, str) and note_text:
            return note_text
    for key in keys:
        value = post.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _safe_media_object(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "alt_text",
        "duration_ms",
        "height",
        "media_key",
        "media_url_https",
        "preview_image_url",
        "type",
        "url",
        "width",
    )
    result = {key: value[key] for key in allowed if key in value}
    video_info = value.get("video_info")
    if isinstance(video_info, Mapping):
        result["video_info"] = dict(video_info)
    variants = value.get("variants")
    if isinstance(variants, list):
        result["variants"] = [dict(item) for item in variants if isinstance(item, Mapping)]
    return result


def _generic_media(post: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    candidates: list[object] = []
    for key in ("media", "photos"):
        value = post.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    for container_key in ("extended_entities", "extendedEntities", "entities"):
        container = post.get(container_key)
        if isinstance(container, Mapping) and isinstance(container.get("media"), list):
            candidates.extend(container["media"])
    normalized: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        media = _safe_media_object(item)
        fingerprint = json.dumps(media, sort_keys=True, default=str)
        if media and fingerprint not in fingerprints:
            normalized.append(media)
            fingerprints.add(fingerprint)
    return tuple(normalized)


def _official_media(
    post: Mapping[str, Any],
    media_by_key: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    attachments = post.get("attachments")
    if not isinstance(attachments, Mapping):
        return ()
    keys = attachments.get("media_keys", [])
    if not isinstance(keys, list):
        return ()
    return tuple(
        _safe_media_object(media_by_key[key])
        for key in keys
        if isinstance(key, str) and key in media_by_key
    )


def _official_relationship(post: Mapping[str, Any]) -> tuple[PostType, str | None]:
    raw = post.get("referenced_tweets", [])
    references = raw if isinstance(raw, list) else []
    for relationship, post_type in (
        ("retweeted", "repost"),
        ("quoted", "quote"),
        ("replied_to", "reply"),
    ):
        for reference in references:
            if isinstance(reference, Mapping) and reference.get("type") == relationship:
                reference_id = _optional_string(reference.get("id"))
                if reference_id:
                    return post_type, reference_id
    if post.get("in_reply_to_user_id") is not None:
        return "reply", None
    return "original", None


def normalize_official_post(
    post: Mapping[str, Any],
    *,
    users_by_id: Mapping[str, Mapping[str, Any]],
    expanded_posts_by_id: Mapping[str, Mapping[str, Any]],
    media_by_key: Mapping[str, Mapping[str, Any]],
) -> NormalizedPost:
    post_id = _required_string(post.get("id"), "post_id")
    author_id = _optional_string(post.get("author_id"))
    author_data = users_by_id.get(author_id or "", {})
    author = _required_string(author_data.get("username"), "author")
    post_type, referenced_id = _official_relationship(post)
    referenced_context = None
    referenced = expanded_posts_by_id.get(referenced_id or "")
    if referenced_id and isinstance(referenced, Mapping):
        referenced_author_id = _optional_string(referenced.get("author_id"))
        referenced_author_data = users_by_id.get(referenced_author_id or "", {})
        referenced_context = NormalizedReference(
            post_id=referenced_id,
            author=_optional_string(referenced_author_data.get("username")),
            created_at=(
                _parse_datetime(referenced.get("created_at"))
                if referenced.get("created_at")
                else None
            ),
            text=_full_text(referenced, "text") or None,
            media_metadata=_official_media(referenced, media_by_key),
        )
    return NormalizedPost(
        post_id=post_id,
        author=author,
        author_id=author_id,
        created_at=_parse_datetime(post.get("created_at")),
        text=_full_text(post, "text"),
        post_type=post_type,
        conversation_id=_optional_string(post.get("conversation_id")),
        referenced_post_id=referenced_id,
        referenced_context=referenced_context,
        media_metadata=_official_media(post, media_by_key),
        provider="official_x",
    )


def _nested_reference(
    value: object,
    *,
    provider: ProviderName,
) -> NormalizedReference | None:
    if not isinstance(value, Mapping):
        return None
    post_id = _optional_string(value.get("id") or value.get("id_str"))
    if not post_id:
        return None
    author_data = value.get("author") or value.get("user")
    author = None
    if isinstance(author_data, Mapping):
        author = _optional_string(
            author_data.get("userName") or author_data.get("screen_name")
        )
    created_raw = value.get("createdAt") or value.get("tweet_created_at")
    return NormalizedReference(
        post_id=post_id,
        author=author,
        created_at=_parse_datetime(created_raw) if created_raw else None,
        text=_full_text(value, "full_text", "text") or None,
        media_metadata=_generic_media(value),
    )


def normalize_twitterapi_io_post(post: Mapping[str, Any]) -> NormalizedPost:
    author_data = post.get("author")
    if not isinstance(author_data, Mapping):
        raise ShadowSpikeError("twitterapi_io response is missing author data.")
    retweeted = post.get("retweeted_tweet") or post.get("retweetedTweet")
    quoted = post.get("quoted_tweet") or post.get("quotedTweet")
    reply_id = _optional_string(post.get("inReplyToId") or post.get("in_reply_to_id"))
    if isinstance(retweeted, Mapping):
        post_type: PostType = "repost"
        context = _nested_reference(retweeted, provider="twitterapi_io")
    elif isinstance(quoted, Mapping):
        post_type = "quote"
        context = _nested_reference(quoted, provider="twitterapi_io")
    elif post.get("isReply") is True or reply_id:
        post_type = "reply"
        context = None
    else:
        post_type = "original"
        context = None
    referenced_id = context.post_id if context else reply_id
    return NormalizedPost(
        post_id=_required_string(post.get("id"), "post_id"),
        author=_required_string(author_data.get("userName"), "author"),
        author_id=_optional_string(author_data.get("id")),
        created_at=_parse_datetime(post.get("createdAt")),
        text=_full_text(post, "text"),
        post_type=post_type,
        conversation_id=_optional_string(post.get("conversationId")),
        referenced_post_id=referenced_id,
        referenced_context=context,
        media_metadata=_generic_media(post),
        provider="twitterapi_io",
    )


def normalize_socialdata_post(post: Mapping[str, Any]) -> NormalizedPost:
    author_data = post.get("user")
    if not isinstance(author_data, Mapping):
        raise ShadowSpikeError("socialdata response is missing author data.")
    retweeted = post.get("retweeted_status")
    quoted = post.get("quoted_status")
    reply_id = _optional_string(post.get("in_reply_to_status_id_str"))
    if isinstance(retweeted, Mapping):
        post_type: PostType = "repost"
        context = _nested_reference(retweeted, provider="socialdata")
    elif isinstance(quoted, Mapping) or post.get("is_quote_status") is True:
        post_type = "quote"
        context = _nested_reference(quoted, provider="socialdata")
    elif reply_id:
        post_type = "reply"
        context = None
    else:
        post_type = "original"
        context = None
    referenced_id = (
        context.post_id
        if context
        else _optional_string(post.get("quoted_status_id_str")) or reply_id
    )
    return NormalizedPost(
        post_id=_required_string(post.get("id_str") or post.get("id"), "post_id"),
        author=_required_string(author_data.get("screen_name"), "author"),
        author_id=_optional_string(author_data.get("id_str") or author_data.get("id")),
        created_at=_parse_datetime(post.get("tweet_created_at") or post.get("created_at")),
        text=_full_text(post, "full_text", "text"),
        post_type=post_type,
        conversation_id=_optional_string(
            post.get("conversation_id_str") or post.get("conversation_id")
        ),
        referenced_post_id=referenced_id,
        referenced_context=context,
        media_metadata=_generic_media(post),
        provider="socialdata",
    )


def _request_json(
    *,
    provider: ProviderName,
    url: str,
    headers: Mapping[str, str],
    params: Mapping[str, object] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    query = urlencode(
        [(key, str(value)) for key, value in (params or {}).items() if value is not None]
    )
    request_url = f"{url}?{query}" if query else url
    request = Request(request_url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            body = response.read()
    except HTTPError as error:
        status = error.code
        body = error.read()
    except (URLError, TimeoutError, OSError) as error:
        raise ProviderRequestError(provider, None, "connection_error") from error
    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderRequestError(provider, status, "unexpected_response_shape") from error
    if not isinstance(payload, dict):
        raise ProviderRequestError(provider, status, "unexpected_response_shape")
    if not 200 <= status < 300:
        if status == 401:
            category = "invalid_credentials"
        elif status == 402:
            category = "credit_exhausted"
        elif status == 403:
            category = "access_denied"
        elif status == 429:
            category = "rate_limited"
        else:
            category = "provider_error"
        raise ProviderRequestError(provider, status, category)
    return status, payload


def _query_for(task: SearchTask, *, include_id_bounds: bool = False) -> str:
    authors = " OR ".join(f"from:{author}" for author in task.authors)
    author_expression = authors if len(task.authors) == 1 else f"({authors})"
    operators = [
        author_expression,
        f"since_time:{int(task.start.timestamp())}",
        f"until_time:{int(task.end.timestamp())}",
    ]
    if include_id_bounds and task.since_id:
        operators.append(f"since_id:{task.since_id}")
    if include_id_bounds and task.max_id:
        operators.append(f"max_id:{task.max_id}")
    return " ".join(operators)


class TwitterApiIoProvider:
    name: ProviderName = "twitterapi_io"
    unit_cost_usd = TWITTERAPI_IO_UNIT_COST_USD
    # Trial keys currently enforce a stricter cadence than the public high-QPS claim.
    minimum_interval_seconds = 5.1
    rate_limit_retry_wait_seconds = 20.0
    max_rate_limit_retries = 3

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ShadowSpikeError("TWITTERAPI_IO_API_KEY is required.")
        self._headers = {"X-API-Key": api_key, "Accept": "application/json"}

    def search(self, task: SearchTask) -> ProviderPage:
        _, payload = _request_json(
            provider=self.name,
            url="https://api.twitterapi.io/twitter/tweet/advanced_search",
            headers=self._headers,
            params={"query": _query_for(task), "queryType": "Latest"},
        )
        raw_posts = payload.get("tweets", [])
        if not isinstance(raw_posts, list):
            raise ProviderRequestError(self.name, 200, "unexpected_response_shape")
        posts = tuple(
            normalize_twitterapi_io_post(item)
            for item in raw_posts
            if isinstance(item, Mapping)
        )
        return ProviderPage(
            posts=posts,
            raw_payload=payload,
            has_more=payload.get("has_next_page") is True,
            possible_incomplete=(
                payload.get("has_next_page") is True
                or len(raw_posts) >= TWITTERAPI_IO_DOCUMENTED_MAX_PAGE_RESULTS
            ),
            billable_resources_returned=len(raw_posts),
        )

    def balance_usd(self) -> Decimal | None:
        _, payload = _request_json(
            provider=self.name,
            url="https://api.twitterapi.io/oapi/my/info",
            headers=self._headers,
        )
        recharge_credits = payload.get("recharge_credits", 0)
        bonus_credits = payload.get("total_bonus_credits", 0)
        if not isinstance(recharge_credits, (int, float)) or not isinstance(
            bonus_credits, (int, float)
        ):
            return None
        credits = Decimal(str(recharge_credits)) + Decimal(str(bonus_credits))
        return credits / TWITTERAPI_IO_CREDITS_PER_USD


class SocialDataProvider:
    name: ProviderName = "socialdata"
    unit_cost_usd = SOCIALDATA_UNIT_COST_USD
    minimum_interval_seconds = 0.0
    rate_limit_retry_wait_seconds = 0.0
    max_rate_limit_retries = 0

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ShadowSpikeError("SOCIALDATA_API_KEY is required.")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def search(self, task: SearchTask) -> ProviderPage:
        params: dict[str, object] = {
            "query": _query_for(task, include_id_bounds=True),
            "type": "Latest",
            "cursor": task.cursor,
        }
        _, payload = _request_json(
            provider=self.name,
            url="https://api.socialdata.tools/twitter/search",
            headers=self._headers,
            params=params,
        )
        raw_posts = payload.get("tweets", [])
        if not isinstance(raw_posts, list):
            raise ProviderRequestError(self.name, 200, "unexpected_response_shape")
        posts = tuple(
            normalize_socialdata_post(item)
            for item in raw_posts
            if isinstance(item, Mapping)
        )
        next_cursor = _optional_string(
            payload.get("next_cursor") or payload.get("next_cursor_str")
        )
        numeric_ids = [
            int(post.post_id) for post in posts if post.post_id.isdigit()
        ]
        continuation_max_id = (
            str(max(0, min(numeric_ids) - 1)) if numeric_ids else None
        )
        explicit_has_more = payload.get("has_more") is True
        possible_incomplete = (
            bool(next_cursor)
            or explicit_has_more
            or len(raw_posts) >= SOCIALDATA_EXPECTED_PAGE_RESULTS
        )
        return ProviderPage(
            posts=posts,
            raw_payload=payload,
            has_more=bool(next_cursor) or explicit_has_more,
            next_cursor=next_cursor,
            continuation_max_id=continuation_max_id,
            possible_incomplete=possible_incomplete,
            billable_resources_returned=len(raw_posts),
        )

    def balance_usd(self) -> Decimal | None:
        return None


def load_provider_keys(
    *,
    dotenv_path: str | Path = ".env",
    environ: Mapping[str, str] | None = None,
) -> dict[ProviderName, str]:
    environment = os.environ if environ is None else environ
    path = Path(dotenv_path)
    file_values = dotenv_values(path) if path.is_file() else {}

    def value(name: str) -> str:
        raw = environment[name] if name in environment else file_values.get(name, "")
        return str(raw or "").strip()

    return {
        "official_x": "",
        "twitterapi_io": value("TWITTERAPI_IO_API_KEY"),
        "socialdata": value("SOCIALDATA_API_KEY"),
    }


def plan_search_tasks(
    benchmark: Sequence[NormalizedPost],
    *,
    start: datetime,
    end: datetime,
) -> tuple[SearchTask, ...]:
    authors: dict[str, tuple[str, int, int | None]] = {}
    for post in benchmark:
        key = post.author.casefold()
        display, count, minimum_id = authors.get(key, (post.author, 0, None))
        numeric_id = int(post.post_id) if post.post_id.isdigit() else None
        if numeric_id is not None:
            minimum_id = (
                numeric_id if minimum_id is None else min(minimum_id, numeric_id)
            )
        authors[key] = (display, count + 1, minimum_id)
    ordered = sorted(authors.values(), key=lambda item: (item[1], item[0].casefold()))
    return tuple(
        SearchTask(
            (author,),
            start,
            end,
            since_id=(str(max(0, minimum_id - 1)) if minimum_id is not None else None),
        )
        for author, _, minimum_id in ordered
    )


def _provider_unit_cost(provider: ProviderName) -> Decimal:
    if provider == "twitterapi_io":
        return TWITTERAPI_IO_UNIT_COST_USD
    if provider == "socialdata":
        return SOCIALDATA_UNIT_COST_USD
    raise ValueError("Cost planning supports only third-party shadow providers.")


def _approved_request_cap(
    approved_budget_usd: Decimal,
    unit_cost_usd: Decimal,
    reserve_page_results: int,
) -> int:
    if approved_budget_usd <= 0:
        raise ValueError("Provider approved budget must be positive.")
    if approved_budget_usd > TRIAL_SPEND_LIMIT_USD:
        raise ValueError("Provider approved budget cannot exceed $0.10.")
    if reserve_page_results < 1:
        raise ValueError("Provider page reserve must be positive.")
    reserve_cost = unit_cost_usd * reserve_page_results
    return int(approved_budget_usd // reserve_cost)


def _canonical_search_tasks(tasks: Sequence[SearchTask]) -> list[dict[str, object]]:
    return [
        {
            "authors": list(task.authors),
            "start": task.start.astimezone(timezone.utc).isoformat(),
            "end": task.end.astimezone(timezone.utc).isoformat(),
            "since_id": task.since_id,
            "max_id": task.max_id,
            "cursor": task.cursor,
            "depth": task.depth,
        }
        for task in tasks
    ]


def _post_id_digest(posts: Sequence[NormalizedPost]) -> str:
    post_ids = sorted({post.post_id for post in posts})
    return sha256("\n".join(post_ids).encode("utf-8")).hexdigest()


def build_discovery_cost_plan(
    *,
    provider: Literal["twitterapi_io", "socialdata"],
    benchmark: Sequence[NormalizedPost],
    start: datetime,
    end: datetime,
    hard_cap_usd: Decimal,
    minimum_twitter_slice_seconds: int = DEFAULT_TWITTERAPI_IO_MINIMUM_SLICE_SECONDS,
) -> ProviderCostPlan:
    """Build a deterministic zero-cost provider discovery preflight."""
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Discovery window must be a valid timezone-aware interval.")
    if minimum_twitter_slice_seconds < 1:
        raise ValueError("TwitterAPI.io minimum time slice must be at least 1 second.")
    tasks = plan_search_tasks(benchmark, start=start, end=end)
    author_count = len(tasks)
    unit_cost = _provider_unit_cost(provider)
    estimated_requests = author_count
    if provider == "twitterapi_io":
        documented_max_page_results = TWITTERAPI_IO_DOCUMENTED_MAX_PAGE_RESULTS
        expected_page_results = TWITTERAPI_IO_DOCUMENTED_MAX_PAGE_RESULTS
        page_size_bound: Literal["documented_maximum", "unknown_unbounded"] = (
            "documented_maximum"
        )
        technical_hard_dollar_cap = True
        seconds = max(1, int((end - start).total_seconds()))
        ratio = max(1, ceil(seconds / minimum_twitter_slice_seconds))
        depth = ceil(log2(ratio)) if ratio > 1 else 0
        per_author_tree = (2 ** (depth + 1)) - 1
        strategy_worst_case_requests = author_count * per_author_tree
        strategy = (
            "author windows; recursively bisect overflow/full windows; no Advanced "
            "Search cursor as canonical traversal"
        )
        notes = (
            f"minimum_time_slice_seconds={minimum_twitter_slice_seconds}",
            "overflow at minimum slice produces explicit incomplete status",
            "canonical post_id dedupe across parent and child windows",
            "documented Advanced Search maximum is 20 returned Posts per request",
        )
    else:
        documented_max_page_results = None
        expected_page_results = SOCIALDATA_EXPECTED_PAGE_RESULTS
        page_size_bound = "unknown_unbounded"
        technical_hard_dollar_cap = False
        strategy = (
            "SocialData cursor traversal; max_id continuation fallback with repeated "
            "cursor and ID protection"
        )
        notes = (
            "SocialData does not inherit TwitterAPI.io time slicing",
            "coverage is incomplete when cursor or max_id progress cannot be proven",
            "canonical post_id dedupe across pages",
            "page-size worst case is not documented; dollar maximum is not technical",
        )
    request_cap = _approved_request_cap(
        hard_cap_usd,
        unit_cost,
        expected_page_results,
    )
    if provider == "socialdata":
        strategy_worst_case_requests = request_cap
    expected_resources = estimated_requests * expected_page_results
    expected_cost = unit_cost * expected_resources
    conservative_resources = request_cap * expected_page_results
    conservative_cost = conservative_resources * unit_cost
    approval_scope = {
        "benchmark_post_ids_sha256": _post_id_digest(benchmark),
        "planned_search_tasks": _canonical_search_tasks(tasks),
        "strategy_parameters": {
            "minimum_twitter_slice_seconds": minimum_twitter_slice_seconds,
            "documented_max_page_results": documented_max_page_results,
            "expected_page_results": expected_page_results,
            "page_size_bound": page_size_bound,
            "approved_request_cap": request_cap,
        },
    }
    return ProviderCostPlan(
        provider=provider,
        mode="discovery",
        benchmark_size=len({post.post_id for post in benchmark}),
        author_count=author_count,
        window_start=start.astimezone(timezone.utc),
        window_end=end.astimezone(timezone.utc),
        strategy=strategy,
        estimated_requests=estimated_requests,
        expected_billable_resources=expected_resources,
        expected_cost_usd=expected_cost,
        strategy_worst_case_requests=strategy_worst_case_requests,
        approved_request_cap=request_cap,
        documented_max_page_results=documented_max_page_results,
        expected_page_results=expected_page_results,
        page_size_bound=page_size_bound,
        technical_hard_dollar_cap=technical_hard_dollar_cap,
        conservative_max_resources=conservative_resources,
        conservative_max_cost_usd=conservative_cost,
        approved_budget_usd=hard_cap_usd,
        unit_cost_usd=unit_cost,
        plan_fits_approved_limits=estimated_requests <= request_cap,
        approval_scope=approval_scope,
        notes=notes,
    )


def build_direct_id_cost_plan(
    *,
    provider: Literal["twitterapi_io", "socialdata"],
    benchmark: Sequence[NormalizedPost],
    hard_cap_usd: Decimal,
) -> ProviderCostPlan:
    """Plan a future direct-ID lookup without implementing or calling an endpoint."""
    selected_ids = sorted({post.post_id for post in benchmark})
    unique_count = len(selected_ids)
    unit_cost = _provider_unit_cost(provider)
    expected_requests = (
        ceil(unique_count / DIRECT_ID_EXPECTED_BATCH_SIZE) if unique_count else 0
    )
    affordable_request_cap = _approved_request_cap(
        hard_cap_usd,
        unit_cost,
        DIRECT_ID_EXPECTED_BATCH_SIZE,
    )
    request_cap = min(expected_requests, affordable_request_cap)
    conservative_resources = request_cap * DIRECT_ID_EXPECTED_BATCH_SIZE
    selection_digest = sha256("\n".join(selected_ids).encode("utf-8")).hexdigest()
    return ProviderCostPlan(
        provider=provider,
        mode="direct_id",
        benchmark_size=unique_count,
        author_count=len({post.author.casefold() for post in benchmark}),
        window_start=(
            min((post.created_at for post in benchmark), default=None)
        ),
        window_end=max((post.created_at for post in benchmark), default=None),
        strategy=(
            "provider-specific batched Post lookup by canonical ID; endpoint and "
            "pricing must be revalidated before a separate implementation task"
        ),
        estimated_requests=expected_requests,
        expected_billable_resources=unique_count,
        expected_cost_usd=unit_cost * unique_count,
        strategy_worst_case_requests=expected_requests,
        approved_request_cap=request_cap,
        documented_max_page_results=None,
        expected_page_results=DIRECT_ID_EXPECTED_BATCH_SIZE,
        page_size_bound="unknown_unbounded",
        technical_hard_dollar_cap=False,
        conservative_max_resources=conservative_resources,
        conservative_max_cost_usd=unit_cost * conservative_resources,
        approved_budget_usd=hard_cap_usd,
        unit_cost_usd=unit_cost,
        plan_fits_approved_limits=(
            unique_count > 0
            and expected_requests <= request_cap
            and unit_cost * conservative_resources <= hard_cap_usd
        ),
        approval_scope={
            "selected_post_ids": selected_ids,
            "selection_sha256": selection_digest,
            "strategy_parameters": {
                "expected_batch_size": DIRECT_ID_EXPECTED_BATCH_SIZE,
                "endpoint_contract_verified": False,
                "approved_request_cap": request_cap,
            },
        },
        notes=(
            "planning and offline comparison only; direct-ID API execution is absent",
            "Official X benchmark data comes only from PostgreSQL or ignored artifacts",
            "availability and content fields are compared by canonical post_id",
        ),
    )


def combined_plan_sha256(plans: Sequence[ProviderCostPlan]) -> str:
    payload = [
        {"provider": plan.provider, "plan_sha256": plan.plan_sha256}
        for plan in plans
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()


def build_preflight_report(plans: Sequence[ProviderCostPlan]) -> dict[str, object]:
    return {
        "plans": [plan.safe_summary() for plan in plans],
        "combined_plan_sha256": combined_plan_sha256(plans),
        "all_plans_fit_approved_limits": all(
            plan.plan_fits_approved_limits for plan in plans
        ),
        "external_requests": 0,
        "approval_required": True,
        "execution_authorized": False,
        "cost_limits_auto_increased": False,
    }


def build_shadow_run_id(
    *,
    window_end: datetime,
    benchmark: Sequence[NormalizedPost],
    combined_plan_digest: str,
    execution_identity: str | None = None,
) -> str:
    """Build a collision-resistant local artifact identity for one execution."""
    identity = execution_identity or uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", identity):
        raise ValueError("execution_identity must be 4-64 safe filename characters.")
    window_identity = window_end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"{window_identity}-{_post_id_digest(benchmark)[:10]}-"
        f"{combined_plan_digest[:10]}-{identity}"
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True, default=str)
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def plan_official_page_size(
    *,
    remaining_budget_usd: Decimal,
    requested_page_size: int,
    worst_case_cost_per_primary_usd: Decimal,
) -> int:
    """Return a page size whose declared worst case fits the remaining budget."""
    if requested_page_size < 1 or requested_page_size > 100:
        raise ValueError("Official X page size must be between 1 and 100.")
    if remaining_budget_usd < 0:
        raise ValueError("Remaining Official X budget must not be negative.")
    if worst_case_cost_per_primary_usd <= 0:
        raise ValueError("Official X worst-case unit cost must be positive.")
    affordable = int(remaining_budget_usd // worst_case_cost_per_primary_usd)
    return min(requested_page_size, affordable)


def _write_official_partial_summary(
    *,
    artifact_dir: Path,
    status: str,
    successful_pages: int,
    attempted_requests: int,
    raw_primary_posts: int,
    unique_primary_posts: int,
    unique_expanded_posts: int,
    unique_users: int,
    unique_media: int,
    next_token_present: bool,
    estimated_spend_usd: Decimal,
    approved_max_spend_usd: Decimal,
    next_page_size: int,
    terminal_error: XApiRequestError | None,
) -> None:
    _write_json(
        artifact_dir / "official_x" / "partial-summary.json",
        {
            "status": status,
            "successful_pages": successful_pages,
            "attempted_requests": attempted_requests,
            "raw_primary_posts": raw_primary_posts,
            "unique_primary_posts": unique_primary_posts,
            "unique_expanded_posts": unique_expanded_posts,
            "unique_users": unique_users,
            "unique_media": unique_media,
            "next_token_present": next_token_present,
            "estimated_spend_usd": format(estimated_spend_usd, "f"),
            "approved_max_spend_usd": format(approved_max_spend_usd, "f"),
            "next_page_size": next_page_size,
            "terminal_http_status": terminal_error.status if terminal_error else None,
            "terminal_error_category": (
                terminal_error.category if terminal_error else None
            ),
            "raw_pages_durable": True,
            "checkpoint_scope": "shadow_only_not_sync_state",
        },
    )


def run_search_provider(
    provider: SearchProvider,
    *,
    benchmark: Sequence[NormalizedPost],
    start: datetime,
    end: datetime,
    spend_limit_usd: Decimal,
    artifact_dir: Path,
    approved_plan_sha256: str | None = None,
    minimum_twitter_slice_seconds: int = DEFAULT_TWITTERAPI_IO_MINIMUM_SLICE_SECONDS,
    monotonic_clock: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> ProviderRun:
    if provider.name not in {"twitterapi_io", "socialdata"}:
        raise ValueError("Unsupported discovery provider.")
    plan = build_discovery_cost_plan(
        provider=provider.name,
        benchmark=benchmark,
        start=start,
        end=end,
        hard_cap_usd=spend_limit_usd,
        minimum_twitter_slice_seconds=minimum_twitter_slice_seconds,
    )
    _require_approved_plan(plan, approved_plan_sha256)
    if provider.name == "twitterapi_io":
        return _run_twitterapi_io_discovery(
            provider,
            benchmark=benchmark,
            start=start,
            end=end,
            artifact_dir=artifact_dir,
            plan=plan,
            minimum_slice_seconds=minimum_twitter_slice_seconds,
            monotonic_clock=monotonic_clock or time.monotonic,
            sleep=sleep or time.sleep,
        )
    return _run_socialdata_discovery(
        provider,
        benchmark=benchmark,
        start=start,
        end=end,
        artifact_dir=artifact_dir,
        plan=plan,
    )


def _require_approved_plan(
    plan: ProviderCostPlan,
    approved_plan_sha256: str | None,
) -> None:
    if approved_plan_sha256 is None:
        raise ShadowSpikeError(
            "External provider execution blocked: explicit preflight approval is missing."
        )
    if approved_plan_sha256 != plan.plan_sha256:
        raise ShadowSpikeError(
            "External provider execution blocked: approved preflight digest mismatch."
        )
    if not plan.plan_fits_approved_limits:
        raise ShadowSpikeError(
            "External provider execution blocked: planned initial coverage exceeds the "
            "approved request and spend limits."
        )


def _provider_error_status(error: ProviderRequestError) -> tuple[str, str]:
    return {
        "credit_exhausted": ("incomplete_due_to_credit", "credit_exhausted"),
        "access_denied": (
            "incomplete_due_to_access",
            "provider_endpoint_access_denied",
        ),
        "invalid_credentials": (
            "incomplete_due_to_auth",
            "provider_credentials_rejected",
        ),
        "rate_limited": (
            "incomplete_due_to_rate_limit",
            "provider_rate_limit_reached",
        ),
    }.get(
        error.category,
        ("incomplete_due_to_request_failure", "provider_request_failed"),
    )


def _dedupe_posts(
    destination: dict[str, NormalizedPost],
    posts: Sequence[NormalizedPost],
) -> int:
    duplicates = 0
    for post in posts:
        if post.post_id in destination:
            duplicates += 1
        else:
            destination[post.post_id] = post
    return duplicates


def _returned_billable_resources(page: ProviderPage) -> int:
    resources = page.billable_resources_returned
    if resources is None:
        return len(page.posts)
    if resources < 0:
        raise ShadowSpikeError("Provider returned a negative billable-resource count.")
    return resources


def _pace_request(
    provider: SearchProvider,
    *,
    last_request_started_at: float | None,
    monotonic_clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> float:
    interval = max(0.0, float(getattr(provider, "minimum_interval_seconds", 0.0)))
    now = monotonic_clock()
    if last_request_started_at is not None:
        remaining = last_request_started_at + interval - now
        if remaining > 0:
            sleep(remaining)
            now = monotonic_clock()
    return now


def _request_reserve_cost(plan: ProviderCostPlan) -> Decimal:
    reserve_results = (
        plan.documented_max_page_results
        if plan.documented_max_page_results is not None
        else plan.expected_page_results
    )
    return plan.unit_cost_usd * reserve_results


def _can_start_next_request(
    *,
    plan: ProviderCostPlan,
    requests: int,
    returned_billable_resources: int,
) -> bool:
    if requests >= plan.approved_request_cap:
        return False
    accounted_cost = plan.unit_cost_usd * returned_billable_resources
    return accounted_cost + _request_reserve_cost(plan) <= plan.approved_budget_usd


def _run_twitterapi_io_discovery(
    provider: SearchProvider,
    *,
    benchmark: Sequence[NormalizedPost],
    start: datetime,
    end: datetime,
    artifact_dir: Path,
    plan: ProviderCostPlan,
    minimum_slice_seconds: int,
    monotonic_clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> ProviderRun:
    queue = deque(plan_search_tasks(benchmark, start=start, end=end))
    seen_windows: set[tuple[tuple[str, ...], int, int]] = set()
    posts_by_id: dict[str, NormalizedPost] = {}
    requests = 0
    raw_resources = 0
    unresolved_windows = 0
    duplicate_rows = 0
    warnings: set[str] = set()
    status = "complete"
    last_request_started_at: float | None = None
    while queue:
        if not _can_start_next_request(
            plan=plan,
            requests=requests,
            returned_billable_resources=raw_resources,
        ):
            status = "incomplete_due_to_budget"
            warnings.add("provider_hard_request_and_spend_guard_reached")
            unresolved_windows += len(queue)
            break
        task = queue.popleft()
        key = (
            tuple(author.casefold() for author in task.authors),
            int(task.start.timestamp()),
            int(task.end.timestamp()),
        )
        if key in seen_windows:
            status = "incomplete_due_to_repeated_window"
            warnings.add("twitterapi_io_repeated_window_blocked")
            unresolved_windows += 1
            continue
        seen_windows.add(key)
        last_request_started_at = _pace_request(
            provider,
            last_request_started_at=last_request_started_at,
            monotonic_clock=monotonic_clock,
            sleep=sleep,
        )
        requests += 1
        try:
            page = provider.search(task)
        except ProviderRequestError as error:
            status, warning = _provider_error_status(error)
            warnings.add(warning)
            unresolved_windows += len(queue) + 1
            break
        _write_json(
            artifact_dir / provider.name / f"response-{requests:04d}.json",
            page.raw_payload,
        )
        raw_resources += _returned_billable_resources(page)
        duplicate_rows += _dedupe_posts(posts_by_id, page.posts)
        if provider.unit_cost_usd * raw_resources >= plan.approved_budget_usd:
            status = "incomplete_due_to_budget"
            warnings.add("approved_budget_reached_after_response")
            unresolved_windows += len(queue)
            break
        overflow = (
            page.has_more
            or page.possible_incomplete
            or len(page.posts) >= TWITTERAPI_IO_DOCUMENTED_MAX_PAGE_RESULTS
        )
        if not overflow:
            continue
        duration_seconds = int((task.end - task.start).total_seconds())
        if duration_seconds <= minimum_slice_seconds:
            status = "incomplete_due_to_minimum_time_slice"
            warnings.add("twitterapi_io_overflow_at_minimum_time_slice")
            unresolved_windows += 1
            continue
        midpoint = task.start + (task.end - task.start) / 2
        midpoint = datetime.fromtimestamp(int(midpoint.timestamp()), tz=timezone.utc)
        if midpoint <= task.start or midpoint >= task.end:
            status = "incomplete_due_to_minimum_time_slice"
            warnings.add("twitterapi_io_window_cannot_be_split_further")
            unresolved_windows += 1
            continue
        warnings.add("twitterapi_io_overflow_window_split")
        left = replace(
            task,
            end=midpoint,
            depth=task.depth + 1,
            cursor=None,
            max_id=None,
        )
        right = replace(
            task,
            start=midpoint,
            depth=task.depth + 1,
            cursor=None,
            max_id=None,
        )
        queue.appendleft(right)
        queue.appendleft(left)
    if duplicate_rows:
        warnings.add("canonical_post_id_duplicates_removed")
    return ProviderRun(
        provider="twitterapi_io",
        status=status,
        posts=tuple(posts_by_id.values()),
        requests=requests,
        pagination_gaps=unresolved_windows,
        estimated_spend_usd=provider.unit_cost_usd * raw_resources,
        actual_spend_usd=None,
        warnings=tuple(sorted(warnings)),
        duplicates_removed=duplicate_rows,
    )


def _run_socialdata_discovery(
    provider: SearchProvider,
    *,
    benchmark: Sequence[NormalizedPost],
    start: datetime,
    end: datetime,
    artifact_dir: Path,
    plan: ProviderCostPlan,
) -> ProviderRun:
    queue = deque(plan_search_tasks(benchmark, start=start, end=end))
    seen_states: set[tuple[tuple[str, ...], int, int, str | None, str | None]] = set()
    seen_cursors: set[tuple[tuple[str, ...], str]] = set()
    seen_max_ids: set[tuple[tuple[str, ...], str]] = set()
    posts_by_id: dict[str, NormalizedPost] = {}
    requests = 0
    raw_resources = 0
    duplicate_rows = 0
    unresolved_pages = 0
    status = "complete"
    warnings: set[str] = set()
    while queue:
        if not _can_start_next_request(
            plan=plan,
            requests=requests,
            returned_billable_resources=raw_resources,
        ):
            status = "incomplete_due_to_budget"
            warnings.add("provider_request_cap_or_conservative_reserve_reached")
            unresolved_pages += len(queue)
            break
        task = queue.popleft()
        author_key = tuple(author.casefold() for author in task.authors)
        state = (
            author_key,
            int(task.start.timestamp()),
            int(task.end.timestamp()),
            task.cursor,
            task.max_id,
        )
        if state in seen_states:
            status = "incomplete_due_to_repeated_page_state"
            warnings.add("socialdata_repeated_page_state_blocked")
            unresolved_pages += 1
            continue
        seen_states.add(state)
        requests += 1
        try:
            page = provider.search(task)
        except ProviderRequestError as error:
            status, warning = _provider_error_status(error)
            warnings.add(warning)
            unresolved_pages += len(queue) + 1
            break
        _write_json(
            artifact_dir / provider.name / f"response-{requests:04d}.json",
            page.raw_payload,
        )
        raw_resources += _returned_billable_resources(page)
        duplicate_rows += _dedupe_posts(posts_by_id, page.posts)
        if provider.unit_cost_usd * raw_resources >= plan.approved_budget_usd:
            status = "incomplete_due_to_budget"
            warnings.add("approved_budget_reached_after_response")
            unresolved_pages += len(queue)
            break
        if page.next_cursor:
            cursor_key = (author_key, page.next_cursor)
            if page.next_cursor == task.cursor or cursor_key in seen_cursors:
                status = "incomplete_due_to_repeated_cursor"
                warnings.add("socialdata_repeated_cursor_blocked")
                unresolved_pages += 1
                continue
            seen_cursors.add(cursor_key)
            warnings.add("socialdata_cursor_continuation_used")
            queue.appendleft(
                replace(task, cursor=page.next_cursor, max_id=None)
            )
            continue
        overflow = (
            page.has_more
            or page.possible_incomplete
            or len(page.posts) >= SOCIALDATA_EXPECTED_PAGE_RESULTS
        )
        if not overflow:
            continue
        next_max_id = page.continuation_max_id
        if not next_max_id:
            status = "incomplete_due_to_unprovable_coverage"
            warnings.add("socialdata_missing_cursor_and_max_id_continuation")
            unresolved_pages += 1
            continue
        max_key = (author_key, next_max_id)
        if next_max_id == task.max_id or max_key in seen_max_ids:
            status = "incomplete_due_to_repeated_max_id"
            warnings.add("socialdata_repeated_max_id_blocked")
            unresolved_pages += 1
            continue
        seen_max_ids.add(max_key)
        warnings.add("socialdata_max_id_fallback_used")
        queue.appendleft(replace(task, cursor=None, max_id=next_max_id))
    if duplicate_rows:
        warnings.add("canonical_post_id_duplicates_removed")
    return ProviderRun(
        provider="socialdata",
        status=status,
        posts=tuple(posts_by_id.values()),
        requests=requests,
        pagination_gaps=unresolved_pages,
        estimated_spend_usd=provider.unit_cost_usd * raw_resources,
        actual_spend_usd=None,
        warnings=tuple(sorted(warnings)),
        duplicates_removed=duplicate_rows,
    )


def fetch_official_benchmark(
    *,
    start: datetime,
    end: datetime,
    max_pages: int,
    artifact_dir: Path,
    approved_max_spend_usd: Decimal | None,
    worst_case_cost_per_primary_usd: Decimal | None,
    max_results_per_page: int = 100,
) -> ProviderRun:
    if max_pages < 1:
        raise ValueError("max_official_pages must be at least 1.")
    if approved_max_spend_usd is None or approved_max_spend_usd <= 0:
        raise ValueError(
            "Fresh Official X requires an explicitly approved positive spend ceiling."
        )
    if worst_case_cost_per_primary_usd is None:
        raise ValueError(
            "Fresh Official X requires the preflight worst-case cost per primary Post."
        )
    initial_page_size = plan_official_page_size(
        remaining_budget_usd=approved_max_spend_usd,
        requested_page_size=max_results_per_page,
        worst_case_cost_per_primary_usd=worst_case_cost_per_primary_usd,
    )
    if initial_page_size < 1:
        raise ValueError(
            "Approved Official X ceiling cannot fund one worst-case primary Post."
        )
    config = load_x_api_config()
    config.require_collector_setup()
    tokens = refresh_access_token(
        client_id=config.client_id,
        refresh_token=config.refresh_token,
    )
    persist_refresh_token(tokens.refresh_token)
    client = XApiClient(token=tokens.access_token, base_url=config.base_url)
    endpoint = f"/users/{config.user_id_for('home')}/timelines/reverse_chronological"
    base_params: dict[str, object] = {
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet.fields": TWEET_FIELDS,
        "expansions": SHADOW_EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": SHADOW_MEDIA_FIELDS,
    }
    posts: list[NormalizedPost] = []
    primary_ids: set[str] = set()
    expanded_ids: set[str] = set()
    user_ids: set[str] = set()
    media_keys: set[str] = set()
    token: str | None = None
    requests = 0
    attempted_requests = 0
    raw_primary_posts = 0
    warnings: set[str] = set()
    status = "complete"
    terminal_error: XApiRequestError | None = None
    while requests < max_pages:
        resources = primary_ids | expanded_ids
        estimated_spend = (
            OFFICIAL_X_POST_READ_COST_USD * len(resources)
            + OFFICIAL_X_USER_READ_COST_USD * len(user_ids)
            + OFFICIAL_X_MEDIA_READ_COST_USD * len(media_keys)
        )
        remaining_budget = approved_max_spend_usd - estimated_spend
        page_size = plan_official_page_size(
            remaining_budget_usd=max(Decimal("0"), remaining_budget),
            requested_page_size=max_results_per_page,
            worst_case_cost_per_primary_usd=worst_case_cost_per_primary_usd,
        )
        if page_size < 1:
            status = "incomplete_due_to_budget"
            warnings.add("official_x_hard_budget_guard_reached")
            break
        params = dict(base_params)
        params["max_results"] = page_size
        if token:
            params["pagination_token"] = token
        attempted_requests += 1
        try:
            response, elapsed = client._get(endpoint, params)
        except XApiRequestError as error:
            if not requests:
                raise
            terminal_error = error
            if error.status == 402:
                status = "incomplete_due_to_credit"
                warnings.add("official_x_credit_exhausted_after_partial_fetch")
            else:
                status = "incomplete_due_to_request_failure"
                warnings.add("official_x_request_failed_after_partial_fetch")
            _write_official_partial_summary(
                artifact_dir=artifact_dir,
                status=status,
                successful_pages=requests,
                attempted_requests=attempted_requests,
                raw_primary_posts=raw_primary_posts,
                unique_primary_posts=len(primary_ids),
                unique_expanded_posts=len(expanded_ids),
                unique_users=len(user_ids),
                unique_media=len(media_keys),
                next_token_present=bool(token),
                estimated_spend_usd=estimated_spend,
                approved_max_spend_usd=approved_max_spend_usd,
                next_page_size=0,
                terminal_error=terminal_error,
            )
            break
        page = parse_content_page(response, endpoint=endpoint, elapsed=elapsed)
        requests += 1
        try:
            raw_payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ShadowSpikeError("Official X returned invalid JSON.") from error
        _write_json(
            artifact_dir / "official_x" / f"response-{requests:04d}.json",
            raw_payload,
        )
        for post in page.posts:
            normalized = normalize_official_post(
                post,
                users_by_id=page.users_by_id,
                expanded_posts_by_id=page.expanded_posts_by_id,
                media_by_key=page.media_by_key,
            )
            posts.append(normalized)
            primary_ids.add(normalized.post_id)
        raw_primary_posts += len(page.posts)
        expanded_ids.update(page.expanded_posts_by_id)
        user_ids.update(page.users_by_id)
        media_keys.update(page.media_by_key)
        if page.partial_error_count:
            warnings.add("official_x_partial_errors_present")
        token = page.next_token
        resources = primary_ids | expanded_ids
        estimated_spend = (
            OFFICIAL_X_POST_READ_COST_USD * len(resources)
            + OFFICIAL_X_USER_READ_COST_USD * len(user_ids)
            + OFFICIAL_X_MEDIA_READ_COST_USD * len(media_keys)
        )
        declared_page_reserve = worst_case_cost_per_primary_usd * page_size
        if estimated_spend > approved_max_spend_usd:
            raise ShadowSpikeError(
                "Official X returned resources above the approved hard spend ceiling."
            )
        next_page_size = plan_official_page_size(
            remaining_budget_usd=max(
                Decimal("0"), approved_max_spend_usd - estimated_spend
            ),
            requested_page_size=max_results_per_page,
            worst_case_cost_per_primary_usd=worst_case_cost_per_primary_usd,
        )
        _write_official_partial_summary(
            artifact_dir=artifact_dir,
            status="in_progress" if token else "complete",
            successful_pages=requests,
            attempted_requests=attempted_requests,
            raw_primary_posts=raw_primary_posts,
            unique_primary_posts=len(primary_ids),
            unique_expanded_posts=len(expanded_ids),
            unique_users=len(user_ids),
            unique_media=len(media_keys),
            next_token_present=bool(token),
            estimated_spend_usd=estimated_spend,
            approved_max_spend_usd=approved_max_spend_usd,
            next_page_size=next_page_size,
            terminal_error=None,
        )
        if estimated_spend > declared_page_reserve + (
            approved_max_spend_usd - remaining_budget
        ):
            raise ShadowSpikeError(
                "Official X response exceeded the declared per-primary worst-case bound."
            )
        if not token:
            break
    if token and status == "complete":
        status = "incomplete_due_to_page_limit"
        warnings.add("official_x_page_limit_reached")
    resources = primary_ids | expanded_ids
    estimated_spend = (
        OFFICIAL_X_POST_READ_COST_USD * len(resources)
        + OFFICIAL_X_USER_READ_COST_USD * len(user_ids)
        + OFFICIAL_X_MEDIA_READ_COST_USD * len(media_keys)
    )
    final_next_page_size = plan_official_page_size(
        remaining_budget_usd=max(
            Decimal("0"), approved_max_spend_usd - estimated_spend
        ),
        requested_page_size=max_results_per_page,
        worst_case_cost_per_primary_usd=worst_case_cost_per_primary_usd,
    )
    _write_official_partial_summary(
        artifact_dir=artifact_dir,
        status=status,
        successful_pages=requests,
        attempted_requests=attempted_requests,
        raw_primary_posts=raw_primary_posts,
        unique_primary_posts=len(primary_ids),
        unique_expanded_posts=len(expanded_ids),
        unique_users=len(user_ids),
        unique_media=len(media_keys),
        next_token_present=bool(token),
        estimated_spend_usd=estimated_spend,
        approved_max_spend_usd=approved_max_spend_usd,
        next_page_size=(final_next_page_size if token else 0),
        terminal_error=terminal_error,
    )
    warnings.add("official_x_cost_includes_returned_post_user_and_media_resources")
    warnings.add("official_x_pages_and_partial_summary_are_durable_per_page")
    return ProviderRun(
        provider="official_x",
        status=status,
        posts=tuple(posts),
        requests=requests,
        pagination_gaps=1 if token else 0,
        estimated_spend_usd=estimated_spend,
        actual_spend_usd=None,
        warnings=tuple(sorted(warnings)),
    )


def fetch_stored_official_benchmark(
    *,
    hours: int,
) -> tuple[ProviderRun, datetime, datetime]:
    """Read the latest already-collected Home Timeline window without DB writes."""
    with connect_database(load_database_config()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT max(created_at)
                FROM posts
                WHERE source_key = 'x_home_timeline'
                """
            )
            end = cursor.fetchone()[0]
            if end is None:
                raise ShadowSpikeError(
                    "No stored Official X Home Timeline Posts are available."
                )
            start = end - timedelta(hours=hours)
            cursor.execute(
                """
                SELECT post_id, author_id, author_username, created_at, text,
                       post_type, conversation_id, referenced_post_id, raw_json
                FROM posts
                WHERE source_key = 'x_home_timeline'
                  AND created_at >= %s
                  AND created_at <= %s
                ORDER BY created_at, post_id
                """,
                (start, end),
            )
            rows = cursor.fetchall()
        connection.rollback()

    posts: list[NormalizedPost] = []
    for row in rows:
        (
            post_id,
            author_id,
            author,
            created_at,
            text,
            post_type,
            conversation_id,
            referenced_post_id,
            raw_json,
        ) = row
        if not author:
            raise ShadowSpikeError(
                "Stored Official X benchmark contains a Post without an author."
            )
        raw = raw_json if isinstance(raw_json, Mapping) else {}
        expanded = raw.get("_expanded")
        expanded_data = expanded if isinstance(expanded, Mapping) else {}
        reference_raw = expanded_data.get("referenced_post")
        reference_author_raw = expanded_data.get("referenced_post_author")
        referenced_context = None
        if referenced_post_id and isinstance(reference_raw, Mapping):
            reference_author = (
                _optional_string(reference_author_raw.get("username"))
                if isinstance(reference_author_raw, Mapping)
                else None
            )
            referenced_context = NormalizedReference(
                post_id=str(referenced_post_id),
                author=reference_author,
                created_at=(
                    _parse_datetime(reference_raw.get("created_at"))
                    if reference_raw.get("created_at")
                    else None
                ),
                text=_full_text(reference_raw, "text") or None,
                media_metadata=(),
            )
        expanded_media = expanded_data.get("media")
        media_metadata = tuple(
            _safe_media_object(item)
            for item in expanded_media or ()
            if isinstance(item, Mapping)
        )
        posts.append(
            NormalizedPost(
                post_id=str(post_id),
                author=str(author),
                author_id=str(author_id) if author_id else None,
                created_at=created_at.astimezone(timezone.utc),
                text=str(text),
                post_type=post_type,
                conversation_id=(
                    str(conversation_id) if conversation_id else None
                ),
                referenced_post_id=(
                    str(referenced_post_id) if referenced_post_id else None
                ),
                referenced_context=referenced_context,
                media_metadata=media_metadata,
                provider="official_x",
            )
        )
    if not posts:
        raise ShadowSpikeError(
            "Stored Official X Home Timeline window contains no Posts."
        )
    return (
        ProviderRun(
            provider="official_x",
            status="complete",
            posts=tuple(posts),
            requests=0,
            pagination_gaps=0,
            estimated_spend_usd=Decimal("0"),
            actual_spend_usd=Decimal("0"),
            warnings=(
                "stored_official_x_benchmark_reused_after_live_http_402",
                "no_incremental_official_x_retrieval_cost",
            ),
        ),
        start,
        end,
    )


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator * 100.0 / denominator, 2)


_ONLY_URLS_RE = re.compile(r"https?://\S+(?:\s+https?://\S+)*", re.IGNORECASE)


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _content_status(expected: str, actual: str) -> tuple[bool, bool, bool]:
    """Return exact match, complete content, and proven truncation flags."""
    if expected == actual:
        return True, True, False
    expected_normalized = _normalized_text(expected)
    actual_normalized = _normalized_text(actual)
    if expected_normalized == actual_normalized:
        return False, True, False
    if actual_normalized.startswith(expected_normalized):
        suffix = actual_normalized[len(expected_normalized) :].strip()
        if suffix and _ONLY_URLS_RE.fullmatch(suffix):
            return False, True, False
    truncated = bool(
        actual_normalized
        and expected_normalized.startswith(actual_normalized)
        and len(actual_normalized) < len(expected_normalized)
    )
    return False, False, truncated


def _systematic_group_loss(
    *,
    group: str,
    total: int,
    missing: int,
    group_recall_pct: float | None,
    overall_recall_pct: float | None,
    thresholds: QualityAcceptanceThresholds,
) -> str | None:
    if (
        total < thresholds.systematic_group_minimum_posts
        or missing < thresholds.systematic_group_minimum_missing
        or group_recall_pct is None
    ):
        return None
    loss_pct = 100.0 - group_recall_pct
    materially_concentrated = (
        overall_recall_pct is not None
        and group_recall_pct + thresholds.systematic_recall_gap_pct
        < overall_recall_pct
    )
    if (
        loss_pct > thresholds.maximum_non_systematic_raw_loss_pct
        and (
            group_recall_pct < thresholds.minimum_raw_recall_pct
            or materially_concentrated
        )
    ):
        return f"systematic_{group}_recall_loss"
    return None


def compare_provider(
    benchmark: Sequence[NormalizedPost],
    run: ProviderRun,
    *,
    thresholds: QualityAcceptanceThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or QualityAcceptanceThresholds()
    benchmark_by_id = {post.post_id: post for post in benchmark}
    provider_by_id: dict[str, NormalizedPost] = {}
    duplicate_count = run.duplicates_removed
    for post in run.posts:
        if post.post_id in provider_by_id:
            duplicate_count += 1
        else:
            provider_by_id[post.post_id] = post
    benchmark_ids = set(benchmark_by_id)
    provider_ids = set(provider_by_id)
    matched_ids = benchmark_ids & provider_ids
    missing_ids = benchmark_ids - provider_ids
    extra_ids = provider_ids - benchmark_ids
    matched_pairs = [
        (benchmark_by_id[post_id], provider_by_id[post_id])
        for post_id in matched_ids
    ]
    text_statuses = [
        _content_status(expected.text, actual.text)
        for expected, actual in matched_pairs
    ]
    exact_text = sum(exact for exact, _, _ in text_statuses)
    complete_text = sum(complete for _, complete, _ in text_statuses)
    truncated_text = sum(truncated for _, _, truncated in text_statuses)
    missing_text = sum(not actual.text for _, actual in matched_pairs)
    long_ids = {
        post_id for post_id, post in benchmark_by_id.items() if len(post.text) > 280
    }
    matched_long_ids = long_ids & matched_ids
    exact_long_text = sum(
        benchmark_by_id[post_id].text == provider_by_id[post_id].text
        for post_id in matched_long_ids
    )
    long_content_statuses = [
        _content_status(
            benchmark_by_id[post_id].text,
            provider_by_id[post_id].text,
        )
        for post_id in matched_long_ids
    ]
    complete_long_text = sum(complete for _, complete, _ in long_content_statuses)
    truncated_long_text = sum(truncated for _, _, truncated in long_content_statuses)
    type_correct = sum(
        expected.post_type == actual.post_type for expected, actual in matched_pairs
    )
    reference_required = {
        post_id
        for post_id, post in benchmark_by_id.items()
        if post.referenced_post_id is not None
    }
    matched_reference_required = reference_required & matched_ids
    reference_id_correct = sum(
        benchmark_by_id[post_id].referenced_post_id
        == provider_by_id[post_id].referenced_post_id
        for post_id in matched_reference_required
    )
    context_available = sum(
        provider_by_id[post_id].referenced_context is not None
        and bool(provider_by_id[post_id].referenced_context.text)
        for post_id in matched_reference_required
    )
    media_required = {
        post_id
        for post_id, post in benchmark_by_id.items()
        if post.media_metadata
    }
    matched_media_required = media_required & matched_ids
    media_available = sum(
        bool(provider_by_id[post_id].media_metadata)
        for post_id in matched_media_required
    )
    missing_by_type = {
        post_type: sum(
            benchmark_by_id[post_id].post_type == post_type for post_id in missing_ids
        )
        for post_type in ("original", "reply", "quote", "repost")
    }
    benchmark_by_type = {
        post_type: sum(post.post_type == post_type for post in benchmark)
        for post_type in ("original", "reply", "quote", "repost")
    }
    recall_by_type = {
        post_type: _percentage(
            benchmark_by_type[post_type] - missing_by_type[post_type],
            benchmark_by_type[post_type],
        )
        for post_type in benchmark_by_type
    }
    recall = _percentage(len(matched_ids), len(benchmark_ids))
    long_recall = _percentage(len(matched_long_ids), len(long_ids))
    systematic = [
        flag
        for flag in (
            _systematic_group_loss(
                group="long_post",
                total=len(long_ids),
                missing=len(long_ids - matched_ids),
                group_recall_pct=long_recall,
                overall_recall_pct=recall,
                thresholds=thresholds,
            ),
            *(
                _systematic_group_loss(
                    group=post_type,
                    total=benchmark_by_type[post_type],
                    missing=missing_by_type[post_type],
                    group_recall_pct=recall_by_type[post_type],
                    overall_recall_pct=recall,
                    thresholds=thresholds,
                )
                for post_type in ("reply", "quote")
            ),
        )
        if flag is not None
    ]
    content_complete_pct = _percentage(complete_text, len(matched_ids))
    raw_recall_passed = bool(
        recall is not None and recall >= thresholds.minimum_raw_recall_pct
    )
    content_complete_passed = bool(
        content_complete_pct is not None
        and content_complete_pct >= thresholds.required_content_complete_pct
    )
    if not content_complete_passed and matched_ids:
        systematic.append("matched_content_incomplete")
    accepted = bool(
        run.status == "complete"
        and raw_recall_passed
        and content_complete_passed
        and not systematic
    )
    return {
        "provider": run.provider,
        "status": run.status,
        "posts_returned": len(run.posts),
        "unique_posts_returned": len(provider_ids),
        "benchmark_posts": len(benchmark_ids),
        "matched_benchmark_ids": len(matched_ids),
        "missing_benchmark_ids": len(missing_ids),
        "extra_ids": len(extra_ids),
        "recall_pct": recall,
        "exact_text_match": {
            "matches": exact_text,
            "matched_posts": len(matched_ids),
            "pct": _percentage(exact_text, len(matched_ids)),
        },
        "content_completeness": {
            "complete": complete_text,
            "matched_posts": len(matched_ids),
            "complete_pct": content_complete_pct,
            "proven_truncations": truncated_text,
            "complete_representation_differences": complete_text - exact_text,
            "incomplete_non_truncating_differences": (
                len(matched_ids) - complete_text - truncated_text
            ),
            "missing_text": missing_text,
        },
        "long_posts": {
            "benchmark": len(long_ids),
            "matched": len(matched_long_ids),
            "recall_pct": long_recall,
            "exact_text": exact_long_text,
            "exact_text_pct": _percentage(exact_long_text, len(matched_long_ids)),
            "content_complete": complete_long_text,
            "content_complete_pct": _percentage(
                complete_long_text, len(matched_long_ids)
            ),
            "proven_truncations": truncated_long_text,
            "complete_representation_differences": (
                complete_long_text - exact_long_text
            ),
            "incomplete_non_truncating_differences": (
                len(matched_long_ids) - complete_long_text - truncated_long_text
            ),
        },
        "post_type": {
            "correct": type_correct,
            "accuracy_pct": _percentage(type_correct, len(matched_ids)),
            "benchmark_by_type": benchmark_by_type,
            "missing_by_type": missing_by_type,
            "recall_by_type_pct": recall_by_type,
        },
        "referenced_context": {
            "benchmark_with_reference": len(reference_required),
            "matched_with_reference": len(matched_reference_required),
            "reference_id_correct": reference_id_correct,
            "context_with_text": context_available,
            "coverage_pct": _percentage(
                context_available, len(matched_reference_required)
            ),
        },
        "media": {
            "benchmark_with_media": len(media_required),
            "matched_with_media": len(matched_media_required),
            "provider_media_present": media_available,
            "coverage_pct": _percentage(media_available, len(matched_media_required)),
        },
        "field_loss_on_matched": {
            "author_missing_or_mismatch": sum(
                expected.author.casefold() != actual.author.casefold()
                for expected, actual in matched_pairs
            ),
            "created_at_missing_or_mismatch": sum(
                expected.created_at != actual.created_at
                for expected, actual in matched_pairs
            ),
            "conversation_id_missing_or_mismatch": sum(
                bool(expected.conversation_id)
                and expected.conversation_id != actual.conversation_id
                for expected, actual in matched_pairs
            ),
            "referenced_post_id_missing_or_mismatch": (
                len(matched_reference_required) - reference_id_correct
            ),
        },
        "duplicates": duplicate_count,
        "pagination_gaps": run.pagination_gaps,
        "requests": run.requests,
        "estimated_spend_usd": format(run.estimated_spend_usd, "f"),
        "actual_spend_usd": (
            format(run.actual_spend_usd, "f")
            if run.actual_spend_usd is not None
            else None
        ),
        "systematic_loss_flags": systematic,
        "acceptance": {
            "accepted": accepted,
            "raw_recall_passed": raw_recall_passed,
            "content_complete_passed": content_complete_passed,
            "systematic_loss_blockers": systematic,
            "raw_recall_band": (
                "target_95_plus"
                if recall is not None and recall >= thresholds.target_raw_recall_pct
                else (
                    "acceptable_90_to_95"
                    if raw_recall_passed
                    else "below_minimum_90"
                )
            ),
            "thresholds": thresholds.safe_summary(),
        },
        "warnings": list(run.warnings),
    }


def select_direct_id_benchmark(
    benchmark: Sequence[NormalizedPost],
    *,
    limit: int = 50,
) -> tuple[NormalizedPost, ...]:
    """Select a deterministic, content-rich local benchmark for future ID lookup."""
    if limit < 1:
        raise ValueError("Direct-ID benchmark limit must be at least 1.")
    unique = {post.post_id: post for post in benchmark}
    ordered = sorted(
        unique.values(),
        key=lambda post: (post.created_at, post.post_id),
        reverse=True,
    )
    selected: dict[str, NormalizedPost] = {}
    predicates = (
        lambda post: len(post.text) > 280,
        lambda post: post.post_type == "reply",
        lambda post: post.post_type == "quote",
        lambda post: post.referenced_context is not None,
        lambda post: bool(post.media_metadata),
    )
    for predicate in predicates:
        candidate = next((post for post in ordered if predicate(post)), None)
        if candidate is not None:
            selected.setdefault(candidate.post_id, candidate)
            if len(selected) >= limit:
                return tuple(selected.values())

    def richness(post: NormalizedPost) -> tuple[int, datetime, str]:
        score = sum(
            (
                len(post.text) > 280,
                post.post_type == "reply",
                post.post_type == "quote",
                post.referenced_context is not None,
                bool(post.media_metadata),
            )
        )
        return score, post.created_at, post.post_id

    for post in sorted(ordered, key=richness, reverse=True):
        selected.setdefault(post.post_id, post)
        if len(selected) >= limit:
            break
    return tuple(selected.values())


def direct_id_selection_summary(
    selected: Sequence[NormalizedPost],
) -> dict[str, object]:
    unique = {post.post_id: post for post in selected}
    ids = sorted(unique)
    selection_digest = sha256("\n".join(ids).encode("utf-8")).hexdigest()
    return {
        "selected_post_ids": len(ids),
        "selection_sha256": selection_digest,
        "long_posts": sum(len(post.text) > 280 for post in unique.values()),
        "replies": sum(post.post_type == "reply" for post in unique.values()),
        "quotes": sum(post.post_type == "quote" for post in unique.values()),
        "with_referenced_context": sum(
            post.referenced_context is not None for post in unique.values()
        ),
        "with_media": sum(bool(post.media_metadata) for post in unique.values()),
        "official_x_external_requests": 0,
    }


def compare_direct_id_lookup(
    benchmark: Sequence[NormalizedPost],
    run: ProviderRun,
) -> dict[str, Any]:
    """Compare an offline direct-ID fixture or a future separately approved run."""
    report = compare_provider(benchmark, run)
    requested = len({post.post_id for post in benchmark})
    available = report["matched_benchmark_ids"]
    return {
        "mode": "direct_id",
        "requested_ids": requested,
        "available_ids": available,
        "unavailable_ids": requested - available,
        "availability_pct": _percentage(available, requested),
        "comparison": report,
    }


def _recommendation(reports: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    accepted: list[Mapping[str, Any]] = []
    for report in reports:
        acceptance = report.get("acceptance")
        if isinstance(acceptance, Mapping) and acceptance.get("accepted") is True:
            accepted.append(report)
    if not accepted:
        return {
            "best_provider": "none",
            "recommendation": (
                "No third-party provider is accepted from this run; retain Official X "
                "and resolve incomplete access or quality gaps before another bounded test."
            ),
        }
    accepted.sort(
        key=lambda item: (
            -float(item.get("recall_pct", 0)),
            Decimal(str(item.get("actual_spend_usd") or item.get("estimated_spend_usd"))),
        )
    )
    winner = str(accepted[0]["provider"])
    return {
        "best_provider": winner,
        "recommendation": (
            f"{winner} meets the raw shadow acceptance hypothesis. Keep Official X in "
            "production until a later explicit provider-integration decision and Task 006 "
            "relevant-Post recall validation."
        ),
    }


def plan_stored_discovery(
    *,
    hours: int,
    provider_names: Sequence[Literal["twitterapi_io", "socialdata"]],
    hard_cap_usd: Decimal,
    minimum_twitter_slice_seconds: int = DEFAULT_TWITTERAPI_IO_MINIMUM_SLICE_SECONDS,
) -> dict[str, object]:
    """Build a DB-read-only discovery preflight with no provider credentials or calls."""
    if hours < 1 or hours > 168:
        raise ValueError("hours must be between 1 and 168.")
    if not provider_names or any(
        provider not in {"twitterapi_io", "socialdata"}
        for provider in provider_names
    ):
        raise ValueError("provider_names must select twitterapi_io and/or socialdata.")
    official, start, end = fetch_stored_official_benchmark(hours=hours)
    benchmark = tuple({post.post_id: post for post in official.posts}.values())
    selected = tuple(dict.fromkeys(provider_names))
    plans = tuple(
        build_discovery_cost_plan(
            provider=provider,
            benchmark=benchmark,
            start=start,
            end=end,
            hard_cap_usd=hard_cap_usd,
            minimum_twitter_slice_seconds=minimum_twitter_slice_seconds,
        )
        for provider in selected
    )
    report = build_preflight_report(plans)
    report.update(
        {
            "mode": "discovery",
            "benchmark_source": "existing_postgresql_x_home_timeline",
            "benchmark_posts": len(benchmark),
            "benchmark_authors": len(
                {post.author.casefold() for post in benchmark}
            ),
            "window": {"start": start.isoformat(), "end": end.isoformat()},
        }
    )
    return report


def plan_stored_direct_id(
    *,
    hours: int,
    limit: int,
    provider_names: Sequence[Literal["twitterapi_io", "socialdata"]],
    hard_cap_usd: Decimal,
) -> dict[str, object]:
    """Select local IDs and build a planning-only direct lookup preflight."""
    if hours < 1 or hours > 168:
        raise ValueError("hours must be between 1 and 168.")
    if limit < 1 or limit > 50:
        raise ValueError("Direct-ID benchmark limit must be between 1 and 50.")
    if not provider_names or any(
        provider not in {"twitterapi_io", "socialdata"}
        for provider in provider_names
    ):
        raise ValueError("provider_names must select twitterapi_io and/or socialdata.")
    official, _, _ = fetch_stored_official_benchmark(hours=hours)
    selected_posts = select_direct_id_benchmark(official.posts, limit=limit)
    providers = tuple(dict.fromkeys(provider_names))
    plans = tuple(
        build_direct_id_cost_plan(
            provider=provider,
            benchmark=selected_posts,
            hard_cap_usd=hard_cap_usd,
        )
        for provider in providers
    )
    report = build_preflight_report(plans)
    report.update(
        {
            "mode": "direct_id",
            "benchmark_source": "existing_postgresql_x_home_timeline",
            "selection": direct_id_selection_summary(selected_posts),
            "direct_id_api_execution_implemented": False,
            "direct_id_api_calls": 0,
        }
    )
    return report


def run_shadow_spike(
    *,
    hours: int = 24,
    max_provider_spend_usd: Decimal = TRIAL_SPEND_LIMIT_USD,
    output_root: str | Path = "data/runtime/x-provider-shadow",
    official_benchmark_source: Literal["api", "stored"] = "stored",
    approved_provider_plan_sha256: str | None = None,
    minimum_twitter_slice_seconds: int = DEFAULT_TWITTERAPI_IO_MINIMUM_SLICE_SECONDS,
    provider_names: Sequence[Literal["twitterapi_io", "socialdata"]] = (
        "twitterapi_io",
        "socialdata",
    ),
) -> dict[str, Any]:
    if hours < 1 or hours > 168:
        raise ValueError("hours must be between 1 and 168.")
    if (
        max_provider_spend_usd <= 0
        or max_provider_spend_usd > TRIAL_SPEND_LIMIT_USD
    ):
        raise ValueError("max_provider_spend_usd must be positive and at most $0.10.")
    selected_provider_names = tuple(dict.fromkeys(provider_names))
    if not selected_provider_names or any(
        provider not in {"twitterapi_io", "socialdata"}
        for provider in selected_provider_names
    ):
        raise ValueError("provider_names must select twitterapi_io and/or socialdata.")
    if official_benchmark_source != "stored":
        raise ShadowSpikeError(
            "Task 004D.2 discovery execution requires a zero-cost stored Official X "
            "benchmark; fresh Official X is disabled in this runner."
        )
    official, start, end = fetch_stored_official_benchmark(hours=hours)
    unique_benchmark = tuple(
        {post.post_id: post for post in official.posts}.values()
    )
    plans = tuple(
        build_discovery_cost_plan(
            provider=provider,
            benchmark=unique_benchmark,
            start=start,
            end=end,
            hard_cap_usd=max_provider_spend_usd,
            minimum_twitter_slice_seconds=minimum_twitter_slice_seconds,
        )
        for provider in selected_provider_names
    )
    expected_combined_digest = combined_plan_sha256(plans)
    if approved_provider_plan_sha256 is None:
        raise ShadowSpikeError(
            "Provider discovery execution blocked: run zero-cost plan-discovery and "
            "obtain explicit approval first."
        )
    if approved_provider_plan_sha256 != expected_combined_digest:
        raise ShadowSpikeError(
            "Provider discovery execution blocked: approved combined plan digest "
            "does not match the current zero-cost plan."
        )
    if not all(plan.plan_fits_approved_limits for plan in plans):
        raise ShadowSpikeError(
            "Provider discovery execution blocked: the plan cannot cover every "
            "benchmark author within the approved request and spend limits."
        )
    keys = load_provider_keys()
    missing = [
        variable
        for provider, variable in (
            ("twitterapi_io", "TWITTERAPI_IO_API_KEY"),
            ("socialdata", "SOCIALDATA_API_KEY"),
        )
        if provider in selected_provider_names and not keys[provider]
    ]
    if missing:
        raise ShadowSpikeError(
            "Missing required local provider credentials: " + ", ".join(missing)
        )
    run_id = build_shadow_run_id(
        window_end=end,
        benchmark=unique_benchmark,
        combined_plan_digest=expected_combined_digest,
    )
    artifact_dir = Path(output_root) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    _write_json(
        artifact_dir / "window.json",
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "hours": hours,
            "benchmark_post_ids_sha256": _post_id_digest(unique_benchmark),
            "combined_plan_sha256": expected_combined_digest,
            "execution_identity": run_id.rsplit("-", 1)[-1],
        },
    )
    if not unique_benchmark:
        raise ShadowSpikeError("Official X benchmark returned no Posts for the window.")
    providers: tuple[SearchProvider, ...] = tuple(
        TwitterApiIoProvider(keys[name])
        if name == "twitterapi_io"
        else SocialDataProvider(keys[name])
        for name in selected_provider_names
    )
    plan_by_provider = {plan.provider: plan for plan in plans}
    third_party_runs = tuple(
        run_search_provider(
            provider,
            benchmark=unique_benchmark,
            start=start,
            end=end,
            spend_limit_usd=max_provider_spend_usd,
            artifact_dir=artifact_dir,
            approved_plan_sha256=plan_by_provider[provider.name].plan_sha256,
            minimum_twitter_slice_seconds=minimum_twitter_slice_seconds,
        )
        for provider in providers
    )
    official_report = {
        "provider": "official_x",
        "status": official.status,
        "posts_returned": len(official.posts),
        "unique_posts_returned": len(unique_benchmark),
        "active_authors": len({post.author.casefold() for post in unique_benchmark}),
        "requests": official.requests,
        "pagination_gaps": official.pagination_gaps,
        "estimated_spend_usd": format(official.estimated_spend_usd, "f"),
        "actual_spend_usd": (
            format(official.actual_spend_usd, "f")
            if official.actual_spend_usd is not None
            else None
        ),
        "warnings": list(official.warnings),
    }
    comparisons = [compare_provider(unique_benchmark, run) for run in third_party_runs]
    recommendation = _recommendation(comparisons)
    summary = {
        "task": "004D",
        "run_id": run_id,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "production_mutations": {
            "collector_changed": False,
            "database_writes": False,
            "sync_state_writes": False,
        },
        "official_benchmark": official_report,
        "providers": comparisons,
        "approved_provider_plan_sha256": approved_provider_plan_sha256,
        "provider_preflight": build_preflight_report(plans),
        **recommendation,
        "raw_artifacts": str(artifact_dir),
    }
    _write_json(artifact_dir / "summary.json", summary)
    return summary

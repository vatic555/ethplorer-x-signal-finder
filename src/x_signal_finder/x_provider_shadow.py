"""Isolated read-only X provider quality and cost spike for Task 004D."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import time
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

from x_signal_finder.config import load_database_config
from x_signal_finder.db.connection import connect_database
from x_signal_finder.x_api.client import XApiClient, parse_content_page
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
MAX_PROVIDER_PAGE_RESULTS = 20
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


@dataclass(frozen=True, repr=False)
class ProviderPage:
    posts: tuple[NormalizedPost, ...]
    raw_payload: Mapping[str, Any]
    has_more: bool

    def __repr__(self) -> str:
        return (
            f"ProviderPage(post_count={len(self.posts)}, has_more={self.has_more})"
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

    def __repr__(self) -> str:
        return (
            "ProviderRun(provider="
            f"{self.provider!r}, status={self.status!r}, "
            f"post_count={len(self.posts)}, requests={self.requests})"
        )


class SearchProvider(Protocol):
    name: ProviderName
    unit_cost_usd: Decimal

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


def _query_for(task: SearchTask) -> str:
    authors = " OR ".join(f"from:{author}" for author in task.authors)
    author_expression = authors if len(task.authors) == 1 else f"({authors})"
    return (
        f"{author_expression} since_time:{int(task.start.timestamp())} "
        f"until_time:{int(task.end.timestamp())}"
    )


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
        _, payload = _request_json(
            provider=self.name,
            url="https://api.socialdata.tools/twitter/search",
            headers=self._headers,
            params={"query": _query_for(task), "type": "Latest"},
        )
        raw_posts = payload.get("tweets", [])
        if not isinstance(raw_posts, list):
            raise ProviderRequestError(self.name, 200, "unexpected_response_shape")
        posts = tuple(
            normalize_socialdata_post(item)
            for item in raw_posts
            if isinstance(item, Mapping)
        )
        return ProviderPage(
            posts=posts,
            raw_payload=payload,
            has_more=bool(payload.get("next_cursor")),
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
    counts = Counter(post.author for post in benchmark)
    ordered = sorted(counts.items(), key=lambda item: (item[1], item[0].casefold()))
    return tuple(SearchTask((author,), start, end) for author, _ in ordered)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def run_search_provider(
    provider: SearchProvider,
    *,
    benchmark: Sequence[NormalizedPost],
    start: datetime,
    end: datetime,
    spend_limit_usd: Decimal,
    artifact_dir: Path,
) -> ProviderRun:
    if spend_limit_usd <= 0 or spend_limit_usd > TRIAL_SPEND_LIMIT_USD:
        raise ValueError("Provider spend limit must be positive and at most $0.10.")
    before_balance: Decimal | None
    try:
        before_balance = provider.balance_usd()
    except ProviderRequestError as error:
        if error.category in {"credit_exhausted", "invalid_credentials", "access_denied"}:
            status = {
                "credit_exhausted": "incomplete_due_to_credit",
                "invalid_credentials": "incomplete_due_to_auth",
                "access_denied": "incomplete_due_to_access",
            }[error.category]
            return ProviderRun(
                provider=provider.name,
                status=status,
                posts=(),
                requests=0,
                pagination_gaps=0,
                estimated_spend_usd=Decimal("0"),
                actual_spend_usd=Decimal("0"),
                warnings=(f"{error.category}_before_search",),
            )
        raise
    effective_limit = min(
        spend_limit_usd,
        before_balance if before_balance is not None else spend_limit_usd,
    )
    queue = deque(plan_search_tasks(benchmark, start=start, end=end))
    posts: list[NormalizedPost] = []
    requests = 0
    pagination_gaps = 0
    estimated_spend = Decimal("0")
    warnings: set[str] = set()
    status = "complete"
    worst_case_request = MAX_PROVIDER_PAGE_RESULTS * provider.unit_cost_usd
    last_request_started: float | None = None
    while queue:
        if estimated_spend + worst_case_request > effective_limit:
            status = (
                "incomplete_due_to_credit"
                if before_balance is not None and before_balance < spend_limit_usd
                else "incomplete_due_to_budget"
            )
            warnings.add("provider_spend_guard_reached")
            break
        task = queue.popleft()
        minimum_interval = float(
            getattr(provider, "minimum_interval_seconds", 0.0)
        )
        if last_request_started is not None and minimum_interval > 0:
            remaining_wait = minimum_interval - (time.monotonic() - last_request_started)
            if remaining_wait > 0:
                time.sleep(remaining_wait)
        rate_limit_retries = 0
        request_error: ProviderRequestError | None = None
        while True:
            try:
                last_request_started = time.monotonic()
                page = provider.search(task)
                request_error = None
                break
            except ProviderRequestError as error:
                if (
                    error.category == "rate_limited"
                    and rate_limit_retries
                    < int(getattr(provider, "max_rate_limit_retries", 0))
                ):
                    rate_limit_retries += 1
                    warnings.add("provider_rate_limit_retry_used")
                    time.sleep(
                        float(
                            getattr(
                                provider,
                                "rate_limit_retry_wait_seconds",
                                0.0,
                            )
                        )
                    )
                    continue
                request_error = error
                break
        if request_error is not None:
            if request_error.category == "credit_exhausted":
                status = "incomplete_due_to_credit"
                warnings.add("credit_exhausted")
                break
            if request_error.category == "access_denied":
                status = "incomplete_due_to_access"
                warnings.add("provider_endpoint_access_denied")
                break
            if request_error.category == "invalid_credentials":
                status = "incomplete_due_to_auth"
                warnings.add("provider_credentials_rejected")
                break
            if request_error.category == "rate_limited":
                status = "incomplete_due_to_rate_limit"
                warnings.add("provider_rate_limit_reached")
                break
            raise request_error
        requests += 1
        _write_json(
            artifact_dir / provider.name / f"response-{requests:04d}.json",
            page.raw_payload,
        )
        posts.extend(page.posts)
        page_cost = provider.unit_cost_usd * max(1, len(page.posts))
        if not page.posts:
            warnings.add("empty_request_minimum_charge_estimated")
        estimated_spend += page_cost
        if page.has_more:
            pagination_gaps += 1
            warnings.add("provider_page_overflow_not_followed")
            warnings.add("unresolved_pagination_gap")
    after_balance = None
    if before_balance is not None:
        try:
            after_balance = provider.balance_usd()
        except ProviderRequestError:
            warnings.add("post_run_balance_unavailable")
    actual_spend = (
        max(Decimal("0"), before_balance - after_balance)
        if before_balance is not None and after_balance is not None
        else None
    )
    if actual_spend is not None and actual_spend > spend_limit_usd:
        raise ShadowSpikeError("Provider reported spend exceeded the hard $0.10 limit.")
    return ProviderRun(
        provider=provider.name,
        status=status,
        posts=tuple(posts),
        requests=requests,
        pagination_gaps=pagination_gaps,
        estimated_spend_usd=estimated_spend,
        actual_spend_usd=actual_spend,
        warnings=tuple(sorted(warnings)),
    )


def fetch_official_benchmark(
    *,
    start: datetime,
    end: datetime,
    max_pages: int,
    artifact_dir: Path,
) -> ProviderRun:
    if max_pages < 1:
        raise ValueError("max_official_pages must be at least 1.")
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
        "max_results": 100,
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
    warnings: set[str] = set()
    status = "complete"
    while requests < max_pages:
        params = dict(base_params)
        if token:
            params["pagination_token"] = token
        response, elapsed = client._get(endpoint, params)
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
        expanded_ids.update(page.expanded_posts_by_id)
        user_ids.update(page.users_by_id)
        media_keys.update(page.media_by_key)
        if page.partial_error_count:
            warnings.add("official_x_partial_errors_present")
        token = page.next_token
        if not token:
            break
    if token:
        status = "incomplete_due_to_page_limit"
        warnings.add("official_x_page_limit_reached")
    resources = primary_ids | expanded_ids
    estimated_spend = (
        OFFICIAL_X_POST_READ_COST_USD * len(resources)
        + OFFICIAL_X_USER_READ_COST_USD * len(user_ids)
        + OFFICIAL_X_MEDIA_READ_COST_USD * len(media_keys)
    )
    warnings.add("official_x_cost_includes_returned_post_user_and_media_resources")
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


def compare_provider(
    benchmark: Sequence[NormalizedPost],
    run: ProviderRun,
) -> dict[str, Any]:
    benchmark_by_id = {post.post_id: post for post in benchmark}
    provider_by_id: dict[str, NormalizedPost] = {}
    duplicate_count = 0
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
    exact_text = sum(expected.text == actual.text for expected, actual in matched_pairs)
    missing_text = sum(not actual.text for _, actual in matched_pairs)
    long_ids = {
        post_id for post_id, post in benchmark_by_id.items() if len(post.text) > 280
    }
    matched_long_ids = long_ids & matched_ids
    exact_long_text = sum(
        benchmark_by_id[post_id].text == provider_by_id[post_id].text
        for post_id in matched_long_ids
    )
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
    systematic: list[str] = []
    if long_ids and _percentage(len(matched_long_ids), len(long_ids)) is not None:
        if len(matched_long_ids) < len(long_ids):
            systematic.append("long_post_recall_below_100")
    for post_type in ("reply", "quote", "repost"):
        typed_recall = recall_by_type[post_type]
        if benchmark_by_type[post_type] and typed_recall is not None and recall is not None:
            if typed_recall + 10 < recall:
                systematic.append(f"{post_type}_recall_materially_below_overall")
    if exact_text < len(matched_ids):
        systematic.append("matched_post_text_not_100_percent_exact")
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
        "full_text": {
            "exact_matches": exact_text,
            "matched_posts": len(matched_ids),
            "exact_pct": _percentage(exact_text, len(matched_ids)),
            "missing_text": missing_text,
        },
        "long_posts": {
            "benchmark": len(long_ids),
            "matched": len(matched_long_ids),
            "recall_pct": _percentage(len(matched_long_ids), len(long_ids)),
            "exact_text": exact_long_text,
            "exact_text_pct": _percentage(exact_long_text, len(matched_long_ids)),
            "truncated_or_mismatched": len(matched_long_ids) - exact_long_text,
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
        "warnings": list(run.warnings),
    }


def _recommendation(reports: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    accepted: list[Mapping[str, Any]] = []
    for report in reports:
        if report.get("status") != "complete":
            continue
        recall = report.get("recall_pct")
        full_text = report.get("full_text")
        systematic = report.get("systematic_loss_flags")
        if (
            isinstance(recall, (int, float))
            and recall >= 90
            and isinstance(full_text, Mapping)
            and full_text.get("exact_pct") == 100.0
            and not systematic
        ):
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


def run_shadow_spike(
    *,
    hours: int = 24,
    max_provider_spend_usd: Decimal = TRIAL_SPEND_LIMIT_USD,
    max_official_pages: int = 20,
    output_root: str | Path = "data/runtime/x-provider-shadow",
    window_end: str | None = None,
    official_benchmark_source: Literal["api", "stored"] = "api",
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
    if official_benchmark_source == "stored":
        if window_end is not None:
            raise ValueError("window_end cannot be used with a stored benchmark.")
        official, start, end = fetch_stored_official_benchmark(hours=hours)
    else:
        end = parse_window_end(window_end)
        start = end - timedelta(hours=hours)
    run_id = end.strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = Path(output_root) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    _write_json(
        artifact_dir / "window.json",
        {"start": start.isoformat(), "end": end.isoformat(), "hours": hours},
    )
    if official_benchmark_source == "api":
        official = fetch_official_benchmark(
            start=start,
            end=end,
            max_pages=max_official_pages,
            artifact_dir=artifact_dir,
        )
    unique_benchmark = tuple(
        {post.post_id: post for post in official.posts}.values()
    )
    if not unique_benchmark:
        raise ShadowSpikeError("Official X benchmark returned no Posts for the window.")
    providers: tuple[SearchProvider, ...] = tuple(
        TwitterApiIoProvider(keys[name])
        if name == "twitterapi_io"
        else SocialDataProvider(keys[name])
        for name in selected_provider_names
    )
    third_party_runs = tuple(
        run_search_provider(
            provider,
            benchmark=unique_benchmark,
            start=start,
            end=end,
            spend_limit_usd=max_provider_spend_usd,
            artifact_dir=artifact_dir,
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
        **recommendation,
        "raw_artifacts": str(artifact_dir),
    }
    _write_json(artifact_dir / "summary.json", summary)
    return summary

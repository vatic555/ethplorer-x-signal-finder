"""Small standard-library HTTP client for read-only X API diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RATE_LIMIT_HEADERS = (
    "x-rate-limit-limit",
    "x-rate-limit-remaining",
    "x-rate-limit-reset",
)

_BEARER = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+")
_TOKEN_ASSIGNMENT = re.compile(
    r"(?i)(access_token|refresh_token|bearer_token|client_secret)(\s*[:=]\s*)[^\s,;&]+"
)


def redact_x_secrets(value: object, secrets: tuple[str, ...] = ()) -> str:
    """Redact common X credential forms and any explicitly supplied secrets."""
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    text = _BEARER.sub(r"\1<redacted>", text)
    return _TOKEN_ASSIGNMENT.sub(r"\1\2<redacted>", text)


@dataclass(frozen=True)
class HttpResponse:
    """Transport-neutral HTTP response used by production and mocked tests."""

    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, Mapping[str, str], float], HttpResponse]


@dataclass(frozen=True)
class XApiPage:
    """Safe subset of an X response, intentionally excluding post content."""

    status: int
    post_ids: tuple[str, ...]
    next_token: str | None
    newest_id: str | None
    oldest_id: str | None
    metadata_keys: tuple[str, ...]
    post_field_keys: tuple[str, ...]
    rate_limits: Mapping[str, str]
    partial_error_count: int
    elapsed_seconds: float
    meta_present: bool


@dataclass(frozen=True, repr=False)
class XApiContentPage:
    """Validated collector page whose representation never exposes X Content."""

    status: int
    posts: tuple[dict[str, Any], ...]
    users_by_id: Mapping[str, Mapping[str, Any]]
    expanded_posts_by_id: Mapping[str, Mapping[str, Any]]
    media_by_key: Mapping[str, Mapping[str, Any]]
    next_token: str | None
    newest_id: str | None
    oldest_id: str | None
    rate_limits: Mapping[str, str]
    partial_error_count: int
    elapsed_seconds: float
    meta_present: bool

    def __repr__(self) -> str:
        return (
            "XApiContentPage(status="
            f"{self.status}, post_count={len(self.posts)}, "
            f"user_count={len(self.users_by_id)}, "
            f"expanded_post_count={len(self.expanded_posts_by_id)}, "
            f"media_count={len(self.media_by_key)}, "
            f"next_token_present={bool(self.next_token)}, "
            f"partial_error_count={self.partial_error_count})"
        )

    __str__ = __repr__


class XApiRequestError(RuntimeError):
    """Safe X API failure without response bodies or credentials."""

    def __init__(
        self,
        *,
        status: int | None,
        category: str,
        endpoint: str,
        rate_limits: Mapping[str, str] | None = None,
    ) -> None:
        self.status = status
        self.category = category
        self.endpoint = endpoint
        self.rate_limits = dict(rate_limits or {})
        status_text = str(status) if status is not None else "unavailable"
        super().__init__(f"X API request failed ({category}, HTTP {status_text}).")

    def safe_diagnostic(self) -> dict[str, object]:
        return {
            "endpoint": self.endpoint,
            "http_result": self.status,
            "error_category": self.category,
            "rate_limits": self.rate_limits,
        }


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except HTTPError as error:
        return HttpResponse(
            status=error.code,
            headers=dict(error.headers.items()) if error.headers else {},
            body=error.read(),
        )
    except (URLError, TimeoutError, OSError) as error:
        raise XApiRequestError(
            status=None,
            category="connection_error",
            endpoint=url.split("?", 1)[0],
        ) from error


def parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Extract only documented X rate-limit headers, case-insensitively."""
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        name: normalized[name]
        for name in RATE_LIMIT_HEADERS
        if name in normalized
    }


def _error_category(status: int, payload: object) -> str:
    error_type = ""
    if isinstance(payload, dict):
        error_type = str(payload.get("type", "")).lower()
        errors = payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            error_type += " " + str(errors[0].get("type", "")).lower()
    if status == 401:
        return "expired_or_invalid_token"
    if status == 403:
        return "insufficient_scope_or_access"
    if status == 429 or "rate-limit" in error_type or "usage-capped" in error_type:
        return "rate_limit_or_usage_cap"
    return "api_error"


def _decode_payload(
    response: HttpResponse,
    *,
    endpoint: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    rate_limits = parse_rate_limit_headers(response.headers)
    try:
        payload: Any = json.loads(response.body.decode("utf-8")) if response.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        ) from error

    if response.status < 200 or response.status >= 300:
        raise XApiRequestError(
            status=response.status,
            category=_error_category(response.status, payload),
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    if not isinstance(payload, dict):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    return payload, rate_limits


def parse_page(response: HttpResponse, *, endpoint: str, elapsed: float) -> XApiPage:
    """Parse a response into a safe diagnostic page or a redacted failure."""
    payload, rate_limits = _decode_payload(response, endpoint=endpoint)

    data = payload.get("data", [])
    meta_present = "meta" in payload
    meta = payload.get("meta", {})
    errors = payload.get("errors", [])
    if not isinstance(data, list) or not isinstance(meta, dict):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )

    post_ids: list[str] = []
    field_keys: set[str] = set()
    for post in data:
        if not isinstance(post, dict) or not isinstance(post.get("id"), str):
            raise XApiRequestError(
                status=response.status,
                category="unexpected_response_shape",
                endpoint=endpoint,
                rate_limits=rate_limits,
            )
        post_ids.append(post["id"])
        field_keys.update(str(key) for key in post)

    next_token = meta.get("next_token")
    if next_token is not None and not isinstance(next_token, str):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    newest_id = meta.get("newest_id") or (post_ids[0] if post_ids else None)
    oldest_id = meta.get("oldest_id") or (post_ids[-1] if post_ids else None)
    return XApiPage(
        status=response.status,
        post_ids=tuple(post_ids),
        next_token=next_token,
        newest_id=str(newest_id) if newest_id is not None else None,
        oldest_id=str(oldest_id) if oldest_id is not None else None,
        metadata_keys=tuple(sorted(str(key) for key in meta)),
        post_field_keys=tuple(sorted(field_keys)),
        rate_limits=rate_limits,
        partial_error_count=len(errors) if isinstance(errors, list) else 0,
        elapsed_seconds=elapsed,
        meta_present=meta_present,
    )


def parse_content_page(
    response: HttpResponse,
    *,
    endpoint: str,
    elapsed: float,
) -> XApiContentPage:
    """Parse a collector page without exposing response content in diagnostics."""
    payload, rate_limits = _decode_payload(response, endpoint=endpoint)
    data = payload.get("data", [])
    meta_present = "meta" in payload
    meta = payload.get("meta", {})
    includes = payload.get("includes", {})
    errors = payload.get("errors", [])
    if (
        not isinstance(data, list)
        or not isinstance(meta, dict)
        or not isinstance(includes, dict)
    ):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )

    posts: list[dict[str, Any]] = []
    for post in data:
        if not isinstance(post, dict) or not isinstance(post.get("id"), str):
            raise XApiRequestError(
                status=response.status,
                category="unexpected_response_shape",
                endpoint=endpoint,
                rate_limits=rate_limits,
            )
        posts.append(dict(post))

    users = includes.get("users", [])
    if not isinstance(users, list):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    users_by_id: dict[str, Mapping[str, Any]] = {}
    for user in users:
        if not isinstance(user, dict) or not isinstance(user.get("id"), str):
            raise XApiRequestError(
                status=response.status,
                category="unexpected_response_shape",
                endpoint=endpoint,
                rate_limits=rate_limits,
            )
        users_by_id[user["id"]] = dict(user)

    expanded_posts = includes.get("tweets", [])
    if not isinstance(expanded_posts, list):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    expanded_posts_by_id: dict[str, Mapping[str, Any]] = {}
    for post in expanded_posts:
        if not isinstance(post, dict) or not isinstance(post.get("id"), str):
            raise XApiRequestError(
                status=response.status,
                category="unexpected_response_shape",
                endpoint=endpoint,
                rate_limits=rate_limits,
            )
        expanded_posts_by_id[post["id"]] = dict(post)

    media = includes.get("media", [])
    if not isinstance(media, list):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    media_by_key: dict[str, Mapping[str, Any]] = {}
    for media_object in media:
        if not isinstance(media_object, dict) or not isinstance(
            media_object.get("media_key"), str
        ):
            raise XApiRequestError(
                status=response.status,
                category="unexpected_response_shape",
                endpoint=endpoint,
                rate_limits=rate_limits,
            )
        media_by_key[media_object["media_key"]] = dict(media_object)

    next_token = meta.get("next_token")
    if next_token is not None and not isinstance(next_token, str):
        raise XApiRequestError(
            status=response.status,
            category="unexpected_response_shape",
            endpoint=endpoint,
            rate_limits=rate_limits,
        )
    post_ids = tuple(str(post["id"]) for post in posts)
    newest_id = meta.get("newest_id") or (post_ids[0] if post_ids else None)
    oldest_id = meta.get("oldest_id") or (post_ids[-1] if post_ids else None)
    return XApiContentPage(
        status=response.status,
        posts=tuple(posts),
        users_by_id=users_by_id,
        expanded_posts_by_id=expanded_posts_by_id,
        media_by_key=media_by_key,
        next_token=next_token,
        newest_id=str(newest_id) if newest_id is not None else None,
        oldest_id=str(oldest_id) if oldest_id is not None else None,
        rate_limits=rate_limits,
        partial_error_count=len(errors) if isinstance(errors, list) else 0,
        elapsed_seconds=elapsed,
        meta_present=meta_present,
    )


class XApiClient:
    """Read-only X client with explicit diagnostic and collector result paths."""

    def __init__(
        self,
        *,
        token: str,
        base_url: str = "https://api.x.com/2",
        timeout: float = 20.0,
        transport: Transport | None = None,
    ) -> None:
        if not token:
            raise ValueError("An X API token is required.")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport or _default_transport

    def get_page(self, endpoint: str, params: Mapping[str, object]) -> XApiPage:
        response, elapsed = self._get(endpoint, params)
        return parse_page(response, endpoint=endpoint, elapsed=elapsed)

    def get_content_page(
        self,
        endpoint: str,
        params: Mapping[str, object],
    ) -> XApiContentPage:
        response, elapsed = self._get(endpoint, params)
        return parse_content_page(response, endpoint=endpoint, elapsed=elapsed)

    def _get(
        self,
        endpoint: str,
        params: Mapping[str, object],
    ) -> tuple[HttpResponse, float]:
        query = urlencode(
            [(key, str(value)) for key, value in params.items() if value is not None]
        )
        url = f"{self._base_url}{endpoint}"
        if query:
            url = f"{url}?{query}"
        started = time.monotonic()
        response = self._transport(
            url,
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "ethplorer-x-signal-finder/0.1",
            },
            self._timeout,
        )
        elapsed = time.monotonic() - started
        return response, elapsed

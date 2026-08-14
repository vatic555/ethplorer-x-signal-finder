from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pytest

from x_signal_finder.x_api.client import (
    HttpResponse,
    XApiClient,
    XApiRequestError,
    parse_content_page,
    parse_page,
    parse_rate_limit_headers,
    redact_x_secrets,
)
from x_signal_finder.x_api.probe import classify_checkpoint, run_probe


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _transport_from(*responses: HttpResponse):
    queue = list(responses)

    def transport(
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        assert url.startswith("https://api.x.com/2/users/")
        assert headers["Authorization"] == "Bearer synthetic-secret-token"
        assert timeout == 20.0
        return queue.pop(0)

    return transport


def _response(fixture: str, status: int = 200) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={
            "X-Rate-Limit-Limit": "180",
            "x-rate-limit-remaining": "179",
            "x-rate-limit-reset": "1900000000",
        },
        body=_fixture(fixture),
    )


def test_response_and_rate_limit_parsing() -> None:
    page = parse_page(_response("x_api_page_1.json"), endpoint="/synthetic", elapsed=0.1)

    assert page.post_ids == ("300", "200")
    assert page.next_token == "synthetic-next-token"
    assert page.metadata_keys == (
        "newest_id",
        "next_token",
        "oldest_id",
        "result_count",
    )
    assert page.post_field_keys == ("author_id", "created_at", "id", "text")
    assert page.rate_limits["x-rate-limit-remaining"] == "179"
    assert parse_rate_limit_headers({"Unrelated": "value"}) == {}


def test_content_parser_keeps_expanded_maps_and_has_content_safe_repr() -> None:
    body = json.dumps(
        {
            "data": [{"id": "1", "text": "sensitive main text"}],
            "includes": {
                "users": [{"id": "10", "username": "author"}],
                "tweets": [{"id": "2", "text": "sensitive referenced text"}],
                "media": [{"media_key": "m1", "type": "video"}],
            },
            "meta": {"newest_id": "1", "oldest_id": "1"},
        }
    ).encode()
    page = parse_content_page(
        HttpResponse(status=200, headers={}, body=body),
        endpoint="/synthetic",
        elapsed=0.0,
    )

    assert page.expanded_posts_by_id["2"]["text"] == "sensitive referenced text"
    assert page.media_by_key["m1"]["type"] == "video"
    rendered = repr(page)
    assert "sensitive main text" not in rendered
    assert "sensitive referenced text" not in rendered
    assert "expanded_post_count=1" in rendered
    assert "media_count=1" in rendered


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            {
                "resource_id": "404",
                "title": "Not Found Error",
                "detail": "sensitive response detail",
            },
            "not_found",
        ),
        (
            {
                "resource_id": "403",
                "title": "Authorization Error",
                "detail": "This resource is protected",
            },
            "protected_or_inaccessible",
        ),
        (
            {"resource_id": "500", "status": 503, "detail": "sensitive"},
            "api_unavailable",
        ),
        ({"resource_id": "0", "detail": "sensitive"}, "unknown"),
    ],
)
def test_content_parser_reduces_resource_errors_without_retaining_body(
    error, expected
) -> None:
    body = json.dumps({"data": [], "includes": {}, "meta": {}, "errors": [error]}).encode()
    page = parse_content_page(
        HttpResponse(status=200, headers={}, body=body),
        endpoint="/synthetic",
        elapsed=0.0,
    )

    assert page.resource_error_categories_by_id[error["resource_id"]] == expected
    assert "sensitive" not in repr(page)


def test_pagination_checkpoint_and_duplicates_are_reported() -> None:
    client = XApiClient(
        token="synthetic-secret-token",
        transport=_transport_from(
            _response("x_api_page_1.json"),
            _response("x_api_page_2.json"),
        ),
    )

    summary = run_probe(
        client=client,
        source="home",
        user_id="123",
        checkpoint_id="100",
    )

    assert summary.pages_requested == 2
    assert summary.post_count == 4
    assert summary.newest_post_id == "300"
    assert summary.oldest_post_id == "100"
    assert summary.checkpoint_status == "checkpoint_reached"
    assert summary.duplicate_ids == ("200",)
    assert "duplicate_post_ids_detected" in summary.limitations
    assert "Synthetic" not in json.dumps(summary.safe_diagnostic())


def test_page_limit_reports_checkpoint_not_reached() -> None:
    client = XApiClient(
        token="synthetic-secret-token",
        transport=_transport_from(_response("x_api_page_1.json")),
    )

    summary = run_probe(
        client=client,
        source="mentions",
        user_id="123",
        max_pages=1,
        checkpoint_id="100",
    )

    assert summary.checkpoint_status == "checkpoint_not_reached"
    assert summary.next_page_token_present is True
    assert "probe_page_limit_reached" in summary.limitations


def test_repeated_first_page_compares_only_ids() -> None:
    client = XApiClient(
        token="synthetic-secret-token",
        transport=_transport_from(
            _response("x_api_page_1.json"),
            _response("x_api_page_1.json"),
        ),
    )

    summary = run_probe(
        client=client,
        source="home",
        user_id="123",
        max_pages=1,
        repeat_first_page=True,
    )

    assert summary.pages_requested == 2
    assert summary.http_results == (200, 200)
    assert summary.repeated_first_page_matches is True


def test_checkpoint_terminal_states() -> None:
    assert (
        classify_checkpoint(
            checkpoint_id="100",
            seen_ids=("300",),
            meta_present=True,
            next_token_present=False,
            page_limit_reached=False,
        )
        == "api_window_exhausted"
    )
    assert (
        classify_checkpoint(
            checkpoint_id="100",
            seen_ids=(),
            meta_present=False,
            next_token_present=False,
            page_limit_reached=False,
        )
        == "pagination_unavailable"
    )
    assert (
        classify_checkpoint(
            checkpoint_id="100",
            seen_ids=(),
            meta_present=True,
            next_token_present=False,
            page_limit_reached=False,
            request_failed=True,
        )
        == "request_failed"
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "expired_or_invalid_token"),
        (403, "insufficient_scope_or_access"),
        (429, "rate_limit_or_usage_cap"),
        (500, "api_error"),
    ],
)
def test_api_errors_are_classified_without_body(status: int, expected: str) -> None:
    error_type = (
        "https://api.x.com/2/problems/rate-limit-exceeded"
        if status == 429
        else "https://api.x.com/2/problems/synthetic"
    )
    body = json.dumps(
        {
            "title": "Synthetic error",
            "detail": "Bearer synthetic-secret-token",
            "type": error_type,
        }
    ).encode()

    with pytest.raises(XApiRequestError) as raised:
        parse_page(
            HttpResponse(status=status, headers={}, body=body),
            endpoint="/synthetic",
            elapsed=0.0,
        )

    assert raised.value.category == expected
    assert "synthetic-secret-token" not in str(raised.value)
    assert "detail" not in raised.value.safe_diagnostic()


def test_unexpected_response_shape_is_rejected() -> None:
    with pytest.raises(XApiRequestError, match="unexpected_response_shape"):
        parse_page(
            HttpResponse(status=200, headers={}, body=b'{"data": {"id": "1"}}'),
            endpoint="/synthetic",
            elapsed=0.0,
        )


def test_secret_redaction() -> None:
    secret = "synthetic-secret-token"
    rendered = redact_x_secrets(
        f"Authorization: Bearer {secret}; access_token={secret}",
        (secret,),
    )

    assert secret not in rendered
    assert rendered.count("<redacted>") >= 1

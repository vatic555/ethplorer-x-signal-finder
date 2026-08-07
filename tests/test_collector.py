from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID

import pytest

from x_signal_finder.collector import (
    CollectionError,
    FetchedSource,
    fetch_source,
    map_x_post,
    record_failed_source_attempt,
    record_source_usage,
    save_source_collection,
)
from x_signal_finder.x_api.client import HttpResponse, XApiClient, XApiRequestError


FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = UUID("00000000-0000-0000-0000-000000000001")
USAGE_ID = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _collector_response() -> HttpResponse:
    return HttpResponse(
        status=200,
        headers={"X-Rate-Limit-Limit": "180"},
        body=(FIXTURES / "x_api_collector_page.json").read_bytes(),
    )


def _page_response(
    post_ids=(),
    *,
    next_token=None,
    expanded_ids=(),
    errors=(),
    status=200,
    headers=None,
) -> HttpResponse:
    posts = [
        {
            "id": str(post_id),
            "text": f"synthetic-{post_id}",
            "created_at": "2026-01-01T00:00:00Z",
        }
        for post_id in post_ids
    ]
    meta = {}
    if posts:
        meta.update(newest_id=posts[0]["id"], oldest_id=posts[-1]["id"])
    if next_token is not None:
        meta["next_token"] = next_token
    payload = {
        "data": posts,
        "includes": {
            "tweets": [
                {"id": str(post_id), "text": f"expanded-{post_id}"}
                for post_id in expanded_ids
            ]
        },
        "meta": meta,
    }
    if errors:
        payload["errors"] = list(errors)
    return HttpResponse(
        status=status,
        headers=headers or {},
        body=json.dumps(payload).encode(),
    )


def _client_from(*responses):
    queue = list(responses)

    def transport(url, headers, timeout):
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return XApiClient(token="synthetic-secret-token", transport=transport)


def _fetch(source="home", checkpoint=None, refresh_existing=False) -> FetchedSource:
    def transport(url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        assert headers["Authorization"] == "Bearer synthetic-secret-token"
        if source == "home":
            assert "exclude=retweets" in url
        if checkpoint and not refresh_existing:
            assert f"since_id={checkpoint}" in url
        if refresh_existing:
            assert "since_id=" not in url
            if checkpoint:
                assert f"until_id={checkpoint}" in url
        return _collector_response()

    return fetch_source(
        client=XApiClient(token="synthetic-secret-token", transport=transport),
        source=source,
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=checkpoint,
        max_pages=1,
        max_results=20,
        refresh_existing=refresh_existing,
    )


class FakeRepository:
    def __init__(self, existing=(), fail_upsert=False) -> None:
        self.existing = frozenset(existing)
        self.fail_upsert = fail_upsert
        self.saved = []
        self.sync_updates = []
        self.usage = []

    def get_existing_post_ids(self, post_ids):
        return self.existing.intersection(post_ids)

    def upsert_posts(self, posts):
        if self.fail_upsert:
            raise RuntimeError("synthetic write failure")
        self.saved.extend(posts)

    def update_sync_state(self, **values):
        self.sync_updates.append(values)

    def record_usage_event(self, event):
        self.usage.append(event)


def test_mapping_excludes_reposts_and_keeps_original_reply_and_quote() -> None:
    fetched = _fetch()

    assert fetched.fetched_posts == 4
    assert fetched.reposts_excluded == 1
    assert [record["post_type"] for record in fetched.records] == [
        "original",
        "reply",
        "quote",
    ]
    assert [record["post_id"] for record in fetched.records] == ["400", "200", "100"]
    assert fetched.records[0]["author_username"] == "synthetic_original"
    assert fetched.records[1]["referenced_post_id"] == "100"
    assert fetched.records[2]["referenced_post_id"] == "50"


def test_source_keys_are_independent() -> None:
    post = {
        "id": "1",
        "text": "Synthetic content.",
        "author_id": "10",
        "created_at": "2026-01-01T00:00:00Z",
    }
    home = map_x_post(
        post,
        users_by_id={},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )
    mentions = map_x_post(
        post,
        users_by_id={},
        source="mentions",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert home is not None and home["source_key"] == "x_home_timeline"
    assert mentions is not None and mentions["source_key"] == "x_ethplorer_mentions"


def _synthetic_post(**overrides):
    post = {
        "id": "1",
        "text": "truncated text",
        "author_id": "10",
        "created_at": "2026-01-01T00:00:00Z",
        "conversation_id": "1",
    }
    post.update(overrides)
    return post


def test_note_tweet_text_has_priority_and_original_json_is_preserved() -> None:
    post = _synthetic_post(note_tweet={"text": "complete long-form text"})
    record = map_x_post(
        post,
        users_by_id={},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert record is not None
    assert record["text"] == "complete long-form text"
    assert record["raw_json"]["text"] == "truncated text"
    assert record["raw_json"]["note_tweet"] == {
        "text": "complete long-form text"
    }
    assert record["raw_json"]["_collector"]["full_text_source"] == "note_tweet"


def test_missing_note_tweet_uses_regular_text() -> None:
    record = map_x_post(
        _synthetic_post(text="regular complete text"),
        users_by_id={},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert record is not None
    assert record["text"] == "regular complete text"
    assert record["raw_json"]["_collector"]["full_text_source"] == "text"


@pytest.mark.parametrize("note_tweet", ["invalid", {"text": 123}])
def test_malformed_note_tweet_is_rejected_safely(note_tweet) -> None:
    with pytest.raises(CollectionError, match="note_tweet"):
        map_x_post(
            _synthetic_post(note_tweet=note_tweet),
            users_by_id={},
            source="home",
            run_id=RUN_ID,
            collected_at=NOW,
        )


@pytest.mark.parametrize(
    ("relationship", "expected_type"),
    [("quoted", "quote"), ("replied_to", "reply")],
)
def test_referenced_post_and_author_are_preserved_with_full_text(
    relationship, expected_type
) -> None:
    referenced = {
        "id": "2",
        "text": "referenced truncated",
        "note_tweet": {"text": "referenced complete long-form text"},
        "author_id": "20",
    }
    record = map_x_post(
        _synthetic_post(
            referenced_tweets=[{"type": relationship, "id": "2"}],
        ),
        users_by_id={"20": {"id": "20", "username": "referenced_author"}},
        expanded_posts_by_id={"2": referenced},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert record is not None
    assert record["post_type"] == expected_type
    assert record["referenced_post_id"] == "2"
    expanded = record["raw_json"]["_expanded"]
    assert expanded["referenced_post"]["note_tweet"]["text"] == (
        "referenced complete long-form text"
    )
    assert expanded["referenced_post_author"] == {
        "id": "20",
        "username": "referenced_author",
    }


def test_missing_referenced_expansion_or_author_is_nonfatal() -> None:
    without_post = map_x_post(
        _synthetic_post(referenced_tweets=[{"type": "quoted", "id": "2"}]),
        users_by_id={},
        expanded_posts_by_id={},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )
    without_author = map_x_post(
        _synthetic_post(referenced_tweets=[{"type": "quoted", "id": "2"}]),
        users_by_id={},
        expanded_posts_by_id={"2": {"id": "2", "text": "context"}},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert without_post is not None
    assert "_expanded" not in without_post["raw_json"]
    assert without_author is not None
    assert "referenced_post_author" not in without_author["raw_json"]["_expanded"]


@pytest.mark.parametrize(
    ("media_type", "expected_video"),
    [("video", True), ("animated_gif", True), ("photo", False)],
)
def test_media_metadata_is_preserved_for_review(media_type, expected_video) -> None:
    record = map_x_post(
        _synthetic_post(attachments={"media_keys": ["m1"]}),
        users_by_id={},
        media_by_key={"m1": {"media_key": "m1", "type": media_type}},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert record is not None
    media = record["raw_json"]["_expanded"]["media"]
    assert media == [{"media_key": "m1", "type": media_type}]
    assert (media[0]["type"] in {"video", "animated_gif"}) is expected_video


def test_multiple_media_and_missing_expansion_are_nonfatal() -> None:
    multiple = map_x_post(
        _synthetic_post(attachments={"media_keys": ["m1", "m2"]}),
        users_by_id={},
        media_by_key={
            "m1": {"media_key": "m1", "type": "photo"},
            "m2": {"media_key": "m2", "type": "video"},
        },
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )
    incomplete = map_x_post(
        _synthetic_post(attachments={"media_keys": ["missing"]}),
        users_by_id={},
        media_by_key={},
        source="home",
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert multiple is not None
    assert len(multiple["raw_json"]["_expanded"]["media"]) == 2
    assert incomplete is not None
    assert incomplete["raw_json"]["_expanded"]["media"] == []
    assert incomplete["raw_json"]["_collector"]["media_expansion_incomplete"] is True
    assert incomplete["raw_json"]["_collector"]["missing_media_count"] == 1


def test_deduplication_counts_and_successful_checkpoint_update() -> None:
    repository = FakeRepository(existing={"200"})
    fetched = _fetch(checkpoint="50")

    summary = save_source_collection(
        repository=repository,
        fetched=fetched,
        previous_state={
            "checkpoint_value": "50",
            "last_successful_at": NOW,
            "last_successful_run_id": RUN_ID,
        },
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )

    assert summary.new_posts == 2
    assert summary.existing_posts == 1
    assert summary.saved_posts == 3
    assert summary.checkpoint_before == "50"
    assert summary.checkpoint_after == "400"
    assert repository.sync_updates[0]["checkpoint_value"] == "400"
    record_source_usage(
        repository=repository,
        fetched=fetched,
        run_id=RUN_ID,
        usage_event_id=USAGE_ID,
        collected_at=NOW,
    )
    assert repository.usage[0]["request_count"] == 1


def test_checkpoint_is_not_updated_when_write_fails() -> None:
    repository = FakeRepository(fail_upsert=True)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        save_source_collection(
            repository=repository,
            fetched=_fetch(checkpoint="50"),
            previous_state={"checkpoint_value": "50"},
            run_id=RUN_ID,
            collected_at=NOW,
            max_pages=1,
            max_results=20,
        )

    assert repository.sync_updates == []


def test_failed_attempt_preserves_checkpoint() -> None:
    repository = FakeRepository()
    record_failed_source_attempt(
        repository=repository,
        source="mentions",
        previous_state={
            "checkpoint_value": "50",
            "checkpoint_metadata": {"synthetic": True},
            "last_successful_at": NOW,
            "last_successful_run_id": RUN_ID,
        },
        attempted_at=NOW,
        warning_code="synthetic_failure",
    )

    update = repository.sync_updates[0]
    assert update["source_key"] == "x_ethplorer_mentions"
    assert update["checkpoint_value"] == "50"
    assert update["last_warning_code"] == "synthetic_failure"


def test_partial_errors_prevent_checkpoint_advance() -> None:
    fetched = _fetch(checkpoint="50")
    incomplete = FetchedSource(
        **{
            **fetched.__dict__,
            "checkpoint_can_advance": False,
            "warnings": ("partial_errors_present",),
        }
    )
    repository = FakeRepository()

    summary = save_source_collection(
        repository=repository,
        fetched=incomplete,
        previous_state={"checkpoint_value": "50"},
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )

    assert summary.checkpoint_after == "50"
    assert summary.has_blocking_warning is True


def test_refresh_existing_ignores_checkpoint_and_never_updates_sync_state() -> None:
    repository = FakeRepository(existing={"100", "200", "400"})
    fetched = _fetch(checkpoint="50", refresh_existing=True)

    summary = save_source_collection(
        repository=repository,
        fetched=fetched,
        previous_state={"checkpoint_value": "50"},
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )

    assert fetched.requests_count == 1
    assert fetched.refresh_existing is True
    assert summary.new_posts == 0
    assert summary.existing_posts == 3
    assert summary.checkpoint_before == "50"
    assert summary.checkpoint_after == "50"
    assert repository.sync_updates == []
    assert len({record["post_id"] for record in repository.saved}) == 3
    record_source_usage(
        repository=repository,
        fetched=fetched,
        run_id=RUN_ID,
        usage_event_id=USAGE_ID,
        collected_at=NOW,
    )
    assert repository.usage[0]["input_units"] == 4


def test_collection_preserves_manual_baseline_audit_metadata() -> None:
    repository = FakeRepository()
    fetched = _fetch(checkpoint="50")
    acceptance = {
        "manual_baseline_acceptance": True,
        "source_run_id": str(RUN_ID),
        "previous_checkpoint": "25",
        "accepted_checkpoint": "50",
        "incomplete_reason": "cost_guard_reached",
        "incomplete_reasons": ["cost_guard_reached"],
        "older_window_may_have_been_skipped": True,
        "accepted_at": NOW.isoformat(),
    }

    save_source_collection(
        repository=repository,
        fetched=fetched,
        previous_state={
            "checkpoint_value": "50",
            "checkpoint_metadata": acceptance,
        },
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=5,
        max_results=100,
    )

    metadata = repository.sync_updates[0]["checkpoint_metadata"]
    assert metadata["baseline_acceptance"] == acceptance
    assert metadata["manual_baseline_acceptance"] is True
    assert metadata["source_run_id"] == str(RUN_ID)
    assert metadata["collection_run_id"] == str(RUN_ID)


def test_summary_is_secret_safe_and_contains_no_post_text() -> None:
    repository = FakeRepository()
    summary = save_source_collection(
        repository=repository,
        fetched=_fetch(),
        previous_state=None,
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )
    rendered = json.dumps(summary.safe_diagnostic())

    assert "synthetic-secret-token" not in rendered
    assert "Synthetic original post" not in rendered
    assert "raw_json" not in rendered
    assert summary.safe_diagnostic()["reposts_excluded"] == 1


def test_complete_incremental_paginates_and_uses_first_page_newest_id() -> None:
    fetched = fetch_source(
        client=_client_from(
            _page_response(("500", "400"), next_token="page-2"),
            _page_response(("300", "200"), next_token="page-3"),
            _page_response(("100",)),
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=5,
        max_results=100,
    )

    assert fetched.requests_count == 3
    assert fetched.fetched_posts == 5
    assert fetched.completion_state == "complete"
    assert fetched.checkpoint_candidate == "500"
    assert fetched.checkpoint_can_advance is True
    assert fetched.warnings == ()


def test_empty_incremental_run_preserves_checkpoint_and_is_complete() -> None:
    fetched = fetch_source(
        client=_client_from(_page_response(())),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=5,
        max_results=100,
    )

    assert fetched.fetched_posts == 0
    assert fetched.distinct_post_resources_received == 0
    assert fetched.checkpoint_candidate == "50"
    assert fetched.checkpoint_can_advance is True
    assert fetched.completion_state == "complete"


def test_duplicate_ids_across_pages_are_counted_once_and_block_checkpoint() -> None:
    fetched = fetch_source(
        client=_client_from(
            _page_response(("300", "200"), next_token="page-2"),
            _page_response(("200", "100")),
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=5,
        max_results=100,
    )

    assert fetched.fetched_posts == 4
    assert fetched.distinct_post_resources_received == 3
    assert len(fetched.records) == 3
    assert "duplicate_post_ids_detected" in fetched.warnings
    assert fetched.checkpoint_can_advance is False


def test_page_and_primary_limits_make_incremental_source_incomplete() -> None:
    page_limited = fetch_source(
        client=_client_from(_page_response(("300",), next_token="page-2")),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=1,
        max_results=20,
    )
    primary_limited = fetch_source(
        client=_client_from(_page_response(tuple(range(20)), next_token="page-2")),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=5,
        max_results=20,
        max_primary_posts_total=20,
    )

    assert "page_limit_reached" in page_limited.warnings
    assert page_limited.checkpoint_can_advance is False
    assert "primary_post_limit_reached" in primary_limited.warnings
    assert primary_limited.fetched_posts == 20
    assert primary_limited.checkpoint_can_advance is False


def test_incomplete_mentions_warns_about_possible_truncation() -> None:
    fetched = fetch_source(
        client=_client_from(_page_response(("2", "1"), next_token="page-2")),
        source="mentions",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=1,
        max_results=100,
    )

    assert "page_limit_reached" in fetched.warnings
    assert "mentions_history_may_be_truncated" in fetched.warnings


def test_cost_estimate_counts_expanded_and_deduplicates_resource_ids() -> None:
    fetched = fetch_source(
        client=_client_from(
            _page_response(
                ("300", "200"),
                next_token="page-2",
                expanded_ids=("200", "100"),
            )
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="50",
        max_pages=5,
        max_results=100,
        max_estimated_cost_usd=Decimal("0.015"),
    )

    assert fetched.fetched_posts == 2
    assert fetched.expanded_posts_received == 2
    assert fetched.distinct_post_resources_received == 3
    assert fetched.estimated_cost_usd == Decimal("0.015")
    assert "cost_guard_reached" in fetched.warnings
    assert fetched.checkpoint_can_advance is False


def test_retry_policy_retries_transient_failures_without_real_sleep() -> None:
    server_error = _page_response((), status=500)
    connection_error = XApiRequestError(
        status=None,
        category="connection_error",
        endpoint="/synthetic",
    )
    waits = []
    fetched_after_500 = fetch_source(
        client=_client_from(server_error, _page_response(("1",))),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=5,
        max_results=100,
        sleep=waits.append,
    )
    fetched_after_connection = fetch_source(
        client=_client_from(connection_error, _page_response(("2",))),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="1",
        max_pages=5,
        max_results=100,
        sleep=waits.append,
    )

    assert fetched_after_500.requests_count == 2
    assert fetched_after_connection.requests_count == 2
    assert waits == [1.0, 1.0]


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_are_not_retried(status) -> None:
    calls = 0

    def transport(url, headers, timeout):
        nonlocal calls
        calls += 1
        return _page_response((), status=status)

    with pytest.raises(XApiRequestError):
        fetch_source(
            client=XApiClient(token="synthetic-secret-token", transport=transport),
            source="home",
            user_id="123",
            run_id=RUN_ID,
            collected_at=NOW,
            checkpoint_before="1",
            max_pages=5,
            max_results=100,
            sleep=lambda _: pytest.fail("sleep must not run"),
        )

    assert calls == 1


def test_429_wait_above_bound_is_not_slept_or_retried() -> None:
    calls = 0

    def transport(url, headers, timeout):
        nonlocal calls
        calls += 1
        return _page_response((), status=429, headers={"Retry-After": "61"})

    with pytest.raises(XApiRequestError):
        fetch_source(
            client=XApiClient(token="synthetic-secret-token", transport=transport),
            source="home",
            user_id="123",
            run_id=RUN_ID,
            collected_at=NOW,
            checkpoint_before="1",
            max_pages=5,
            max_results=100,
            max_retry_wait_seconds=60,
            sleep=lambda _: pytest.fail("sleep must not run"),
        )

    assert calls == 1


def test_429_short_retry_after_is_retried_with_mocked_sleep() -> None:
    waits = []
    fetched = fetch_source(
        client=_client_from(
            _page_response((), status=429, headers={"Retry-After": "2"}),
            _page_response(("1",)),
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=5,
        max_results=100,
        max_retry_wait_seconds=60,
        sleep=waits.append,
    )

    assert fetched.requests_count == 2
    assert waits == [2.0]


def test_partial_errors_save_available_data_but_block_checkpoint() -> None:
    fetched = fetch_source(
        client=_client_from(
            _page_response(("2", "1"), errors=({"title": "synthetic"},))
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=5,
        max_results=100,
    )

    assert len(fetched.records) == 2
    assert "partial_errors_present" in fetched.warnings
    assert fetched.completion_state == "incomplete"
    assert fetched.checkpoint_can_advance is False


def test_invalid_post_shape_is_not_retried_and_valid_posts_are_kept() -> None:
    body = {
        "data": [
            {
                "id": "2",
                "text": "valid",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {"id": "1", "text": "missing created_at"},
        ],
        "includes": {},
        "meta": {"newest_id": "2", "oldest_id": "1"},
    }
    calls = 0

    def transport(url, headers, timeout):
        nonlocal calls
        calls += 1
        return HttpResponse(status=200, headers={}, body=json.dumps(body).encode())

    fetched = fetch_source(
        client=XApiClient(token="synthetic-secret-token", transport=transport),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=5,
        max_results=100,
        sleep=lambda _: pytest.fail("sleep must not run"),
    )

    assert calls == 1
    assert [record["post_id"] for record in fetched.records] == ["2"]
    assert "invalid_post_shape_present" in fetched.warnings
    assert fetched.checkpoint_can_advance is False


def test_terminal_error_after_a_page_keeps_prior_page_and_usage() -> None:
    fetched = fetch_source(
        client=_client_from(
            _page_response(("2",), next_token="page-2"),
            _page_response((), status=503),
        ),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="0",
        max_pages=5,
        max_results=100,
        max_attempts=1,
        sleep=lambda _: pytest.fail("sleep must not run"),
    )

    assert [record["post_id"] for record in fetched.records] == ["2"]
    assert fetched.requests_count == 2
    assert fetched.distinct_post_resources_received == 1
    assert fetched.terminal_http_status == 503
    assert "request_failed_after_partial_fetch" in fetched.warnings
    assert fetched.checkpoint_can_advance is False


def test_usage_is_recorded_before_a_later_post_write_failure() -> None:
    repository = FakeRepository(fail_upsert=True)
    fetched = _fetch(checkpoint="50")
    record_source_usage(
        repository=repository,
        fetched=fetched,
        run_id=RUN_ID,
        usage_event_id=USAGE_ID,
        collected_at=NOW,
    )

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        save_source_collection(
            repository=repository,
            fetched=fetched,
            previous_state={"checkpoint_value": "50"},
            run_id=RUN_ID,
            collected_at=NOW,
            max_pages=1,
            max_results=20,
        )

    assert len(repository.usage) == 1
    assert repository.sync_updates == []
    metadata = repository.usage[0]["metadata"]
    assert metadata["primary_posts_received"] == 4
    assert metadata["expanded_posts_received"] == 0
    assert metadata["distinct_post_resources_received"] == 4
    assert repository.usage[0]["reported_cost"] is None


def test_home_missed_window_warnings_use_previous_success_time() -> None:
    six_days = fetch_source(
        client=_client_from(_page_response(())),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="1",
        max_pages=5,
        max_results=100,
        previous_successful_at=NOW - timedelta(days=6),
    )
    seven_days = fetch_source(
        client=_client_from(_page_response(())),
        source="home",
        user_id="123",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="1",
        max_pages=5,
        max_results=100,
        previous_successful_at=NOW - timedelta(days=7),
    )

    assert "home_history_window_at_risk" in six_days.warnings
    assert "home_history_window_may_be_lost" not in six_days.warnings
    assert "home_history_window_at_risk" in seven_days.warnings
    assert "home_history_window_may_be_lost" in seven_days.warnings

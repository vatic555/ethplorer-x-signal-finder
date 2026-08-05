from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from x_signal_finder.collector import (
    FetchedSource,
    fetch_source,
    map_x_post,
    record_failed_source_attempt,
    save_source_collection,
)
from x_signal_finder.x_api.client import HttpResponse, XApiClient


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


def _fetch(source="home", checkpoint=None) -> FetchedSource:
    def transport(url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        assert headers["Authorization"] == "Bearer synthetic-secret-token"
        if source == "home":
            assert "exclude=retweets" in url
        if checkpoint:
            assert f"since_id={checkpoint}" in url
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
        usage_event_id=USAGE_ID,
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
    assert repository.usage[0]["request_count"] == 1


def test_checkpoint_is_not_updated_when_write_fails() -> None:
    repository = FakeRepository(fail_upsert=True)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        save_source_collection(
            repository=repository,
            fetched=_fetch(checkpoint="50"),
            previous_state={"checkpoint_value": "50"},
            run_id=RUN_ID,
            usage_event_id=USAGE_ID,
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
        usage_event_id=USAGE_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )

    assert summary.checkpoint_after == "50"
    assert summary.has_blocking_warning is True


def test_summary_is_secret_safe_and_contains_no_post_text() -> None:
    repository = FakeRepository()
    summary = save_source_collection(
        repository=repository,
        fetched=_fetch(),
        previous_state=None,
        run_id=RUN_ID,
        usage_event_id=USAGE_ID,
        collected_at=NOW,
        max_pages=1,
        max_results=20,
    )
    rendered = json.dumps(summary.safe_diagnostic())

    assert "synthetic-secret-token" not in rendered
    assert "Synthetic original post" not in rendered
    assert "raw_json" not in rendered
    assert summary.safe_diagnostic()["reposts_excluded"] == 1

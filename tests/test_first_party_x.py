from datetime import datetime, timezone
from decimal import Decimal
import inspect
from pathlib import Path
from uuid import UUID

import pytest

from x_signal_finder.cli import build_parser
from x_signal_finder.db.repository import StorageRepository
from x_signal_finder.first_party_x import (
    ACCOUNTS,
    FirstPartyXError,
    fetch_first_party_source,
    map_first_party_x_post,
    record_first_party_usage,
    save_first_party_source,
    source_key_for,
)
from x_signal_finder.x_api.client import XApiContentPage, XApiRequestError


RUN_ID = UUID("00000000-0000-0000-0000-000000000501")
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def _post(
    post_id: str,
    *,
    text: str = "main text",
    references=None,
    attachments=None,
    note_tweet=None,
    created_at: str = "2026-08-14T10:00:00Z",
):
    result = {
        "id": post_id,
        "author_id": ACCOUNTS["ethplorer"].user_id,
        "created_at": created_at,
        "conversation_id": post_id,
        "text": text,
        "lang": "en",
        "entities": {"urls": []},
        "public_metrics": {"like_count": 1},
    }
    if references is not None:
        result["referenced_tweets"] = references
    if attachments is not None:
        result["attachments"] = attachments
    if note_tweet is not None:
        result["note_tweet"] = note_tweet
    return result


def _page(
    posts,
    *,
    expanded=(),
    media=(),
    next_token=None,
    meta_present=True,
    partial_errors=0,
    resource_errors=None,
):
    users = {
        ACCOUNTS["ethplorer"].user_id: {
            "id": ACCOUNTS["ethplorer"].user_id,
            "username": "ethplorer",
        },
        "external-author": {"id": "external-author", "username": "external"},
    }
    return XApiContentPage(
        status=200,
        posts=tuple(posts),
        users_by_id=users,
        expanded_posts_by_id={str(post["id"]): post for post in expanded},
        media_by_key={str(item["media_key"]): item for item in media},
        resource_error_categories_by_id=dict(resource_errors or {}),
        next_token=next_token,
        newest_id=str(posts[0]["id"]) if posts else None,
        oldest_id=str(posts[-1]["id"]) if posts else None,
        rate_limits={},
        partial_error_count=partial_errors,
        elapsed_seconds=0.01,
        meta_present=meta_present,
    )


class FakeClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def get_content_page(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeRepository:
    def __init__(self):
        self.posts = {}
        self.states = {}
        self.usage = []

    def get_existing_first_party_x_post_ids(self, post_ids):
        return frozenset(set(post_ids) & set(self.posts))

    def upsert_first_party_x_posts(self, posts):
        for post in posts:
            previous = self.posts.get(post["post_id"])
            merged = dict(post)
            if previous:
                merged["first_seen_run_id"] = previous["first_seen_run_id"]
                merged["first_collected_at"] = previous["first_collected_at"]
                merged["publication_origin"] = previous["publication_origin"]
                merged["opportunity_id"] = previous["opportunity_id"]
            self.posts[post["post_id"]] = merged

    def update_sync_state(self, **values):
        self.states[values["source_key"]] = dict(values)

    def record_usage_event(self, event):
        self.usage.append(dict(event))


def _map(post, *, expanded=(), media=()):
    return map_first_party_x_post(
        post,
        source="ethplorer",
        users_by_id={
            ACCOUNTS["ethplorer"].user_id: {
                "id": ACCOUNTS["ethplorer"].user_id,
                "username": "ethplorer",
            },
            "external-author": {"id": "external-author", "username": "external"},
        },
        expanded_posts_by_id={str(item["id"]): item for item in expanded},
        media_by_key={str(item["media_key"]): item for item in media},
        run_id=RUN_ID,
        collected_at=NOW,
    )


def test_original_post_mapping_and_nullable_provenance() -> None:
    record = _map(_post("101"))

    assert record["post_type"] == "original"
    assert record["referenced_context_state"] == "not_applicable"
    assert record["post_url"] == "https://x.com/ethplorer/status/101"
    assert record["publication_origin"] == "unknown"
    assert record["opportunity_id"] is None


@pytest.mark.parametrize(
    ("relationship_type", "post_type"),
    (("replied_to", "reply"), ("quoted", "quote"), ("retweeted", "repost")),
)
def test_relationship_types_retain_available_context(
    relationship_type, post_type
) -> None:
    expanded = _post("900", text="external context")
    expanded["author_id"] = "external-author"
    record = _map(
        _post(
            "102",
            references=[{"type": relationship_type, "id": "900"}],
        ),
        expanded=[expanded],
    )

    assert record["post_type"] == post_type
    assert record["referenced_context_state"] == "available"
    assert record["references"][0]["referenced_text"] == "external context"
    assert record["references"][0]["referenced_author_username"] == "external"
    assert "unavailable_reason" not in record["references"][0]


def test_long_note_tweet_is_authoritative_without_truncation() -> None:
    full_text = "complete " * 100
    record = _map(
        _post("103", text="truncated…", note_tweet={"text": full_text})
    )

    assert record["text"] == full_text
    assert record["raw_json"]["text"] == "truncated…"
    assert record["raw_json"]["note_tweet"]["text"] == full_text
    assert record["raw_json"]["_collector"]["full_text_source"] == "note_tweet"


def test_malformed_note_tweet_is_content_safe_error() -> None:
    with pytest.raises(FirstPartyXError, match="invalid note_tweet"):
        _map(_post("104", note_tweet="bad"))


def test_missing_reference_expansion_is_explicitly_unavailable() -> None:
    record = _map(
        _post("105", references=[{"type": "quoted", "id": "901"}])
    )

    assert record["referenced_context_state"] == "unavailable"
    assert record["references"][0]["context_state"] == "unavailable"
    assert record["references"][0]["unavailable_reason"] == "unknown"
    assert "referenced_text" not in record["references"][0]


def test_resource_specific_unavailable_reference_reason_is_retained() -> None:
    post = _post("1052", references=[{"type": "quoted", "id": "905"}])
    record = map_first_party_x_post(
        post,
        source="ethplorer",
        users_by_id={},
        expanded_posts_by_id={},
        media_by_key={},
        unavailable_reference_reasons={"905": "protected_or_inaccessible"},
        run_id=RUN_ID,
        collected_at=NOW,
    )

    assert record["references"][0]["unavailable_reason"] == (
        "protected_or_inaccessible"
    )
    assert record["raw_json"]["_expanded"]["relationships"][0][
        "unavailable_reason"
    ] == "protected_or_inaccessible"


def test_referenced_post_uses_its_own_note_tweet_full_text() -> None:
    expanded = _post(
        "904",
        text="truncated…",
        note_tweet={"text": "complete referenced long text"},
    )
    expanded["author_id"] = "external-author"
    record = _map(
        _post("1051", references=[{"type": "quoted", "id": "904"}]),
        expanded=[expanded],
    )

    assert record["references"][0]["referenced_text"] == "complete referenced long text"
    relationship = record["raw_json"]["_expanded"]["relationships"][0]
    assert relationship["full_text_source"] == "note_tweet"


def test_multiple_referenced_relationships_are_not_lost() -> None:
    first = _post("902", text="reply parent")
    second = _post("903", text="quoted Post")
    first["author_id"] = "external-author"
    second["author_id"] = "external-author"
    record = _map(
        _post(
            "106",
            references=[
                {"type": "replied_to", "id": "902"},
                {"type": "quoted", "id": "903"},
            ],
        ),
        expanded=[first, second],
    )

    assert [item["referenced_post_id"] for item in record["references"]] == [
        "902",
        "903",
    ]
    assert len(record["raw_json"]["_expanded"]["relationships"]) == 2


def test_media_metadata_is_retained_without_blob_download() -> None:
    media = {
        "media_key": "m1",
        "type": "video",
        "preview_image_url": "https://example.test/preview.jpg",
        "duration_ms": 1234,
    }
    record = _map(
        _post("107", attachments={"media_keys": ["m1"]}),
        media=[media],
    )

    assert record["media_metadata"] == [media]
    assert record["raw_json"]["_expanded"]["media"] == [media]
    assert not any(key in record for key in ("media_blob", "downloaded_media"))


def test_missing_media_expansion_is_explicit_and_nonfatal() -> None:
    record = _map(_post("1071", attachments={"media_keys": ["missing"]}))

    assert record["media_metadata"] == []
    assert record["raw_json"]["_collector"]["media_expansion_incomplete"] is True
    assert record["raw_json"]["_collector"]["missing_media_count"] == 1


def test_multi_page_initial_sync_has_no_since_id_and_completes() -> None:
    client = FakeClient(
        [
            _page([_post("110")], next_token="next"),
            _page([_post("109")]),
        ]
    )
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=2,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert fetched.primary_posts_received == 2
    assert fetched.completion_state == "complete"
    assert fetched.checkpoint_candidate == "110"
    assert client.calls[0][1]["since_id"] is None
    assert client.calls[1][1]["pagination_token"] == "next"


def test_incremental_sync_uses_checkpoint() -> None:
    client = FakeClient([_page([_post("111")])])
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="110",
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert client.calls[0][1]["since_id"] == "110"
    assert fetched.checkpoint_candidate == "111"


def test_page_guard_marks_incomplete_and_prevents_checkpoint_advance() -> None:
    fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("112")], next_token="older")]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="100",
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert fetched.completion_state == "incomplete"
    assert fetched.checkpoint_can_advance is False
    assert "page_limit_reached" in fetched.warnings


def test_partial_unavailable_resources_are_warned_without_losing_window_checkpoint() -> None:
    fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("1121")], partial_errors=2)]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert fetched.completion_state == "complete"
    assert fetched.checkpoint_can_advance is True
    assert "partial_resources_unavailable" in fetched.warnings


def test_resource_reason_from_page_is_attached_to_unavailable_reference() -> None:
    fetched = fetch_first_party_source(
        client=FakeClient(
            [
                _page(
                    [_post("1122", references=[{"type": "quoted", "id": "906"}])],
                    partial_errors=1,
                    resource_errors={"906": "not_found"},
                ),
                _page([], partial_errors=1, resource_errors={"906": "not_found"}),
            ]
        ),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert fetched.records[0]["references"][0]["unavailable_reason"] == "not_found"


def test_cost_guard_stops_before_another_timeline_page() -> None:
    client = FakeClient([_page([_post("113")], next_token="older")])
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="100",
        max_pages=5,
        max_estimated_cost_usd=Decimal("0.005"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert len(client.calls) == 1
    assert "cost_guard_reached" in fetched.warnings
    assert fetched.checkpoint_can_advance is False


def test_reference_completion_deduplicates_ids() -> None:
    reference = {"type": "quoted", "id": "950"}
    completed = _post("950", text="completed context")
    completed["author_id"] = "external-author"
    client = FakeClient(
        [
            _page([_post("114", references=[reference]), _post("115", references=[reference])]),
            _page([completed], meta_present=False),
        ]
    )
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=2,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert client.calls[1][0] == "/tweets"
    assert client.calls[1][1]["ids"] == "950"
    assert fetched.reference_lookup_requests_count == 1
    assert all(
        record["references"][0]["context_state"] == "available"
        for record in fetched.records
    )


def test_failed_reference_completion_keeps_context_unavailable_safely() -> None:
    error = XApiRequestError(
        status=503,
        category="api_error",
        endpoint="/tweets",
    )
    client = FakeClient(
        [
            _page(
                [_post("116", references=[{"type": "replied_to", "id": "951"}])]
            ),
            error,
        ]
    )
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=2,
        max_estimated_cost_usd=Decimal("1"),
        max_attempts=1,
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert "reference_completion_request_failed" in fetched.warnings
    assert fetched.records[0]["referenced_context_state"] == "unavailable"
    assert fetched.checkpoint_can_advance is True


def test_save_is_idempotent_preserves_first_seen_and_updates_last_seen() -> None:
    repository = FakeRepository()
    fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("117", text="first")])]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )
    first = save_first_party_source(
        repository=repository,
        fetched=fetched,
        previous_state=None,
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
    )
    second_run = UUID("00000000-0000-0000-0000-000000000502")
    second_fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("117", text="updated")])]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=second_run,
        collected_at=NOW,
        checkpoint_before="117",
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )
    second = save_first_party_source(
        repository=repository,
        fetched=second_fetched,
        previous_state=repository.states[source_key_for("ethplorer")],
        run_id=second_run,
        collected_at=NOW,
        max_pages=1,
    )

    assert first.new_posts == 1
    assert second.new_posts == 0
    assert second.existing_posts_updated == 1
    assert len(repository.posts) == 1
    assert repository.posts["117"]["text"] == "updated"
    assert repository.posts["117"]["first_seen_run_id"] == RUN_ID
    assert repository.posts["117"]["last_seen_run_id"] == second_run


def test_incremental_checkpoint_metadata_preserves_inventory_snapshot() -> None:
    repository = FakeRepository()
    previous_state = {
        "checkpoint_value": "117",
        "checkpoint_metadata": {"inventory_tweet_count": 352},
        "last_successful_at": NOW,
        "last_successful_run_id": RUN_ID,
    }
    fetched = fetch_first_party_source(
        client=FakeClient([_page([])]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="117",
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )
    summary = save_first_party_source(
        repository=repository,
        fetched=fetched,
        previous_state=previous_state,
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
    )

    assert summary.inventory_tweet_count == 352
    assert (
        repository.states["first_party_x_ethplorer"]["checkpoint_metadata"]
        ["inventory_tweet_count"]
        == 352
    )


def test_source_checkpoints_are_independent() -> None:
    repository = FakeRepository()
    for source, post_id in (("ethplorer", "120"), ("binplorer", "220")):
        fetched = fetch_first_party_source(
            client=FakeClient([_page([_post(post_id)])]),  # type: ignore[arg-type]
            source=source,
            run_id=RUN_ID,
            collected_at=NOW,
            checkpoint_before=None,
            max_pages=1,
            max_estimated_cost_usd=Decimal("1"),
            sleep=lambda _: None,
            now_timestamp=lambda: 0,
        )
        save_first_party_source(
            repository=repository,
            fetched=fetched,
            previous_state=None,
            run_id=RUN_ID,
            collected_at=NOW,
            max_pages=1,
        )

    assert repository.states["first_party_x_ethplorer"]["checkpoint_value"] == "120"
    assert repository.states["first_party_x_binplorer"]["checkpoint_value"] == "220"


def test_usage_is_separate_and_reports_resource_categories() -> None:
    repository = FakeRepository()
    fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("121")])]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )
    record_first_party_usage(
        repository=repository,
        fetched=fetched,
        run_id=RUN_ID,
        usage_event_id=UUID("00000000-0000-0000-0000-000000000503"),
        collected_at=NOW,
    )

    event = repository.usage[0]
    assert event["operation"] == "first_party_x_sync_ethplorer"
    assert event["reported_cost"] is None
    assert event["metadata"]["primary_post_resources"] == 1
    assert "expanded_post_resources" in event["metadata"]
    assert "reference_completion_post_resources" in event["metadata"]
    assert "media_resources" in event["metadata"]
    assert event["metadata"]["user_resources"] == 2
    assert event["metadata"]["estimated_post_cost_usd"] == "0.005"
    assert event["metadata"]["estimated_user_cost_usd"] == "0.020"
    assert event["metadata"]["estimated_media_cost_usd"] == "0.000"
    assert event["metadata"]["estimated_total_cost_usd"] == "0.025"
    assert event["estimated_cost"] == Decimal("0.025")


def test_cost_guard_uses_post_user_and_media_resource_costs() -> None:
    media = {"media_key": "m-cost", "type": "photo"}
    client = FakeClient(
        [
            _page(
                [_post("1211", attachments={"media_keys": ["m-cost"]})],
                media=[media],
                next_token="older",
            )
        ]
    )
    fetched = fetch_first_party_source(
        client=client,  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before="100",
        max_pages=5,
        max_estimated_cost_usd=Decimal("0.030"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )

    assert len(client.calls) == 1
    assert fetched.estimated_post_cost_usd == Decimal("0.005")
    assert fetched.estimated_user_cost_usd == Decimal("0.020")
    assert fetched.estimated_media_cost_usd == Decimal("0.005")
    assert fetched.estimated_cost_usd == Decimal("0.030")
    assert "cost_guard_reached" in fetched.warnings


def test_safe_representations_and_diagnostics_never_include_post_text() -> None:
    sentinel = "SECRET EDITORIAL SENTENCE"
    fetched = fetch_first_party_source(
        client=FakeClient([_page([_post("122", text=sentinel)])]),  # type: ignore[arg-type]
        source="ethplorer",
        run_id=RUN_ID,
        collected_at=NOW,
        checkpoint_before=None,
        max_pages=1,
        max_estimated_cost_usd=Decimal("1"),
        sleep=lambda _: None,
        now_timestamp=lambda: 0,
    )
    summary = save_first_party_source(
        repository=FakeRepository(),
        fetched=fetched,
        previous_state=None,
        run_id=RUN_ID,
        collected_at=NOW,
        max_pages=1,
    )

    assert sentinel not in repr(fetched)
    assert sentinel not in repr(summary)
    assert sentinel not in str(summary.safe_diagnostic())


def test_first_party_upsert_preserves_manual_and_first_seen_fields() -> None:
    source = inspect.getsource(StorageRepository.upsert_first_party_x_posts)
    conflict_update = source.split("ON CONFLICT (post_id) DO UPDATE SET", 1)[1]

    for field in (
        "first_seen_run_id",
        "first_collected_at",
        "publication_origin",
        "opportunity_id",
    ):
        assert f"{field} =" not in conflict_update
    for field in ("text", "raw_json", "last_seen_run_id", "last_collected_at"):
        assert f"{field} = EXCLUDED.{field}" in conflict_update


def test_migration_003_is_separate_rls_enabled_and_lossless() -> None:
    sql = (
        Path(__file__).parents[1]
        / "migrations"
        / "003_first_party_x_corpus.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE first_party_x_posts" in sql
    assert "CREATE TABLE first_party_x_post_references" in sql
    assert "PRIMARY KEY (source_post_id, relationship_index)" in sql
    assert "publication_origin" in sql
    assert "opportunity_id uuid REFERENCES opportunities" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE TABLE posts" not in sql


def test_first_party_cli_defaults_are_bounded_and_read_only() -> None:
    args = build_parser().parse_args(
        ["first-party-x", "sync", "--source", "both"]
    )

    assert args.command == "first-party-x"
    assert args.first_party_command == "sync"
    assert args.source == "both"
    assert args.max_pages == 5
    assert args.max_estimated_cost_usd == Decimal("1.00")
    assert not hasattr(args, "write")

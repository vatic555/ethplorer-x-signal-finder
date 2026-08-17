from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from uuid import UUID

from x_signal_finder.x_shadow_recovery import (
    apply_official_shadow_recovery,
    prepare_official_shadow_recovery,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
RUN_ID = UUID("00000000-0000-0000-0000-000000000001")
USAGE_ID = UUID("00000000-0000-0000-0000-000000000002")


class _Repository:
    def __init__(self, existing=()):
        self.existing = frozenset(existing)
        self.calls = []

    def get_existing_post_ids(self, post_ids):
        self.calls.append(("get_existing_post_ids", tuple(post_ids)))
        return self.existing.intersection(post_ids)

    def create_run(self, **values):
        self.calls.append(("create_run", values))

    def upsert_posts(self, posts):
        self.calls.append(("upsert_posts", tuple(posts)))

    def record_usage_event(self, event):
        self.calls.append(("record_usage_event", event))

    def complete_run(self, **values):
        self.calls.append(("complete_run", values))


def _payload(posts, *, users):
    return {
        "data": posts,
        "includes": {"users": users},
        "meta": {
            "result_count": len(posts),
            "newest_id": posts[0]["id"],
            "oldest_id": posts[-1]["id"],
            "next_token": "more",
        },
    }


def _write_artifacts(tmp_path):
    directory = tmp_path / "20260814T205734Z" / "official_x"
    directory.mkdir(parents=True)
    users = [
        {"id": "10", "username": "alice"},
        {"id": "11", "username": "bob"},
    ]
    first = _payload(
        [
            {
                "id": "100",
                "author_id": "10",
                "created_at": "2026-08-14T20:00:00Z",
                "conversation_id": "100",
                "text": "Synthetic original.",
            },
            {
                "id": "90",
                "author_id": "11",
                "created_at": "2026-08-14T19:59:00Z",
                "conversation_id": "80",
                "text": "Synthetic repost.",
                "referenced_tweets": [{"type": "retweeted", "id": "80"}],
            },
        ],
        users=users,
    )
    second = _payload(
        [
            first["data"][0],
            {
                "id": "80",
                "author_id": "11",
                "created_at": "2026-08-14T19:58:00Z",
                "conversation_id": "80",
                "text": "Synthetic reply.",
                "referenced_tweets": [{"type": "replied_to", "id": "70"}],
            },
        ],
        users=users,
    )
    (directory / "response-0001.json").write_text(json.dumps(first), encoding="utf-8")
    (directory / "response-0002.json").write_text(json.dumps(second), encoding="utf-8")
    return directory


def test_recovery_dry_run_maps_dedupes_and_excludes_reposts(tmp_path) -> None:
    repository = _Repository(existing={"80"})
    plan = prepare_official_shadow_recovery(
        artifact_dir=_write_artifacts(tmp_path),
        repository=repository,
        run_id=RUN_ID,
        recovered_at=NOW,
    )

    assert plan.raw_primary_count == 4
    assert plan.unique_primary_count == 3
    assert plan.artifact_duplicate_count == 1
    assert plan.valid_primary_count == 3
    assert plan.valid_mapped_count == 2
    assert plan.reposts_excluded == 1
    assert plan.duplicates_existing == 1
    assert plan.unique_new_posts == 1
    assert plan.invalid_primary_count == 0
    assert plan.records[0]["raw_json"]["_collector"]["recovery"][
        "external_requests_during_recovery"
    ] == 0
    assert [name for name, _ in repository.calls] == ["get_existing_post_ids"]


def test_recovery_apply_records_provenance_without_sync_state(tmp_path) -> None:
    repository = _Repository(existing={"80"})
    plan = prepare_official_shadow_recovery(
        artifact_dir=_write_artifacts(tmp_path),
        repository=repository,
        run_id=RUN_ID,
        recovered_at=NOW,
    )
    summary = apply_official_shadow_recovery(
        repository=repository,
        plan=plan,
        confirmed_manifest_sha256=plan.manifest_sha256,
        run_id=RUN_ID,
        recovered_at=NOW,
        usage_event_id=USAGE_ID,
        application_version="test",
        git_commit=None,
        reported_post_reads=1133,
        reported_cost_usd=Decimal("5.665"),
    )

    names = [name for name, _ in repository.calls]
    assert names == [
        "get_existing_post_ids",
        "create_run",
        "upsert_posts",
        "record_usage_event",
        "complete_run",
    ]
    assert "update_sync_state" not in names
    usage = next(value for name, value in repository.calls if name == "record_usage_event")
    assert usage["request_count"] == 2
    assert usage["input_units"] == 1133
    assert usage["reported_cost"] == Decimal("5.665")
    assert usage["metadata"]["external_requests_during_recovery"] == 0
    assert summary["status"] == "incomplete_recovered"
    assert summary["database_writes"] is True

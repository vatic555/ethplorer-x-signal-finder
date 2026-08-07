from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from x_signal_finder.baseline import (
    BaselineAcceptanceError,
    accept_baseline_candidate,
    inspect_baseline_candidate,
)


RUN_ID = UUID("00000000-0000-0000-0000-000000000123")
NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


class FakeBaselineRepository:
    def __init__(self) -> None:
        self.run_source = {
            "run_status": "completed_with_warnings",
            "trigger_type": "manual_x_collection",
            "usage_metadata": {
                "source": "home",
                "source_key": "x_home_timeline",
                "completion_state": "incomplete",
                "primary_posts_received": 194,
                "newest_post_id": "300",
                "warnings": ["cost_guard_reached"],
            },
            "saved_posts": 152,
            "highest_saved_post_id": "299",
        }
        self.state = {
            "checkpoint_value": "100",
            "checkpoint_metadata": {
                "completion_state": "incomplete",
                "primary_posts_received": 194,
                "warnings": ["cost_guard_reached"],
            },
            "last_attempt_at": NOW,
        }
        self.updates = []
        self.run_acceptances = []

    def get_collection_run_source(self, **values):
        return self.run_source

    def get_sync_state(self, source_key):
        return self.state

    def update_sync_state(self, **values):
        self.updates.append(values)
        self.state = {
            **self.state,
            "checkpoint_value": values["checkpoint_value"],
            "checkpoint_metadata": values["checkpoint_metadata"],
        }

    def record_run_baseline_acceptance(self, **values):
        self.run_acceptances.append(values)


def test_inspection_prefers_recorded_first_page_newest_id() -> None:
    repository = FakeBaselineRepository()

    candidate = inspect_baseline_candidate(
        repository=repository,
        run_id=RUN_ID,
        source="home",
    )

    assert candidate["status"] == "confirmation_required"
    assert candidate["previous_checkpoint"] == "100"
    assert candidate["accepted_checkpoint"] == "300"
    assert candidate["checkpoint_provenance"] == "usage_metadata.newest_post_id"
    assert repository.updates == []


def test_legacy_candidate_uses_highest_saved_post_id_fallback() -> None:
    repository = FakeBaselineRepository()
    repository.run_source["usage_metadata"].pop("newest_post_id")

    candidate = inspect_baseline_candidate(
        repository=repository,
        run_id=RUN_ID,
        source="home",
    )

    assert candidate["accepted_checkpoint"] == "299"
    assert candidate["checkpoint_provenance"] == (
        "highest_saved_post_id_legacy_fallback"
    )


def test_confirmed_acceptance_updates_only_sync_state_with_audit_metadata() -> None:
    repository = FakeBaselineRepository()
    candidate = inspect_baseline_candidate(
        repository=repository,
        run_id=RUN_ID,
        source="home",
    )

    result = accept_baseline_candidate(
        repository=repository,
        candidate=candidate,
        accepted_at=NOW,
        run_id=RUN_ID,
    )

    assert result["status"] == "accepted"
    assert len(repository.updates) == 1
    assert repository.run_acceptances == [
        {"run_id": RUN_ID, "metadata": repository.updates[0]["checkpoint_metadata"]}
    ]
    update = repository.updates[0]
    assert update["checkpoint_value"] == "300"
    assert update["last_successful_at"] == NOW
    assert update["last_successful_run_id"] == RUN_ID
    metadata = update["checkpoint_metadata"]
    assert metadata["manual_baseline_acceptance"] is True
    assert metadata["source_run_id"] == str(RUN_ID)
    assert metadata["previous_checkpoint"] == "100"
    assert metadata["accepted_checkpoint"] == "300"
    assert metadata["incomplete_reason"] == "cost_guard_reached"
    assert metadata["older_window_may_have_been_skipped"] is True
    assert metadata["primary_posts_received"] == 194
    assert metadata["saved_posts"] == 152
    assert metadata["accepted_at"] == NOW.isoformat()


@pytest.mark.parametrize("status", ["failed", "running", "completed"])
def test_failed_or_non_incomplete_run_status_is_rejected(status) -> None:
    repository = FakeBaselineRepository()
    repository.run_source["run_status"] = status

    with pytest.raises(BaselineAcceptanceError):
        inspect_baseline_candidate(
            repository=repository,
            run_id=RUN_ID,
            source="home",
        )

    assert repository.updates == []


def test_candidate_without_valid_newest_or_saved_posts_is_rejected() -> None:
    repository = FakeBaselineRepository()
    repository.run_source["usage_metadata"].pop("newest_post_id")
    repository.run_source["highest_saved_post_id"] = None
    repository.run_source["saved_posts"] = 0

    with pytest.raises(BaselineAcceptanceError, match="newest Post ID"):
        inspect_baseline_candidate(
            repository=repository,
            run_id=RUN_ID,
            source="home",
        )


def test_stale_candidate_is_rejected() -> None:
    repository = FakeBaselineRepository()
    repository.state["checkpoint_metadata"]["primary_posts_received"] = 20

    with pytest.raises(BaselineAcceptanceError, match="current incomplete"):
        inspect_baseline_candidate(
            repository=repository,
            run_id=RUN_ID,
            source="home",
        )

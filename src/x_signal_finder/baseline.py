"""Explicit, auditable acceptance of an incomplete collection baseline."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from x_signal_finder.collector import BLOCKING_WARNINGS, Source, source_key_for


class BaselineAcceptanceError(RuntimeError):
    """Safe refusal to accept an invalid or stale baseline candidate."""


class BaselineRepository(Protocol):
    def get_collection_run_source(
        self,
        *,
        run_id: UUID,
        source: Source,
        source_key: str,
    ) -> Mapping[str, Any] | None: ...

    def get_sync_state(self, source_key: str) -> Mapping[str, Any] | None: ...

    def update_sync_state(self, **values) -> None: ...

    def record_run_baseline_acceptance(
        self,
        *,
        run_id: UUID,
        metadata: Mapping[str, Any],
    ) -> None: ...


def _positive_count(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BaselineAcceptanceError(f"Candidate has invalid {name} metadata.")
    return value


def _post_id(value: object) -> str | None:
    if isinstance(value, str) and value.isdigit() and 1 <= len(value) <= 19:
        return value
    return None


def inspect_baseline_candidate(
    *,
    repository: BaselineRepository,
    run_id: UUID,
    source: Source,
) -> dict[str, Any]:
    """Validate one incomplete run and return a content-safe summary."""
    source_key = source_key_for(source)
    candidate = repository.get_collection_run_source(
        run_id=run_id,
        source=source,
        source_key=source_key,
    )
    if candidate is None:
        raise BaselineAcceptanceError(
            "No unique X usage record exists for this run and source."
        )
    if candidate.get("run_status") != "completed_with_warnings":
        raise BaselineAcceptanceError(
            "Only a completed-with-warnings collection run can be accepted."
        )
    if candidate.get("trigger_type") != "manual_x_collection":
        raise BaselineAcceptanceError(
            "Refresh, diagnostic, failed, and non-collection runs cannot be accepted."
        )

    usage_metadata = candidate.get("usage_metadata")
    if not isinstance(usage_metadata, Mapping):
        raise BaselineAcceptanceError("Candidate usage metadata is unavailable.")
    if usage_metadata.get("source") != source:
        raise BaselineAcceptanceError("Candidate belongs to a different source.")
    if usage_metadata.get("source_key") != source_key:
        raise BaselineAcceptanceError("Candidate source key does not match.")
    if usage_metadata.get("completion_state") != "incomplete":
        raise BaselineAcceptanceError("Candidate source is not incomplete.")

    raw_warnings = usage_metadata.get("warnings")
    if not isinstance(raw_warnings, list) or not all(
        isinstance(warning, str) for warning in raw_warnings
    ):
        raise BaselineAcceptanceError("Candidate warnings are unavailable.")
    incomplete_reasons = sorted(set(raw_warnings).intersection(BLOCKING_WARNINGS))
    if not incomplete_reasons:
        raise BaselineAcceptanceError(
            "Candidate has no recognized incomplete-run reason."
        )

    primary_posts = _positive_count(
        usage_metadata.get("primary_posts_received"),
        "primary Post count",
    )
    saved_posts = _positive_count(candidate.get("saved_posts"), "saved Post count")
    newest_id = _post_id(usage_metadata.get("newest_post_id"))
    checkpoint_provenance = "usage_metadata.newest_post_id"
    if newest_id is None:
        newest_id = _post_id(candidate.get("highest_saved_post_id"))
        checkpoint_provenance = "highest_saved_post_id_legacy_fallback"
    if newest_id is None or primary_posts == 0 or saved_posts == 0:
        raise BaselineAcceptanceError(
            "Candidate has no valid newest Post ID or saved Post evidence."
        )

    state = repository.get_sync_state(source_key)
    if state is None:
        raise BaselineAcceptanceError("Current source checkpoint does not exist.")
    state_metadata = state.get("checkpoint_metadata")
    if not isinstance(state_metadata, Mapping):
        state_metadata = {}
    if (
        state_metadata.get("manual_baseline_acceptance") is True
        and state_metadata.get("source_run_id") == str(run_id)
        and state.get("checkpoint_value") == newest_id
    ):
        return {
            "action": "accept_baseline",
            "status": "already_accepted",
            "source": source,
            "source_key": source_key,
            "source_run_id": str(run_id),
            "previous_checkpoint": state_metadata.get("previous_checkpoint"),
            "accepted_checkpoint": newest_id,
            "incomplete_reasons": incomplete_reasons,
            "older_window_may_have_been_skipped": True,
            "primary_posts_received": primary_posts,
            "saved_posts": saved_posts,
            "checkpoint_provenance": checkpoint_provenance,
        }

    sync_completion = state_metadata.get("completion_state")
    sync_primary = state_metadata.get("primary_posts_received")
    sync_warnings = state_metadata.get("warnings")
    if (
        sync_completion != "incomplete"
        or sync_primary != primary_posts
        or not isinstance(sync_warnings, list)
        or sorted(sync_warnings) != sorted(raw_warnings)
    ):
        raise BaselineAcceptanceError(
            "Candidate is not the source's current incomplete collection attempt."
        )

    return {
        "action": "accept_baseline",
        "status": "confirmation_required",
        "source": source,
        "source_key": source_key,
        "source_run_id": str(run_id),
        "previous_checkpoint": state.get("checkpoint_value"),
        "accepted_checkpoint": newest_id,
        "incomplete_reasons": incomplete_reasons,
        "older_window_may_have_been_skipped": True,
        "primary_posts_received": primary_posts,
        "saved_posts": saved_posts,
        "checkpoint_provenance": checkpoint_provenance,
    }


def accept_baseline_candidate(
    *,
    repository: BaselineRepository,
    candidate: Mapping[str, Any],
    accepted_at: datetime,
    run_id: UUID,
) -> dict[str, Any]:
    """Persist one previously inspected baseline acceptance."""
    if candidate.get("status") == "already_accepted":
        return dict(candidate)
    if candidate.get("status") != "confirmation_required":
        raise BaselineAcceptanceError("Baseline candidate is not acceptable.")

    metadata = {
        "manual_baseline_acceptance": True,
        "source": candidate["source"],
        "source_key": candidate["source_key"],
        "source_run_id": str(run_id),
        "previous_checkpoint": candidate["previous_checkpoint"],
        "accepted_checkpoint": candidate["accepted_checkpoint"],
        "incomplete_reason": candidate["incomplete_reasons"][0],
        "incomplete_reasons": list(candidate["incomplete_reasons"]),
        "older_window_may_have_been_skipped": True,
        "primary_posts_received": candidate["primary_posts_received"],
        "saved_posts": candidate["saved_posts"],
        "accepted_at": accepted_at.isoformat(),
        "checkpoint_provenance": candidate["checkpoint_provenance"],
    }
    current_state = repository.get_sync_state(str(candidate["source_key"]))
    if current_state is None:
        raise BaselineAcceptanceError("Current source checkpoint no longer exists.")
    if current_state.get("checkpoint_value") != candidate.get("previous_checkpoint"):
        raise BaselineAcceptanceError(
            "Source checkpoint changed after inspection; baseline was not accepted."
        )
    repository.update_sync_state(
        source_key=str(candidate["source_key"]),
        checkpoint_value=str(candidate["accepted_checkpoint"]),
        checkpoint_metadata=metadata,
        last_attempt_at=current_state.get("last_attempt_at"),
        last_successful_at=accepted_at,
        last_successful_run_id=run_id,
        last_warning_code="manual_baseline_acceptance",
        updated_at=accepted_at,
    )
    repository.record_run_baseline_acceptance(run_id=run_id, metadata=metadata)
    result = dict(candidate)
    result["status"] = "accepted"
    result["accepted_at"] = accepted_at.isoformat()
    return result

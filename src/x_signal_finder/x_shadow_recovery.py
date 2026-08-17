"""Offline recovery of already-paid Official X shadow pages.

This module never contacts X. The default operation is a read-only dry-run;
database mutation is exposed separately and must be confirmation-gated by the
artifact manifest digest printed by the dry-run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Protocol
from uuid import UUID

from x_signal_finder.collector import CollectionError, map_x_post
from x_signal_finder.x_api.client import HttpResponse, XApiRequestError, parse_content_page


_RESPONSE_FILE = re.compile(r"response-(\d{4})\.json\Z")
_ARTIFACT_RUN_ID = re.compile(r"\d{8}T\d{6}Z\Z")
RECOVERY_SOURCE_KEY = "x_home_timeline"
RECOVERY_TERMINAL_HTTP_STATUS = 402
RECOVERY_TERMINAL_STATE = "incomplete_due_to_credit"


class ShadowRecoveryError(RuntimeError):
    """Content-safe local recovery failure."""


class RecoveryRepository(Protocol):
    def get_existing_post_ids(self, post_ids) -> frozenset[str]: ...

    def create_run(self, **values) -> None: ...

    def upsert_posts(self, posts) -> None: ...

    def record_usage_event(self, event) -> None: ...

    def complete_run(self, **values) -> None: ...


@dataclass(frozen=True, repr=False)
class OfficialShadowRecoveryPlan:
    artifact_dir: Path
    artifact_run_id: str
    manifest_sha256: str
    page_count: int
    raw_primary_count: int
    unique_primary_count: int
    artifact_duplicate_count: int
    valid_primary_count: int
    valid_mapped_count: int
    invalid_primary_count: int
    reposts_excluded: int
    existing_post_ids: frozenset[str]
    records: tuple[dict[str, Any], ...]
    unique_expanded_post_count: int
    unique_user_count: int
    unique_media_count: int

    @property
    def duplicates_existing(self) -> int:
        return len(self.existing_post_ids)

    @property
    def unique_new_posts(self) -> int:
        return self.valid_mapped_count - self.duplicates_existing

    def safe_summary(self, *, mode: str = "dry_run") -> dict[str, object]:
        return {
            "task": "004D_official_x_offline_recovery",
            "mode": mode,
            "source_key": RECOVERY_SOURCE_KEY,
            "artifact_run_id": self.artifact_run_id,
            "artifact_manifest_sha256": self.manifest_sha256,
            "successful_paid_pages_recovered": self.page_count,
            "terminal_state": RECOVERY_TERMINAL_STATE,
            "terminal_http_status": RECOVERY_TERMINAL_HTTP_STATUS,
            "raw_primary_count": self.raw_primary_count,
            "unique_primary_count": self.unique_primary_count,
            "artifact_duplicates_excluded": self.artifact_duplicate_count,
            "valid_primary_count": self.valid_primary_count,
            "valid_mapped": self.valid_mapped_count,
            "invalid_primary_count": self.invalid_primary_count,
            "simple_reposts_excluded": self.reposts_excluded,
            "duplicates_existing": self.duplicates_existing,
            "unique_new_posts_to_insert": self.unique_new_posts,
            "local_resource_inventory": {
                "unique_expanded_posts": self.unique_expanded_post_count,
                "unique_users": self.unique_user_count,
                "unique_media": self.unique_media_count,
            },
            "external_requests_during_recovery": 0,
            "sync_state_writes": False,
            "database_writes": mode == "apply",
            "collection_complete": False,
            "recovery_ready": self.invalid_primary_count == 0,
        }

    def __repr__(self) -> str:
        return f"OfficialShadowRecoveryPlan({self.safe_summary()!r})"


def _load_pages(
    artifact_dir: Path,
) -> tuple[
    tuple[tuple[Path, str, object], ...],
    str,
]:
    if not artifact_dir.is_dir():
        raise ShadowRecoveryError("Official X artifact directory does not exist.")
    indexed: list[tuple[int, Path]] = []
    for path in artifact_dir.iterdir():
        match = _RESPONSE_FILE.fullmatch(path.name)
        if match:
            indexed.append((int(match.group(1)), path))
    indexed.sort()
    if not indexed:
        raise ShadowRecoveryError("Official X artifact directory has no response pages.")
    expected = list(range(1, len(indexed) + 1))
    actual = [index for index, _ in indexed]
    if actual != expected:
        raise ShadowRecoveryError("Official X response page sequence is not contiguous.")

    loaded: list[tuple[Path, str, object]] = []
    manifest = sha256()
    for _, path in indexed:
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ShadowRecoveryError(
                f"Official X artifact {path.name} is not valid JSON."
            ) from error
        manifest.update(path.name.encode("utf-8"))
        manifest.update(b"\0")
        manifest.update(digest.encode("ascii"))
        manifest.update(b"\n")
        loaded.append((path, digest, payload))
    return tuple(loaded), manifest.hexdigest()


def prepare_official_shadow_recovery(
    *,
    artifact_dir: str | Path,
    repository: RecoveryRepository,
    run_id: UUID,
    recovered_at: datetime,
) -> OfficialShadowRecoveryPlan:
    """Validate and map local pages, then inventory existing Post IDs read-only."""
    directory = Path(artifact_dir)
    artifact_run_id = directory.parent.name
    if not _ARTIFACT_RUN_ID.fullmatch(artifact_run_id):
        raise ShadowRecoveryError(
            "Artifact directory must be <run-id>/official_x with a UTC run ID."
        )
    if directory.name != "official_x":
        raise ShadowRecoveryError("Artifact directory must end in official_x.")
    if recovered_at.tzinfo is None:
        raise ValueError("recovered_at must include a timezone.")

    loaded, manifest_sha256 = _load_pages(directory)
    pages = []
    page_by_post_id: dict[str, tuple[int, str, str]] = {}
    for page_number, (path, digest, payload) in enumerate(loaded, start=1):
        response = HttpResponse(
            status=200,
            headers={},
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        )
        try:
            page = parse_content_page(
                response,
                endpoint="offline://official-x-shadow-recovery",
                elapsed=0,
            )
        except XApiRequestError as error:
            raise ShadowRecoveryError(
                f"Official X artifact {path.name} failed content-page validation."
            ) from error
        pages.append(page)
        for post in page.posts:
            post_id = str(post["id"])
            page_by_post_id.setdefault(post_id, (page_number, path.name, digest))

    users_by_id: dict[str, Mapping[str, Any]] = {}
    expanded_posts_by_id: dict[str, Mapping[str, Any]] = {}
    media_by_key: dict[str, Mapping[str, Any]] = {}
    for page in pages:
        users_by_id.update(page.users_by_id)
        expanded_posts_by_id.update(page.expanded_posts_by_id)
        media_by_key.update(page.media_by_key)

    raw_posts = tuple(post for page in pages for post in page.posts)
    unique_posts: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for post in raw_posts:
        post_id = str(post["id"])
        if post_id not in seen_ids:
            unique_posts.append(post)
            seen_ids.add(post_id)

    records: list[dict[str, Any]] = []
    valid_primary_count = 0
    invalid_primary_count = 0
    reposts_excluded = 0
    for post in unique_posts:
        post_id = str(post["id"])
        try:
            record = map_x_post(
                post,
                users_by_id=users_by_id,
                expanded_posts_by_id=expanded_posts_by_id,
                media_by_key=media_by_key,
                source="home",
                run_id=run_id,
                collected_at=recovered_at,
            )
        except CollectionError:
            invalid_primary_count += 1
            continue
        valid_primary_count += 1
        if record is None:
            reposts_excluded += 1
            continue
        page_number, filename, file_digest = page_by_post_id[post_id]
        raw_json = dict(record["raw_json"])
        collector_metadata = dict(raw_json.get("_collector") or {})
        collector_metadata["recovery"] = {
            "task": "004D",
            "method": "offline_official_x_shadow_page_recovery",
            "artifact_run_id": artifact_run_id,
            "artifact_page": page_number,
            "artifact_file": filename,
            "artifact_file_sha256": file_digest,
            "artifact_manifest_sha256": manifest_sha256,
            "source_collection_state": RECOVERY_TERMINAL_STATE,
            "source_terminal_http_status": RECOVERY_TERMINAL_HTTP_STATUS,
            "recovered_at": recovered_at.isoformat(),
            "external_requests_during_recovery": 0,
            "sync_state_updated": False,
        }
        raw_json["_collector"] = collector_metadata
        record["raw_json"] = raw_json
        records.append(record)

    post_ids = tuple(str(record["post_id"]) for record in records)
    existing_ids = repository.get_existing_post_ids(post_ids)
    return OfficialShadowRecoveryPlan(
        artifact_dir=directory,
        artifact_run_id=artifact_run_id,
        manifest_sha256=manifest_sha256,
        page_count=len(pages),
        raw_primary_count=len(raw_posts),
        unique_primary_count=len(unique_posts),
        artifact_duplicate_count=len(raw_posts) - len(unique_posts),
        valid_primary_count=valid_primary_count,
        valid_mapped_count=len(records),
        invalid_primary_count=invalid_primary_count,
        reposts_excluded=reposts_excluded,
        existing_post_ids=existing_ids,
        records=tuple(records),
        unique_expanded_post_count=len(expanded_posts_by_id),
        unique_user_count=len(users_by_id),
        unique_media_count=len(media_by_key),
    )


def apply_official_shadow_recovery(
    *,
    repository: RecoveryRepository,
    plan: OfficialShadowRecoveryPlan,
    confirmed_manifest_sha256: str,
    run_id: UUID,
    recovered_at: datetime,
    usage_event_id: UUID,
    application_version: str,
    git_commit: str | None,
    reported_post_reads: int | None,
    reported_cost_usd: Decimal | None,
) -> dict[str, object]:
    """Atomically record a recovery run and upsert mapped Posts without sync state."""
    if confirmed_manifest_sha256 != plan.manifest_sha256:
        raise ShadowRecoveryError(
            "Confirmation digest does not match the dry-run artifact manifest."
        )
    if plan.invalid_primary_count:
        raise ShadowRecoveryError("Recovery contains invalid primary Posts.")
    if reported_post_reads is not None and reported_post_reads < 0:
        raise ValueError("reported_post_reads must not be negative.")
    if reported_cost_usd is not None and reported_cost_usd < 0:
        raise ValueError("reported_cost_usd must not be negative.")

    repository.create_run(
        run_id=run_id,
        started_at=recovered_at,
        trigger_type="manual_offline_x_shadow_recovery",
        application_version=application_version,
        git_commit=git_commit,
        metadata={
            "task": "004D",
            "recovery_status": "recovered",
            "source_collection_status": RECOVERY_TERMINAL_STATE,
            "source_terminal_http_status": RECOVERY_TERMINAL_HTTP_STATUS,
            "source_artifact_run_id": plan.artifact_run_id,
            "source_artifact_manifest_sha256": plan.manifest_sha256,
            "successful_paid_pages": plan.page_count,
            "raw_primary_posts": plan.raw_primary_count,
            "valid_mapped_posts": plan.valid_mapped_count,
            "simple_reposts_excluded": plan.reposts_excluded,
            "external_requests_during_recovery": 0,
            "sync_state_updated": False,
        },
    )
    repository.upsert_posts(plan.records)
    repository.record_usage_event(
        {
            "usage_event_id": usage_event_id,
            "run_id": run_id,
            "provider": "x",
            "operation": "recover_task_004d_official_shadow",
            "request_count": plan.page_count,
            "input_units": reported_post_reads,
            "reported_cost": reported_cost_usd,
            "estimated_cost": (
                Decimal("0.005") * reported_post_reads
                if reported_post_reads is not None
                else None
            ),
            "currency": "USD" if reported_cost_usd is not None else None,
            "created_at": recovered_at,
            "metadata": {
                "historical_successful_paid_requests": plan.page_count,
                "historical_reported_post_reads": reported_post_reads,
                "billing_source": "owner_reported_x_developer_console",
                "source_collection_status": RECOVERY_TERMINAL_STATE,
                "source_terminal_http_status": RECOVERY_TERMINAL_HTTP_STATUS,
                "source_artifact_run_id": plan.artifact_run_id,
                "source_artifact_manifest_sha256": plan.manifest_sha256,
                "local_unique_primary_posts": plan.unique_primary_count,
                "local_unique_expanded_posts": plan.unique_expanded_post_count,
                "local_unique_users": plan.unique_user_count,
                "local_unique_media": plan.unique_media_count,
                "external_requests_during_recovery": 0,
                "recovered_from_local_artifacts": True,
            },
        }
    )
    repository.complete_run(
        run_id=run_id,
        finished_at=recovered_at,
        completed_with_warnings=True,
        fetched_posts_count=plan.raw_primary_count,
        new_posts_count=plan.unique_new_posts,
        rejected_posts_count=plan.reposts_excluded,
        warning_count=2,
        error_summary=(
            "Recovered saved pages offline; the original Official X collection "
            "remains incomplete after HTTP 402."
        ),
    )
    summary = plan.safe_summary(mode="apply")
    summary.update(
        {
            "run_id": str(run_id),
            "status": "incomplete_recovered",
            "historical_reported_post_reads": reported_post_reads,
            "historical_reported_cost_usd": (
                format(reported_cost_usd, "f")
                if reported_cost_usd is not None
                else None
            ),
        }
    )
    return summary

"""Explicit, parameterized PostgreSQL persistence operations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


JsonObject = Mapping[str, Any]


class StorageRepository:
    """Small storage interface operating on a caller-owned transaction."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def create_run(
        self,
        *,
        run_id: UUID,
        started_at: datetime,
        trigger_type: str,
        application_version: str | None = None,
        git_commit: str | None = None,
        metadata: JsonObject | None = None,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO runs (
                run_id, started_at, status, trigger_type, application_version,
                git_commit, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                started_at,
                "running",
                trigger_type,
                application_version,
                git_commit,
                Jsonb(dict(metadata or {})),
            ),
        )

    def complete_run(
        self,
        *,
        run_id: UUID,
        finished_at: datetime,
        completed_with_warnings: bool = False,
        fetched_posts_count: int = 0,
        new_posts_count: int = 0,
        rejected_posts_count: int = 0,
        signals_count: int = 0,
        opportunities_count: int = 0,
        warning_count: int = 0,
    ) -> None:
        status = "completed_with_warnings" if completed_with_warnings else "completed"
        self._connection.execute(
            """
            UPDATE runs
            SET finished_at = %s, status = %s, fetched_posts_count = %s,
                new_posts_count = %s, rejected_posts_count = %s,
                signals_count = %s, opportunities_count = %s, warning_count = %s
            WHERE run_id = %s
            """,
            (
                finished_at,
                status,
                fetched_posts_count,
                new_posts_count,
                rejected_posts_count,
                signals_count,
                opportunities_count,
                warning_count,
                run_id,
            ),
        )

    def fail_run(
        self,
        *,
        run_id: UUID,
        finished_at: datetime,
        error_summary: str,
        warning_count: int = 0,
    ) -> None:
        self._connection.execute(
            """
            UPDATE runs
            SET finished_at = %s, status = %s, error_summary = %s,
                warning_count = %s
            WHERE run_id = %s
            """,
            (finished_at, "failed", error_summary, warning_count, run_id),
        )

    def upsert_posts(self, posts: Iterable[JsonObject]) -> None:
        statement = """
            INSERT INTO posts (
                post_id, author_id, author_username, created_at, conversation_id,
                referenced_post_id, post_type, source_key, text, raw_json,
                first_seen_run_id, last_seen_run_id, first_collected_at,
                last_collected_at, processing_status, rejection_stage,
                rejection_reason, availability_status, last_verified_at,
                content_deleted_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (post_id) DO UPDATE SET
                author_id = EXCLUDED.author_id,
                author_username = EXCLUDED.author_username,
                created_at = EXCLUDED.created_at,
                conversation_id = EXCLUDED.conversation_id,
                referenced_post_id = EXCLUDED.referenced_post_id,
                post_type = EXCLUDED.post_type,
                source_key = EXCLUDED.source_key,
                text = EXCLUDED.text,
                raw_json = EXCLUDED.raw_json,
                last_seen_run_id = EXCLUDED.last_seen_run_id,
                last_collected_at = EXCLUDED.last_collected_at,
                processing_status = EXCLUDED.processing_status,
                rejection_stage = EXCLUDED.rejection_stage,
                rejection_reason = EXCLUDED.rejection_reason,
                availability_status = EXCLUDED.availability_status,
                last_verified_at = EXCLUDED.last_verified_at,
                content_deleted_at = EXCLUDED.content_deleted_at
        """
        parameters = []
        for post in posts:
            parameters.append(
                (
                    post["post_id"],
                    post.get("author_id"),
                    post.get("author_username"),
                    post["created_at"],
                    post.get("conversation_id"),
                    post.get("referenced_post_id"),
                    post["post_type"],
                    post["source_key"],
                    post["text"],
                    Jsonb(dict(post["raw_json"])),
                    post["first_seen_run_id"],
                    post["last_seen_run_id"],
                    post["first_collected_at"],
                    post["last_collected_at"],
                    post["processing_status"],
                    post.get("rejection_stage"),
                    post.get("rejection_reason"),
                    post["availability_status"],
                    post.get("last_verified_at"),
                    post.get("content_deleted_at"),
                )
            )
        if parameters:
            with self._connection.cursor() as cursor:
                cursor.executemany(statement, parameters)

    def get_sync_state(self, source_key: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT source_key, checkpoint_value, checkpoint_metadata,
                last_attempt_at, last_successful_at, last_successful_run_id,
                last_warning_code, updated_at
            FROM sync_state
            WHERE source_key = %s
            """,
            (source_key,),
        ).fetchone()
        if row is None:
            return None
        columns = (
            "source_key",
            "checkpoint_value",
            "checkpoint_metadata",
            "last_attempt_at",
            "last_successful_at",
            "last_successful_run_id",
            "last_warning_code",
            "updated_at",
        )
        return dict(zip(columns, row, strict=True))

    def update_sync_state(
        self,
        *,
        source_key: str,
        checkpoint_value: str | None,
        checkpoint_metadata: JsonObject,
        last_attempt_at: datetime | None,
        last_successful_at: datetime | None,
        last_successful_run_id: UUID | None,
        last_warning_code: str | None,
        updated_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO sync_state (
                source_key, checkpoint_value, checkpoint_metadata,
                last_attempt_at, last_successful_at, last_successful_run_id,
                last_warning_code, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_key) DO UPDATE SET
                checkpoint_value = EXCLUDED.checkpoint_value,
                checkpoint_metadata = EXCLUDED.checkpoint_metadata,
                last_attempt_at = EXCLUDED.last_attempt_at,
                last_successful_at = EXCLUDED.last_successful_at,
                last_successful_run_id = EXCLUDED.last_successful_run_id,
                last_warning_code = EXCLUDED.last_warning_code,
                updated_at = EXCLUDED.updated_at
            """,
            (
                source_key,
                checkpoint_value,
                Jsonb(dict(checkpoint_metadata)),
                last_attempt_at,
                last_successful_at,
                last_successful_run_id,
                last_warning_code,
                updated_at,
            ),
        )

    def create_signal(self, signal: JsonObject) -> None:
        self._connection.execute(
            """
            INSERT INTO signals (
                signal_id, created_at, updated_at, first_run_id, title, summary,
                topic, status, gate_decision, gate_reason, evidence, inferences,
                uncertainties, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                signal["signal_id"],
                signal["created_at"],
                signal["updated_at"],
                signal["first_run_id"],
                signal["title"],
                signal["summary"],
                signal.get("topic"),
                signal["status"],
                signal["gate_decision"],
                signal.get("gate_reason"),
                Jsonb(list(signal.get("evidence", []))),
                Jsonb(list(signal.get("inferences", []))),
                Jsonb(list(signal.get("uncertainties", []))),
                Jsonb(dict(signal.get("metadata", {}))),
            ),
        )

    def attach_posts_to_signal(
        self,
        *,
        signal_id: UUID,
        posts: Iterable[tuple[str, str]],
        added_at: datetime,
    ) -> None:
        parameters = [
            (signal_id, post_id, relationship_type, added_at)
            for post_id, relationship_type in posts
        ]
        if parameters:
            with self._connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO signal_posts (
                        signal_id, post_id, relationship_type, added_at
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (signal_id, post_id) DO UPDATE SET
                        relationship_type = EXCLUDED.relationship_type,
                        added_at = EXCLUDED.added_at
                    """,
                    parameters,
                )

    def create_opportunity(self, opportunity: JsonObject) -> None:
        self._connection.execute(
            """
            INSERT INTO opportunities (
                opportunity_id, signal_id, created_at, updated_at,
                opportunity_type, information_gap, audience_benefit, asset_id,
                natural_relevance_reason, recommended_action, gate_snapshot,
                evidence, verified_facts, inferences, uncertainties, draft_text,
                visual_required, visual_brief, review_status,
                current_review_comment, edited_text, published_url, reviewed_at,
                metadata
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                opportunity["opportunity_id"],
                opportunity["signal_id"],
                opportunity["created_at"],
                opportunity["updated_at"],
                opportunity["opportunity_type"],
                opportunity["information_gap"],
                opportunity["audience_benefit"],
                opportunity.get("asset_id"),
                opportunity["natural_relevance_reason"],
                opportunity["recommended_action"],
                Jsonb(dict(opportunity["gate_snapshot"])),
                Jsonb(list(opportunity.get("evidence", []))),
                Jsonb(list(opportunity.get("verified_facts", []))),
                Jsonb(list(opportunity.get("inferences", []))),
                Jsonb(list(opportunity.get("uncertainties", []))),
                opportunity.get("draft_text"),
                opportunity.get("visual_required", False),
                (
                    Jsonb(dict(opportunity["visual_brief"]))
                    if opportunity.get("visual_brief") is not None
                    else None
                ),
                opportunity["review_status"],
                opportunity.get("current_review_comment"),
                opportunity.get("edited_text"),
                opportunity.get("published_url"),
                opportunity.get("reviewed_at"),
                Jsonb(dict(opportunity.get("metadata", {}))),
            ),
        )

    def add_human_review(self, review: JsonObject) -> None:
        self._connection.execute(
            """
            INSERT INTO human_reviews (
                review_id, opportunity_id, reviewer, decision, reason,
                edited_text, published_url, created_at, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review["review_id"],
                review["opportunity_id"],
                review["reviewer"],
                review["decision"],
                review.get("reason"),
                review.get("edited_text"),
                review.get("published_url"),
                review["created_at"],
                Jsonb(dict(review.get("metadata", {}))),
            ),
        )

    def record_usage_event(self, event: JsonObject) -> None:
        self._connection.execute(
            """
            INSERT INTO usage_events (
                usage_event_id, run_id, provider, operation, model,
                request_count, input_units, output_units, reported_cost,
                estimated_cost, currency, created_at, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event["usage_event_id"],
                event["run_id"],
                event["provider"],
                event["operation"],
                event.get("model"),
                event["request_count"],
                event.get("input_units"),
                event.get("output_units"),
                event.get("reported_cost"),
                event.get("estimated_cost"),
                event.get("currency"),
                event["created_at"],
                Jsonb(dict(event.get("metadata", {}))),
            ),
        )

from datetime import datetime, timezone
import inspect
from uuid import UUID

from x_signal_finder.db.repository import StorageRepository


class RecordingConnection:
    def __init__(self) -> None:
        self.query = ""
        self.parameters = ()

    def execute(self, query, parameters=()):
        self.query = str(query)
        self.parameters = parameters
        return self

    def fetchall(self):
        return [("known-post",)]


def test_create_run_uses_bound_parameters() -> None:
    connection = RecordingConnection()
    repository = StorageRepository(connection)  # type: ignore[arg-type]
    sensitive_trigger = "value-that-must-not-be-in-sql"

    repository.create_run(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        trigger_type=sensitive_trigger,
        metadata={"synthetic": True},
    )

    assert sensitive_trigger not in connection.query
    assert "%s" in connection.query
    assert sensitive_trigger in connection.parameters


def test_existing_post_lookup_uses_bound_array() -> None:
    connection = RecordingConnection()
    repository = StorageRepository(connection)  # type: ignore[arg-type]

    existing = repository.get_existing_post_ids(["known-post", "new-post"])

    assert existing == frozenset({"known-post"})
    assert "known-post" not in connection.query
    assert connection.parameters == (["known-post", "new-post"],)


def test_post_upsert_preserves_first_seen_and_workflow_fields() -> None:
    source = inspect.getsource(StorageRepository.upsert_posts)
    conflict_update = source.split("ON CONFLICT (post_id) DO UPDATE SET", 1)[1]

    assert "first_seen_run_id =" not in conflict_update
    assert "first_collected_at =" not in conflict_update
    assert "processing_status =" not in conflict_update
    assert "rejection_stage =" not in conflict_update
    assert "rejection_reason =" not in conflict_update
    assert "availability_status =" not in conflict_update
    assert "content_deleted_at =" not in conflict_update
    for field in (
        "author_id",
        "author_username",
        "created_at",
        "conversation_id",
        "referenced_post_id",
        "post_type",
        "source_key",
        "text",
        "raw_json",
        "last_seen_run_id",
        "last_collected_at",
        "last_verified_at",
    ):
        assert f"{field} = EXCLUDED.{field}" in conflict_update

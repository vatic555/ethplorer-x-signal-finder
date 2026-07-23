from datetime import datetime, timezone
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

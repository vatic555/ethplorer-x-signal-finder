import os

import psycopg
import pytest

from x_signal_finder.config import DatabaseConfig
from x_signal_finder.db.connection import connect_database


pytestmark = pytest.mark.integration


@pytest.fixture
def test_database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return value


def test_explicit_test_database_connection(test_database_url: str) -> None:
    config = DatabaseConfig(test_database_url)
    with connect_database(config) as connection:
        version = connection.execute("SHOW server_version").fetchone()
        connection.rollback()

    assert version is not None
    assert isinstance(version[0], str)
    assert psycopg.__version__

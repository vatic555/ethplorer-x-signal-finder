"""PostgreSQL connection creation."""

from __future__ import annotations

import psycopg

from x_signal_finder.config import DatabaseConfig


def connect_database(config: DatabaseConfig) -> psycopg.Connection:
    """Create a non-autocommit PostgreSQL connection."""
    return psycopg.connect(config.database_url, autocommit=False)

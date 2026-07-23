"""Application configuration with deliberate secret handling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from dotenv import dotenv_values


class ConfigurationError(ValueError):
    """Raised when required application configuration is invalid."""


_POSTGRES_URL = re.compile(
    r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]+",
    flags=re.IGNORECASE,
)


def redact_secrets(value: object) -> str:
    """Return text with complete PostgreSQL connection strings redacted."""
    return _POSTGRES_URL.sub("<redacted PostgreSQL connection>", str(value))


@dataclass(frozen=True, repr=False)
class DatabaseConfig:
    """Validated database configuration whose representation hides its URL."""

    database_url: str

    def __post_init__(self) -> None:
        url = self.database_url.strip()
        if not url:
            raise ConfigurationError(
                "DATABASE_URL is required for database commands."
            )
        if not re.match(r"^postgres(?:ql)?(?:\+\w+)?://", url, re.IGNORECASE):
            raise ConfigurationError(
                "DATABASE_URL must be a PostgreSQL connection string."
            )
        try:
            parsed = urlsplit(url)
            parsed.port
        except ValueError as error:
            raise ConfigurationError(
                "DATABASE_URL is malformed. Percent-encode reserved characters "
                "in the username or password."
            ) from error
        if url.count("@") > 1 or ("@" in url and "@" not in parsed.netloc):
            raise ConfigurationError(
                "DATABASE_URL contains an unescaped reserved character. "
                "Percent-encode reserved characters in the username or password."
            )
        object.__setattr__(self, "database_url", url)

    def __repr__(self) -> str:
        return "DatabaseConfig(database_url='<redacted>')"

    __str__ = __repr__


def load_database_config(
    *,
    environ: Mapping[str, str] | None = None,
    dotenv_path: str | Path | None = None,
) -> DatabaseConfig:
    """Load DATABASE_URL without modifying process-global environment state.

    Values in ``environ`` take precedence over values read from ``.env``.
    Tests can pass an isolated mapping and a temporary dotenv path.
    """
    environment = os.environ if environ is None else environ
    path = Path(".env") if dotenv_path is None else Path(dotenv_path)
    file_values = dotenv_values(path) if path.is_file() else {}
    database_url = (
        environment["DATABASE_URL"]
        if "DATABASE_URL" in environment
        else file_values.get("DATABASE_URL")
    )
    return DatabaseConfig(database_url=database_url or "")

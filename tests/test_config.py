from pathlib import Path

import pytest

from x_signal_finder.config import (
    ConfigurationError,
    DatabaseConfig,
    load_database_config,
    redact_secrets,
)


def test_environment_overrides_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "DATABASE_URL=postgresql://file-user:file-pass@file-host/db\n",
        encoding="utf-8",
    )

    config = load_database_config(
        environ={
            "DATABASE_URL": "postgresql://env-user:env-pass@env-host/db",
        },
        dotenv_path=dotenv_path,
    )

    assert config.database_url == "postgresql://env-user:env-pass@env-host/db"


def test_empty_environment_value_does_not_fall_back_to_dotenv(
    tmp_path: Path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "DATABASE_URL=postgresql://file-user:file-pass@file-host/db\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="DATABASE_URL is required"):
        load_database_config(
            environ={"DATABASE_URL": ""},
            dotenv_path=dotenv_path,
        )


def test_configuration_repr_and_redaction_hide_connection_string() -> None:
    url = "postgresql://secret-user:secret-pass@example.test/database?sslmode=require"
    config = DatabaseConfig(url)

    assert url not in repr(config)
    assert "secret-pass" not in repr(config)
    redacted = redact_secrets(f"failed while opening {url}")
    assert url not in redacted
    assert "secret-pass" not in redacted
    assert "<redacted PostgreSQL connection>" in redacted


def test_non_postgresql_url_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="PostgreSQL"):
        DatabaseConfig("sqlite:///runtime.db")


def test_unescaped_at_sign_in_password_is_rejected_without_echoing_url() -> None:
    url = "postgresql://user:secret@fragment@host.example/database"

    with pytest.raises(ConfigurationError, match="unescaped") as raised:
        DatabaseConfig(url)

    assert url not in str(raised.value)
    assert "secret" not in str(raised.value)

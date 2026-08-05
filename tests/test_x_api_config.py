from pathlib import Path

import pytest

from x_signal_finder.x_api.config import (
    XApiConfigurationError,
    load_x_api_config,
    persist_refresh_token,
)


def test_x_environment_overrides_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "X_ACCESS_TOKEN=file-token\nX_HOME_USER_ID=100\n",
        encoding="utf-8",
    )

    config = load_x_api_config(
        environ={"X_ACCESS_TOKEN": "environment-token", "X_HOME_USER_ID": "200"},
        dotenv_path=dotenv_path,
    )

    assert config.access_token == "environment-token"
    assert config.home_user_id == "200"
    assert "environment-token" not in repr(config)


def test_missing_credentials_fail_before_any_request(tmp_path: Path) -> None:
    config = load_x_api_config(environ={}, dotenv_path=tmp_path / "missing")

    with pytest.raises(XApiConfigurationError, match="X_ACCESS_TOKEN"):
        config.token_for("home")
    with pytest.raises(XApiConfigurationError, match="X_BEARER_TOKEN"):
        config.token_for("mentions")


def test_user_ids_must_be_numeric(tmp_path: Path) -> None:
    config = load_x_api_config(
        environ={"X_HOME_USER_ID": "not-an-id"},
        dotenv_path=tmp_path / "missing",
    )

    with pytest.raises(XApiConfigurationError, match="digits"):
        config.user_id_for("home")


def test_refresh_token_is_persisted_only_to_existing_local_env(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "X_CLIENT_ID=synthetic-client\nX_REFRESH_TOKEN=\n",
        encoding="utf-8",
    )

    persist_refresh_token("synthetic-rotated-token", dotenv_path=dotenv_path)

    config = load_x_api_config(environ={}, dotenv_path=dotenv_path)
    assert config.client_id == "synthetic-client"
    assert config.refresh_token == "synthetic-rotated-token"

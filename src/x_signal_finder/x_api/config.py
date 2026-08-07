"""Environment-only configuration for the X API diagnostic spike."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re

from dotenv import dotenv_values, set_key


X_API_BASE_URL = "https://api.x.com/2"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
_USER_ID = re.compile(r"^[0-9]{1,19}$")


class XApiConfigurationError(ValueError):
    """Raised when required X API diagnostic configuration is unavailable."""


@dataclass(frozen=True, repr=False)
class XApiConfig:
    """Validated X API credentials and IDs with secret-safe representation."""

    client_id: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI
    access_token: str = ""
    refresh_token: str = ""
    bearer_token: str = ""
    home_user_id: str = ""
    ethplorer_user_id: str = ""
    post_read_unit_cost_usd: Decimal = Decimal("0.005")
    base_url: str = X_API_BASE_URL

    def __repr__(self) -> str:
        return (
            "XApiConfig(client_id='<redacted>', redirect_uri="
            f"{self.redirect_uri!r}, access_token='<redacted>', "
            "refresh_token='<redacted>', bearer_token='<redacted>', "
            f"home_user_id={self.home_user_id!r}, "
            f"ethplorer_user_id={self.ethplorer_user_id!r})"
        )

    __str__ = __repr__

    def user_id_for(self, source: str, explicit_user_id: str | None = None) -> str:
        value = explicit_user_id or (
            self.home_user_id if source == "home" else self.ethplorer_user_id
        )
        if not value:
            variable = "X_HOME_USER_ID" if source == "home" else "X_ETHPLORER_USER_ID"
            raise XApiConfigurationError(
                f"A user ID is required. Set {variable} or pass --user-id."
            )
        if not _USER_ID.fullmatch(value):
            raise XApiConfigurationError("X user IDs must contain 1 to 19 digits.")
        return value

    def token_for(self, source: str) -> str:
        if source == "home":
            if not self.access_token:
                raise XApiConfigurationError(
                    "X_ACCESS_TOKEN with OAuth user context is required for the home probe."
                )
            return self.access_token
        token = self.bearer_token or self.access_token
        if not token:
            raise XApiConfigurationError(
                "X_BEARER_TOKEN or X_ACCESS_TOKEN is required for the mentions probe."
            )
        return token

    def require_oauth_setup(self) -> None:
        if not self.client_id:
            raise XApiConfigurationError(
                "X_CLIENT_ID is required for OAuth 2.0 PKCE authorization."
            )

    def require_collector_setup(self) -> None:
        self.require_oauth_setup()
        if not self.refresh_token:
            raise XApiConfigurationError(
                "X_REFRESH_TOKEN is required. Run `python -m x_signal_finder "
                "x-api oauth-setup` once."
            )


def load_x_api_config(
    *,
    environ: Mapping[str, str] | None = None,
    dotenv_path: str | Path | None = None,
) -> XApiConfig:
    """Load X configuration without mutating process-global environment state."""
    environment = os.environ if environ is None else environ
    path = Path(".env") if dotenv_path is None else Path(dotenv_path)
    file_values = dotenv_values(path) if path.is_file() else {}

    def value(name: str, default: str = "") -> str:
        raw = environment[name] if name in environment else file_values.get(name, default)
        return str(raw or "").strip()

    raw_unit_cost = value("X_POST_READ_UNIT_COST_USD", "0.005") or "0.005"
    try:
        unit_cost = Decimal(raw_unit_cost)
    except InvalidOperation as error:
        raise XApiConfigurationError(
            "X_POST_READ_UNIT_COST_USD must be a decimal number."
        ) from error
    if unit_cost <= 0:
        raise XApiConfigurationError(
            "X_POST_READ_UNIT_COST_USD must be positive."
        )

    return XApiConfig(
        client_id=value("X_CLIENT_ID"),
        redirect_uri=value("X_REDIRECT_URI", DEFAULT_REDIRECT_URI)
        or DEFAULT_REDIRECT_URI,
        access_token=value("X_ACCESS_TOKEN"),
        refresh_token=value("X_REFRESH_TOKEN"),
        bearer_token=value("X_BEARER_TOKEN"),
        home_user_id=value("X_HOME_USER_ID"),
        ethplorer_user_id=value("X_ETHPLORER_USER_ID"),
        post_read_unit_cost_usd=unit_cost,
    )


def persist_refresh_token(
    refresh_token: str,
    *,
    dotenv_path: str | Path = ".env",
) -> None:
    """Persist only the refresh token in an existing local dotenv file."""
    if not refresh_token:
        raise XApiConfigurationError("A non-empty X refresh token is required.")
    path = Path(dotenv_path)
    if not path.is_file():
        raise XApiConfigurationError(
            "Local .env does not exist. Create it from .env.example first."
        )
    success, _, _ = set_key(
        str(path),
        "X_REFRESH_TOKEN",
        refresh_token,
        quote_mode="always",
    )
    if not success:
        raise XApiConfigurationError("Could not update X_REFRESH_TOKEN in local .env.")

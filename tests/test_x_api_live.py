import os
from pathlib import Path

import pytest

from x_signal_finder.x_api.client import XApiClient
from x_signal_finder.x_api.config import load_x_api_config
from x_signal_finder.x_api.probe import run_probe


pytestmark = pytest.mark.x_api_live


def test_live_home_probe_is_read_only_and_does_not_persist() -> None:
    config = load_x_api_config(
        environ=os.environ,
        dotenv_path=Path("/definitely-not-loaded-by-live-test"),
    )
    if not config.access_token or not config.home_user_id:
        pytest.skip("X_ACCESS_TOKEN and X_HOME_USER_ID are not configured")

    summary = run_probe(
        client=XApiClient(token=config.access_token),
        source="home",
        user_id=config.home_user_id,
        max_pages=1,
        max_results=10,
    )

    assert summary.http_results == (200,)


def test_live_mentions_probe_is_read_only_and_does_not_persist() -> None:
    config = load_x_api_config(
        environ=os.environ,
        dotenv_path=Path("/definitely-not-loaded-by-live-test"),
    )
    token = config.bearer_token or config.access_token
    if not token or not config.ethplorer_user_id:
        pytest.skip(
            "X_BEARER_TOKEN or X_ACCESS_TOKEN and X_ETHPLORER_USER_ID are not configured"
        )

    summary = run_probe(
        client=XApiClient(token=token),
        source="mentions",
        user_id=config.ethplorer_user_id,
        max_pages=1,
        max_results=10,
    )

    assert summary.http_results == (200,)

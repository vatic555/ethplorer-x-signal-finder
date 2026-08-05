import pytest


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-x-api-live",
        action="store_true",
        default=False,
        help="Run explicitly opted-in live X API access-spike tests.",
    )


def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--run-x-api-live"):
        return
    skip = pytest.mark.skip(reason="requires explicit --run-x-api-live opt-in")
    for item in items:
        if "x_api_live" in item.keywords:
            item.add_marker(skip)

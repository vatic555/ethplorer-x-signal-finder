from x_signal_finder.cli import build_parser, main


def test_database_subcommands_parse() -> None:
    parser = build_parser()

    for subcommand in ("doctor", "migrate", "status", "smoke-test"):
        args = parser.parse_args(["db", subcommand])
        assert args.command == "db"
        assert args.db_command == subcommand


def test_project_status_does_not_require_database(capsys) -> None:
    result = main(["status"])

    assert result == 0
    output = capsys.readouterr().out
    assert "PostgreSQL storage foundation is implemented" in output
    assert "access spike is complete with a constrained-go decision" in output
    assert "Task 004B content completeness and review views are complete" in output


def test_x_api_subcommands_parse() -> None:
    parser = build_parser()

    args = parser.parse_args(["x-api", "probe", "home", "--user-id", "123"])
    assert args.command == "x-api"
    assert args.x_api_command == "probe"
    assert args.source == "home"

    oauth_setup = parser.parse_args(["x-api", "oauth-setup"])
    assert oauth_setup.x_api_command == "oauth-setup"


def test_collect_defaults_are_bounded() -> None:
    args = build_parser().parse_args(["collect", "--source", "home"])

    assert args.command == "collect"
    assert args.max_pages == 1
    assert args.max_results == 20
    assert args.refresh_existing is False


def test_collect_refresh_existing_requires_explicit_flag() -> None:
    args = build_parser().parse_args(
        ["collect", "--source", "home", "--refresh-existing"]
    )

    assert args.refresh_existing is True


def test_collect_rejects_invalid_shared_page_size_before_external_calls(capsys) -> None:
    result = main(["collect", "--source", "both", "--max-results", "1"])

    assert result == 2
    assert "max_results for mentions" in capsys.readouterr().err


def test_x_api_probe_without_credentials_fails_before_network(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "X_ACCESS_TOKEN",
        "X_BEARER_TOKEN",
        "X_HOME_USER_ID",
        "X_ETHPLORER_USER_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    result = main(["x-api", "probe", "home", "--user-id", "123"])

    assert result == 2
    assert "X_ACCESS_TOKEN" in capsys.readouterr().err

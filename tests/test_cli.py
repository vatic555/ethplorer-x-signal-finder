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
    assert "PostgreSQL storage foundation is implemented" in capsys.readouterr().out

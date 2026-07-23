# Tests

Run the default cross-platform test suite with:

```text
python -m pytest
```

Default tests require no credentials and make no external API calls. They cover configuration precedence and redaction, migration ordering and checksums, CLI parsing, and parameterized repository SQL.

Tests marked `integration` are optional. They require `TEST_DATABASE_URL`, never use `DATABASE_URL` automatically, and are skipped when the explicit test connection is absent:

```text
python -m pytest -m integration
```

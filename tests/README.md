# Tests

Run the default cross-platform test suite with:

```text
python -m pytest
```

Default tests require no credentials and make no external API calls. They cover configuration precedence and redaction, migration ordering and checksums, CLI parsing, parameterized repository SQL, X response parsing, pagination metadata, checkpoint outcomes, OAuth PKCE helpers, collector mapping, simple-repost exclusion, source keys, deduplication counts, safe checkpoint updates, refresh-token persistence, and secret-safe output.

Tests marked `integration` are optional. They require `TEST_DATABASE_URL`, never use `DATABASE_URL` automatically, and are skipped when the explicit test connection is absent:

```text
python -m pytest -m integration
```

Tests marked `x_api_live` are also optional and require both explicit opt-in and the relevant environment variables. They never load `.env`, never access PostgreSQL, never persist API responses, and request at most one page per source:

```text
python -m pytest -m x_api_live --run-x-api-live
```

Without `--run-x-api-live`, these tests are always skipped even if credentials exist in the environment.

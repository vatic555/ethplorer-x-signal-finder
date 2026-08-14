# Database Migrations

Numbered PostgreSQL migrations are discovered from this directory and applied in ascending numeric order by:

```text
python -m x_signal_finder db migrate
```

Migration file names use `<version>_<name>.sql`, such as `001_initial_schema.sql`, `002_content_review_views.sql`, `003_first_party_x_corpus.sql`, and `004_first_party_x_review_fields.sql`.

Migration 003 creates the permanent PostgreSQL first-party Ethplorer/Binplorer X editorial corpus and its ordered direct-reference table. It keeps this operational X content separate from incoming `posts` and enables RLS on both new tables.

Migration 004 adds the safe relational unavailable-reference reason and two security-invoker first-party review views for stored resolved URLs and canonical Post inspection. It backfills historical unavailable rows as `unknown` without an X request and does not modify migration 003.

Each applied migration is recorded in `schema_migrations` with its version, file name, SHA-256 checksum, and application timestamp. Migrations are applied one at a time inside explicit transactions. Re-running the command is safe. If an applied migration is missing or its content has changed, execution fails instead of silently reapplying it.

Never edit an applied migration. Add a new numbered migration for every schema change. Migrations must remain standard PostgreSQL and must not include secrets, runtime data, provider API keys, or Supabase-specific SDK calls.

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from x_signal_finder.config import DatabaseConfig
from x_signal_finder.db.connection import connect_database
from x_signal_finder.db.migrations import discover_migrations, get_migration_status
from x_signal_finder.db.repository import StorageRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def test_database_config() -> DatabaseConfig:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return DatabaseConfig(value)


def test_explicit_test_database_connection(
    test_database_config: DatabaseConfig,
) -> None:
    with connect_database(test_database_config) as connection:
        version = connection.execute("SHOW server_version").fetchone()
        connection.rollback()

    assert version is not None
    assert isinstance(version[0], str)
    assert psycopg.__version__


def test_content_review_views_with_synthetic_posts(
    test_database_config: DatabaseConfig,
) -> None:
    migrations = discover_migrations(Path(__file__).parents[1] / "migrations")
    with connect_database(test_database_config) as connection:
        status = get_migration_status(connection, migrations)
        if status.pending:
            pytest.skip("All migrations must be applied explicitly before this test")

        run_id = uuid4()
        now = datetime(2026, 1, 30, tzinfo=timezone.utc)
        try:
            with connection.transaction(force_rollback=True):
                connection.execute(
                    """
                    INSERT INTO runs (run_id, started_at, status, trigger_type)
                    VALUES (%s, %s, 'running', 'synthetic_integration_test')
                    """,
                    (run_id, now),
                )

                rows = []

                def add_post(
                    post_id,
                    *,
                    author_id,
                    username,
                    created_at,
                    text,
                    post_type="original",
                    referenced_post_id=None,
                    raw_json=None,
                ):
                    rows.append(
                        (
                            post_id,
                            author_id,
                            username,
                            created_at,
                            post_id,
                            referenced_post_id,
                            post_type,
                            "x_home_timeline",
                            text,
                            Jsonb(raw_json or {"id": post_id, "text": text}),
                            run_id,
                            run_id,
                            now,
                            now,
                            "unprocessed",
                            "available",
                            now,
                        )
                    )

                add_post(
                    "synthetic-review-quote",
                    author_id="synthetic-review-author",
                    username="review_author",
                    created_at=now,
                    text="complete main note text",
                    post_type="quote",
                    referenced_post_id="synthetic-reference",
                    raw_json={
                        "id": "synthetic-review-quote",
                        "text": "truncated",
                        "note_tweet": {"text": "complete main note text"},
                        "attachments": {"media_keys": ["m1", "m2"]},
                        "_collector": {"full_text_source": "note_tweet"},
                        "_expanded": {
                            "referenced_post": {
                                "id": "synthetic-reference",
                                "text": "referenced truncated",
                                "note_tweet": {"text": "referenced complete"},
                            },
                            "referenced_post_author": {
                                "id": "synthetic-referenced-author",
                                "username": "referenced_author",
                            },
                            "media": [
                                {"media_key": "m1", "type": "photo"},
                                {"media_key": "m2", "type": "video"},
                            ],
                        },
                    },
                )
                add_post(
                    "synthetic-review-reply",
                    author_id="synthetic-review-replier",
                    username=None,
                    created_at=now,
                    text="FT @review_author",
                    post_type="reply",
                    referenced_post_id="synthetic-review-quote",
                )
                for index in range(20):
                    add_post(
                        f"synthetic-volume-{index}",
                        author_id="synthetic-volume-author",
                        username="volume_author",
                        created_at=now - timedelta(hours=index),
                        text="ordinary unrelated observation",
                    )
                    add_post(
                        f"synthetic-keyword-{index}",
                        author_id="synthetic-keyword-author",
                        username="keyword_author",
                        created_at=now - timedelta(hours=index),
                        text="Ethereum update",
                    )
                for index, days in enumerate((0, 8)):
                    add_post(
                        f"synthetic-span-{index}",
                        author_id="synthetic-span-author",
                        username="span_author",
                        created_at=now - timedelta(days=days),
                        text="ordinary unrelated observation",
                    )

                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO posts (
                            post_id, author_id, author_username, created_at,
                            conversation_id, referenced_post_id, post_type,
                            source_key, text, raw_json, first_seen_run_id,
                            last_seen_run_id, first_collected_at, last_collected_at,
                            processing_status, availability_status, last_verified_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        rows,
                    )

                review = connection.execute(
                    """
                    SELECT post_url, full_text_source, has_media, has_video,
                        media_types, media_count, referenced_post_url,
                        referenced_post_text, low_information_reply_candidate
                    FROM posts_review
                    WHERE post_id = 'synthetic-review-quote'
                    """
                ).fetchone()
                assert review == (
                    "https://x.com/review_author/status/synthetic-review-quote",
                    "note_tweet",
                    True,
                    True,
                    ["photo", "video"],
                    2,
                    "https://x.com/referenced_author/status/synthetic-reference",
                    "referenced complete",
                    False,
                )

                reply = connection.execute(
                    """
                    SELECT post_url, referenced_post_url,
                        low_information_reply_candidate, processing_status
                    FROM posts_review
                    WHERE post_id = 'synthetic-review-reply'
                    """
                ).fetchone()
                assert reply == (
                    "https://x.com/i/web/status/synthetic-review-reply",
                    "https://x.com/i/web/status/synthetic-review-quote",
                    True,
                    "unprocessed",
                )

                volume_stats = connection.execute(
                    """
                    SELECT observed_posts, blockchain_keyword_matches,
                        estimated_stored_post_cost_usd
                    FROM author_source_stats
                    WHERE author_id = 'synthetic-volume-author'
                    """
                ).fetchone()
                assert volume_stats == (20, 0, Decimal("0.100"))

                candidates = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT username
                        FROM author_unfollow_candidates
                        WHERE username IN (
                            'volume_author', 'span_author', 'keyword_author'
                        )
                        """
                    ).fetchall()
                }
                assert candidates == {"volume_author", "span_author"}
        finally:
            connection.rollback()


def test_first_party_reference_reasons_and_url_review_views(
    test_database_config: DatabaseConfig,
) -> None:
    migrations = discover_migrations(Path(__file__).parents[1] / "migrations")
    with connect_database(test_database_config) as connection:
        status = get_migration_status(connection, migrations)
        if status.pending:
            pytest.skip("All migrations must be applied explicitly before this test")

        run_id = uuid4()
        now = datetime(2026, 8, 14, tzinfo=timezone.utc)
        canonical_text = "complete canonical note_tweet text"
        article_url = (
            "https://ethplorer.io/posts/"
            "ethereum-rich-list-by-aggregated-usd-holdings-part-1"
        )
        common_url = {
            "url": "https://t.co/common",
            "expanded_url": "https://ethplorer.io/posts/common-article",
        }
        post = {
            "post_id": "synthetic-first-party-review",
            "source_account": "ethplorer",
            "source_user_id": "synthetic-source-user",
            "author_id": "synthetic-first-party-author",
            "author_username": "ethplorer",
            "post_url": (
                "https://x.com/ethplorer/status/synthetic-first-party-review"
            ),
            "created_at": now,
            "conversation_id": "synthetic-first-party-review",
            "in_reply_to_user_id": None,
            "post_type": "quote",
            "text": canonical_text,
            "lang": "en",
            "entities": {
                "urls": [
                    common_url,
                    {
                        "url": "https://t.co/unwound",
                        "expanded_url": "https://ethplorer.io/posts/expanded",
                        "unwound_url": "https://ethplorer.io/posts/unwound",
                    },
                    {
                        "url": "https://t.co/binplorer",
                        "expanded_url": "https://binplorer.com/token/1",
                    },
                    {
                        "url": "https://t.co/second",
                        "expanded_url": "https://example.test/second",
                    },
                ]
            },
            "public_metrics": {},
            "media_metadata": [],
            "referenced_relationships": [],
            "referenced_context_state": "unavailable",
            "raw_json": {
                "id": "synthetic-first-party-review",
                "text": "truncated",
                "note_tweet": {
                    "text": canonical_text,
                    "entities": {
                        "urls": [
                            common_url,
                            {
                                "url": "https://t.co/article",
                                "expanded_url": article_url,
                            },
                        ]
                    },
                },
            },
            "publication_origin": "manual",
            "opportunity_id": None,
            "first_seen_run_id": run_id,
            "last_seen_run_id": run_id,
            "first_collected_at": now,
            "last_collected_at": now,
            "references": [
                {
                    "relationship_index": 0,
                    "relationship_type": "quoted",
                    "referenced_post_id": "synthetic-not-found",
                    "context_state": "unavailable",
                    "unavailable_reason": "not_found",
                    "raw_relationship": {
                        "type": "quoted",
                        "id": "synthetic-not-found",
                    },
                },
                {
                    "relationship_index": 1,
                    "relationship_type": "replied_to",
                    "referenced_post_id": "synthetic-protected",
                    "context_state": "unavailable",
                    "unavailable_reason": "protected_or_inaccessible",
                    "raw_relationship": {
                        "type": "replied_to",
                        "id": "synthetic-protected",
                    },
                },
                {
                    "relationship_index": 2,
                    "relationship_type": "quoted",
                    "referenced_post_id": "synthetic-available",
                    "context_state": "available",
                    "referenced_text": "available referenced text",
                    "raw_relationship": {
                        "type": "quoted",
                        "id": "synthetic-available",
                    },
                    "expanded_raw_json": {
                        "id": "synthetic-available",
                        "text": "available referenced text",
                    },
                },
                {
                    "relationship_index": 3,
                    "relationship_type": "retweeted",
                    "referenced_post_id": "synthetic-old-unknown",
                    "context_state": "unavailable",
                    "raw_relationship": {
                        "type": "retweeted",
                        "id": "synthetic-old-unknown",
                    },
                },
            ],
        }

        try:
            with connection.transaction(force_rollback=True):
                connection.execute(
                    """
                    INSERT INTO runs (run_id, started_at, status, trigger_type)
                    VALUES (%s, %s, 'running', 'synthetic_integration_test')
                    """,
                    (run_id, now),
                )
                StorageRepository(connection).upsert_first_party_x_posts([post])

                reasons = dict(
                    connection.execute(
                        """
                        SELECT referenced_post_id, unavailable_reason
                        FROM first_party_x_post_references
                        WHERE source_post_id = %s
                        """,
                        (post["post_id"],),
                    ).fetchall()
                )
                assert reasons == {
                    "synthetic-not-found": "not_found",
                    "synthetic-protected": "protected_or_inaccessible",
                    "synthetic-available": None,
                    "synthetic-old-unknown": "unknown",
                }

                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        connection.execute(
                            """
                            INSERT INTO first_party_x_post_references (
                                source_post_id, relationship_index,
                                relationship_type, referenced_post_id,
                                context_state, unavailable_reason,
                                raw_relationship
                            )
                            VALUES (%s, 4, 'quoted', 'synthetic-invalid',
                                'unavailable', 'unsafe_raw_reason', %s)
                            """,
                            (
                                post["post_id"],
                                Jsonb({"type": "quoted", "id": "synthetic-invalid"}),
                            ),
                        )

                urls = connection.execute(
                    """
                    SELECT original_url, expanded_url, unwound_url,
                        resolved_url, resolution_source, is_ethplorer_url,
                        is_binplorer_url, is_article_url
                    FROM first_party_x_post_urls
                    WHERE post_id = %s
                    ORDER BY original_url
                    """,
                    (post["post_id"],),
                ).fetchall()
                assert len(urls) == 5
                by_original = {row[0]: row for row in urls}
                assert by_original["https://t.co/common"][3] == (
                    "https://ethplorer.io/posts/common-article"
                )
                assert by_original["https://t.co/article"][3] == article_url
                assert by_original["https://t.co/unwound"][3:5] == (
                    "https://ethplorer.io/posts/unwound",
                    "unwound_url",
                )
                assert by_original["https://t.co/binplorer"][6] is True
                assert by_original["https://t.co/article"][7] is True

                review = connection.execute(
                    """
                    SELECT text, resolved_urls, article_urls,
                        url_count, article_url_count
                    FROM first_party_x_posts_review
                    WHERE post_id = %s
                    """,
                    (post["post_id"],),
                ).fetchone()
                assert review is not None
                assert review[0] == canonical_text
                assert article_url in review[1]
                assert article_url in review[2]
                assert review[3:] == (5, 3)
        finally:
            connection.rollback()

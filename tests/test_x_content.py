from x_signal_finder.x_content import (
    first_party_site,
    is_tco_url,
    resolve_x_url_entity,
    resolved_x_urls_from_stored_post,
    summarize_stored_x_urls,
    unavailable_reference_reason,
)


def test_url_resolution_priority_is_deterministic_and_network_free() -> None:
    resolved = resolve_x_url_entity(
        {
            "url": "https://t.co/short",
            "expanded_url": "https://ethplorer.io/address/0x1",
            "unwound_url": "https://ethplorer.io/address/0x1?final=true",
        }
    )

    assert resolved is not None
    assert resolved.resolved_url == "https://ethplorer.io/address/0x1?final=true"
    assert resolved.resolution_source == "unwound_url"


def test_expanded_url_falls_back_to_original_url() -> None:
    expanded = resolve_x_url_entity(
        {"url": "https://t.co/one", "expanded_url": "https://binplorer.com/token/1"}
    )
    original = resolve_x_url_entity({"url": "https://t.co/two"})

    assert expanded is not None and expanded.resolution_source == "expanded_url"
    assert original is not None and original.resolved_url == "https://t.co/two"
    assert is_tco_url(original.resolved_url)


def test_stored_post_reader_includes_note_tweet_entities_without_duplicates() -> None:
    common = {
        "url": "https://t.co/common",
        "expanded_url": "https://ethplorer.io/",
    }
    urls = resolved_x_urls_from_stored_post(
        entities={"urls": [common]},
        raw_json={
            "note_tweet": {
                "entities": {
                    "urls": [common, {"url": "https://t.co/note-only"}],
                }
            }
        },
    )

    assert [item.original_url for item in urls] == [
        "https://t.co/common",
        "https://t.co/note-only",
    ]
    assert first_party_site(urls[0].resolved_url) == "ethplorer.io"
    assert first_party_site("https://docs.binplorer.com/path") == "binplorer.com"


def test_malformed_entities_are_ignored_safely() -> None:
    assert resolved_x_urls_from_stored_post(entities={"urls": "bad"}) == ()
    assert resolve_x_url_entity({"expanded_url": "https://example.test"}) is None


def test_old_unavailable_reference_defaults_to_unknown_reason() -> None:
    assert unavailable_reference_reason({"context_state": "unavailable"}) == "unknown"
    assert unavailable_reference_reason(
        {"context_state": "unavailable", "unavailable_reason": "not_found"}
    ) == "not_found"
    assert unavailable_reference_reason({"context_state": "available"}) is None


def test_url_summary_reports_only_safe_counts() -> None:
    result = summarize_stored_x_urls(
        [
            {
                "entities": {
                    "urls": [
                        {
                            "url": "https://t.co/one",
                            "expanded_url": "https://ethplorer.io/address/1",
                        },
                        {"url": "https://t.co/two"},
                    ]
                },
                "raw_json": {},
            },
            {
                "entities": {},
                "raw_json": {
                    "note_tweet": {
                        "entities": {
                            "urls": [
                                {
                                    "url": "https://t.co/three",
                                    "unwound_url": "https://binplorer.com/token/3",
                                }
                            ]
                        }
                    }
                },
            },
        ]
    )

    assert result == {
        "posts_with_url_entities": 2,
        "url_entities": 3,
        "url_entities_with_expanded_url": 1,
        "url_entities_with_unwound_url": 1,
        "urls_remaining_tco_only": 1,
        "ethplorer_site_urls": 1,
        "binplorer_site_urls": 1,
        "first_party_site_urls": 2,
    }

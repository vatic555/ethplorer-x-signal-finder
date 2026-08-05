from urllib.parse import parse_qs, urlsplit

from x_signal_finder.x_api.client import HttpResponse
from x_signal_finder.x_api.oauth import (
    OAUTH_SCOPES,
    build_authorization_url,
    exchange_authorization_code,
    generate_pkce_pair,
    refresh_access_token,
)


def test_authorization_url_uses_pkce_and_minimum_scopes() -> None:
    verifier, challenge = generate_pkce_pair()
    url = build_authorization_url(
        client_id="synthetic-client",
        redirect_uri="http://127.0.0.1:8765/callback",
        state="synthetic-state",
        code_challenge=challenge,
    )
    query = parse_qs(urlsplit(url).query)

    assert len(verifier) >= 43
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == [" ".join(OAUTH_SCOPES)]
    assert "tweet.write" not in query["scope"][0]


def test_code_exchange_and_refresh_do_not_expose_tokens() -> None:
    responses = iter(
        [
            HttpResponse(
                200,
                {},
                b'{"access_token":"first-secret","refresh_token":"refresh-secret","scope":"tweet.read users.read offline.access"}',
            ),
            HttpResponse(
                200,
                {},
                b'{"access_token":"second-secret","refresh_token":"rotated-secret","scope":"tweet.read users.read offline.access"}',
            ),
        ]
    )

    def transport(url, body, headers, timeout):
        assert b"synthetic" in body or b"refresh-secret" in body
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        return next(responses)

    first = exchange_authorization_code(
        client_id="synthetic-client",
        redirect_uri="http://127.0.0.1:8765/callback",
        code="synthetic-code",
        code_verifier="synthetic-verifier",
        transport=transport,
    )
    second = refresh_access_token(
        client_id="synthetic-client",
        refresh_token=first.refresh_token,
        transport=transport,
    )

    assert first.access_token == "first-secret"
    assert second.access_token == "second-secret"
    assert "first-secret" not in repr(first)
    assert "refresh-secret" not in repr(first)


def test_refresh_keeps_current_token_when_rotation_is_omitted() -> None:
    def transport(url, body, headers, timeout):
        return HttpResponse(
            200,
            {},
            b'{"access_token":"new-access","scope":"tweet.read offline.access"}',
        )

    tokens = refresh_access_token(
        client_id="synthetic-client",
        refresh_token="current-refresh",
        transport=transport,
    )

    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "current-refresh"

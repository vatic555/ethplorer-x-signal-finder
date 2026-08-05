"""One-shot official OAuth 2.0 PKCE flow for live spike validation."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
import webbrowser

from x_signal_finder.x_api.client import HttpResponse


AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
OAUTH_SCOPES = ("tweet.read", "users.read", "offline.access")


class OAuthFlowError(RuntimeError):
    """Safe OAuth failure that never contains token response content."""


@dataclass(frozen=True, repr=False)
class OAuthTokens:
    access_token: str
    refresh_token: str
    scope: str

    def __repr__(self) -> str:
        return (
            "OAuthTokens(access_token='<redacted>', refresh_token='<redacted>', "
            f"scope={self.scope!r})"
        )

    __str__ = __repr__


TokenTransport = Callable[[str, bytes, Mapping[str, str], float], HttpResponse]


def generate_pkce_pair() -> tuple[str, str]:
    """Return an RFC 7636 verifier and S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    return AUTHORIZE_URL + "?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(OAUTH_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )


def _default_token_transport(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except HTTPError as error:
        return HttpResponse(
            status=error.code,
            headers=dict(error.headers.items()) if error.headers else {},
            body=error.read(),
        )
    except (URLError, TimeoutError, OSError) as error:
        raise OAuthFlowError("OAuth token endpoint is unavailable.") from error


def _parse_tokens(response: HttpResponse) -> OAuthTokens:
    if response.status < 200 or response.status >= 300:
        raise OAuthFlowError(f"OAuth token exchange failed with HTTP {response.status}.")
    try:
        payload: Any = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OAuthFlowError("OAuth token endpoint returned an invalid response.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise OAuthFlowError("OAuth token endpoint returned an unexpected response shape.")
    refresh_token = payload.get("refresh_token", "")
    scope = payload.get("scope", "")
    return OAuthTokens(
        access_token=payload["access_token"],
        refresh_token=refresh_token if isinstance(refresh_token, str) else "",
        scope=scope if isinstance(scope, str) else "",
    )


def exchange_authorization_code(
    *,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    transport: TokenTransport | None = None,
) -> OAuthTokens:
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        }
    ).encode("ascii")
    response = (transport or _default_token_transport)(
        TOKEN_URL,
        body,
        {"Content-Type": "application/x-www-form-urlencoded"},
        20.0,
    )
    return _parse_tokens(response)


def refresh_access_token(
    *,
    client_id: str,
    refresh_token: str,
    transport: TokenTransport | None = None,
) -> OAuthTokens:
    if not refresh_token:
        raise OAuthFlowError(
            "No refresh token was issued despite requesting offline.access."
        )
    body = urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
    ).encode("ascii")
    response = (transport or _default_token_transport)(
        TOKEN_URL,
        body,
        {"Content-Type": "application/x-www-form-urlencoded"},
        20.0,
    )
    return _parse_tokens(response)


def authorize_with_local_callback(
    *,
    client_id: str,
    redirect_uri: str,
    timeout_seconds: int = 180,
    open_browser: Callable[[str], object] = webbrowser.open,
) -> OAuthTokens:
    """Authorize once, exchange and refresh in memory, then discard on exit."""
    parsed = urlsplit(redirect_uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port is None
        or not parsed.path
    ):
        raise OAuthFlowError(
            "X_REDIRECT_URI must be an HTTP localhost callback with an explicit port."
        )

    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    authorization_url = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
    )
    result: dict[str, str] = {}
    expected_path = parsed.path

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            request_url = urlsplit(self.path)
            if request_url.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(request_url.query)
            for key in ("code", "state", "error"):
                values = query.get(key)
                if values:
                    result[key] = values[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"Authorization received. Return to the terminal; this server will stop."
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((parsed.hostname, parsed.port), CallbackHandler)
    server.timeout = timeout_seconds
    print("Open this official X authorization URL if the browser does not open:")
    print(authorization_url)
    open_browser(authorization_url)
    try:
        server.handle_request()
    finally:
        server.server_close()

    if result.get("error"):
        raise OAuthFlowError("X authorization was denied or cancelled.")
    if not result.get("code"):
        raise OAuthFlowError("Timed out waiting for the one-time OAuth callback.")
    if result.get("state") != state:
        raise OAuthFlowError("OAuth callback state validation failed.")

    tokens = exchange_authorization_code(
        client_id=client_id,
        redirect_uri=redirect_uri,
        code=result["code"],
        code_verifier=verifier,
    )
    return refresh_access_token(
        client_id=client_id,
        refresh_token=tokens.refresh_token,
    )

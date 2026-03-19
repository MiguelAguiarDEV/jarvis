"""OAuth 2.0 PKCE flow for native desktop apps (RFC 7636)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import structlog

log = structlog.get_logger()


class OAuthError(Exception):
    """Raised when OAuth flow fails."""


@dataclass
class OAuthTokens:
    """OAuth token set."""

    access_token: str
    refresh_token: str | None
    expires_at: float  # Unix timestamp
    account_id: str | None = None

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class OAuthPKCEFlow:
    """RFC 7636 PKCE flow for native desktop apps.

    Flow:
    1. Generate code_verifier (43-128 char random string)
    2. Compute code_challenge = BASE64URL(SHA256(code_verifier))
    3. Open browser to authorization URL with code_challenge
    4. Start local HTTP server on 127.0.0.1:{port} to receive callback
    5. Exchange authorization_code + code_verifier for tokens
    6. Return tokens for storage
    """

    def __init__(
        self,
        auth_url: str,
        token_url: str,
        client_id: str,
        redirect_port: int = 8976,
        scopes: list[str] | None = None,
        timeout_sec: int = 120,
    ) -> None:
        self._auth_url = auth_url
        self._token_url = token_url
        self._client_id = client_id
        self._redirect_port = redirect_port
        self._scopes = scopes or []
        self._timeout_sec = timeout_sec
        self._redirect_uri = f"http://127.0.0.1:{redirect_port}/auth/callback"

    async def authenticate(self) -> OAuthTokens:
        """Run full PKCE flow. Opens browser, waits for callback.

        Returns:
            OAuthTokens with access_token and optional refresh_token.

        Raises:
            OAuthError: On timeout, user denial, or token exchange failure.
        """
        verifier = self._generate_code_verifier()
        challenge = self._generate_code_challenge(verifier)
        state = secrets.token_urlsafe(32)

        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if self._scopes:
            params["scope"] = " ".join(self._scopes)

        auth_url = f"{self._auth_url}?{urlencode(params)}"

        # Start local callback server
        callback_result: dict[str, Any] = {}
        callback_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        server = self._start_callback_server(callback_result, callback_event, loop)

        try:
            # Open browser
            log.info("oauth.browser_opening", url=auth_url)
            webbrowser.open(auth_url)
            print(
                f"\nOpening browser for authentication...\nIf it doesn't open, visit:\n{auth_url}\n"
            )

            # Wait for callback
            try:
                await asyncio.wait_for(callback_event.wait(), timeout=self._timeout_sec)
            except TimeoutError as e:
                msg = f"OAuth flow timed out after {self._timeout_sec}s"
                raise OAuthError(msg) from e

            # Validate state
            if callback_result.get("state") != state:
                msg = "OAuth state mismatch — possible CSRF attack"
                raise OAuthError(msg)

            if "error" in callback_result:
                msg = f"OAuth error: {callback_result['error']}"
                raise OAuthError(msg)

            code = callback_result.get("code")
            if not code:
                msg = "No authorization code received"
                raise OAuthError(msg)

            # Exchange code for tokens
            return await self._exchange_code(code, verifier)

        finally:
            server.shutdown()

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token from a previous auth flow.

        Returns:
            New OAuthTokens with fresh access_token.

        Raises:
            OAuthError: If refresh fails.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self._client_id,
                        "refresh_token": refresh_token,
                    },
                )

                if response.status_code != 200:
                    msg = f"Token refresh failed ({response.status_code}): {response.text}"
                    raise OAuthError(msg)

                return self._parse_token_response(response.json())

            except OAuthError:
                raise
            except Exception as e:
                msg = f"Token refresh error: {e}"
                raise OAuthError(msg) from e

    async def _exchange_code(self, code: str, verifier: str) -> OAuthTokens:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_url,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self._client_id,
                        "code": code,
                        "redirect_uri": self._redirect_uri,
                        "code_verifier": verifier,
                    },
                )

                if response.status_code != 200:
                    msg = f"Token exchange failed ({response.status_code}): {response.text}"
                    raise OAuthError(msg)

                tokens = self._parse_token_response(response.json())
                log.info("oauth.tokens_received", has_refresh=tokens.refresh_token is not None)
                return tokens

            except OAuthError:
                raise
            except Exception as e:
                msg = f"Token exchange error: {e}"
                raise OAuthError(msg) from e

    def _parse_token_response(self, data: dict[str, Any]) -> OAuthTokens:
        """Parse token endpoint response."""
        access_token = data.get("access_token")
        if not access_token:
            msg = f"No access_token in response: {list(data.keys())}"
            raise OAuthError(msg)

        expires_in = data.get("expires_in", 3600)
        expires_at = time.time() + expires_in

        return OAuthTokens(
            access_token=access_token,
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            account_id=data.get("account_id"),
        )

    def _start_callback_server(
        self,
        result: dict[str, Any],
        event: asyncio.Event,
        loop: asyncio.AbstractEventLoop,
    ) -> HTTPServer:
        """Start a local HTTP server to receive the OAuth callback."""

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Extract single values from lists
                for key, value in params.items():
                    result[key] = value[0] if len(value) == 1 else value

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authentication successful!</h1>"
                    b"<p>You can close this tab and return to JARVIS.</p>"
                    b"</body></html>"
                )

                # Signal the async event from the sync handler
                loop.call_soon_threadsafe(event.set)

            def log_message(self, format: str, *args: Any) -> None:
                # Suppress default HTTP server logging
                pass

        server = HTTPServer(("127.0.0.1", self._redirect_port), CallbackHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a random code verifier (43-128 chars, URL-safe)."""
        return secrets.token_urlsafe(64)[:128]

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Compute S256 code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

from __future__ import annotations

from typing import Any

from app.auth.oauth_client import OAuthClient
from app.auth.pkce import generate_code_challenge, generate_code_verifier, generate_state
from app.auth.token_store import TokenStore
from app.xapi.client import XApiClient


class AuthError(RuntimeError):
    pass


class AuthService:
    def __init__(self, oauth_client: OAuthClient, token_store: TokenStore, x_client: XApiClient):
        self.oauth_client = oauth_client
        self.token_store = token_store
        self.x_client = x_client

    def create_login_redirect(self) -> str:
        if not self.oauth_client.settings.x_client_id:
            raise AuthError("X_CLIENT_ID is not configured")
        state = generate_state()
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        self.token_store.save_oauth_state(state, code_verifier)
        return self.oauth_client.build_authorize_url(state, code_challenge)

    async def handle_callback(self, code: str, state: str) -> None:
        code_verifier = self.token_store.pop_oauth_state(state)
        if not code_verifier:
            raise AuthError("Invalid or expired OAuth state")
        token_payload = await self.oauth_client.exchange_code(code, code_verifier)
        user = await self.x_client.get_me(token_payload["access_token"])
        self.token_store.save_token(token_payload, user)

    async def get_valid_access_token(self) -> str:
        token = self.token_store.get_token()
        if not token:
            raise AuthError("Not connected to X")
        if not self.token_store.is_expired(token):
            return token["access_token"]
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise AuthError("Access token expired and no refresh token is available")
        refreshed = await self.oauth_client.refresh_access_token(refresh_token)
        user = {
            "id": token.get("user_id"),
            "username": token.get("username"),
            "name": token.get("name"),
        }
        self.token_store.save_token(refreshed, user)
        latest = self.token_store.get_token()
        if not latest:
            raise AuthError("Failed to persist refreshed token")
        return latest["access_token"]

    def get_auth_status(self) -> dict[str, Any]:
        token = self.token_store.get_token()
        if not token:
            return {"connected": False, "user": None, "token_expires_at": None}
        return {
            "connected": True,
            "user": {
                "id": token.get("user_id"),
                "username": token.get("username"),
                "name": token.get("name"),
            },
            "token_expires_at": token.get("expires_at"),
            "scope": token.get("scope"),
        }

    def get_current_user_id(self) -> str:
        token = self.token_store.get_token()
        if not token or not token.get("user_id"):
            raise AuthError("Authenticated user ID is not available")
        return token["user_id"]

    def logout(self) -> None:
        self.token_store.clear()

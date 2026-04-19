from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings


class OAuthClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build_authorize_url(self, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.settings.x_client_id,
            "redirect_uri": self.settings.x_redirect_uri,
            "scope": self.settings.scope_string,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.settings.x_authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.x_redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self.settings.x_client_id,
        }
        return await self._token_request(data)

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.x_client_id,
        }
        return await self._token_request(data)

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.settings.x_client_secret:
            secret = f"{self.settings.x_client_id}:{self.settings.x_client_secret}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(secret).decode("ascii")
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self.settings.x_token_url, data=data, headers=headers)
            response.raise_for_status()
            return response.json()

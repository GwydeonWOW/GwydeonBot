from __future__ import annotations

import time
from dataclasses import dataclass

import aiohttp

from ..domain.errors import WowApiError, WowRateLimited


@dataclass
class OAuthToken:
    access_token: str
    expires_at: float


class BlizzardOAuthClient:
    """Client-credentials OAuth for Battle.net."""

    TOKEN_URL = "https://oauth.battle.net/token"

    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: OAuthToken | None = None

    async def get_access_token(self) -> str:
        # Refresh a bit early
        if self._token and time.time() < self._token.expires_at - 30:
            return self._token.access_token

        try:
            async with self._session.post(
                self.TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 429:
                    raise WowRateLimited("Rate limited (OAuth)")
                if resp.status != 200:
                    raise WowApiError(f"OAuth error {resp.status}: {await resp.text()}")
                data = await resp.json()
        except aiohttp.ClientError as e:
            raise WowApiError(f"OAuth network error: {e}") from e

        self._token = OAuthToken(
            access_token=data["access_token"],
            expires_at=time.time() + float(data.get("expires_in", 0)),
        )
        return self._token.access_token

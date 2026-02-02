import time
import aiohttp
from dataclasses import dataclass

@dataclass
class OAuthToken:
    access_token: str
    expires_at: float

class BlizzardOAuthClient:
    TOKEN_URL = "https://oauth.battle.net/token"

    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: OAuthToken | None = None

    async def get_access_token(self) -> str:
        if self._token and time.time() < self._token.expires_at - 30:
            return self._token.access_token

        async with self._session.post(
            self.TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"OAuth error {resp.status}: {await resp.text()}")
            data = await resp.json()

        self._token = OAuthToken(
            access_token=data["access_token"],
            expires_at=time.time() + float(data.get("expires_in", 0)),
        )
        return self._token.access_token

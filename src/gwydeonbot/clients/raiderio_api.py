from __future__ import annotations

from typing import Any

import aiohttp

from ..domain.errors import WowApiError, WowNotFound, WowRateLimited


class RaiderIoClient:
    BASE_URL = "https://raider.io/api/v1"

    def __init__(self, session: aiohttp.ClientSession, *, region: str):
        self._session = session
        self.region = region.lower()

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = self.BASE_URL + path
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 404:
                    raise WowNotFound("No encontrado (Raider.IO)")
                if resp.status == 429:
                    ra = resp.headers.get("Retry-After")
                    msg = "Rate limited (Raider.IO)"
                    if ra:
                        msg += f" retry-after={ra}"
                    raise WowRateLimited(msg)
                if resp.status >= 500:
                    raise WowApiError(f"Raider.IO {resp.status}")
                if resp.status != 200:
                    raise WowApiError(f"Raider.IO error {resp.status}: {await resp.text()}")
                return await resp.json()
        except aiohttp.ClientError as e:
            raise WowApiError(f"Network error (Raider.IO): {e}") from e

    async def character_profile(self, realm_slug: str, character_name: str, fields: list[str] | None = None) -> dict[str, Any]:
        fields_str = ",".join(fields) if fields else ",".join([
            "raid_progression",
            "mythic_plus_scores_by_season:current",
            "mythic_plus_best_runs",
        ])

        return await self._get(
            "/characters/profile",
            {
                "region": self.region,
                "realm": realm_slug,
                "name": character_name,
                "fields": fields_str,
            },
        )

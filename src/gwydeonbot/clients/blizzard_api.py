from __future__ import annotations

import re
from typing import Any

import aiohttp

from ..domain.errors import WowApiError, WowNotFound, WowRateLimited
from .blizzard_oauth import BlizzardOAuthClient


class BlizzardApiClient:
    def __init__(self, session: aiohttp.ClientSession, oauth: BlizzardOAuthClient, *, region: str, locale: str):
        self._session = session
        self._oauth = oauth
        self.region = region.lower()
        self.locale = locale

    @property
    def base_url(self) -> str:
        return f"https://{self.region}.api.blizzard.com"

    def _ns_profile(self) -> str:
        return f"profile-{self.region}"

    def _ns_dynamic(self) -> str:
        return f"dynamic-{self.region}"

    def _ns_static(self) -> str:
        return f"static-{self.region}"

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        token = await self._oauth.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = self.base_url + path

        try:
            async with self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 404:
                    raise WowNotFound("No encontrado")
                if resp.status == 429:
                    raise WowRateLimited("Rate limited (Blizzard)")
                if resp.status >= 500:
                    raise WowApiError(f"Blizzard API {resp.status}")
                if resp.status != 200:
                    raise WowApiError(f"Error {resp.status}: {await resp.text()}")
                return await resp.json()
        except aiohttp.ClientError as e:
            raise WowApiError(f"Network error (Blizzard): {e}") from e

    # -----------------------------
    # Character Profile APIs
    # -----------------------------
    async def character_profile_summary(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}",
            {"namespace": self._ns_profile(), "locale": self.locale},
        )

    async def character_equipment_summary(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/equipment",
            {"namespace": self._ns_profile(), "locale": self.locale},
        )

    async def character_statistics(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/statistics",
            {"namespace": self._ns_profile(), "locale": self.locale},
        )

    async def character_media(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/character-media",
            {"namespace": self._ns_profile(), "locale": self.locale},
        )

    # -----------------------------
    # Guild APIs (Profile namespace)
    # -----------------------------
    async def guild_roster(self, realm_slug: str, guild_slug: str) -> dict[str, Any]:
        """
        Devuelve el roster (miembros) de una hermandad.

        Endpoint:
          GET /data/wow/guild/{realmSlug}/{guildSlug}/roster
        Namespace:
          profile-<region>
        """
        return await self._get(
            f"/data/wow/guild/{realm_slug}/{guild_slug}/roster",
            {"namespace": self._ns_profile(), "locale": self.locale},
        )

    # -----------------------------
    # Game Data APIs (Achievement)
    # -----------------------------
    async def achievement_by_id(self, achievement_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/achievement/{achievement_id}",
            {"namespace": self._ns_static(), "locale": self.locale},
        )

    # -----------------------------
    # Game Data APIs (Playable Class)
    # -----------------------------
    async def playable_class_by_id(self, class_id: int) -> dict[str, Any]:
        """
        GET /data/wow/playable-class/{classId}
        Namespace: static-<region>
        """
        return await self._get(
            f"/data/wow/playable-class/{class_id}",
            {"namespace": self._ns_static(), "locale": self.locale},
        )

    # -----------------------------
    # Realms
    # -----------------------------
    async def realm_index(self) -> dict[str, Any]:
        return await self._get(
            "/data/wow/realm/index",
            {"namespace": self._ns_dynamic(), "locale": self.locale},
        )

    async def realm_by_id(self, realm_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/realm/{realm_id}",
            {"namespace": self._ns_dynamic(), "locale": self.locale},
        )

    @staticmethod
    def extract_id_from_href(href: str) -> int | None:
        m = re.search(r"/connected-realm/(\d+)", href)
        return int(m.group(1)) if m else None

    async def connected_realm(self, connected_realm_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/connected-realm/{connected_realm_id}",
            {"namespace": self._ns_dynamic(), "locale": self.locale},
        )

    # -----------------------------
    # Armory URLs
    # -----------------------------
    def armory_character_url(self, realm_slug: str, character_name: str) -> str:
        locale_web = self.locale.replace("_", "-").lower()
        return f"https://worldofwarcraft.blizzard.com/{locale_web}/character/{self.region}/{realm_slug}/{character_name}"

    def armory_guild_url(self, realm_slug: str, guild_slug: str) -> str:
        """
        URL pública de Armory para la guild (web).
        Nota: la web puede variar por locale, pero esta estructura funciona bien para EU/US.
        """
        locale_web = self.locale.replace("_", "-").lower()
        return f"https://worldofwarcraft.blizzard.com/{locale_web}/guild/{self.region}/{realm_slug}/{guild_slug}"

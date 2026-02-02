import re
import aiohttp
from typing import Any

import discord

from .blizzard_oauth import BlizzardOAuthClient


class WowApiError(Exception):
    pass


class WowNotFound(WowApiError):
    pass


class WowRateLimited(WowApiError):
    pass


class WowApi:
    def __init__(self, session: aiohttp.ClientSession, oauth: BlizzardOAuthClient, region: str, locale: str):
        self._session = session
        self._oauth = oauth
        self._region = region.lower()
        self._locale = locale

    # -----------------------------
    # Blizzard
    # -----------------------------
    @property
    def base_url(self) -> str:
        return f"https://{self._region}.api.blizzard.com"

    def _ns_profile(self) -> str:
        return f"profile-{self._region}"

    def _ns_dynamic(self) -> str:
        return f"dynamic-{self._region}"

    def _ns_static(self) -> str:
        return f"static-{self._region}"

    @staticmethod
    def normalize_realm_slug(realm: str) -> str:
        return (
            realm.strip().lower()
            .replace("’", "")
            .replace("'", "")
            .replace(" ", "-")
        )

    @staticmethod
    def normalize_character_name(name: str) -> str:
        return name.strip().lower()

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        token = await self._oauth.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = self.base_url + path

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

    # -----------------------------
    # Raider.IO (público)
    # -----------------------------
    @property
    def raider_base_url(self) -> str:
        return "https://raider.io/api/v1"

    async def _get_raider(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = self.raider_base_url + path

        async with self._session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
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

    async def raider_character_profile(self, realm_slug: str, character_name: str, fields: list[str] | None = None) -> dict[str, Any]:
        """
        GET /characters/profile?region=eu&realm=<realm>&name=<name>&fields=...
        """
        fields_str = ",".join(fields) if fields else ",".join([
            "raid_progression",
            "mythic_plus_scores_by_season:current",
            "mythic_plus_best_runs",
        ])

        return await self._get_raider(
            "/characters/profile",
            {
                "region": self._region,   # eu/us/...
                "realm": realm_slug,
                "name": character_name,
                "fields": fields_str,
            },
        )

    # -----------------------------
    # Character Profile APIs (Blizzard)
    # -----------------------------
    async def character_profile_summary(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_equipment_summary(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/equipment",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_statistics(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/statistics",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_media(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/character-media",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_raid_encounters(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/encounters/raids",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_achievements_summary(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/achievements",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_mythic_keystone_profile(self, realm_slug: str, character_name: str) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/mythic-keystone-profile",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    async def character_mythic_keystone_season_details(self, realm_slug: str, character_name: str, season_id: int) -> dict[str, Any]:
        return await self._get(
            f"/profile/wow/character/{realm_slug}/{character_name}/mythic-keystone-profile/season/{season_id}",
            {"namespace": self._ns_profile(), "locale": self._locale},
        )

    # -----------------------------
    # Game Data APIs (Achievement)
    # -----------------------------
    async def achievement_by_id(self, achievement_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/achievement/{achievement_id}",
            {"namespace": self._ns_static(), "locale": self._locale},
        )

    # -----------------------------
    # Armory URLs
    # -----------------------------
    def armory_character_url(self, realm_slug: str, character_name: str) -> str:
        locale_web = self._locale.replace("_", "-").lower()
        return f"https://worldofwarcraft.blizzard.com/{locale_web}/character/{self._region}/{realm_slug}/{character_name}"

    # -----------------------------
    # Utility: class color
    # -----------------------------
    def class_color(self, class_id: int | None, class_name: str | None = None) -> discord.Color:
        by_id: dict[int, discord.Color] = {
            1: discord.Color.from_rgb(198, 155, 109),
            2: discord.Color.from_rgb(244, 140, 186),
            3: discord.Color.from_rgb(170, 211, 114),
            4: discord.Color.from_rgb(255, 244, 104),
            5: discord.Color.from_rgb(255, 255, 255),
            6: discord.Color.from_rgb(196, 30, 58),
            7: discord.Color.from_rgb(0, 112, 222),
            8: discord.Color.from_rgb(63, 199, 235),
            9: discord.Color.from_rgb(135, 136, 238),
            10: discord.Color.from_rgb(0, 255, 152),
            11: discord.Color.from_rgb(255, 125, 10),
            12: discord.Color.from_rgb(163, 48, 201),
            13: discord.Color.from_rgb(51, 147, 127),
        }
        if isinstance(class_id, int) and class_id in by_id:
            return by_id[class_id]
        return discord.Color.blurple()

    # -----------------------------
    # Realms / Status
    # -----------------------------
    async def realm_index(self) -> dict[str, Any]:
        return await self._get(
            "/data/wow/realm/index",
            {"namespace": self._ns_dynamic(), "locale": self._locale},
        )

    async def realm_by_id(self, realm_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/realm/{realm_id}",
            {"namespace": self._ns_dynamic(), "locale": self._locale},
        )

    @staticmethod
    def extract_id_from_href(href: str) -> int | None:
        m = re.search(r"/connected-realm/(\d+)", href)
        return int(m.group(1)) if m else None

    async def connected_realm(self, connected_realm_id: int) -> dict[str, Any]:
        return await self._get(
            f"/data/wow/connected-realm/{connected_realm_id}",
            {"namespace": self._ns_dynamic(), "locale": self._locale},
        )

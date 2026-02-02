from __future__ import annotations

from typing import Any

from ..clients.blizzard_api import BlizzardApiClient
from ..utils.cache import TTLCache
from ..domain.errors import WowNotFound


class IlvlService:
    def __init__(self, blizzard: BlizzardApiClient, *, ttl_seconds: float = 60 * 60 * 2):
        self._blizzard = blizzard
        # cache por personaje (realm_slug, name) -> ilvl
        self._cache: TTLCache[tuple[str, str], int] = TTLCache(ttl_seconds)

    async def get_equipped_ilvl(self, realm_slug: str, character_name: str) -> int | None:
        key = (realm_slug, character_name.lower())
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            data = await self._blizzard.character_equipment_summary(realm_slug, character_name.lower())
        except WowNotFound:
            return None

        ilvl = data.get("equipped_item_level")
        if not isinstance(ilvl, int):
            return None

        self._cache.set(key, ilvl)
        return ilvl

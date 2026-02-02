from __future__ import annotations

from collections import Counter
from typing import Any

from ..clients.blizzard_api import BlizzardApiClient
from ..utils.cache import TTLCache


class GuildService:
    def __init__(self, blizzard: BlizzardApiClient, *, roster_ttl_seconds: float = 300):
        self._blizzard = blizzard
        self._roster_cache: TTLCache[tuple[str, str], dict[str, Any]] = TTLCache(roster_ttl_seconds)

        # Cache de nombres de clases (casi “para siempre”)
        self._class_name_cache: TTLCache[int, str] = TTLCache(60 * 60 * 24 * 30)  # 30 días

    @property
    def region(self) -> str:
        return self._blizzard.region

    async def get_guild_roster(self, *, realm_slug: str, guild_slug: str) -> dict[str, Any]:
        cache_key = (realm_slug, guild_slug)
        cached = self._roster_cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._blizzard.guild_roster(realm_slug, guild_slug)
        self._roster_cache.set(cache_key, payload)
        return payload

    async def _class_name(self, class_id: int) -> str:
        cached = self._class_name_cache.get(class_id)
        if cached is not None:
            return cached

        data = await self._blizzard.playable_class_by_id(class_id)
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            name = f"Class {class_id}"

        self._class_name_cache.set(class_id, name)
        return name

    async def summarize_roster(self, roster_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Devuelve un resumen listo para embed:
        - total
        - top_by_level
        - class_counter (ya con nombres)
        - dominant_class_id
        """
        members = roster_payload.get("members")
        if not isinstance(members, list):
            members = []

        parsed: list[dict[str, Any]] = []
        class_ids_needed: set[int] = set()

        for m in members:
            if not isinstance(m, dict):
                continue
            ch = m.get("character")
            if not isinstance(ch, dict):
                continue

            pc = ch.get("playable_class")
            pc = pc if isinstance(pc, dict) else {}

            class_id = pc.get("id")
            class_id = class_id if isinstance(class_id, int) else None

            # OJO: el roster a veces no trae name
            class_name = pc.get("name")
            class_name = class_name if isinstance(class_name, str) and class_name.strip() else None

            if class_id is not None and class_name is None:
                class_ids_needed.add(class_id)

            parsed.append(
                {
                    "name": ch.get("name"),
                    "level": ch.get("level"),
                    "class_id": class_id,
                    "class_name": class_name,  # se completa luego si falta
                    "rank": m.get("rank"),
                }
            )

        # Resolver nombres de clases faltantes (con cache)
        # Lo hacemos secuencial para no disparar rate limits.
        class_id_to_name: dict[int, str] = {}
        for cid in sorted(class_ids_needed):
            class_id_to_name[cid] = await self._class_name(cid)

        for p in parsed:
            if p.get("class_name") is None and isinstance(p.get("class_id"), int):
                p["class_name"] = class_id_to_name.get(p["class_id"], f"Class {p['class_id']}")

        total = len(parsed)

        def lvl(x: dict[str, Any]) -> int:
            v = x.get("level")
            return int(v) if isinstance(v, int) else 0

        top_by_level = sorted(parsed, key=lvl, reverse=True)[:10]

        class_counter = Counter(
            p.get("class_name")
            for p in parsed
            if isinstance(p.get("class_name"), str) and p.get("class_name")
        )

        dominant_class_id: int | None = None
        if class_counter:
            common_name = class_counter.most_common(1)[0][0]
            for p in parsed:
                if p.get("class_name") == common_name and isinstance(p.get("class_id"), int):
                    dominant_class_id = p["class_id"]
                    break

        return {
            "total": total,
            "top_by_level": top_by_level,
            "class_counter": class_counter,
            "dominant_class_id": dominant_class_id,
        }

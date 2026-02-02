from __future__ import annotations

from typing import Any

from ..clients.blizzard_api import BlizzardApiClient
from ..clients.raiderio_api import RaiderIoClient
from ..domain.errors import WowNotFound, WowRateLimited
from ..domain.models import CharacterOverview, MythicPlusSummary
from ..utils.cache import TTLCache


class CharacterService:
    def __init__(
        self,
        blizzard: BlizzardApiClient,
        raiderio: RaiderIoClient,
        *,
        raiderio_ttl_seconds: float = 120,
    ):
        self._blizzard = blizzard
        self._raiderio = raiderio
        self._raider_cache: TTLCache[tuple[str, str], dict[str, Any]] = TTLCache(raiderio_ttl_seconds)

    @property
    def region(self) -> str:
        return self._blizzard.region

    async def get_character_overview(self, *, realm_slug: str, character_name: str) -> CharacterOverview:
        profile = await self._blizzard.character_profile_summary(realm_slug, character_name)

        level = str(profile.get("level", "—"))
        class_obj = profile.get("character_class") or {}
        class_name = str(class_obj.get("name", "—"))
        class_id = class_obj.get("id") if isinstance(class_obj, dict) else None
        if not isinstance(class_id, int):
            class_id = None

        faction = str((profile.get("faction") or {}).get("name", "—"))
        race = str((profile.get("race") or {}).get("name", "—"))
        spec = (profile.get("active_spec") or {}).get("name")
        spec = str(spec) if spec else None
        guild = (profile.get("guild") or {}).get("name")
        guild = str(guild) if guild else None

        ilvl = await self._resolve_item_level(realm_slug, character_name)
        thumbnail_url = await self._resolve_thumbnail(realm_slug, character_name)
        armory_url = self._blizzard.armory_character_url(realm_slug, character_name)

        mythic_plus, raid_lines = await self._resolve_raiderio(realm_slug, character_name)

        return CharacterOverview(
            name=str(profile.get("name", character_name)),
            realm=realm_slug,
            region=self._blizzard.region,
            level=level,
            class_name=class_name,
            class_id=class_id,
            race=race,
            faction=faction,
            spec=spec,
            guild=guild,
            item_level=ilvl,
            thumbnail_url=thumbnail_url,
            armory_url=armory_url,
            mythic_plus=mythic_plus,
            raid_progress_lines=raid_lines,
        )

    async def _resolve_item_level(self, realm_slug: str, character_name: str) -> str:
        # 1) equipped_item_level (most reliable)
        equip: dict[str, Any] | None = None
        try:
            equip = await self._blizzard.character_equipment_summary(realm_slug, character_name)
            direct = equip.get("equipped_item_level")
            if isinstance(direct, int) and direct > 0:
                return str(direct)
        except Exception:
            equip = None

        # 2) statistics average_item_level_equipped
        try:
            stats = await self._blizzard.character_statistics(realm_slug, character_name)
            v = stats.get("average_item_level_equipped")
            if isinstance(v, int) and v > 0:
                return str(v)
            v2 = stats.get("average_item_level")
            if isinstance(v2, int) and v2 > 0:
                return str(v2)
        except Exception:
            pass

        # 3) average from equipped_items[].level.value
        try:
            if equip is None:
                equip = await self._blizzard.character_equipment_summary(realm_slug, character_name)
            items = equip.get("equipped_items") or []
            levels: list[int] = []
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    val = (it.get("level") or {}).get("value")
                    if isinstance(val, int) and val > 0:
                        levels.append(val)
            if levels:
                return str(round(sum(levels) / len(levels), 1))
        except Exception:
            pass

        return "—"

    async def _resolve_thumbnail(self, realm_slug: str, character_name: str) -> str | None:
        try:
            media = await self._blizzard.character_media(realm_slug, character_name)
            assets = media.get("assets") or []
            if isinstance(assets, list):
                for key in ("avatar", "inset", "main"):
                    match = next(
                        (a for a in assets if isinstance(a, dict) and a.get("key") == key and a.get("value")),
                        None,
                    )
                    if match:
                        return str(match["value"])
        except Exception:
            return None
        return None

    async def _resolve_raiderio(self, realm_slug: str, character_name: str) -> tuple[MythicPlusSummary, list[str]]:
        # Raider.IO can be missing for a character even if Blizzard has it
        cache_key = (realm_slug, character_name)
        payload = self._raider_cache.get(cache_key)
        if payload is None:
            try:
                payload = await self._raiderio.character_profile(
                    realm_slug,
                    character_name,
                    fields=[
                        "raid_progression",
                        "mythic_plus_scores_by_season:current",
                        "mythic_plus_best_runs",
                    ],
                )
                self._raider_cache.set(cache_key, payload)
            except WowNotFound:
                return MythicPlusSummary(score="—", top_runs=[]), []
            except WowRateLimited:
                return MythicPlusSummary(score="—", top_runs=["Rate limit en Raider.IO. Prueba en 1–2 min."]), [
                    "Rate limit en Raider.IO. Prueba en 1–2 min.",
                ]

        mplus = self._extract_mplus(payload)
        raids = self._extract_raid_progress(payload)
        return mplus, raids

    @staticmethod
    def _extract_raid_progress(raider_payload: dict[str, Any]) -> list[str]:
        rp = raider_payload.get("raid_progression")
        if not isinstance(rp, dict) or not rp:
            return []

        lines: list[str] = []
        for raid_slug, data in rp.items():
            if not isinstance(data, dict):
                continue

            raid_name = data.get("name") or raid_slug.replace("-", " ").title()

            summary = data.get("summary")
            if isinstance(summary, str) and summary.strip():
                lines.append(f"{raid_name}: {summary.strip()}")
                continue

            total = data.get("total_bosses")
            if not isinstance(total, int) or total <= 0:
                continue

            m = data.get("mythic_bosses_killed")
            h = data.get("heroic_bosses_killed")
            n = data.get("normal_bosses_killed")

            parts: list[str] = []
            if isinstance(m, int) and m > 0:
                parts.append(f"{m}/{total}M")
            if isinstance(h, int) and h > 0:
                parts.append(f"{h}/{total}H")
            if isinstance(n, int) and n > 0:
                parts.append(f"{n}/{total}N")

            if parts:
                lines.append(f"{raid_name}: " + " ".join(parts))

        return lines[:6]

    @staticmethod
    def _extract_mplus(raider_payload: dict[str, Any]) -> MythicPlusSummary:
        rating = "—"
        top_runs: list[str] = []

        seasons = raider_payload.get("mythic_plus_scores_by_season")
        if isinstance(seasons, list) and seasons:
            cur = seasons[0]
            if isinstance(cur, dict):
                scores = cur.get("scores")
                if isinstance(scores, dict):
                    all_score = scores.get("all")
                    if isinstance(all_score, (int, float)) and all_score > 0:
                        rating = str(round(float(all_score), 1))

        runs = raider_payload.get("mythic_plus_best_runs")
        if isinstance(runs, list) and runs:
            cleaned = [r for r in runs if isinstance(r, dict) and isinstance(r.get("keystone_level"), int)]

            def is_timed(r: dict[str, Any]) -> bool:
                v = r.get("timed")
                return bool(v) if isinstance(v, bool) else False

            cleaned.sort(key=lambda r: (is_timed(r), int(r["keystone_level"])), reverse=True)

            for r in cleaned[:3]:
                lvl = r.get("keystone_level", "—")
                dung = (r.get("dungeon") or {}).get("name") or "Dungeon"
                timed = "✅" if is_timed(r) else "⏱️"
                top_runs.append(f"+{lvl} {timed} — {dung}")

        return MythicPlusSummary(score=rating, top_runs=top_runs)

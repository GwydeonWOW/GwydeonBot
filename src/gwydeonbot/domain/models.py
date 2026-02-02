from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MythicPlusSummary:
    score: str
    top_runs: list[str]


@dataclass(frozen=True)
class CharacterOverview:
    name: str
    realm: str
    region: str
    level: str
    class_name: str
    class_id: int | None
    race: str
    faction: str
    spec: str | None
    guild: str | None
    item_level: str
    thumbnail_url: str | None
    armory_url: str
    mythic_plus: MythicPlusSummary
    raid_progress_lines: list[str]

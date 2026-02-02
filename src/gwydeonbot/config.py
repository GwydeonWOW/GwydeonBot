from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env from repo root if present; fallback to default behaviour."""
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Useful when running in environments where variables are injected
        load_dotenv(override=False)


_load_env()


@dataclass(frozen=True)
class Settings:
    discord_token: str
    blizzard_client_id: str
    blizzard_client_secret: str
    wow_region: str = "eu"
    wow_locale: str = "es_ES"
    discord_guild_id: int | None = None


def get_settings() -> Settings:
    missing: list[str] = []

    def must(name: str) -> str:
        v = os.getenv(name)
        if not v:
            missing.append(name)
        return v or ""

    guild_id = os.getenv("DISCORD_GUILD_ID")
    settings = Settings(
        discord_token=must("DISCORD_TOKEN"),
        blizzard_client_id=must("BLIZZARD_CLIENT_ID"),
        blizzard_client_secret=must("BLIZZARD_CLIENT_SECRET"),
        wow_region=os.getenv("WOW_REGION", "eu"),
        wow_locale=os.getenv("WOW_LOCALE", "es_ES"),
        discord_guild_id=int(guild_id) if guild_id else None,
    )

    if missing:
        raise RuntimeError(f"Faltan variables de entorno: {', '.join(missing)}")

    return settings

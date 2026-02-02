from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

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

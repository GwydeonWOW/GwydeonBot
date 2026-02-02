from __future__ import annotations

import aiohttp
import discord
from discord.ext import commands

from .config import Settings, get_settings
from .clients.blizzard_oauth import BlizzardOAuthClient
from .clients.blizzard_api import BlizzardApiClient
from .clients.raiderio_api import RaiderIoClient
from .services.character_service import CharacterService
from .services.realm_service import RealmService
from .services.guild_service import GuildService
from .services.ilvl_service import IlvlService
from .cogs.wow import WowCog
from .cogs.guild import GuildCog


class GwydeonBot(commands.Bot):
    def __init__(self, settings: Settings | None = None):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.settings = settings or get_settings()

        self.http_session: aiohttp.ClientSession | None = None
        self.character_service: CharacterService | None = None
        self.realm_service: RealmService | None = None
        self.guild_service: GuildService | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()

        oauth = BlizzardOAuthClient(
            self.http_session,
            self.settings.blizzard_client_id,
            self.settings.blizzard_client_secret,
        )
        blizzard = BlizzardApiClient(
            self.http_session,
            oauth,
            region=self.settings.wow_region,
            locale=self.settings.wow_locale,
        )
        raider = RaiderIoClient(self.http_session, region=self.settings.wow_region)

        self.character_service = CharacterService(blizzard, raider)
        self.realm_service = RealmService(blizzard)
        self.guild_service = GuildService(blizzard)
        self.ilvl_service = IlvlService(blizzard)


        await self.add_cog(WowCog(self, self.character_service, self.realm_service))
        await self.add_cog(GuildCog(self, self.guild_service, self.ilvl_service))

        # Sync rápido en tu servidor (dev)
        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()

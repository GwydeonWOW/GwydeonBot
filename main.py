import aiohttp
import discord
from discord.ext import commands

from .config import get_settings
from .services.blizzard_oauth import BlizzardOAuthClient
from .services.wow_api import WowApi
from .cogs.wow import WowCog
from .cogs.guild import GuildCog

class GwydeonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.http_session: aiohttp.ClientSession | None = None
        self.wow_api: WowApi | None = None
        self.ilvl_service: IlvlService | None = None
        self.settings = get_settings()

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        oauth = BlizzardOAuthClient(
            self.http_session,
            self.settings.blizzard_client_id,
            self.settings.blizzard_client_secret,
        )
        self.wow_api = WowApi(
            self.http_session,
            oauth,
            region=self.settings.wow_region,
            locale=self.settings.wow_locale,
        )

        await self.add_cog(WowCog(self))
        await self.add_cog(GuildCog(self))

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

def main():
    bot = GwydeonBot()
    bot.run(bot.settings.discord_token)

if __name__ == "__main__":
    main()

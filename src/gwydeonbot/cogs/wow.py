from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..domain.errors import WowApiError, WowNotFound
from ..services.character_service import CharacterService
from ..services.realm_service import RealmService
from ..utils.discord_helpers import class_color
from ..utils.text import normalize_character_name, normalize_realm_slug


class WowCog(commands.Cog):
    def __init__(self, bot: commands.Bot, character_service: CharacterService, realm_service: RealmService):
        self.bot = bot
        self._characters = character_service
        self._realms = realm_service

    @app_commands.command(
        name="personaje",
        description="Nivel, clase, raza, spec, hermandad, ilvl, M+ y progreso de raid.",
    )
    async def personaje(self, interaction: discord.Interaction, nombre: str, reino: str):
        await interaction.response.defer(thinking=True)

        realm_slug = normalize_realm_slug(reino)
        char_name = normalize_character_name(nombre)

        try:
            ov = await self._characters.get_character_overview(realm_slug=realm_slug, character_name=char_name)

            desc_lines = [f"**Facción:** {ov.faction}"]
            if ov.guild:
                desc_lines.append(f"**Hermandad:** {ov.guild}")
            desc_lines.append(f"🔗 [Ver en la Armory]({ov.armory_url})")

            embed = discord.Embed(
                title=f"{ov.name} - {reino} ({ov.region.upper()})",
                description="\n".join(desc_lines),
                color=class_color(ov.class_id),
            )

            embed.add_field(name="Nivel", value=ov.level, inline=True)
            embed.add_field(name="Clase", value=ov.class_name, inline=True)
            embed.add_field(name="Raza", value=ov.race, inline=True)
            if ov.spec:
                embed.add_field(name="Spec", value=ov.spec, inline=True)

            embed.add_field(name="Item Level", value=ov.item_level, inline=True)

            mplus_value = f"**Score:** {ov.mythic_plus.score}"
            if ov.mythic_plus.top_runs:
                mplus_value += "\n" + "\n".join(ov.mythic_plus.top_runs)
            embed.add_field(name="Mythic+ (Raider.IO)", value=mplus_value, inline=False)

            raid_text = "\n".join(ov.raid_progress_lines) if ov.raid_progress_lines else "—"
            embed.add_field(name="Raid Progress (Raider.IO)", value=raid_text, inline=False)

            if ov.thumbnail_url:
                embed.set_thumbnail(url=ov.thumbnail_url)

            await interaction.followup.send(embed=embed)

        except WowNotFound:
            await interaction.followup.send(
                f"No encuentro **{nombre}** en **{reino}** ({self._characters.region.upper()}).",
                ephemeral=True,
            )
        except WowApiError as e:
            await interaction.followup.send(
                f"API respondió con error.\n`{e}`",
                ephemeral=True,
            )

    @app_commands.command(name="status", description="Estado aproximado de un reino.")
    async def status(self, interaction: discord.Interaction, reino: str):
        await interaction.response.defer(thinking=True)

        realm_slug = normalize_realm_slug(reino)

        try:
            status_text = await self._realms.get_realm_status_text(realm_slug=realm_slug)
            embed = discord.Embed(title=f"Estado del reino: {reino} ({self._realms.region.upper()})")
            embed.add_field(name="Estado", value=status_text, inline=False)
            await interaction.followup.send(embed=embed)
        except WowNotFound:
            await interaction.followup.send(
                f"No encuentro el reino **{reino}** en {self._realms.region.upper()}.",
                ephemeral=True,
            )
        except WowApiError as e:
            await interaction.followup.send(f"Error Blizzard API:\n`{e}`", ephemeral=True)

from __future__ import annotations
import random
import discord
from discord import app_commands
from discord.ext import commands

from ..domain.errors import WowApiError, WowNotFound, WowRateLimited
from ..services.guild_service import GuildService
from ..services.ilvl_service import IlvlService
from ..utils.discord_helpers import class_color
from ..utils.text import normalize_guild_slug, normalize_realm_slug


class GuildCog(commands.Cog):
    def __init__(self, bot: commands.Bot, guild_service: GuildService, ilvl_service: IlvlService):
        self.bot = bot
        self._guilds = guild_service
        self._ilvl = ilvl_service

    @app_commands.command(
        name="guild",
        description="Resumen de una hermandad: miembros, top niveles y distribución de clases.",
    )
    async def guild(self, interaction: discord.Interaction, nombre: str, reino: str):
        await interaction.response.defer(thinking=True)

        realm_slug = normalize_realm_slug(reino)
        guild_slug = normalize_guild_slug(nombre)

        try:
            roster = await self._guilds.get_guild_roster(realm_slug=realm_slug, guild_slug=guild_slug)
            summary = await self._guilds.summarize_roster(roster)

            total: int = summary["total"]
            top_by_level = summary["top_by_level"]
            class_counter = summary["class_counter"]
            dominant_class_id = summary["dominant_class_id"]

            # Armory url (del cliente blizzard)
            armory_url = self._guilds._blizzard.armory_guild_url(realm_slug, guild_slug)  # acceso intencional

            embed = discord.Embed(
                title=f"{nombre} — {reino} ({self._guilds.region.upper()})",
                description=f"👥 **Miembros:** {total}\n🔗 [Ver en Armory]({armory_url})",
                color=class_color(dominant_class_id),
            )

            # Top levels
            lines = []
            for p in top_by_level:
                nm = p.get("name") or "?"
                lv = p.get("level") if isinstance(p.get("level"), int) else "—"
                cn = p.get("class_name") or "—"
                lines.append(f"**{nm}** — {lv} ({cn})")

            embed.add_field(name="Top nivel (10)", value="\n".join(lines) if lines else "—", inline=False)

            # Class distribution
            class_lines = [f"{cls}: **{count}**" for cls, count in class_counter.most_common(10)]
            embed.add_field(name="Clases (top 10)", value="\n".join(class_lines) if class_lines else "—", inline=False)

            embed.set_footer(text="Datos: Blizzard Guild Roster · Cache 5 min")

            await interaction.followup.send(embed=embed)

        except WowNotFound:
            await interaction.followup.send(
                f"No encuentro la hermandad **{nombre}** en **{reino}** ({self._guilds.region.upper()}).",
                ephemeral=True,
            )
        except WowRateLimited:
            await interaction.followup.send(
                "Blizzard está aplicando *rate limit* (429). Prueba de nuevo en 1–2 minutos.",
                ephemeral=True,
            )
        except WowApiError as e:
            await interaction.followup.send(f"Error Blizzard API:\n`{e}`", ephemeral=True)

    @app_commands.command(
        name="guild_topilvl",
        description="Top item level de una hermandad (cacheado, con límite de llamadas para evitar rate limits).",
    )
    @app_commands.describe(limite="Cuántos personajes mostrar (máx 20)")
    async def guild_topilvl(self, interaction: discord.Interaction, nombre: str, reino: str, limite: int = 10):
        await interaction.response.defer(thinking=True)

        limite = max(1, min(20, limite))
        realm_slug = normalize_realm_slug(reino)
        guild_slug = normalize_guild_slug(nombre)

        roster = await self._guilds.get_guild_roster(realm_slug=realm_slug, guild_slug=guild_slug)
        members = roster.get("members")
        if not isinstance(members, list) or not members:
            await interaction.followup.send("No pude obtener miembros del roster.", ephemeral=True)
            return

        # candidatos: solo nivel max + muestra aleatoria para no llamar a 309
        parsed = []
        for m in members:
            if not isinstance(m, dict):
                continue
            ch = m.get("character")
            if not isinstance(ch, dict):
                continue
            nm = ch.get("name")
            lv = ch.get("level")
            if isinstance(nm, str):
                parsed.append({"name": nm, "level": lv if isinstance(lv, int) else 0})

        # ordena por nivel para priorizar mains al cap
        parsed.sort(key=lambda x: x["level"], reverse=True)

        # elegimos un pool: top 80 por lvl + 40 random (si hay)
        top_pool = parsed[:80]
        tail = parsed[80:]
        random.shuffle(tail)
        pool = top_pool + tail[:40]

        # límite de llamadas por ejecución (para evitar 429)
        max_fetch = 30
        pool = pool[:max_fetch]

        results: list[tuple[str, int]] = []
        for p in pool:
            name = p["name"]
            ilvl = await self._ilvl.get_equipped_ilvl(realm_slug, name)
            if isinstance(ilvl, int):
                results.append((name, ilvl))

        if not results:
            await interaction.followup.send(
                "No pude calcular item level (puede ser privacidad o rate limit).",
                ephemeral=True,
            )
            return

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limite]

        armory_url = self._guilds._blizzard.armory_guild_url(realm_slug, guild_slug)  # acceso intencional
        lines = [f"**{i+1}. {nm}** — {ilvl}" for i, (nm, ilvl) in enumerate(results)]

        embed = discord.Embed(
            title=f"Top ilvl — {nombre} ({reino})",
            description=f"🔗 [Ver en Armory]({armory_url})\n\n" + "\n".join(lines),
        )
        embed.set_footer(text=f"Muestra: {len(pool)} miembros · Cache ilvl 2h · Límite llamadas: {max_fetch}")
        await interaction.followup.send(embed=embed)

import time
import discord
from discord import app_commands
from discord.ext import commands

from ..services.wow_api import WowApi, WowNotFound, WowApiError, WowRateLimited


class WowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache simple para Raider.IO: {(region, realm, name): (expires_ts, payload)}
        self._raider_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}

    def api(self) -> WowApi:
        return self.bot.wow_api  # type: ignore[attr-defined]

    # =========================================================
    # Raider.IO helpers (cache + parsers)
    # =========================================================

    async def _get_raider_cached(self, realm_slug: str, char_name: str) -> dict:
        api = self.api()
        key = (api._region, realm_slug, char_name)
        now = time.time()

        cached = self._raider_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        payload = await api.raider_character_profile(
            realm_slug,
            char_name,
            fields=[
                "raid_progression",
                "mythic_plus_scores_by_season:current",
                "mythic_plus_best_runs",
            ],
        )
        self._raider_cache[key] = (now + 120, payload)  # TTL 120s
        return payload

    @staticmethod
    def _extract_raid_progress(raider_payload: dict) -> list[str]:
        """
        Devuelve líneas tipo:
        "Liberation of Undermine: 8/8H 2/8M"
        """
        rp = raider_payload.get("raid_progression")
        if not isinstance(rp, dict) or not rp:
            return []

        lines: list[str] = []
        for raid_slug, data in rp.items():
            if not isinstance(data, dict):
                continue

            raid_name = data.get("name") or raid_slug.replace("-", " ").title()

            # Raider.IO normalmente trae "summary" ya listo
            summary = data.get("summary")
            if isinstance(summary, str) and summary.strip():
                lines.append(f"{raid_name}: {summary.strip()}")
                continue

            # fallback si no hubiera summary (raro)
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
    def _extract_mplus(raider_payload: dict) -> tuple[str, list[str]]:
        """
        Score actual + top 3 best runs
        """
        rating = "—"
        lines: list[str] = []

        seasons = raider_payload.get("mythic_plus_scores_by_season")
        if isinstance(seasons, list) and seasons:
            cur = seasons[0]  # cuando pedimos :current suele venir un solo elemento
            if isinstance(cur, dict):
                scores = cur.get("scores")
                if isinstance(scores, dict):
                    all_score = scores.get("all")
                    if isinstance(all_score, (int, float)) and all_score > 0:
                        rating = str(round(float(all_score), 1))

        runs = raider_payload.get("mythic_plus_best_runs")
        if isinstance(runs, list) and runs:
            cleaned = [r for r in runs if isinstance(r, dict) and isinstance(r.get("keystone_level"), int)]

            def is_timed(r: dict) -> bool:
                v = r.get("timed")
                return bool(v) if isinstance(v, bool) else False

            # timed primero, luego key level desc
            cleaned.sort(key=lambda r: (is_timed(r), int(r["keystone_level"])), reverse=True)

            for r in cleaned[:3]:
                lvl = r.get("keystone_level", "—")
                dung = (r.get("dungeon") or {}).get("name") or "Dungeon"
                timed = "✅" if is_timed(r) else "⏱️"
                lines.append(f"+{lvl} {timed} — {dung}")

        return rating, lines

    # =========================================================
    # Commands
    # =========================================================

    @app_commands.command(
        name="personaje",
        description="Nivel, clase, raza, spec, hermandad, ilvl, M+ y progreso de raid."
    )
    async def personaje(self, interaction: discord.Interaction, nombre: str, reino: str):
        await interaction.response.defer(thinking=True)

        api = self.api()
        realm_slug = api.normalize_realm_slug(reino)
        char_name = api.normalize_character_name(nombre)

        try:
            # -----------------------------
            # Blizzard: perfil básico
            # -----------------------------
            profile = await api.character_profile_summary(realm_slug, char_name)

            level = profile.get("level", "—")
            class_obj = profile.get("character_class") or {}
            class_name = class_obj.get("name", "—")
            class_id = class_obj.get("id")

            faction = (profile.get("faction") or {}).get("name", "—")
            race = (profile.get("race") or {}).get("name", "—")
            active_spec = (profile.get("active_spec") or {}).get("name", None)
            guild_name = (profile.get("guild") or {}).get("name", None)

            # -----------------------------
            # ILVL robusto
            # -----------------------------
            ilvl: int | float | str = "—"
            equip = None

            try:
                equip = await api.character_equipment_summary(realm_slug, char_name)
                direct = equip.get("equipped_item_level")
                if isinstance(direct, int) and direct > 0:
                    ilvl = direct
            except Exception:
                equip = None

            if ilvl == "—":
                try:
                    stats = await api.character_statistics(realm_slug, char_name)
                    v = stats.get("average_item_level_equipped")
                    if isinstance(v, int) and v > 0:
                        ilvl = v
                    else:
                        v2 = stats.get("average_item_level")
                        if isinstance(v2, int) and v2 > 0:
                            ilvl = v2
                except Exception:
                    pass

            if ilvl == "—":
                try:
                    if equip is None:
                        equip = await api.character_equipment_summary(realm_slug, char_name)
                    items = equip.get("equipped_items") or []
                    levels: list[int] = []
                    if isinstance(items, list):
                        for it in items:
                            if not isinstance(it, dict):
                                continue
                            v = (it.get("level") or {}).get("value")
                            if isinstance(v, int) and v > 0:
                                levels.append(v)
                    if levels:
                        ilvl = round(sum(levels) / len(levels), 1)
                except Exception:
                    pass

            # -----------------------------
            # Foto
            # -----------------------------
            thumbnail_url: str | None = None
            try:
                media = await api.character_media(realm_slug, char_name)
                assets = media.get("assets") or []
                if isinstance(assets, list):
                    for key in ("avatar", "inset", "main"):
                        match = next(
                            (a for a in assets if isinstance(a, dict) and a.get("key") == key and a.get("value")),
                            None
                        )
                        if match:
                            thumbnail_url = match["value"]
                            break
            except Exception:
                thumbnail_url = None

            # -----------------------------
            # Armory + color
            # -----------------------------
            armory_url = api.armory_character_url(realm_slug=realm_slug, character_name=char_name)
            embed_color = api.class_color(class_id=class_id, class_name=class_name)

            # -----------------------------
            # Raider.IO: M+ + Raid
            # -----------------------------
            mplus_rating = "—"
            mplus_lines: list[str] = []
            raid_lines: list[str] = []

            try:
                raider = await self._get_raider_cached(realm_slug, char_name)
                mplus_rating, mplus_lines = WowCog._extract_mplus(raider)
                raid_lines = WowCog._extract_raid_progress(raider)
            except WowNotFound:
                # Raider.IO puede no tener el char aunque Blizzard sí (poco frecuente)
                mplus_rating, mplus_lines, raid_lines = "—", [], []
            except WowRateLimited:
                mplus_rating, mplus_lines = "—", []
                raid_lines = ["Rate limit en Raider.IO. Prueba en 1–2 min."]
            except Exception:
                mplus_rating, mplus_lines, raid_lines = "—", [], []

            raid_text = "\n".join(raid_lines) if raid_lines else "—"

            # -----------------------------
            # Embed
            # -----------------------------
            desc_lines = [f"**Facción:** {faction}"]
            if guild_name:
                desc_lines.append(f"**Hermandad:** {guild_name}")
            desc_lines.append(f"🔗 [Ver en la Armory]({armory_url})")

            embed = discord.Embed(
                title=f"{profile.get('name', nombre)} - {reino} (EU)",
                description="\n".join(desc_lines),
                color=embed_color,
            )

            embed.add_field(name="Nivel", value=str(level), inline=True)
            embed.add_field(name="Clase", value=str(class_name), inline=True)
            embed.add_field(name="Raza", value=str(race), inline=True)
            if active_spec:
                embed.add_field(name="Spec", value=str(active_spec), inline=True)

            embed.add_field(name="Item Level", value=str(ilvl), inline=True)

            if mplus_lines:
                embed.add_field(
                    name="Mythic+ (Raider.IO)",
                    value=f"**Score:** {mplus_rating}\n" + "\n".join(mplus_lines),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Mythic+ (Raider.IO)",
                    value=f"**Score:** {mplus_rating}",
                    inline=False,
                )

            embed.add_field(name="Raid Progress (Raider.IO)", value=raid_text, inline=False)

            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            await interaction.followup.send(embed=embed)

        except WowNotFound:
            await interaction.followup.send(
                f"No encuentro **{nombre}** en **{reino}** (EU).",
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

        api = self.api()
        realm_slug = api.normalize_realm_slug(reino)

        try:
            idx = await api.realm_index()
            realms = idx.get("realms") or []

            realm = next((r for r in realms if r.get("slug") == realm_slug), None)
            if not realm:
                raise WowNotFound()

            realm_id = realm.get("id")
            if not realm_id:
                await interaction.followup.send("El realm_index no trae ID del reino.", ephemeral=True)
                return

            realm_data = await api.realm_by_id(int(realm_id))

            cr_href = ((realm_data.get("connected_realm") or {}).get("href"))
            if not cr_href:
                await interaction.followup.send("No pude resolver el connected realm.", ephemeral=True)
                return

            cr_id = api.extract_id_from_href(cr_href)
            if not cr_id:
                await interaction.followup.send("No pude extraer el ID del connected realm.", ephemeral=True)
                return

            cr = await api.connected_realm(cr_id)
            status_obj = cr.get("status") or {}
            status_type = status_obj.get("type")  # UP / DOWN

            mapping = {"UP": "Online ✅", "DOWN": "Offline ❌"}
            status_text = mapping.get(status_type, status_type or "Desconocido")

            embed = discord.Embed(title=f"Estado del reino: {reino} (EU)")
            embed.add_field(name="Estado", value=status_text, inline=False)
            await interaction.followup.send(embed=embed)

        except WowNotFound:
            await interaction.followup.send(f"No encuentro el reino **{reino}** en EU.", ephemeral=True)
        except WowApiError as e:
            await interaction.followup.send(f"Error Blizzard API:\n`{e}`", ephemeral=True)

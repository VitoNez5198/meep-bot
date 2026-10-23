"""
Cog de League of Legends para Meep Bot.
Incluye comandos unificados /champion, counters, live y perfil con botones interactivos.
"""

import asyncio
import datetime
import urllib.parse
from typing import Optional, Tuple
import discord
from discord import app_commands
from discord.ext import commands

import config
from services.lol_service import lol_service, CHAMPION_ALIASES
from services.emoji_service import get_emoji_service
from services.card_service import generate_build_card_file
from ui.lol_views import BuildVariantView, create_champion_embed


class LoLCog(commands.Cog, name="League of Legends"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _handle_champion_query(
        self,
        target_message,
        champ_query: str,
        mode_or_role: Optional[str] = None,
        style_preference: Optional[str] = None,
        author_id: int = None,
    ):
        """Lógica compartida entre comandos Slash y comandos con prefijo."""
        # Manejar defer inmediatamente para evitar el timeout de 3 segundos de Discord ("La aplicación no respondió")
        is_interaction = isinstance(target_message, discord.Interaction)
        msg_wait = None
        if is_interaction:
            if not target_message.response.is_done():
                try:
                    await target_message.response.defer()
                except Exception:
                    pass
        else:
            msg_wait = await target_message.reply("🔍 Obteniendo datos de campeón...", mention_author=False)

        resolved = lol_service.resolve_champion(champ_query)
        if not resolved:
            embed = discord.Embed(
                title="🔍 Campeón no encontrado",
                description=(
                    f"No pude encontrar ningún campeón con el nombre **'{champ_query}'**.\n\n"
                    f"💡 *Prueba usando alias comunes como:* `mf`, `tf`, `cait`, `lee`, `nunu`, `kaisa`."
                ),
                color=config.COLOR_ERROR,
            )
            if is_interaction:
                await target_message.followup.send(embed=embed, ephemeral=True)
            else:
                await msg_wait.edit(content=None, embed=embed)
            return

        champ_id, champ_info = resolved
        champ_name = champ_info.get("name", champ_id)

        # Determinar modo (Grieta vs ARAM)
        mode = "normal"
        if mode_or_role:
            m_lower = mode_or_role.lower().strip()
            if m_lower in ["aram", "a", "abismo"]:
                mode = "aram"

        # Obtener builds y variantes
        builds = lol_service.get_builds(champ_id, mode=mode)
        current_idx = 0

        # Si el usuario especificó un estilo directamente (ej: 'ap' o 'tank')
        if style_preference:
            pref = style_preference.lower()
            for idx, b in enumerate(builds):
                if pref in b.get("style_id", "").lower() or pref in b.get("style_name", "").lower():
                    current_idx = idx

        # Obtener detalles del campeón (lore y habilidades)
        details = lol_service.get_champion_details(champ_id)
        selected_build = builds[current_idx]

        embed = await create_champion_embed(
            bot=self.bot,
            champ_id=champ_id,
            champ_name=champ_name,
            mode=mode,
            build=selected_build,
            details=details,
        )
        view = BuildVariantView(
            bot=self.bot,
            champ_id=champ_id,
            champ_name=champ_name,
            mode=mode,
            builds=builds,
            details=details,
            current_index=current_idx,
            author_id=author_id,
        )

        if is_interaction:
            await target_message.followup.send(embed=embed, view=view)
        else:
            await msg_wait.edit(content=None, embed=embed, view=view)

    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================

    @app_commands.command(
        name="champion",
        description="Consulta runas, habilidades e ítems recomendados de un campeón (Clásico o ARAM)."
    )
    @app_commands.describe(
        campeon="Nombre o alias del campeón (ej: Miss Fortune, mf, Lee Sin, Kai'Sa)",
        modo="Selecciona el modo de juego (Clásico o ARAM)",
    )
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="Clásico (Grieta del Invocador)", value="normal"),
            app_commands.Choice(name="ARAM", value="aram"),
        ]
    )
    async def slash_champion(
        self,
        interaction: discord.Interaction,
        campeon: str,
        modo: Optional[app_commands.Choice[str]] = None,
    ):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass
        selected_mode = modo.value if isinstance(modo, app_commands.Choice) else (modo or "normal")
        await self._handle_champion_query(
            target_message=interaction,
            champ_query=campeon,
            mode_or_role=selected_mode,
            author_id=interaction.user.id,
        )

    async def _champion_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocompletado dinámico de campeones y alias comunes para selección con teclado."""
        curr = current.lower().strip()
        starts = []
        contains = []

        # Ordenar alfabéticamente por nombre
        sorted_champs = sorted(lol_service.champions_cache.values(), key=lambda c: c.get("name", ""))

        # Buscar por alias primero si coincide el prefijo (ej: 'mf', 'tf', 'cait', 'yi')
        for alias, cid in CHAMPION_ALIASES.items():
            if curr and alias.startswith(curr):
                champ = lol_service.champions_cache.get(cid)
                if champ:
                    c_name = champ.get("name", cid)
                    starts.append(app_commands.Choice(name=f"{c_name} ({alias.upper()})", value=c_name))

        for champ in sorted_champs:
            name = champ.get("name", "")
            n_low = name.lower()
            if not curr:
                starts.append(app_commands.Choice(name=name, value=name))
            elif n_low.startswith(curr):
                starts.append(app_commands.Choice(name=name, value=name))
            elif curr in n_low:
                contains.append(app_commands.Choice(name=name, value=name))

        seen = set()
        final = []
        for c in starts + contains:
            if c.value not in seen:
                seen.add(c.value)
                final.append(c)
            if len(final) >= 25:
                break
        return final

    @slash_champion.autocomplete("campeon")
    async def slash_champion_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            return await self._champion_autocomplete(interaction, current)
        except Exception:
            return []

    @app_commands.command(
        name="counters",
        description="Muestra los mejores y peores enfrentamientos de un campeón según OP.GG."
    )
    @app_commands.describe(campeon="Nombre o alias del campeón")
    async def slash_counters(self, interaction: discord.Interaction, campeon: str):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass
        resolved = lol_service.resolve_champion(campeon)
        if not resolved:
            await interaction.followup.send(f"❌ No se encontró el campeón **{campeon}**.", ephemeral=True)
            return

        champ_id, champ_info = resolved
        champ_name = champ_info.get("name", champ_id)
        loop = asyncio.get_running_loop()
        counters = await loop.run_in_executor(None, lol_service.get_counters, champ_id)

        embed = discord.Embed(
            title=f"⚔️ Enfrentamientos de {champ_name}",
            description="Estadísticas de enfrentamientos directos en clasificatorias (Fuente: **OP.GG**).",
            color=config.COLOR_LOL,
        )
        embed.set_thumbnail(url=lol_service.get_champion_icon_url(champ_id))
        embed.add_field(
            name="🔴 Matchups Difíciles (Menor Winrate)",
            value="\n".join(counters["dificiles"]) if counters.get("dificiles") else "• Sin datos suficientes en OP.GG.",
            inline=False,
        )
        embed.add_field(
            name="🟢 Matchups Favorables (Mayor Winrate)",
            value="\n".join(counters["favorables"]) if counters.get("favorables") else "• Sin datos suficientes en OP.GG.",
            inline=False,
        )
        footer_icon = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg"
        embed.set_footer(text=f"Parche {lol_service.display_patch} • Datos en vivo de OP.GG • Creado por VitoNez", icon_url=footer_icon)

        view = discord.ui.View()
        opgg_url = counters.get("opgg_url", f"https://www.op.gg/champions/{champ_id.lower()}/counters")
        view.add_item(discord.ui.Button(label="Ver Matchups en OP.GG", url=opgg_url, style=discord.ButtonStyle.link))
        await interaction.followup.send(embed=embed, view=view)

    @slash_counters.autocomplete("campeon")
    async def slash_counters_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            return await self._champion_autocomplete(interaction, current)
        except Exception:
            return []

    # =========================================================================
    # PREFIX COMMANDS (Texto corto en chat)
    # =========================================================================

    @commands.command(name="champion", aliases=["c", "build", "champ"])
    async def prefix_champion(self, ctx: commands.Context, campeon: str, modo: Optional[str] = None):
        """
        Uso: !c <campeon> [aram/clasico]
        Ejemplos:
          !c mf
          !c mf aram
          !c varus
        """
        await self._handle_champion_query(
            target_message=ctx,
            champ_query=campeon,
            mode_or_role=modo,
            author_id=ctx.author.id,
        )

    @commands.command(name="counters", aliases=["counter"])
    async def prefix_counters(self, ctx: commands.Context, campeon: str):
        """Uso: !counters <campeon>"""
        resolved = lol_service.resolve_champion(campeon)
        if not resolved:
            await ctx.reply(f"❌ No se encontró el campeón **{campeon}**.", mention_author=False)
            return

        champ_id, champ_info = resolved
        champ_name = champ_info.get("name", champ_id)
        counters = lol_service.get_counters(champ_id)

        embed = discord.Embed(
            title=f"⚔️ Enfrentamientos de {champ_name}",
            description="Estadísticas de enfrentamientos directos en clasificatorias (Fuente: **OP.GG**).",
            color=config.COLOR_LOL,
        )
        embed.set_thumbnail(url=lol_service.get_champion_icon_url(champ_id))
        embed.add_field(
            name="🔴 Matchups Difíciles (Menor Winrate)",
            value="\n".join(counters["dificiles"]) if counters.get("dificiles") else "• Sin datos suficientes en OP.GG.",
            inline=False,
        )
        embed.add_field(
            name="🟢 Matchups Favorables (Mayor Winrate)",
            value="\n".join(counters["favorables"]) if counters.get("favorables") else "• Sin datos suficientes en OP.GG.",
            inline=False,
        )
        footer_icon = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg"
        embed.set_footer(text=f"Parche {lol_service.display_patch} • Datos en vivo de OP.GG • Creado por VitoNez", icon_url=footer_icon)

        view = discord.ui.View()
        opgg_url = counters.get("opgg_url", f"https://www.op.gg/champions/{champ_id.lower()}/counters")
        view.add_item(discord.ui.Button(label="Ver Matchups en OP.GG", url=opgg_url, style=discord.ButtonStyle.link))
        await ctx.reply(embed=embed, view=view, mention_author=False)

    def _build_profile_response(self, summoner_query: str, region: str) -> Tuple[discord.Embed, discord.ui.View]:
        """Construye un Embed enriquecido con los datos del invocador extraídos de OP.GG."""
        profile = lol_service.get_summoner_profile(summoner_query, region)
        view = discord.ui.View()

        if not profile.get("found"):
            embed = discord.Embed(
                title="🔍 Invocador no Encontrado",
                description=profile.get("error", "No se encontró el invocador."),
                color=config.COLOR_ERROR,
            )
            embed.set_footer(text="Asegúrate de escribir tu Riot ID correctamente (Nombre#Tag).")
            if profile.get("url"):
                view.add_item(discord.ui.Button(label="Buscar en OP.GG", url=profile["url"], style=discord.ButtonStyle.link))
            return embed, view

        riot_id = profile["riot_id"]
        reg = profile["region"]
        opgg_url = profile["opgg_url"]
        source = profile.get("source", "OP.GG")

        if source == "Riot Games":
            level = profile.get("level", 1)
            embed = discord.Embed(
                title=f"🏆 Perfil Oficial: {riot_id}",
                description=f"Nivel de Invocador: **{level}** | Servidor: **{reg}**",
                color=config.COLOR_LOL,
                url=opgg_url,
            )
            if profile.get("profile_icon"):
                embed.set_thumbnail(url=profile["profile_icon"])

            embed.add_field(name="⚔️ Solo / Dúo 5v5", value=profile.get("solo_rank", "Unranked"), inline=True)
            embed.add_field(name="🛡️ Flexible 5v5", value=profile.get("flex_rank", "Unranked"), inline=True)

            masteries = profile.get("masteries", [])
            if masteries:
                mastery_lines = [
                    f"• **{m['name']}** — `Nivel {m['level']}` ({m['points']:,} pts)"
                    for m in masteries[:5]
                ]
                embed.add_field(name="🎖️ Campeones con Mayor Maestría (Oficial)", value="\n".join(mastery_lines), inline=False)

            embed.set_footer(text="Fuente: API Oficial de Riot Games • Creado por VitoNez", icon_url=profile.get("tier_badge"))
        else:
            rank_tier = profile.get("rank_tier", "Unranked")
            winrate_info = profile.get("winrate_info", "0W 0L")
            embed = discord.Embed(
                title=f"🏆 Perfil de Invocador: {riot_id}",
                description=f"Estadísticas de clasificatorias en el servidor **{reg}** (Fuente: **OP.GG**).",
                color=config.COLOR_LOL,
                url=opgg_url,
            )
            if profile.get("profile_icon"):
                embed.set_thumbnail(url=profile["profile_icon"])

            embed.add_field(name="🏅 División / Rango", value=f"**{rank_tier}**", inline=True)
            embed.add_field(name="📊 Win Rate & Registro", value=f"`{winrate_info}`", inline=True)

            masteries = profile.get("masteries", [])
            if masteries:
                mastery_lines = [
                    f"• **{m['name']}** — `Nivel {m['level']}` ({m['points']:,} pts)"
                    for m in masteries[:5]
                ]
                embed.add_field(name="🎖️ Campeones con Mayor Maestría", value="\n".join(mastery_lines), inline=False)

            top_champs = profile.get("top_champions", [])
            if top_champs:
                champs_lines = [f"• **{c}**" for c in top_champs[:4]]
                embed.add_field(name="📈 Desempeño en Clasificatorias (Temporada)", value="\n".join(champs_lines), inline=False)

            footer_icon = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg"
            embed.set_footer(text=f"Datos obtenidos en vivo desde OP.GG • Creado por VitoNez", icon_url=footer_icon)

        view.add_item(discord.ui.Button(label="Ver Perfil Completo en OP.GG", url=opgg_url, style=discord.ButtonStyle.link))
        return embed, view

    @app_commands.command(
        name="perfil",
        description="Consulta las estadísticas de un invocador en OP.GG (Rango, Winrate y Campeones)."
    )
    @app_commands.describe(
        invocador="Nombre de invocador o Riot ID (ej: MiNombre#LAS o MiNombre)",
        servidor="Región o servidor de League of Legends (por defecto: LAS)"
    )
    @app_commands.choices(
        servidor=[
            app_commands.Choice(name="LAS (Latinoamérica Sur)", value="las"),
            app_commands.Choice(name="LAN (Latinoamérica Norte)", value="lan"),
            app_commands.Choice(name="BR (Brasil)", value="br"),
            app_commands.Choice(name="NA (Norteamérica)", value="na"),
            app_commands.Choice(name="EUW (Europa Oeste)", value="euw"),
            app_commands.Choice(name="KR (Corea)", value="kr"),
        ]
    )
    async def slash_profile(
        self,
        interaction: discord.Interaction,
        invocador: str,
        servidor: Optional[app_commands.Choice[str]] = None,
    ):
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return
        region = servidor.value if isinstance(servidor, app_commands.Choice) else (servidor or "las")
        loop = asyncio.get_running_loop()
        embed, view = await loop.run_in_executor(None, self._build_profile_response, invocador, region)
        await interaction.followup.send(embed=embed, view=view)

    @commands.command(name="perfil", aliases=["invocador", "profile", "pelo"])
    async def prefix_profile(self, ctx: commands.Context, *, argumentos: Optional[str] = None):
        """
        Consulta rango, winrate y campeones en OP.GG.
        Uso: !perfil <Nombre#Tag o Nombre> [servidor]
        Ejemplos:
          !perfil MiNombre#LAS
          !perfil Faker#KR1 kr
        """
        if not argumentos:
            embed = discord.Embed(
                title="🏆 Perfil de Invocador",
                description=(
                    "Consulta rango clasificatorio, winrate y campeones con mayor maestría.\n\n"
                    f"**Uso:** `{config.BOT_PREFIX}perfil <Nombre#Tag> [servidor]` o `/perfil`\n"
                    f"**Ejemplos:**\n"
                    f"• `{config.BOT_PREFIX}perfil MiNombre#LAS`\n"
                    f"• `{config.BOT_PREFIX}perfil Faker#KR1 kr`"
                ),
                color=config.COLOR_LOL,
            )
            embed.set_footer(text="Fuente: OP.GG • Creado por VitoNez")
            await ctx.reply(embed=embed, mention_author=False)
            return

        parts = argumentos.strip().split()
        known_servers = {"las", "lan", "na", "euw", "eun", "br", "kr", "jp", "oce"}
        if len(parts) > 1 and parts[-1].lower() in known_servers:
            server = parts[-1].lower()
            summoner = " ".join(parts[:-1])
        else:
            server = "las"
            summoner = argumentos.strip()

        embed, view = self._build_profile_response(summoner, server)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    async def _build_live_response(self, summoner_query: str, server: str) -> Tuple[discord.Embed, discord.ui.View]:
        """Construye un Embed con grid perfectamente alineado, iconos oficiales y destacado de color."""
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, lol_service.get_active_game, summoner_query, server)
        view = discord.ui.View()

        if not res.get("success"):
            err_type = res.get("error")
            title = "⚡ Live Game"
            color = config.COLOR_ERROR if err_type != "no_key" else config.COLOR_LOL
            embed = discord.Embed(
                title=title,
                description=res.get("message", "Error al consultar la partida."),
                color=color,
            )
            embed.set_footer(text="Riot Games Spectator API • Creado por VitoNez")
            return embed, view

        if not res.get("in_game"):
            embed = discord.Embed(
                title="⚡ Live Game",
                description=f"El jugador **{res.get('player_name')}** no se encuentra en una partida activa en este momento.",
                color=config.COLOR_LOL,
            )
            embed.set_footer(text="Riot Games Spectator API • Creado por VitoNez")
            if res.get("opgg_url"):
                view.add_item(discord.ui.Button(label="Ver Perfil en OP.GG", url=res["opgg_url"], style=discord.ButtonStyle.link))
            return embed, view

        mode = res.get("game_mode", "5v5 Game")
        mins = res.get("duration_mins", 0)
        srv = res.get("server", "LAS")
        player = res.get("player_name", summoner_query)
        target_asset = res.get("target_champion_asset")
        opgg_url = res.get("opgg_url")
        start_time_ms = res.get("game_start_time", 0)

        emoji_service = get_emoji_service(self.bot)

        # Cargar emojis de campeones en paralelo para ambos equipos
        blue_team = res.get("blue_team", [])
        red_team = res.get("red_team", [])

        blue_emojis = await asyncio.gather(*[
            emoji_service.get_champion_emoji(p.get("champion_id", "")) for p in blue_team
        ])
        red_emojis = await asyncio.gather(*[
            emoji_service.get_champion_emoji(p.get("champion_id", "")) for p in red_team
        ])

        if mins > 0:
            desc = f"**{player}** is {mins} minutes into a {mode} game."
        else:
            desc = f"**{player}** is in loading screen for a {mode} game."

        embed = discord.Embed(
            title=f"⚔️ Live Game details for {player}",
            description=desc,
            color=0x202225,
            url=opgg_url,
        )

        # Icono discreto del campeón buscado en la esquina superior derecha
        if target_asset:
            embed.set_thumbnail(url=f"https://ddragon.leagueoflegends.com/cdn/{lol_service.latest_version}/img/champion/{target_asset}.png")

        # 1. Bans alineados
        blue_bans = res.get("blue_bans", [])
        red_bans = res.get("red_bans", [])
        blue_bans_str = " • ".join(blue_bans[:5]) if blue_bans else "None"
        red_bans_str = " • ".join(red_bans[:5]) if red_bans else "None"

        # 2. Formato de Picks para Equipo Azul
        blue_picks_lines = []
        for i, p in enumerate(blue_team):
            c_icon = blue_emojis[i] if i < len(blue_emojis) else "👤"
            rk = p.get("rank_info", {})
            rank_str = rk.get("short_str", "└ 🔘 Unranked")

            if p.get("is_target"):
                enc_name = urllib.parse.quote(p['riot_id'].replace('#', '-'))
                p_url = f"https://op.gg/lol/summoners/{srv.lower()}/{enc_name}"
                player_fmt = f"[__**{p['riot_id']}**__]({p_url}) 🎯"
            else:
                player_fmt = f"**{p['riot_id']}**"

            blue_picks_lines.append(
                f"{c_icon} {player_fmt}: {p['champion_name']}\n"
                f"{rank_str}"
            )

        # 3. Formato de Picks para Equipo Rojo
        red_picks_lines = []
        for i, p in enumerate(red_team):
            c_icon = red_emojis[i] if i < len(red_emojis) else "👤"
            rk = p.get("rank_info", {})
            rank_str = rk.get("short_str", "└ 🔘 Unranked")

            if p.get("is_target"):
                enc_name = urllib.parse.quote(p['riot_id'].replace('#', '-'))
                p_url = f"https://op.gg/lol/summoners/{srv.lower()}/{enc_name}"
                player_fmt = f"[__**{p['riot_id']}**__]({p_url}) 🎯"
            else:
                player_fmt = f"**{p['riot_id']}**"

            red_picks_lines.append(
                f"{c_icon} {player_fmt}: {p['champion_name']}\n"
                f"{rank_str}"
            )

        blue_val = (
            f"**Bans**\n🚫 {blue_bans_str}\n\n"
            f"**Picks**\n" + ("\n\n".join(blue_picks_lines) if blue_picks_lines else "None")
        )

        red_val = (
            f"**Bans**\n🚫 {red_bans_str}\n\n"
            f"**Picks**\n" + ("\n\n".join(red_picks_lines) if red_picks_lines else "None")
        )

        # Columnas side-by-side con inline=True
        embed.add_field(name="Blue Team", value=blue_val, inline=True)
        embed.add_field(name="Red Team", value=red_val, inline=True)

        # Footer con Game started y hora de inicio (sin el splash art gigante)
        embed.set_footer(text=f"Game started • Server {srv}")
        if start_time_ms and start_time_ms > 0:
            embed.timestamp = datetime.datetime.fromtimestamp(start_time_ms / 1000, tz=datetime.timezone.utc)
        else:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        if opgg_url:
            view.add_item(discord.ui.Button(label="Ver en Vivo en OP.GG", url=f"{opgg_url}/ingame", style=discord.ButtonStyle.link))
            view.add_item(discord.ui.Button(label="Perfil en OP.GG", url=opgg_url, style=discord.ButtonStyle.link))

        return embed, view

    @app_commands.command(
        name="live",
        description="Consulta los 10 jugadores, runas y campeones de una partida en curso en tiempo real."
    )
    @app_commands.describe(
        invocador="Nombre de invocador o Riot ID (ej: MiNombre#LAS o Faker#KR1)",
        servidor="Servidor de League of Legends (por defecto: LAS)"
    )
    @app_commands.choices(
        servidor=[
            app_commands.Choice(name="LAS (Latinoamérica Sur)", value="las"),
            app_commands.Choice(name="LAN (Latinoamérica Norte)", value="lan"),
            app_commands.Choice(name="BR (Brasil)", value="br"),
            app_commands.Choice(name="NA (Norteamérica)", value="na"),
            app_commands.Choice(name="EUW (Europa Oeste)", value="euw"),
            app_commands.Choice(name="EUN (Europa Nórdica y Este)", value="eun"),
            app_commands.Choice(name="KR (Corea)", value="kr"),
        ]
    )
    async def slash_live(
        self,
        interaction: discord.Interaction,
        invocador: str,
        servidor: Optional[app_commands.Choice[str]] = None,
    ):
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return
        reg_val = servidor.value if servidor else "las"
        embed, view = await self._build_live_response(invocador, reg_val)
        await interaction.followup.send(embed=embed, view=view)

    @commands.command(name="live", aliases=["partida", "ingame"])
    async def prefix_live(self, ctx: commands.Context, *, argumentos: Optional[str] = None):
        """
        Consulta la partida en curso en tiempo real (requiere RIOT_API_KEY).
        Uso: !live <Nombre#Tag o Nombre> [servidor]
        Ejemplos:
          !live MiNombre#LAS
          !live Faker#KR1 kr
        """
        if not argumentos:
            embed = discord.Embed(
                title="⚡ Partida en Vivo",
                description=(
                    "Consulta los 10 jugadores, runas y campeones de una partida en curso en tiempo real.\n\n"
                    f"**Uso:** `{config.BOT_PREFIX}live <Nombre#Tag> [servidor]` o `/live`\n"
                    f"**Ejemplos:**\n"
                    f"• `{config.BOT_PREFIX}live MiNombre#LAS`\n"
                    f"• `{config.BOT_PREFIX}live Faker#KR1 kr`\n\n"
                    f"*Servidores disponibles:* `las`, `lan`, `na`, `euw`, `eun`, `br`, `kr` (por defecto: `las`)."
                ),
                color=config.COLOR_LOL,
            )
            embed.set_footer(text="Riot Games Spectator API • Creado por VitoNez")
            await ctx.reply(embed=embed, mention_author=False)
            return

        parts = argumentos.strip().split()
        known_servers = {"las", "lan", "na", "euw", "eun", "br", "kr", "jp", "oce"}
        if len(parts) > 1 and parts[-1].lower() in known_servers:
            server = parts[-1].lower()
            summoner = " ".join(parts[:-1])
        else:
            server = "las"
            summoner = argumentos.strip()

        embed, view = await self._build_live_response(summoner, server)
        await ctx.reply(embed=embed, view=view, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(LoLCog(bot))

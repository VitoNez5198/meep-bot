"""
Cog de League of Legends para Meep Bot.
Incluye comandos unificados /champion, counters, live y perfil con botones interactivos.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

import config
from services.lol_service import lol_service
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
                await target_message.response.defer()
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
        await interaction.response.defer()
        selected_mode = modo.value if isinstance(modo, app_commands.Choice) else (modo or "normal")
        await self._handle_champion_query(
            target_message=interaction,
            champ_query=campeon,
            mode_or_role=selected_mode,
            author_id=interaction.user.id,
        )

    @app_commands.command(
        name="counters",
        description="Muestra los mejores y peores enfrentamientos de un campeón."
    )
    @app_commands.describe(campeon="Nombre o alias del campeón")
    async def slash_counters(self, interaction: discord.Interaction, campeon: str):
        await interaction.response.defer()
        resolved = lol_service.resolve_champion(campeon)
        if not resolved:
            await interaction.followup.send(f"❌ No se encontró el campeón **{campeon}**.", ephemeral=True)
            return

        champ_id, champ_info = resolved
        champ_name = champ_info.get("name", champ_id)
        counters = lol_service.get_counters(champ_id)

        embed = discord.Embed(
            title=f"⚔️ Enfrentamientos de {champ_name}",
            color=config.COLOR_LOL,
        )
        embed.set_thumbnail(url=lol_service.get_champion_icon_url(champ_id))
        embed.add_field(
            name="🔴 Matchups Difíciles (Cuidado)",
            value="\n".join([f"• {c}" for c in counters["dificiles"]]),
            inline=False,
        )
        embed.add_field(
            name="🟢 Matchups Favorables (Ventaja)",
            value="\n".join([f"• {c}" for c in counters["favorables"]]),
            inline=False,
        )
        embed.set_footer(text="Información calculada para el parche actual")
        await interaction.followup.send(embed=embed)

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
            color=config.COLOR_LOL,
        )
        embed.set_thumbnail(url=lol_service.get_champion_icon_url(champ_id))
        embed.add_field(
            name="🔴 Matchups Difíciles (Cuidado)",
            value="\n".join([f"• {c}" for c in counters["dificiles"]]),
            inline=False,
        )
        embed.add_field(
            name="🟢 Matchups Favorables (Ventaja)",
            value="\n".join([f"• {c}" for c in counters["favorables"]]),
            inline=False,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="live", aliases=["partida"])
    async def prefix_live(self, ctx: commands.Context, *, invocador: Optional[str] = None):
        """Consulta la partida en curso (requiere RIOT_API_KEY)."""
        if not config.RIOT_API_KEY:
            embed = discord.Embed(
                title="⚡ Partida en Vivo",
                description=(
                    "Para consultar partidas en vivo en tiempo real, añade tu clave gratuita de Riot Games al archivo `.env`:\n\n"
                    "1. Ingresa a: https://developer.riotgames.com/\n"
                    "2. Inicia sesión con tu cuenta de Riot y copia tu **Development API Key**.\n"
                    "3. Pégala en `.env` en la variable `RIOT_API_KEY`."
                ),
                color=config.COLOR_LOL,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        await ctx.reply("🔍 Consultando estado de partida en los servidores de Riot...", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(LoLCog(bot))

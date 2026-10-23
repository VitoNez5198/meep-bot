"""
Componentes interactivos de Discord para League of Legends (Diseño exacto estilo PoroScout).
Utiliza Emojis nativos de Discord para objetos y runas, y código ANSI para colorear habilidades.
"""

from typing import List, Dict, Any, Optional
import discord

import config
from services.lol_service import lol_service
from services.emoji_service import get_emoji_service


async def create_champion_embed(
    bot: discord.Client,
    champ_id: str,
    champ_name: str,
    mode: str,
    build: Dict[str, Any],
    details: Dict[str, Any],
) -> discord.Embed:
    """Genera un Discord Embed limpio con iconos emoji, idéntico al formato visual de PoroScout."""
    emoji_service = get_emoji_service(bot)
    version = lol_service.latest_version
    display_patch = lol_service.display_patch
    tier = build.get("tier", "Tier S")
    is_aram = mode.lower() == "aram"
    color = config.COLOR_ARAM if is_aram else config.COLOR_LOL

    # Título estilo PoroScout reflejando el estilo activo
    style_label = build.get("style_name", "Build Principal")
    clean_style = style_label.split("(")[0].strip() if "(" in style_label else style_label
    title = f"[{display_patch}] [{tier}] {champ_name} • {clean_style}"
    if is_aram:
        title = f"[{display_patch}] [{tier}] {champ_name} (ARAM) • {clean_style}"

    # Descripción con lore breve y partidas analizadas
    lore = details.get("lore", "")
    if len(lore) > 170:
        lore = lore[:170] + "..."

    description = (
        f"Basado en más de **{build.get('games_analyzed', '342.3k')}** partidas analizadas.\n\n"
        f"> *{lore}*"
    )

    embed = discord.Embed(title=title, description=description, color=color)

    # Miniatura del campeón arriba a la derecha
    icon_url = lol_service.get_champion_icon_url(champ_id)
    embed.set_thumbnail(url=icon_url)

    # -------------------------------------------------------------
    # 3 Columnas Superiores: Pick Rate, Ban Rate, Win Rate
    # -------------------------------------------------------------
    embed.add_field(name="Pick Rate", value=f"{build.get('pick_rate', '12.4%')} (Sin cambios)", inline=True)
    embed.add_field(name="Ban Rate", value=f"{build.get('ban_rate', '7.8%')} (Sin cambios)", inline=True)
    embed.add_field(name="Win Rate", value=f"**{build.get('win_rate', '52.3%')}** (Sin cambios)", inline=True)

    # -------------------------------------------------------------
    # 3 Columnas Centrales: Most Popular Build, Primary Runes, Secondary Runes
    # -------------------------------------------------------------

    # Obtener emojis para objetos
    starter_ids = build.get("starter_item_ids", ["1056", "2003", "3340"])
    core_ids = build.get("core_item_ids", ["6653", "6655", "3157"])
    situational_ids = build.get("situational_item_ids", ["3089", "3135", "3020"])

    starter_emojis = [await emoji_service.get_item_emoji(i_id, version) for i_id in starter_ids]
    core_emojis = [await emoji_service.get_item_emoji(i_id, version) for i_id in core_ids]
    situational_emojis = [await emoji_service.get_item_emoji(i_id, version) for i_id in situational_ids]

    # Columna 1: Most Popular Build (SOLO ICONOS, SIN TEXTO DE NOMBRES)
    build_column_text = (
        f"**Starter Items**\n{' '.join(starter_emojis)}\n\n"
        f"**Core Items**\n{' '.join(core_emojis)}\n\n"
        f"**Situational Items**\n{' '.join(situational_emojis)}"
    )
    embed.add_field(name="Most Popular Build", value=build_column_text, inline=True)

    # Columna 2: Primary Runes (Icono de Runa + Nombre)
    keystone = build.get("keystone", "Cometa Arcano")
    keystone_em = await emoji_service.get_rune_emoji(keystone, version)
    primary_lines = [f"{keystone_em} **{keystone}**"]
    for r in build.get("primary_runes", []):
        r_em = await emoji_service.get_rune_emoji(r, version)
        primary_lines.append(f"{r_em} {r}")

    primary_tree_title = build.get("primary_tree", "Dominación").split("(")[0].strip()
    embed.add_field(name=f"Primary Runes", value="\n".join(primary_lines), inline=True)

    # Columna 3: Secondary Runes (Icono de Runa + Nombre + Shards)
    secondary_lines = []
    for r in build.get("secondary_runes", []):
        r_em = await emoji_service.get_rune_emoji(r, version)
        secondary_lines.append(f"{r_em} {r}")
    secondary_tree_title = build.get("secondary_tree", "Inspiración").split("(")[0].strip()
    embed.add_field(name=f"Secondary Runes", value="\n".join(secondary_lines), inline=True)

    # -------------------------------------------------------------
    # Fila Completa: Skill Order (Matriz con Colores ANSI)
    # -------------------------------------------------------------
    skill_max = build.get("skill_max", "Q > W > E")
    skill_matrix_ansi = lol_service.generate_skill_matrix(skill_max)
    embed.add_field(
        name=f"Skill Order ({skill_max})",
        value=skill_matrix_ansi,
        inline=False,
    )

    footer_icon = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg"
    embed.set_footer(text=f"Parche {display_patch} • OP.GG & DataDragon • Creado por VitoNez", icon_url=footer_icon)

    return embed


class BuildVariantView(discord.ui.View):
    """
    Vista interactiva con botones de Discord para alternar entre diferentes estilos
    de build y enlaces externos.
    """
    def __init__(
        self,
        bot: discord.Client,
        champ_id: str,
        champ_name: str,
        mode: str,
        builds: List[Dict[str, Any]],
        details: Dict[str, Any],
        current_index: int = 0,
        author_id: int = None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.champ_id = champ_id
        self.champ_name = champ_name
        self.mode = mode
        self.builds = builds
        self.details = details
        self.current_index = current_index
        self.author_id = author_id

        self._build_buttons()

    def _build_buttons(self):
        """Genera los botones según las variantes disponibles."""
        self.clear_items()

        # Nombres de botones limpios y estandarizados solicitados por el usuario
        standard_labels = ["Build Principal", "Build Secundaria", "Build Alternativa", "Build Opcional"]
        if len(self.builds) > 1:
            for idx, build in enumerate(self.builds):
                button_label = standard_labels[idx] if idx < len(standard_labels) else f"Build {idx + 1}"
                is_active = (idx == self.current_index)

                button = discord.ui.Button(
                    label=button_label,
                    style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                    disabled=is_active,
                    custom_id=f"build_btn_{idx}",
                )
                button.callback = self._create_callback(idx)
                self.add_item(button)

        # Botón de enlace directo oficial a OP.GG solicitado por el usuario
        champ_key = self.champ_id.lower()
        if self.mode.lower() == "aram":
            opgg_url = f"https://op.gg/lol/modes/aram/{champ_key}/build"
        else:
            opgg_url = f"https://op.gg/lol/champions/{champ_key}/build"

        self.add_item(discord.ui.Button(label="Ver en OP.GG", url=opgg_url, style=discord.ButtonStyle.link))

    def _create_callback(self, target_idx: int):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.current_index = target_idx
            self._build_buttons()

            new_build = self.builds[self.current_index]
            new_embed = await create_champion_embed(
                bot=self.bot,
                champ_id=self.champ_id,
                champ_name=self.champ_name,
                mode=self.mode,
                build=new_build,
                details=self.details,
            )

            await interaction.message.edit(embed=new_embed, view=self)

        return callback

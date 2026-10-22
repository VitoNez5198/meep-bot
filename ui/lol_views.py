"""
Componentes interactivos de Discord para League of Legends (Diseño estilo PoroScout).
Incluye tarjeta gráfica de objetos y habilidades generada con Pillow.
"""

from typing import List, Dict, Any, Optional
import discord

import config
from services.lol_service import lol_service
from services.card_service import generate_build_card_file


def create_champion_embed(
    champ_id: str,
    champ_name: str,
    mode: str,
    build: Dict[str, Any],
    details: Dict[str, Any],
) -> discord.Embed:
    """Genera un Discord Embed estilizado idéntico al formato de PoroScout/Mobalytics."""
    is_aram = mode.lower() == "aram"
    mode_tag = "ARAM" if is_aram else "Grieta"
    tier = build.get("tier", "Tier S")
    version = lol_service.latest_version
    color = config.COLOR_ARAM if is_aram else config.COLOR_LOL

    # Título estilo PoroScout: [16.21] [Tier S] Champion data for Ahri
    title = f"[{version}] [{tier}] Datos de campeón para {champ_name}"
    if is_aram:
        title = f"[{version}] [{tier}] {champ_name} — Modo ARAM"

    # Descripción con lore breve y juegos analizados
    lore = details.get("lore", "")
    if len(lore) > 170:
        lore = lore[:170] + "..."

    description = (
        f"Basado en más de **{build.get('games_analyzed', '340.5k')}** partidas analizadas.\n"
        f"**Estilo:** {build.get('style_name', 'Estándar')}\n\n"
        f"> *{lore}*"
    )

    embed = discord.Embed(title=title, description=description, color=color)

    # Miniatura del campeón arriba a la derecha
    icon_url = lol_service.get_champion_icon_url(champ_id)
    embed.set_thumbnail(url=icon_url)

    # -------------------------------------------------------------
    # 3 Columnas Superiores: Pick Rate, Ban Rate, Win Rate
    # -------------------------------------------------------------
    embed.add_field(name="Pick Rate", value=f"**{build.get('pick_rate', '12.4%')}**", inline=True)
    embed.add_field(name="Ban Rate", value=f"**{build.get('ban_rate', '7.8%')}**", inline=True)
    embed.add_field(name="Win Rate", value=f"**{build.get('win_rate', '52.3%')}**", inline=True)

    # -------------------------------------------------------------
    # 3 Columnas Centrales: Objetos, Runas Primarias, Runas Secundarias
    # -------------------------------------------------------------
    # Columna 1: Most Popular Build
    items_content = (
        f"**Starter Items**\n{build.get('starting_items', 'Doran + Poción')}\n\n"
        f"**Core Items**\n{build.get('core_items', 'Objetos Core')}\n\n"
        f"**Situational Items**\n{build.get('situational_items', 'Objetos Situacionales')}"
    )
    embed.add_field(name="Most Popular Build", value=items_content, inline=True)

    # Columna 2: Primary Runes
    primary_tree = build.get("primary_tree", "Brujería")
    primary_lines = [f"🌟 **{build.get('keystone', 'Cometa Arcano')}**"]
    for r in build.get("primary_runes", []):
        primary_lines.append(f"• {r}")
    embed.add_field(name=f"Primary Runes", value="\n".join(primary_lines), inline=True)

    # Columna 3: Secondary Runes y Fragmentos
    secondary_tree = build.get("secondary_tree", "Inspiración")
    secondary_lines = []
    for r in build.get("secondary_runes", []):
        secondary_lines.append(f"• {r}")

    shards_clean = "  ".join([f"`{s.replace('+', '').strip()}`" for s in build.get("shards", [])])
    secondary_lines.append(f"\n**Fragmentos:**\n{shards_clean}")
    embed.add_field(name=f"Secondary Runes", value="\n".join(secondary_lines), inline=True)

    # -------------------------------------------------------------
    # Fila Completa: Skill Order (Matriz de Habilidades 1 al 18)
    # -------------------------------------------------------------
    skill_max = build.get("skill_max", "Q > W > E")
    skill_matrix = lol_service.generate_skill_matrix(skill_max)
    embed.add_field(
        name=f"Skill Order ({skill_max})",
        value=f"```text\n{skill_matrix}\n```",
        inline=False,
    )

    # Imagen de banner con los iconos reales de objetos y habilidades
    embed.set_image(url="attachment://build_card.png")

    footer_icon = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg"
    embed.set_footer(text=f"Powered by Riot DataDragon • Meep LoL Assistant", icon_url=footer_icon)

    return embed


class BuildVariantView(discord.ui.View):
    """
    Vista interactiva con botones de Discord para alternar entre diferentes estilos
    de build (ej: AD vs AP vs Tanque) y actualizar tanto el texto como la imagen de objetos.
    """
    def __init__(
        self,
        champ_id: str,
        champ_name: str,
        mode: str,
        builds: List[Dict[str, Any]],
        details: Dict[str, Any],
        current_index: int = 0,
        author_id: int = None,
    ):
        super().__init__(timeout=180)
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

        # Botones de cambio de estilo (si hay 2 o más estilos)
        if len(self.builds) > 1:
            for idx, build in enumerate(self.builds):
                style_name = build.get("style_name", f"Build {idx + 1}")
                button_label = style_name.split("(")[0].strip() if "(" in style_name else style_name
                is_active = (idx == self.current_index)

                button = discord.ui.Button(
                    label=button_label,
                    style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                    disabled=is_active,
                    custom_id=f"build_btn_{idx}",
                )
                button.callback = self._create_callback(idx)
                self.add_item(button)

        # Botón de enlace directo externo estilo PoroScout ("View on U.GG")
        ugg_url = f"https://u.gg/lol/champions/{self.champ_id.lower()}/build"
        if self.mode.lower() == "aram":
            ugg_url = f"https://u.gg/lol/champions/aram/{self.champ_id.lower()}-aram"
        self.add_item(discord.ui.Button(label="Ver en U.GG", url=ugg_url, style=discord.ButtonStyle.link))

    def _create_callback(self, target_idx: int):
        async def callback(interaction: discord.Interaction):
            self.current_index = target_idx
            self._build_buttons()

            new_build = self.builds[self.current_index]
            new_embed = create_champion_embed(
                champ_id=self.champ_id,
                champ_name=self.champ_name,
                mode=self.mode,
                build=new_build,
                details=self.details,
            )

            # Regenerar la tarjeta gráfica con los ítems del nuevo estilo
            new_card_file = generate_build_card_file(
                version=lol_service.latest_version,
                starter_item_ids=new_build.get("starter_item_ids", ["1056", "2003"]),
                core_item_ids=new_build.get("core_item_ids", ["226653", "226655", "223157"]),
                situational_item_ids=new_build.get("situational_item_ids", ["223089", "3135", "3020"]),
                spell_icons=self.details.get("spells", []),
            )

            if new_card_file:
                await interaction.response.edit_message(embed=new_embed, attachments=[new_card_file], view=self)
            else:
                await interaction.response.edit_message(embed=new_embed, view=self)

        return callback

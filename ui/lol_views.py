"""
Componentes interactivos de Discord para League of Legends (Botones de variantes).
"""

from typing import List, Dict, Any
import discord

import config
from services.lol_service import lol_service


def create_champion_embed(champ_id: str, champ_name: str, mode: str, build: Dict[str, Any]) -> discord.Embed:
    """Genera un Discord Embed estilizado con la build y runas seleccionadas."""
    is_aram = mode.lower() == "aram"
    mode_title = "ARAM" if is_aram else "GRIETA DEL INVOCADOR"
    color = config.COLOR_ARAM if is_aram else config.COLOR_LOL

    embed = discord.Embed(
        title=f"⚔️ {champ_name.upper()} — {mode_title}",
        description=f"**Estilo Seleccionado:** {build.get('style_name', 'Estándar')} *(WR: {build.get('win_rate', '50.0%')})*",
        color=color,
    )

    # Miniatura del campeón
    icon_url = lol_service.get_champion_icon_url(champ_id)
    embed.set_thumbnail(url=icon_url)

    # Campo 1: Runas completas
    primary_runes = " • ".join(build.get("primary_runes", []))
    secondary_runes = " • ".join(build.get("secondary_runes", []))
    shards = " • ".join(build.get("shards", []))

    runes_text = (
        f"**Rama Principal:** `{build.get('primary_tree', 'Precisión')}`\n"
        f"└ Runas: {primary_runes}\n"
        f"**Rama Secundaria:** `{build.get('secondary_tree', 'Inspiración')}`\n"
        f"└ Runas: {secondary_runes}\n"
        f"**Fragmentos:** {shards}"
    )
    embed.add_field(name="📜 Runas Recomendadas", value=runes_text, inline=False)

    # Campo 2: Habilidades y Hechizos
    habilidades_text = (
        f"**Maxeo de Habilidades:** `{build.get('skill_max', 'Q > W > E')}`\n"
        f"**Hechizos de Invocador:** {build.get('summoner_spells', 'Flash + Curación')}"
    )
    embed.add_field(name="⚡ Habilidades y Hechizos", value=habilidades_text, inline=False)

    # Campo 3: Objetos recomendados
    items_text = (
        f"**Inicial:** {build.get('starting_items', 'Espada de Doran')}\n"
        f"**Core (Esenciales):** `{build.get('core_items', 'Objetos Core')}`\n"
        f"**Situacionales:** {build.get('situational_items', 'Objetos Finales')}"
    )
    embed.add_field(name="🛡️ Objetos Recomendados", value=items_text, inline=False)

    # Campo 4: Consejo en partida
    if build.get("tips"):
        embed.add_field(name="💡 Consejo de Juego", value=f"*{build.get('tips')}*", inline=False)

    footer_text = f"Parche {lol_service.latest_version} • Haz clic en los botones para alternar estilos"
    embed.set_footer(text=footer_text, icon_url="https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/29.jpg")

    return embed


class BuildVariantView(discord.ui.View):
    """
    Vista interactiva con botones de Discord para alternar entre diferentes estilos
    de build (ej: AD vs AP vs Tanque) sin generar nuevos mensajes en el chat.
    """
    def __init__(
        self,
        champ_id: str,
        champ_name: str,
        mode: str,
        builds: List[Dict[str, Any]],
        current_index: int = 0,
        author_id: int = None,
    ):
        super().__init__(timeout=180)  # Los botones responden durante 3 minutos
        self.champ_id = champ_id
        self.champ_name = champ_name
        self.mode = mode
        self.builds = builds
        self.current_index = current_index
        self.author_id = author_id

        self._build_buttons()

    def _build_buttons(self):
        """Genera los botones según las variantes disponibles."""
        self.clear_items()

        # Si solo hay una build, no se necesitan botones
        if len(self.builds) <= 1:
            return

        for idx, build in enumerate(self.builds):
            style_name = build.get("style_name", f"Build {idx + 1}")
            # Cortar nombre si es muy largo para el límite del botón de Discord (80 chars)
            button_label = style_name.split("(")[0].strip() if "(" in style_name else style_name
            is_active = (idx == self.current_index)

            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                disabled=is_active,  # Desactivar el botón actualmente visible
                custom_id=f"build_btn_{idx}",
            )
            button.callback = self._create_callback(idx)
            self.add_item(button)

    def _create_callback(self, target_idx: int):
        async def callback(interaction: discord.Interaction):
            self.current_index = target_idx
            self._build_buttons()

            new_build = self.builds[self.current_index]
            new_embed = create_champion_embed(self.champ_id, self.champ_name, self.mode, new_build)

            await interaction.response.edit_message(embed=new_embed, view=self)

        return callback

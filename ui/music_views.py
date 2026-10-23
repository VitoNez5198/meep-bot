"""
Componentes interactivos de Discord para el Sistema de Música de Meep Bot.
Proporciona:
- Embeds estilizados para reproducción actual, colas y estado.
- MusicControlView: Botonera interactiva para Play/Pause, Skip, Shuffle, Cola y Stop.
- QueuePaginationView: Paginación interactiva para navegar por listas de reproducción largas.
"""

import time
import math
import asyncio
import logging
from typing import Optional, List, Tuple
import discord

import config
from services.music_service import GuildMusicPlayer, Track, format_duration

logger = logging.getLogger("meep.ui.music")


def create_now_playing_embed(player: GuildMusicPlayer) -> discord.Embed:
    """Genera un Embed visualmente estético para la canción en reproducción actual."""
    cur = player.current
    if not cur:
        embed = discord.Embed(
            title="🔇 Reproductor Inactivo",
            description="No hay ninguna pista en reproducción en este momento.\nUsa `/play` o `!p` para reproducir música.",
            color=config.COLOR_MEEP,
        )
        return embed

    is_paused = player.is_paused or (player.voice_client and player.voice_client.is_paused())
    title_prefix = "⏸️ En Pausa" if is_paused else "🎶 Sonando Ahora"
    embed_color = 0xF39C12 if is_paused else config.COLOR_MUSIC

    clean_title = cur.title.replace("[", "(").replace("]", ")")
    description = f"**[{clean_title}]({cur.webpage_url})**"
    if getattr(cur, "playlist_name", None):
        description += f"\n*Lista: {cur.playlist_name}*"

    embed = discord.Embed(
        title=f"{title_prefix}: {clean_title[:40]}..." if len(clean_title) > 40 else f"{title_prefix}: {clean_title}",
        description=description,
        color=embed_color,
    )

    # Barra de progreso dinámica
    progress_bar = player.get_progress_bar(length=14)
    embed.add_field(name="Progreso", value=progress_bar, inline=False)

    # Metadatos en 3 columnas inline
    uploader_name = cur.uploader[:25] + "..." if len(cur.uploader) > 25 else cur.uploader
    embed.add_field(name="Canal / Artista", value=uploader_name or "Desconocido", inline=True)
    embed.add_field(name="Duración", value=cur.duration_str, inline=True)
    embed.add_field(name="Pedido por", value=cur.requester or "Desconocido", inline=True)

    if cur.thumbnail:
        embed.set_thumbnail(url=cur.thumbnail)

    # Footer con información de la sesión
    loop_str = f"Bucle: {player.loop_mode.upper()}"
    queue_len = len(player.queue)
    queue_str = f"{queue_len} en espera" if queue_len > 0 else "Cola vacía"
    vol_str = f"Vol: {int(player.volume * 100)}%"
    radio_str = "📻 Radio: ON" if getattr(player, "radio_mode", False) else "📻 Radio: OFF"
    embed.set_footer(text=f"{queue_str} • {loop_str} • {radio_str} • {vol_str} • Meep Melodies")

    return embed


def create_queue_embed(player: GuildMusicPlayer, page: int = 0, page_size: int = 7) -> Tuple[discord.Embed, int]:
    """
    Construye un Embed paginado para la cola de reproducción.
    Retorna (embed, total_pages).
    """
    total_tracks = len(player.queue)
    total_pages = max(1, math.ceil(total_tracks / page_size))
    page = max(0, min(page, total_pages - 1))

    embed = discord.Embed(
        title="📜 Cola de Reproducción de Meep",
        color=config.COLOR_MUSIC,
    )

    # Sección: Canción actual
    if player.current:
        cur_title = player.current.title.replace("[", "(").replace("]", ")")
        if len(cur_title) > 45:
            cur_title = cur_title[:42] + "..."
        cur_desc = f"[{cur_title}]({player.current.webpage_url}) (`{player.current.duration_str}`)"
        if getattr(player.current, "playlist_name", None):
            cur_desc += f"\n*Lista: {player.current.playlist_name}*"
        cur_desc += f" — Pedido por: **{player.current.requester}**"
        embed.add_field(name="🔊 Sonando Ahora", value=cur_desc, inline=False)

    # Sección: Lista paginada de canciones en espera
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_tracks = player.queue[start_idx:end_idx]

    if page_tracks:
        lines = []
        for i, t in enumerate(page_tracks):
            pos = start_idx + i + 1
            clean_title = t.title.replace("[", "(").replace("]", ")")
            if len(clean_title) > 36:
                clean_title = clean_title[:33] + "..."
            line = f"`{pos}.` [{clean_title}]({t.webpage_url}) (`{t.duration_str}`) • *{t.requester}*"
            lines.append(line)

        embed.add_field(name=f"Próximas en Cola (Página {page + 1}/{total_pages})", value="\n".join(lines), inline=False)
    else:
        if not player.current:
            embed.description = "📭 La cola de reproducción está vacía."
        else:
            embed.add_field(name="Próximas en Cola", value="*No hay más pistas en espera.*", inline=False)

    # Resumen de listas completas en cola si existen
    pl_summary = player.get_queued_playlists_summary()
    if pl_summary:
        pl_lines = [f"• **{name}**: {cnt} pistas" for name, cnt in pl_summary[:3]]
        if len(pl_summary) > 3:
            pl_lines.append(f"*... y {len(pl_summary) - 3} listas más.*")
        embed.add_field(name="📚 Listas en Cola", value="\n".join(pl_lines), inline=False)

    # Cálculo de duración total restante
    total_sec = sum(t.duration for t in player.queue if t.duration)
    duration_info = f"Duración en cola: `{format_duration(total_sec)}`" if total_sec > 0 else ""

    embed.set_footer(
        text=f"Página {page + 1}/{total_pages} • Total: {total_tracks} pistas • {duration_info}".strip(" • ")
    )
    return embed, total_pages


def create_status_embed(title: str, description: str, color: int = config.COLOR_MUSIC) -> discord.Embed:
    """Crea un embed compacto para notificaciones de estado o acciones."""
    return discord.Embed(title=title, description=description, color=color)


class MusicControlView(discord.ui.View):
    """
    Panel interactivo con botones de control para el reproductor de audio:
    - [ ⏯️ Pausar / Reanudar ]
    - [ ⏭️ Skip ]
    - [ 🔀 Shuffle ]
    - [ 📜 Ver Cola ]
    - [ ⏹️ Detener ]
    """

    def __init__(self, player: GuildMusicPlayer, timeout: Optional[float] = 300.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.player.controller_view = self
        self.message: Optional[discord.Message] = None
        self._sync_buttons()

    def _sync_buttons(self):
        """Actualiza el texto, icono y estilo del botón Play/Pause según el estado actual."""
        self.clear_items()

        is_paused = self.player.is_paused or (
            self.player.voice_client and self.player.voice_client.is_paused()
        )

        # Botón Play / Pause
        btn_pause = discord.ui.Button(
            label="Reanudar" if is_paused else "Pausar",
            emoji="▶️" if is_paused else "⏸️",
            style=discord.ButtonStyle.success if is_paused else discord.ButtonStyle.secondary,
            custom_id="btn_music_toggle_pause",
            row=0,
        )
        btn_pause.callback = self._on_toggle_pause
        self.add_item(btn_pause)

        # Botón Skip
        btn_skip = discord.ui.Button(
            label="Saltar",
            emoji="⏭️",
            style=discord.ButtonStyle.primary,
            custom_id="btn_music_skip",
            row=0,
        )
        btn_skip.callback = self._on_skip
        self.add_item(btn_skip)

        # Botón Radio (Autoplay de pistas similares sin remixes)
        is_radio = getattr(self.player, "radio_mode", False)
        btn_radio = discord.ui.Button(
            label="Radio: ON" if is_radio else "Radio",
            emoji="📻",
            style=discord.ButtonStyle.success if is_radio else discord.ButtonStyle.secondary,
            custom_id="btn_music_radio",
            row=0,
        )
        btn_radio.callback = self._on_toggle_radio
        self.add_item(btn_radio)

        # Botón Shuffle
        btn_shuffle = discord.ui.Button(
            label="Mezclar",
            emoji="🔀",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_music_shuffle",
            row=0,
        )
        btn_shuffle.callback = self._on_shuffle
        self.add_item(btn_shuffle)

        # Botón Stop
        btn_stop = discord.ui.Button(
            label="Detener",
            emoji="⏹️",
            style=discord.ButtonStyle.danger,
            custom_id="btn_music_stop",
            row=0,
        )
        btn_stop.callback = self._on_stop
        self.add_item(btn_stop)

        # Botón Cola (en Fila 1 para respetar límite de 5 botones por fila)
        btn_queue = discord.ui.Button(
            label="Ver Cola",
            emoji="📜",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_music_queue",
            row=1,
        )
        btn_queue.callback = self._on_show_queue
        self.add_item(btn_queue)

    async def _check_voice(self, interaction: discord.Interaction) -> bool:
        """Verifica que el usuario esté en el mismo canal de voz que el bot."""
        vc = self.player.voice_client
        if not vc or not vc.channel:
            await interaction.response.send_message("❌ Meep no está conectado a ningún canal de voz.", ephemeral=True)
            return False

        user = interaction.user
        if not getattr(user, "voice", None) or not user.voice.channel:
            await interaction.response.send_message("⚠️ Debes estar conectado al canal de voz para usar los controles.", ephemeral=True)
            return False

        if user.voice.channel != vc.channel:
            await interaction.response.send_message(
                f"⚠️ Debes estar en **{vc.channel.name}** para interactuar con los controles.",
                ephemeral=True,
            )
            return False

        return True

    async def _on_toggle_pause(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return

        vc = self.player.voice_client
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            await interaction.response.send_message("❌ No hay ninguna pista activa para pausar o reanudar.", ephemeral=True)
            return

        if vc.is_paused():
            vc.resume()
            self.player.total_paused_duration += time.time() - self.player.pause_start_time
            self.player.is_paused = False
        else:
            vc.pause()
            self.player.pause_start_time = time.time()
            self.player.is_paused = True

        self._sync_buttons()
        embed = create_now_playing_embed(self.player)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_skip(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return

        vc = self.player.voice_client
        if not vc or not self.player.is_playing:
            await interaction.response.send_message("❌ No hay ninguna pista sonando para saltar.", ephemeral=True)
            return

        # Deferir de inmediato para evitar que Discord marque timeout de 3 segundos
        await interaction.response.defer()

        # Guardar referencias activas del mensaje en el player para actualizaciones continuas
        if interaction.message:
            self.player.controller_message = interaction.message
            self.player.controller_view = self

        old_track = self.player.current
        skipped_title = old_track.title if old_track else "Pista actual"

        # Detener la reproducción gatilla el callback after_callback para avanzar de canción
        vc.stop()

        # Esperar a que el reproductor resuelva la siguiente pista (cola o radio)
        for _ in range(45):  # hasta 4.5s en pasos de 100ms
            await asyncio.sleep(0.1)
            # Solo salir si ya no está en proceso de carga y la pista cambió o se vació
            if not getattr(self.player, "is_loading_next", False):
                if self.player.current != old_track:
                    break
                if not self.player.queue and not self.player.is_playing:
                    break

        # Sincronizar botones y generar el nuevo embed con los datos de la nueva canción
        self._sync_buttons()
        embed = create_now_playing_embed(self.player)

        # Actualizar el mensaje actual donde está la botonera
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception:
            if interaction.message:
                try:
                    await interaction.message.edit(embed=embed, view=self)
                except Exception as ex:
                    logger.warning(f"Error actualizando el preview del mensaje tras saltar: {ex}")

        # Mensaje de confirmación efímero discreto para quien presionó el botón
        try:
            if self.player.current:
                clean_next = self.player.current.title.replace("[", "(").replace("]", ")")
                await interaction.followup.send(
                    f"⏭️ Saltaste: **{skipped_title}**\n▶️ Sonando ahora: **{clean_next}**",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"⏭️ Saltaste: **{skipped_title}**\n📭 Fin de la lista de reproducción.",
                    ephemeral=True,
                )
        except Exception:
            pass

    async def _on_shuffle(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return

        if len(self.player.queue) < 2:
            await interaction.response.send_message("❌ Se necesitan al menos 2 canciones en cola para mezclar.", ephemeral=True)
            return

        self.player.shuffle_queue()
        await interaction.response.send_message(
            f"🔀 **{interaction.user.display_name}** mezcló las **{len(self.player.queue)} canciones** en la cola."
        )

    async def _on_toggle_radio(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return

        self.player.radio_mode = not self.player.radio_mode
        self._sync_buttons()
        embed = create_now_playing_embed(self.player)
        await interaction.response.edit_message(embed=embed, view=self)

        status = "activado 📻 (Meep sugerirá canciones de estudio similares sin remixes)" if self.player.radio_mode else "desactivado ⚪"
        await interaction.followup.send(f"📻 Modo Radio **{status}**.", ephemeral=True)

    async def _on_show_queue(self, interaction: discord.Interaction):
        """Abre la cola paginada de forma efímera para no saturar el canal de texto."""
        if not self.player.current and not self.player.queue:
            await interaction.response.send_message("📭 La cola de reproducción está vacía.", ephemeral=True)
            return

        view = QueuePaginationView(self.player)
        embed, _ = create_queue_embed(self.player, page=0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _on_stop(self, interaction: discord.Interaction):
        if not await self._check_voice(interaction):
            return

        # Detener completamente la reproducción, vaciar cola y apagar la radio
        self.player.stop()
        await self.player.music_service.update_presence_for_track(None)

        for child in self.children:
            child.disabled = True

        embed = create_status_embed(
            title="⏹️ Reproducción Finalizada",
            description=f"La música y el Modo Radio fueron detenidos por {interaction.user.mention}. Cola vaciada.",
            color=config.COLOR_ERROR,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Deshabilita los botones cuando la interacción expira para mantener higiene visual."""
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class QueuePaginationView(discord.ui.View):
    """
    Vista interactiva con paginación para explorar la cola de reproducción:
    - [ ⏪ Inicio ]
    - [ ◀️ Anterior ]
    - [ Pág. X / Y ]
    - [ Siguiente ▶️ ]
    - [ Fin ⏩ ]
    """

    def __init__(self, player: GuildMusicPlayer, page_size: int = 7, timeout: Optional[float] = 180.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.page_size = page_size
        self.current_page = 0
        self.total_pages = max(1, math.ceil(len(player.queue) / page_size))
        self.message: Optional[discord.Message] = None
        self._build_pagination_buttons()

    def _build_pagination_buttons(self):
        self.clear_items()
        self.total_pages = max(1, math.ceil(len(self.player.queue) / self.page_size))

        # Botón Primera Página
        btn_first = discord.ui.Button(
            emoji="⏪",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0),
        )
        btn_first.callback = self._on_first_page
        self.add_item(btn_first)

        # Botón Anterior
        btn_prev = discord.ui.Button(
            emoji="◀️",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page == 0),
        )
        btn_prev.callback = self._on_prev_page
        self.add_item(btn_prev)

        # Indicador de Página (Botón pasivo deshabilitado)
        btn_indicator = discord.ui.Button(
            label=f"{self.current_page + 1} / {self.total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        self.add_item(btn_indicator)

        # Botón Siguiente
        btn_next = discord.ui.Button(
            emoji="▶️",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page >= self.total_pages - 1),
        )
        btn_next.callback = self._on_next_page
        self.add_item(btn_next)

        # Botón Última Página
        btn_last = discord.ui.Button(
            emoji="⏩",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.total_pages - 1),
        )
        btn_last.callback = self._on_last_page
        self.add_item(btn_last)

    def get_current_embed(self) -> discord.Embed:
        embed, self.total_pages = create_queue_embed(
            self.player,
            page=self.current_page,
            page_size=self.page_size,
        )
        return embed

    async def _update_view(self, interaction: discord.Interaction):
        self._build_pagination_buttons()
        embed = self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_first_page(self, interaction: discord.Interaction):
        self.current_page = 0
        await self._update_view(interaction)

    async def _on_prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        await self._update_view(interaction)

    async def _on_next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self._update_view(interaction)

    async def _on_last_page(self, interaction: discord.Interaction):
        self.current_page = max(0, self.total_pages - 1)
        await self._update_view(interaction)

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

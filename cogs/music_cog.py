"""
Cog de Música para Meep Bot.
Comandos Slash y de texto para reproducción, colas, artista y control de audio.
"""

from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands

import config
from services.music_service import get_music_service, Track, GuildMusicPlayer, format_duration
from ui.music_views import (
    create_now_playing_embed,
    create_queue_embed,
    MusicControlView,
    QueuePaginationView,
)

async def jump_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[int]]:
    """Autocomplete para mostrar canciones de la cola con su número y título."""
    music_service = get_music_service(interaction.client)
    player = music_service.get_player(interaction.guild_id)
    if not player or not player.queue:
        return []

    choices = []
    current_low = current.lower().strip()

    for idx, track in enumerate(player.queue[:25]):
        pos = idx + 1
        clean_title = track.title.replace("[", "(").replace("]", ")").strip()
        artist = getattr(track, "uploader", "") or ""
        artist = artist.replace("- Topic", "").replace("– Topic", "").strip()
        if artist and artist.lower() not in ("youtube", "spotify", "desconocido", "artista", "unknown") and artist.lower() not in clean_title.lower():
            label = f"#{pos} - {clean_title} ({artist})"
        else:
            label = f"#{pos} - {clean_title}"

        if len(label) > 95:
            label = label[:92] + "..."

        if not current_low or current_low in label.lower() or current_low == str(pos):
            choices.append(app_commands.Choice(name=label, value=pos))

    return choices[:25]


class MusicCog(commands.Cog, name="Música"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_service = get_music_service(bot)

    async def _ensure_voice(self, target) -> Optional[discord.VoiceClient]:
        """Asegura que el bot esté conectado al canal de voz del usuario."""
        is_interaction = isinstance(target, discord.Interaction)
        user = target.user if is_interaction else target.author
        guild = target.guild

        if not user.voice or not user.voice.channel:
            msg = "⚠️ ¡Debes estar conectado a un canal de voz para usar este comando!"
            if is_interaction:
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.reply(msg, mention_author=False)
            return None

        voice_channel = user.voice.channel
        voice_client = guild.voice_client

        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        player = self.music_service.get_player(guild.id)
        player.voice_client = voice_client
        player.cancel_disconnect_timer()
        return voice_client

    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================

    @app_commands.command(name="play", description="Reproduce una canción o playlist (YouTube, YouTube Music o Spotify).")
    @app_commands.describe(busqueda="Nombre de la canción o enlace directo de YouTube/Spotify")
    async def slash_play(self, interaction: discord.Interaction, busqueda: str):
        voice_client = await self._ensure_voice(interaction)
        if not voice_client:
            return

        await interaction.response.defer()
        tracks = await self.music_service.resolve_query(busqueda, requester=interaction.user.display_name)
        if not tracks:
            await interaction.followup.send(f"❌ No se encontró ninguna canción para: **'{busqueda}'**.")
            return

        player = self.music_service.get_player(interaction.guild_id)
        first_track = tracks[0]
        is_playlist = len(tracks) > 1

        if not player.is_playing and not (player.voice_client and player.voice_client.is_paused()):
            player.add_tracks(tracks)
            await player.play_next()

            if is_playlist:
                total_duration = sum(t.duration for t in tracks if t.duration)
                embed = discord.Embed(
                    title="📋 Playlist Añadida y Reproduciendo",
                    description=f"Sonando ahora: **[{first_track.title}]({first_track.webpage_url})**",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="🎶 Pistas Añadidas", value=f"**{len(tracks)} canciones**", inline=True)
                if total_duration > 0:
                    embed.add_field(name="⏱️ Duración Total", value=f"`{format_duration(total_duration)}`", inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                embed.set_footer(text=f"Las siguientes {len(tracks) - 1} canciones están en cola. Usa /queue para verlas.")
                view = MusicControlView(player)
                msg = await interaction.followup.send(embed=embed, view=view)
                view.message = msg
                player.controller_message = msg
                player.controller_view = view
            else:
                embed = create_now_playing_embed(player)
                view = MusicControlView(player)
                msg = await interaction.followup.send(embed=embed, view=view)
                view.message = msg
                player.controller_message = msg
                player.controller_view = view
        else:
            prev_queue_len = len(player.queue)
            player.add_tracks(tracks)
            pos = prev_queue_len + 1

            if is_playlist:
                total_duration = sum(t.duration for t in tracks if t.duration)
                embed = discord.Embed(
                    title="✅ Playlist Añadida a la Cola",
                    description=f"Se agregaron **{len(tracks)} canciones** a la lista de espera.",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="📍 Inicia en Posición", value=f"#{pos}", inline=True)
                if total_duration > 0:
                    embed.add_field(name="⏱️ Duración Total", value=f"`{format_duration(total_duration)}`", inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="✅ Añadido a la Cola",
                    description=f"[{first_track.title}]({first_track.webpage_url})",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="📍 Posición", value=f"#{len(player.queue)}", inline=True)
                embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                await interaction.followup.send(embed=embed)


    @app_commands.command(name="artist", description="Encola automáticamente el Top 10-15 mejores canciones de un artista.")
    @app_commands.describe(artista="Nombre del artista o banda (ej: Bad Bunny, Dua Lipa, Linkin Park)")
    async def slash_artist(self, interaction: discord.Interaction, artista: str):
        voice_client = await self._ensure_voice(interaction)
        if not voice_client:
            return

        await interaction.response.defer()
        tracks = await self.music_service.resolve_artist_top_tracks(artista, requester=interaction.user.display_name)
        if not tracks:
            await interaction.followup.send(f"❌ No se encontraron canciones populares para el artista **'{artista}'**.")
            return

        player = self.music_service.get_player(interaction.guild_id)
        player.add_tracks(tracks)

        embed = discord.Embed(
            title=f"🌟 Top Tracks de {artista.title()}",
            description=f"Se agregaron **{len(tracks)} canciones** populares a la cola de reproducción.",
            color=config.COLOR_MUSIC,
        )
        preview_list = "\n".join([f"`{i+1}.` {t.title[:45]}..." if len(t.title) > 45 else f"`{i+1}.` {t.title}" for i, t in enumerate(tracks[:6])])
        if len(tracks) > 6:
            preview_list += f"\n*... y {len(tracks) - 6} canciones más.*"

        embed.add_field(name="🎶 Próximas Pistas", value=preview_list, inline=False)
        embed.set_footer(text="Usa /shuffle si deseas mezclar el orden de las canciones.")

        if not player.is_playing and not player.voice_client.is_paused():
            await player.play_next()

        view = MusicControlView(player)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg

    def _build_queue_embed(self, player: GuildMusicPlayer) -> discord.Embed:
        """Construye un embed seguro de cola de reproducción respetando límites de Discord."""
        embed, _ = create_queue_embed(player, page=0)
        return embed

    @app_commands.command(name="skip", description="Salta la canción actual e indica cuál sigue.")
    async def slash_skip(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.voice_client or not player.is_playing:
            await interaction.response.send_message("❌ No hay ninguna canción reproduciéndose actualmente.", ephemeral=True)
            return

        current_title = player.current.title if player.current else "Canción"
        next_track = player.queue[0] if player.queue else None

        player.voice_client.stop()

        if next_track:
            next_info = f"**[{next_track.title}]({next_track.webpage_url})**"
            if getattr(next_track, "playlist_name", None):
                next_info += f" *(de {next_track.playlist_name})*"
            await interaction.response.send_message(f"⏭️ Se saltó: **{current_title}**\n▶️ A continuación: {next_info}")
        else:
            await interaction.response.send_message(f"⏭️ Se saltó: **{current_title}**\n📭 Fin de la cola de reproducción.")

    @app_commands.command(name="skipplaylist", description="Salta todas las canciones de la lista actual y pasa a la siguiente lista.")
    async def slash_skip_playlist(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.voice_client or not player.is_playing:
            await interaction.response.send_message("❌ No hay ninguna canción reproduciéndose actualmente.", ephemeral=True)
            return

        pl_name, discarded, next_track = player.skip_playlist()
        player.voice_client.stop()

        msg = f"⏭️ Se saltó la lista: **{pl_name}** ({discarded} canciones descartadas de la cola)."
        if next_track:
            next_info = f"**[{next_track.title}]({next_track.webpage_url})**"
            if getattr(next_track, "playlist_name", None):
                next_info += f" *(de {next_track.playlist_name})*"
            msg += f"\n▶️ A continuación: {next_info}"
        else:
            msg += "\n📭 Fin de la cola de reproducción."

        await interaction.response.send_message(msg)

    @app_commands.command(name="jump", description="Salta directamente al número de canción indicado en la cola.")
    @app_commands.describe(posicion="Número de la canción en la lista (usa /queue o autocomplete para ver las posiciones)")
    @app_commands.autocomplete(posicion=jump_autocomplete)
    async def slash_jump(self, interaction: discord.Interaction, posicion: int):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.queue:
            await interaction.response.send_message("❌ La cola de reproducción está vacía.", ephemeral=True)
            return

        total_tracks = len(player.queue)
        if posicion < 1 or posicion > total_tracks:
            await interaction.response.send_message(
                f"❌ No existe ninguna pista en la posición **#{posicion}**.\n"
                f"La cola actual tiene **{total_tracks} canciones** (posiciones válidas: del `1` al `{total_tracks}`).\n"
                f"Usa `/queue` para ver los números disponibles.",
                ephemeral=True,
            )
            return

        success, target_track, discarded = player.jump_to_track(posicion)
        if not success or not target_track:
            await interaction.response.send_message("❌ No se pudo saltar a la pista indicada.", ephemeral=True)
            return

        clean_title = target_track.title.replace("[", "(").replace("]", ")").strip()
        artist = getattr(target_track, "uploader", "") or ""
        artist = artist.replace("- Topic", "").replace("– Topic", "").strip()

        artist_suffix = ""
        if artist and artist.lower() not in ("youtube", "spotify", "desconocido", "artista", "unknown"):
            if artist.lower() not in clean_title.lower():
                artist_suffix = f" • *{artist}*"

        msg = f"⏭️ Saltando directamente a la posición **#{posicion}**: **{clean_title}**{artist_suffix}"
        await interaction.response.send_message(msg, suppress_embeds=True)

    @app_commands.command(name="find", description="Busca canciones en la cola por nombre o artista y muestra su número de posición.")
    @app_commands.describe(texto="Palabra o frase a buscar dentro de la cola de reproducción")
    async def slash_find(self, interaction: discord.Interaction, texto: str):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.queue:
            await interaction.response.send_message("📭 La cola de reproducción está vacía.", ephemeral=True)
            return

        results = player.find_in_queue(texto)
        if not results:
            await interaction.response.send_message(
                f"🔍 No se encontraron canciones en la cola que contengan: **'{texto}'**.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🔍 Resultados en Cola para: '{texto}'",
            color=config.COLOR_MUSIC,
        )
        lines = []
        for pos, track in results[:10]:
            clean_title = track.title.replace("[", "(").replace("]", ")")
            if len(clean_title) > 40:
                clean_title = clean_title[:37] + "..."
            lines.append(f"`#{pos}` [{clean_title}]({track.webpage_url}) (`{track.duration_str}`) • *{track.requester}*")

        if len(results) > 10:
            lines.append(f"\n*... y {len(results) - 10} coincidencias más.*")

        embed.description = "\n".join(lines)
        embed.set_footer(text="Usa /jump <número> o !jump <número> para reproducir cualquiera de ellas.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pause", description="Pausa la reproducción de música.")
    async def slash_pause(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            player.is_paused = True
            await interaction.response.send_message("⏸️ Música pausada. Usa `/resume` para continuar.")
        else:
            await interaction.response.send_message("❌ No hay audio sonando para pausar.", ephemeral=True)

    @app_commands.command(name="resume", description="Reanuda la música pausada.")
    async def slash_resume(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            player.is_paused = False
            await interaction.response.send_message("▶️ Música reanudada.")
        else:
            await interaction.response.send_message("❌ La música no está pausada.", ephemeral=True)

    @app_commands.command(name="queue", description="Muestra la lista de canciones en espera con paginación interactiva.")
    async def slash_queue(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.current and not player.queue:
            await interaction.response.send_message("📭 La cola de reproducción está vacía.")
            return

        view = QueuePaginationView(player)
        embed = view.get_current_embed()
        if view.total_pages > 1:
            await interaction.response.send_message(embed=embed, view=view)
            try:
                view.message = await interaction.original_response()
            except Exception:
                pass
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Muestra la canción actual con barra de progreso y botonera de control.")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.current:
            await interaction.response.send_message("🔇 No hay ninguna canción reproduciéndose.", ephemeral=True)
            return

        embed = create_now_playing_embed(player)
        view = MusicControlView(player)
        await interaction.response.send_message(embed=embed, view=view)
        try:
            msg = await interaction.original_response()
            view.message = msg
            player.controller_message = msg
            player.controller_view = view
        except Exception:
            pass

    @app_commands.command(name="radio", description="Activa el Modo Radio (Autoplay continuo de temas similares sin remixes).")
    @app_commands.describe(artista_o_tema="Opcional: Inicia la radio con un artista o tema específico (ej: Bad Bunny, Dua Lipa)")
    async def slash_radio(self, interaction: discord.Interaction, artista_o_tema: Optional[str] = None):
        player = self.music_service.get_player(interaction.guild_id)

        if artista_o_tema:
            voice_client = await self._ensure_voice(interaction)
            if not voice_client:
                return

            await interaction.response.defer()
            dummy_base = Track(
                title=artista_o_tema,
                webpage_url="",
                uploader=artista_o_tema,
                requester=interaction.user.display_name,
            )
            first_track = await self.music_service.get_radio_recommendation(
                dummy_base,
                player.played_history,
                requester=f"📻 Radio ({interaction.user.display_name})",
            )
            if not first_track:
                await interaction.followup.send(f"❌ No se pudieron encontrar canciones de estudio limpias para **'{artista_o_tema}'**.")
                return

            player.radio_mode = True
            player.clear_queue()
            if player.voice_client and (player.voice_client.is_playing() or player.voice_client.is_paused()):
                player.voice_client.stop()

            player.add_track(first_track)
            await player.play_next()

            embed = create_now_playing_embed(player)
            embed.title = f"📻 Radio Iniciada: {artista_o_tema.title()}"
            view = MusicControlView(player)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg
        else:
            player.radio_mode = not player.radio_mode
            status_text = "ACTIVADO 📻" if player.radio_mode else "DESACTIVADO ⚪"
            desc = (
                "Meep seleccionará automáticamente canciones de estudio similares del mismo artista "
                "cuando la cola se quede vacía (sin remixes de 1 hora ni enganchados)."
                if player.radio_mode
                else "La música se detendrá normalmente al finalizar la lista de reproducción."
            )
            color = config.COLOR_SUCCESS if player.radio_mode else config.COLOR_MUSIC
            embed = discord.Embed(
                title=f"Modo Radio: {status_text}",
                description=desc,
                color=color,
            )
            embed.set_footer(text="También puedes activarlo o desactivarlo usando el botón 📻 de la botonera.")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Mezcla aleatoriamente las canciones en la cola.")
    async def slash_shuffle(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.queue:
            await interaction.response.send_message("❌ La cola no tiene suficientes canciones para mezclar.", ephemeral=True)
            return

        player.shuffle_queue()
        await interaction.response.send_message(f"🔀 Se mezclaron **{len(player.queue)} canciones** en la cola.")

    @app_commands.command(name="stop", description="Detiene la música, vacía la cola y apaga la radio.")
    async def slash_stop(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        player.stop()
        await self.music_service.update_presence_for_track(None)
        await interaction.response.send_message("⏹️ Música y Modo Radio detenidos. Cola vaciada. (Meep permanece en el canal)")

    @app_commands.command(name="disconnect", description="Detiene la música, limpia la cola y desconecta a Meep del canal.")
    async def slash_disconnect(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if player.voice_client:
            player.stop()
            await player.voice_client.disconnect()
            player.voice_client = None
            await self.music_service.update_presence_for_track(None)
            await interaction.response.send_message("👋 Meep se ha desconectado del canal de voz.")
        else:
            await interaction.response.send_message("❌ El bot no está conectado a ningún canal de voz.", ephemeral=True)



    # =========================================================================
    # PREFIX COMMANDS (Comandos cortos de texto)
    # =========================================================================

    @commands.command(name="play", aliases=["p"])
    async def prefix_play(self, ctx: commands.Context, *, busqueda: str):
        """Uso: !p <cancion o link>"""
        voice_client = await self._ensure_voice(ctx)
        if not voice_client:
            return

        msg_wait = await ctx.reply("🔍 Buscando canción...", mention_author=False)
        tracks = await self.music_service.resolve_query(busqueda, requester=ctx.author.display_name)
        if not tracks:
            await msg_wait.edit(content=f"❌ No se encontró ninguna canción para: **'{busqueda}'**.")
            return

        player = self.music_service.get_player(ctx.guild.id)
        first_track = tracks[0]
        is_playlist = len(tracks) > 1

        if not player.is_playing and not (player.voice_client and player.voice_client.is_paused()):
            player.add_tracks(tracks)
            await player.play_next()

            if is_playlist:
                total_duration = sum(t.duration for t in tracks if t.duration)
                embed = discord.Embed(
                    title="📋 Playlist Añadida y Reproduciendo",
                    description=f"Sonando ahora: **[{first_track.title}]({first_track.webpage_url})**",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="🎶 Pistas Añadidas", value=f"**{len(tracks)} canciones**", inline=True)
                if total_duration > 0:
                    embed.add_field(name="⏱️ Duración Total", value=f"`{format_duration(total_duration)}`", inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                embed.set_footer(text=f"Las siguientes {len(tracks) - 1} canciones están en cola. Usa !q para verlas.")
                view = MusicControlView(player)
                msg = await msg_wait.edit(content=None, embed=embed, view=view)
                view.message = msg
                player.controller_message = msg
                player.controller_view = view
            else:
                embed = create_now_playing_embed(player)
                view = MusicControlView(player)
                msg = await msg_wait.edit(content=None, embed=embed, view=view)
                view.message = msg
                player.controller_message = msg
                player.controller_view = view
        else:
            prev_queue_len = len(player.queue)
            player.add_tracks(tracks)
            pos = prev_queue_len + 1

            if is_playlist:
                total_duration = sum(t.duration for t in tracks if t.duration)
                embed = discord.Embed(
                    title="✅ Playlist Añadida a la Cola",
                    description=f"Se agregaron **{len(tracks)} canciones** a la lista de espera.",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="📍 Inicia en Posición", value=f"#{pos}", inline=True)
                if total_duration > 0:
                    embed.add_field(name="⏱️ Duración Total", value=f"`{format_duration(total_duration)}`", inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                await msg_wait.edit(content=None, embed=embed)
            else:
                embed = discord.Embed(
                    title="✅ Añadido a la Cola",
                    description=f"[{first_track.title}]({first_track.webpage_url})",
                    color=config.COLOR_MUSIC,
                )
                embed.add_field(name="📍 Posición", value=f"#{len(player.queue)}", inline=True)
                embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
                embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
                if first_track.thumbnail:
                    embed.set_thumbnail(url=first_track.thumbnail)
                await msg_wait.edit(content=None, embed=embed)


    @commands.command(name="artist")
    async def prefix_artist(self, ctx: commands.Context, *, artista: str):
        """Uso: !artist <nombre del artista>"""
        voice_client = await self._ensure_voice(ctx)
        if not voice_client:
            return

        msg_wait = await ctx.reply(f"🔍 Buscando los grandes éxitos de **{artista}**...", mention_author=False)
        tracks = await self.music_service.resolve_artist_top_tracks(artista, requester=ctx.author.display_name)
        if not tracks:
            await msg_wait.edit(content=f"❌ No se encontraron canciones populares para **'{artista}'**.")
            return

        player = self.music_service.get_player(ctx.guild.id)
        player.add_tracks(tracks)

        embed = discord.Embed(
            title=f"🌟 Top Tracks de {artista.title()}",
            description=f"Se agregaron **{len(tracks)} canciones** populares a la cola de reproducción.",
            color=config.COLOR_MUSIC,
        )
        preview_list = "\n".join([f"`{i+1}.` {t.title[:45]}..." if len(t.title) > 45 else f"`{i+1}.` {t.title}" for i, t in enumerate(tracks[:6])])
        if len(tracks) > 6:
            preview_list += f"\n*... y {len(tracks) - 6} canciones más.*"

        embed.add_field(name="🎶 Próximas Pistas", value=preview_list, inline=False)
        embed.set_footer(text=f"Usa {config.BOT_PREFIX}sh para mezclar el orden.")

        if not player.is_playing and not player.voice_client.is_paused():
            await player.play_next()

        view = MusicControlView(player)
        msg = await msg_wait.edit(content=None, embed=embed, view=view)
        view.message = msg

    @commands.command(name="skip", aliases=["s", "next"])
    async def prefix_skip(self, ctx: commands.Context):
        """Uso: !s"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.voice_client or not player.is_playing:
            await ctx.reply("❌ No hay ninguna canción sonando.", mention_author=False)
            return

        current_title = player.current.title if player.current else "Canción"
        next_track = player.queue[0] if player.queue else None

        player.voice_client.stop()

        if next_track:
            next_info = f"**[{next_track.title}]({next_track.webpage_url})**"
            if getattr(next_track, "playlist_name", None):
                next_info += f" *(de {next_track.playlist_name})*"
            await ctx.reply(f"⏭️ Se saltó: **{current_title}**\n▶️ A continuación: {next_info}", mention_author=False)
        else:
            await ctx.reply(f"⏭️ Se saltó: **{current_title}**\n📭 Fin de la cola de reproducción.", mention_author=False)

    @commands.command(name="skipplaylist", aliases=["sp", "nextplaylist"])
    async def prefix_skip_playlist(self, ctx: commands.Context):
        """Uso: !sp o !skipplaylist"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.voice_client or not player.is_playing:
            await ctx.reply("❌ No hay ninguna canción sonando.", mention_author=False)
            return

        pl_name, discarded, next_track = player.skip_playlist()
        player.voice_client.stop()

        msg = f"⏭️ Se saltó la lista: **{pl_name}** ({discarded} canciones descartadas de la cola)."
        if next_track:
            next_info = f"**[{next_track.title}]({next_track.webpage_url})**"
            if getattr(next_track, "playlist_name", None):
                next_info += f" *(de {next_track.playlist_name})*"
            msg += f"\n▶️ A continuación: {next_info}"
        else:
            msg += "\n📭 Fin de la cola de reproducción."

        await ctx.reply(msg, mention_author=False)

    @commands.command(name="jump", aliases=["skipto", "goto"])
    async def prefix_jump(self, ctx: commands.Context, posicion: int):
        """Salta a una canción de la cola por su número. Uso: !jump <número>"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.queue:
            await ctx.reply("❌ La cola de reproducción está vacía.", mention_author=False)
            return

        total_tracks = len(player.queue)
        if posicion < 1 or posicion > total_tracks:
            await ctx.reply(
                f"❌ No existe ninguna pista en la posición **#{posicion}**.\n"
                f"La cola actual tiene **{total_tracks} canciones** (posiciones válidas: del `1` al `{total_tracks}`).\n"
                f"Usa `{config.BOT_PREFIX}queue` para ver los números disponibles.",
                mention_author=False,
            )
            return

        success, target_track, discarded = player.jump_to_track(posicion)
        if not success or not target_track:
            await ctx.reply("❌ No se pudo saltar a la pista indicada.", mention_author=False)
            return

        clean_title = target_track.title.replace("[", "(").replace("]", ")").strip()
        artist = getattr(target_track, "uploader", "") or ""
        artist = artist.replace("- Topic", "").replace("– Topic", "").strip()

        artist_suffix = ""
        if artist and artist.lower() not in ("youtube", "spotify", "desconocido", "artista", "unknown"):
            if artist.lower() not in clean_title.lower():
                artist_suffix = f" • *{artist}*"

        msg = f"⏭️ Saltando directamente a la posición **#{posicion}**: **{clean_title}**{artist_suffix}"
        await ctx.reply(msg, mention_author=False, suppress_embeds=True)

    @commands.command(name="find", aliases=["buscar", "searchqueue"])
    async def prefix_find(self, ctx: commands.Context, *, texto: str):
        """Busca canciones en la cola por nombre y muestra su número. Uso: !find <texto>"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.queue:
            await ctx.reply("📭 La cola de reproducción está vacía.", mention_author=False)
            return

        results = player.find_in_queue(texto)
        if not results:
            await ctx.reply(f"🔍 No se encontraron canciones en la cola que contengan: **'{texto}'**.", mention_author=False)
            return

        embed = discord.Embed(
            title=f"🔍 Resultados en Cola para: '{texto}'",
            color=config.COLOR_MUSIC,
        )
        lines = []
        for pos, track in results[:10]:
            clean_title = track.title.replace("[", "(").replace("]", ")")
            if len(clean_title) > 40:
                clean_title = clean_title[:37] + "..."
            lines.append(f"`#{pos}` [{clean_title}]({track.webpage_url}) (`{track.duration_str}`) • *{track.requester}*")

        if len(results) > 10:
            lines.append(f"\n*... y {len(results) - 10} coincidencias más.*")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Usa {config.BOT_PREFIX}jump <número> para reproducir cualquiera de ellas.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="pause")
    async def prefix_pause(self, ctx: commands.Context):
        """Uso: !pause"""
        player = self.music_service.get_player(ctx.guild.id)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            player.is_paused = True
            await ctx.reply("⏸️ Pausado.", mention_author=False)

    @commands.command(name="resume", aliases=["res", "unpause"])
    async def prefix_resume(self, ctx: commands.Context):
        """Uso: !res"""
        player = self.music_service.get_player(ctx.guild.id)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            player.is_paused = False
            await ctx.reply("▶️ Reanudado.", mention_author=False)

    @commands.command(name="queue", aliases=["q"])
    async def prefix_queue(self, ctx: commands.Context):
        """Uso: !q"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.current and not player.queue:
            await ctx.reply("📭 La cola está vacía.", mention_author=False)
            return

        view = QueuePaginationView(player)
        embed = view.get_current_embed()
        if view.total_pages > 1:
            msg = await ctx.reply(embed=embed, view=view, mention_author=False)
            view.message = msg
        else:
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="nowplaying", aliases=["np"])
    async def prefix_nowplaying(self, ctx: commands.Context):
        """Uso: !np"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.current:
            await ctx.reply("🔇 No hay ninguna canción reproduciéndose.", mention_author=False)
            return

        embed = create_now_playing_embed(player)
        view = MusicControlView(player)
        msg = await ctx.reply(embed=embed, view=view, mention_author=False)
        view.message = msg
        player.controller_message = msg
        player.controller_view = view

    @commands.command(name="radio", aliases=["rad", "autoplay"])
    async def prefix_radio(self, ctx: commands.Context, *, artista_o_tema: Optional[str] = None):
        """Activa o alterna el Modo Radio. Uso: !radio o !radio Bad Bunny"""
        player = self.music_service.get_player(ctx.guild.id)

        if artista_o_tema:
            voice_client = await self._ensure_voice(ctx)
            if not voice_client:
                return

            msg_wait = await ctx.reply(f"📻 Sintonizando Radio para **{artista_o_tema}**...", mention_author=False)
            dummy_base = Track(
                title=artista_o_tema,
                webpage_url="",
                uploader=artista_o_tema,
                requester=ctx.author.display_name,
            )
            first_track = await self.music_service.get_radio_recommendation(
                dummy_base,
                player.played_history,
                requester=f"📻 Radio ({ctx.author.display_name})",
            )
            if not first_track:
                await msg_wait.edit(content=f"❌ No se pudieron encontrar canciones de estudio limpias para **'{artista_o_tema}'**.")
                return

            player.radio_mode = True
            player.clear_queue()
            if player.voice_client and (player.voice_client.is_playing() or player.voice_client.is_paused()):
                player.voice_client.stop()

            player.add_track(first_track)
            await player.play_next()

            embed = create_now_playing_embed(player)
            embed.title = f"📻 Radio Iniciada: {artista_o_tema.title()}"
            view = MusicControlView(player)
            sent = await msg_wait.edit(content=None, embed=embed, view=view)
            view.message = sent
        else:
            player.radio_mode = not player.radio_mode
            status_text = "ACTIVADO 📻" if player.radio_mode else "DESACTIVADO ⚪"
            desc = (
                "Meep continuará reproduciendo automáticamente canciones de estudio similares "
                "cuando termine la cola."
                if player.radio_mode
                else "La música se detendrá al finalizar la cola."
            )
            await ctx.reply(f"📻 **Modo Radio:** {status_text}\n*{desc}*", mention_author=False)

    @commands.command(name="shuffle", aliases=["sh"])
    async def prefix_shuffle(self, ctx: commands.Context):
        """Uso: !sh"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.queue:
            await ctx.reply("❌ No hay canciones suficientes en la cola para mezclar.", mention_author=False)
            return

        player.shuffle_queue()
        await ctx.reply(f"🔀 Se mezclaron **{len(player.queue)} canciones** en la cola.", mention_author=False)

    @commands.command(name="stop")
    async def prefix_stop(self, ctx: commands.Context):
        """Detiene la música y apaga la radio sin desconectar. Uso: !stop"""
        player = self.music_service.get_player(ctx.guild.id)
        player.stop()
        await self.music_service.update_presence_for_track(None)
        await ctx.reply("⏹️ Música y Modo Radio detenidos. Cola vaciada. (Meep sigue en el canal)", mention_author=False)

    @commands.command(name="disconnect", aliases=["leave", "dc"])
    async def prefix_disconnect(self, ctx: commands.Context):
        """Detiene la música, limpia la cola y desconecta al bot. Uso: !dc o !leave"""
        player = self.music_service.get_player(ctx.guild.id)
        if player.voice_client:
            player.stop()
            await player.voice_client.disconnect()
            player.voice_client = None
            await self.music_service.update_presence_for_track(None)
            await ctx.reply("👋 Meep se ha desconectado del canal de voz.", mention_author=False)
        else:
            await ctx.reply("❌ No estoy conectado a ningún canal de voz.", mention_author=False)



    @commands.command(name="volume", aliases=["vol"])
    async def prefix_volume(self, ctx: commands.Context, volumen: int):
        """Uso: !vol <1-100>"""
        if volumen < 1 or volumen > 100:
            await ctx.reply("❌ El volumen debe estar entre 1 y 100.", mention_author=False)
            return

        player = self.music_service.get_player(ctx.guild.id)
        player.volume = volumen / 100.0
        if player.voice_client and player.voice_client.source:
            player.voice_client.source.volume = player.volume

        await ctx.reply(f"🔊 Volumen ajustado al **{volumen}%**.", mention_author=False)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Maneja desconexiones del bot y desconexión automática cuando queda solo."""
        guild = member.guild
        player = self.music_service.get_player(guild.id)

        # 1. Si el bot fue desconectado manualmente del canal
        if self.bot.user and member.id == self.bot.user.id:
            if before.channel is not None and after.channel is None:
                player.cancel_disconnect_timer()
                player.stop()
                player.voice_client = None
                await self.music_service.update_presence_for_track(None)
            return

        # 2. Monitorear si el canal donde está el bot se quedó sin personas
        voice_client = guild.voice_client
        if voice_client and voice_client.channel:
            bot_channel = voice_client.channel
            # Si el evento ocurrió en el canal donde está el bot
            if before.channel == bot_channel or after.channel == bot_channel:
                humans = [m for m in bot_channel.members if not m.bot]
                if len(humans) == 0:
                    player.start_disconnect_timer(delay=120)
                else:
                    player.cancel_disconnect_timer()


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))

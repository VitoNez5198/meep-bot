"""
Cog de Música para Meep Bot.
Comandos Slash y de texto para reproducción, colas, artista y control de audio.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

import config
from services.music_service import get_music_service, Track, GuildMusicPlayer


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
        return voice_client

    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================

    @app_commands.command(name="play", description="Reproduce una canción o playlist (YouTube o Spotify).")
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

        if not player.is_playing and not player.voice_client.is_paused():
            player.add_tracks(tracks)
            await player.play_next()
            embed = discord.Embed(
                title="🎵 Reproduciendo Ahora",
                description=f"[{first_track.title}]({first_track.webpage_url})",
                color=config.COLOR_MUSIC,
            )
            embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
            embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
            if first_track.thumbnail:
                embed.set_thumbnail(url=first_track.thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            player.add_tracks(tracks)
            pos = len(player.queue)
            embed = discord.Embed(
                title="✅ Añadido a la Cola",
                description=f"[{first_track.title}]({first_track.webpage_url})",
                color=config.COLOR_MUSIC,
            )
            embed.add_field(name="📍 Posición", value=f"#{pos}", inline=True)
            embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
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

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Salta la canción actual.")
    async def slash_skip(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.voice_client or not player.is_playing:
            await interaction.response.send_message("❌ No hay ninguna canción reproduciéndose actualmente.", ephemeral=True)
            return

        current_title = player.current.title if player.current else "Canción"
        player.voice_client.stop()
        await interaction.response.send_message(f"⏭️ Se saltó: **{current_title}**")

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

    @app_commands.command(name="queue", description="Muestra la lista de canciones en espera.")
    async def slash_queue(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.current and not player.queue:
            await interaction.response.send_message("📭 La cola de reproducción está vacía.")
            return

        embed = discord.Embed(title="📜 Cola de Reproducción de Meep", color=config.COLOR_MUSIC)
        if player.current:
            embed.add_field(
                name="🔊 Sonando Ahora",
                value=f"[{player.current.title}]({player.current.webpage_url}) (`{player.current.duration_str}`)",
                inline=False,
            )

        if player.queue:
            q_list = "\n".join([f"`{i+1}.` [{t.title[:45]}]({t.webpage_url}) (`{t.duration_str}`)" for i, t in enumerate(player.queue[:10])])
            if len(player.queue) > 10:
                q_list += f"\n*... y {len(player.queue) - 10} canciones más.*"
            embed.add_field(name="Próximas en Cola", value=q_list, inline=False)
            embed.set_footer(text=f"Total de pistas en espera: {len(player.queue)} | Bucle: {player.loop_mode.upper()}")
        else:
            embed.add_field(name="Próximas en Cola", value="*No hay más pistas en espera.*", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Muestra la canción actual con barra de progreso.")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.current:
            await interaction.response.send_message("🔇 No hay ninguna canción reproduciéndose.", ephemeral=True)
            return

        cur = player.current
        embed = discord.Embed(
            title="🎶 Sonando Ahora",
            description=f"**[{cur.title}]({cur.webpage_url})**",
            color=config.COLOR_MUSIC,
        )
        embed.add_field(name="Progreso", value=player.get_progress_bar(), inline=False)
        embed.add_field(name="Canal / Subido por", value=cur.uploader, inline=True)
        embed.add_field(name="Pedido por", value=cur.requester, inline=True)
        if cur.thumbnail:
            embed.set_thumbnail(url=cur.thumbnail)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Mezcla aleatoriamente las canciones en la cola.")
    async def slash_shuffle(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        if not player.queue:
            await interaction.response.send_message("❌ La cola no tiene suficientes canciones para mezclar.", ephemeral=True)
            return

        player.shuffle_queue()
        await interaction.response.send_message(f"🔀 Se mezclaron **{len(player.queue)} canciones** en la cola.")

    @app_commands.command(name="disconnect", description="Detiene la música y desconecta al bot.")
    async def slash_disconnect(self, interaction: discord.Interaction):
        player = self.music_service.get_player(interaction.guild_id)
        player.clear_queue()
        if player.voice_client:
            await player.voice_client.disconnect()
            player.voice_client = None
            player.current = None
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

        if not player.is_playing and not player.voice_client.is_paused():
            player.add_tracks(tracks)
            await player.play_next()
            embed = discord.Embed(
                title="🎵 Reproduciendo Ahora",
                description=f"[{first_track.title}]({first_track.webpage_url})",
                color=config.COLOR_MUSIC,
            )
            embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
            embed.add_field(name="👤 Pedido por", value=first_track.requester, inline=True)
            if first_track.thumbnail:
                embed.set_thumbnail(url=first_track.thumbnail)
            await msg_wait.edit(content=None, embed=embed)
        else:
            player.add_tracks(tracks)
            pos = len(player.queue)
            embed = discord.Embed(
                title="✅ Añadido a la Cola",
                description=f"[{first_track.title}]({first_track.webpage_url})",
                color=config.COLOR_MUSIC,
            )
            embed.add_field(name="📍 Posición", value=f"#{pos}", inline=True)
            embed.add_field(name="⏱️ Duración", value=first_track.duration_str, inline=True)
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

        await msg_wait.edit(content=None, embed=embed)

    @commands.command(name="skip", aliases=["s", "next"])
    async def prefix_skip(self, ctx: commands.Context):
        """Uso: !s"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.voice_client or not player.is_playing:
            await ctx.reply("❌ No hay ninguna canción sonando.", mention_author=False)
            return

        player.voice_client.stop()
        await ctx.reply("⏭️ Pista saltada.", mention_author=False)

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

        embed = discord.Embed(title="📜 Cola de Reproducción", color=config.COLOR_MUSIC)
        if player.current:
            embed.add_field(
                name="🔊 Sonando Ahora",
                value=f"[{player.current.title}]({player.current.webpage_url}) (`{player.current.duration_str}`)",
                inline=False,
            )

        if player.queue:
            q_list = "\n".join([f"`{i+1}.` [{t.title[:45]}]({t.webpage_url}) (`{t.duration_str}`)" for i, t in enumerate(player.queue[:10])])
            if len(player.queue) > 10:
                q_list += f"\n*... y {len(player.queue) - 10} canciones más.*"
            embed.add_field(name="Próximas en Cola", value=q_list, inline=False)
            embed.set_footer(text=f"Total: {len(player.queue)} pistas en cola")

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="nowplaying", aliases=["np"])
    async def prefix_nowplaying(self, ctx: commands.Context):
        """Uso: !np"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.current:
            await ctx.reply("🔇 No hay ninguna canción reproduciéndose.", mention_author=False)
            return

        cur = player.current
        embed = discord.Embed(
            title="🎶 Sonando Ahora",
            description=f"**[{cur.title}]({cur.webpage_url})**",
            color=config.COLOR_MUSIC,
        )
        embed.add_field(name="Progreso", value=player.get_progress_bar(), inline=False)
        embed.add_field(name="Canal", value=cur.uploader, inline=True)
        embed.add_field(name="Pedido por", value=cur.requester, inline=True)
        if cur.thumbnail:
            embed.set_thumbnail(url=cur.thumbnail)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="shuffle", aliases=["sh"])
    async def prefix_shuffle(self, ctx: commands.Context):
        """Uso: !sh"""
        player = self.music_service.get_player(ctx.guild.id)
        if not player.queue:
            await ctx.reply("❌ No hay canciones suficientes en la cola para mezclar.", mention_author=False)
            return

        player.shuffle_queue()
        await ctx.reply(f"🔀 Se mezclaron **{len(player.queue)} canciones** en la cola.", mention_author=False)

    @commands.command(name="stop", aliases=["leave", "dc", "disconnect"])
    async def prefix_stop(self, ctx: commands.Context):
        """Uso: !dc"""
        player = self.music_service.get_player(ctx.guild.id)
        player.clear_queue()
        if player.voice_client:
            await player.voice_client.disconnect()
            player.voice_client = None
            player.current = None
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


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))

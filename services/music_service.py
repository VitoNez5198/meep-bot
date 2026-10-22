"""
Servicio de Música para Meep Bot.
Maneja extracción de audio limpia con yt-dlp, decodificación FFmpeg,
colas de reproducción por servidor y soporte para artistas y Spotify.
"""

import time
import random
import asyncio
import logging
from typing import Dict, List, Optional, Any
import requests
import yt_dlp
import discord

import config

logger = logging.getLogger("meep.music")

# Opciones de yt-dlp optimizadas para streaming rápido sin descarga a disco
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def format_duration(seconds: int) -> str:
    """Convierte segundos a formato MM:SS o HH:MM:SS."""
    if not seconds or seconds < 0:
        return "En vivo"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class Track:
    """Representa una pista de audio lista para reproducir."""
    def __init__(
        self,
        title: str,
        webpage_url: str,
        stream_url: str,
        duration: int,
        thumbnail: str,
        uploader: str,
        requester: str = "Desconocido",
    ):
        self.title = title
        self.webpage_url = webpage_url
        self.stream_url = stream_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.uploader = uploader
        self.requester = requester

    @property
    def duration_str(self) -> str:
        return format_duration(self.duration)


class GuildMusicPlayer:
    """Gestiona el reproductor y la cola de música para un servidor específico."""
    def __init__(self, bot: discord.Client, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.loop_mode: str = "off"  # "off", "track", "queue"
        self.volume: float = 0.8
        self.start_playback_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.total_paused_duration: float = 0.0
        self.is_paused: bool = False
        self._lock = asyncio.Lock()

    @property
    def is_playing(self) -> bool:
        return self.voice_client and self.voice_client.is_playing()

    def get_elapsed_seconds(self) -> int:
        """Calcula los segundos transcurridos de la canción actual."""
        if not self.current or self.start_playback_time == 0.0:
            return 0
        if self.is_paused:
            return int(self.pause_start_time - self.start_playback_time - self.total_paused_duration)
        return int(time.time() - self.start_playback_time - self.total_paused_duration)

    def get_progress_bar(self, length: int = 14) -> str:
        """Genera una barra de progreso visual (ej: 01:23 🔘─────── 03:45)."""
        if not self.current or not self.current.duration:
            return "🔘" + "─" * length

        elapsed = self.get_elapsed_seconds()
        total = self.current.duration
        progress = min(1.0, max(0.0, elapsed / total))
        button_pos = int(progress * length)

        bar = ""
        for i in range(length):
            if i == button_pos:
                bar += "🔘"
            else:
                bar += "▬"

        return f"`{format_duration(elapsed)}` {bar} `{format_duration(total)}`"

    def add_track(self, track: Track):
        self.queue.append(track)

    def add_tracks(self, tracks: List[Track]):
        self.queue.extend(tracks)

    def shuffle_queue(self):
        random.shuffle(self.queue)

    def clear_queue(self):
        self.queue.clear()

    async def play_next(self):
        """Reproduce la siguiente canción respetando el modo de repetición."""
        async with self._lock:
            if not self.voice_client or not self.voice_client.is_connected():
                return

            # Manejar bucle
            if self.loop_mode == "track" and self.current:
                pass  # Mantiene self.current para repetirla
            elif self.loop_mode == "queue" and self.current:
                self.queue.append(self.current)
                if self.queue:
                    self.current = self.queue.pop(0)
                else:
                    self.current = None
            else:
                if self.queue:
                    self.current = self.queue.pop(0)
                else:
                    self.current = None

            if not self.current:
                # No hay más canciones en cola
                self.start_playback_time = 0.0
                return

            try:
                # Crear fuente de audio decodificada por FFmpeg
                source = discord.FFmpegPCMAudio(
                    self.current.stream_url,
                    executable=config.FFMPEG_EXE,
                    **FFMPEG_OPTIONS,
                )
                # Aplicar volumen
                transformer = discord.PCMVolumeTransformer(source, volume=self.volume)

                def after_callback(error):
                    if error:
                        logger.error(f"Error en reproducción de audio: {error}")
                    fut = asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)
                    try:
                        fut.result()
                    except Exception as ex:
                        logger.error(f"Error en callback after_callback: {ex}")

                self.voice_client.play(transformer, after=after_callback)
                self.start_playback_time = time.time()
                self.total_paused_duration = 0.0
                self.is_paused = False
                logger.info(f"Reproduciendo: '{self.current.title}' en guild {self.guild_id}")

            except Exception as e:
                logger.error(f"Error al iniciar reproducción de audio: {e}", exc_info=True)
                # Intentar con la siguiente si esta falló
                await self.play_next()


class MusicService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.players: Dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild_id: int) -> GuildMusicPlayer:
        """Obtiene o inicializa el reproductor de un servidor."""
        if guild_id not in self.players:
            self.players[guild_id] = GuildMusicPlayer(self.bot, guild_id)
        return self.players[guild_id]

    async def resolve_query(self, query: str, requester: str = "Usuario") -> List[Track]:
        """
        Resuelve una búsqueda de texto, enlace de YouTube o enlace de Spotify.
        Devuelve una lista de objetos Track.
        """
        # Chequeo si es enlace de Spotify
        if "spotify.com" in query:
            return await self._resolve_spotify(query, requester)

        # Búsqueda normal con yt-dlp
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_ytdl_tracks, query, requester)

    def _extract_ytdl_tracks(self, query: str, requester: str, max_results: int = 1) -> List[Track]:
        """Extrae metadata y stream directo usando yt-dlp (ejecutado en threadpool)."""
        tracks = []
        is_url = query.startswith("http://") or query.startswith("https://")
        search_query = query if is_url else f"ytsearch{max_results}:{query}"

        opts = dict(YTDL_OPTIONS)
        if max_results > 1:
            opts["extract_flat"] = False

        with yt_dlp.YoutubeDL(opts) as ytdl:
            try:
                info = ytdl.extract_info(search_query, download=False)
                if not info:
                    return []

                entries = info.get("entries") if "entries" in info else [info]

                for entry in entries:
                    if not entry:
                        continue
                    # Buscar la mejor URL de audio
                    stream_url = entry.get("url")
                    if not stream_url and "formats" in entry:
                        audio_formats = [f for f in entry["formats"] if f.get("acodec") != "none"]
                        if audio_formats:
                            stream_url = audio_formats[-1]["url"]

                    if stream_url:
                        tracks.append(
                            Track(
                                title=entry.get("title", "Audio Desconocido"),
                                webpage_url=entry.get("webpage_url", query),
                                stream_url=stream_url,
                                duration=int(entry.get("duration", 0)),
                                thumbnail=entry.get("thumbnail", ""),
                                uploader=entry.get("uploader", "Artista"),
                                requester=requester,
                            )
                        )
            except Exception as e:
                logger.error(f"Error extrayendo con yt-dlp para query '{query}': {e}")

        return tracks

    async def _resolve_spotify(self, spotify_url: str, requester: str) -> List[Track]:
        """Extrae el título de Spotify vía oEmbed y busca el stream en YouTube."""
        try:
            oembed_url = f"https://open.spotify.com/oembed?url={spotify_url}"
            res = requests.get(oembed_url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                title = data.get("title", "")
                if title:
                    logger.info(f"Enlace de Spotify resuelto como: '{title}'")
                    # Buscar el título en YouTube
                    return await self.resolve_query(title, requester)
        except Exception as e:
            logger.warning(f"Error resolviendo Spotify oEmbed: {e}")

        return []

    async def resolve_artist_top_tracks(self, artist_name: str, requester: str, count: int = 12) -> List[Track]:
        """
        Busca las mejores canciones de un artista y las devuelve en bloque.
        """
        query = f"{artist_name} top tracks greatest hits"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_ytdl_tracks, query, requester, count)


# Instancia del servicio de música (se vincula al bot en el cog)
music_service: Optional[MusicService] = None


def get_music_service(bot: discord.Client) -> MusicService:
    global music_service
    if music_service is None:
        music_service = MusicService(bot)
    return music_service

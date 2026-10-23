"""
Servicio de Música para Meep Bot.
Maneja extracción de audio limpia con yt-dlp, decodificación FFmpeg,
resolución perezosa (Lazy Loading) de streams, soporte para playlists
completas (YouTube, YouTube Music y Spotify) y heurística de audio de estudio (sin intros).
"""

import os
import time
import random
import asyncio
import logging
import re
import json
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
import requests
import yt_dlp
import discord

import config
from services.tray_service import tray_manager

logger = logging.getLogger("meep.music")

# Opciones de yt-dlp para streaming rápido directo sin descarga a disco
# Nota: No fijamos 'format' aquí para que yt-dlp extraiga todos los formatos sin
# fallar con 'Requested format is not available'; la selección óptima se hace en _get_best_audio_stream
YTDL_BASE_OPTIONS = {
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

# Detección automática de cookies para evitar bloqueos en AWS / VPS ("Sign in to confirm you're not a bot")
_COOKIES_PATH = None
_cookie_candidates = [
    os.getenv("YOUTUBE_COOKIES_FILE"),
    str(config.BASE_DIR / "cookies.txt"),
    str(config.BASE_DIR / "data" / "cookies.txt"),
    os.path.expanduser("~/cookies.txt"),
    os.path.expanduser("~/meep-bot/cookies.txt"),
    os.path.expanduser("~/bot_discord_2/cookies.txt"),
    "/home/ubuntu/meep-bot/cookies.txt",
    "/home/ubuntu/cookies.txt",
]

for _cand in _cookie_candidates:
    if _cand and os.path.isfile(_cand):
        try:
            if os.path.getsize(_cand) > 0:
                _COOKIES_PATH = _cand
                break
        except Exception:
            pass

if _COOKIES_PATH:
    YTDL_BASE_OPTIONS["cookiefile"] = _COOKIES_PATH
    logger.info(f"Cargadas cookies de YouTube para yt-dlp desde: {_COOKIES_PATH}")
else:
    logger.warning("No se detectó archivo 'cookies.txt'. Si YouTube bloquea la IP, coloca 'cookies.txt' en la carpeta del bot.")

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


def sanitize_url(url: str) -> str:
    """
    Limpia parámetros de tracking e índices innecesarios (&si=..., &feature=..., etc.)
    conservando parámetros esenciales como 'v' y 'list'.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        qs = urllib.parse.parse_qs(parsed.query)
        cleaned_qs = {}
        for key in ("v", "list"):
            if key in qs:
                cleaned_qs[key] = qs[key]
        new_query = urllib.parse.urlencode(cleaned_qs, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))
    except Exception:
        return url


class Track:
    """Representa una pista de audio para la cola y reproducción."""
    def __init__(
        self,
        title: str,
        webpage_url: str,
        stream_url: Optional[str] = None,
        duration: int = 0,
        thumbnail: str = "",
        uploader: str = "Artista",
        requester: str = "Desconocido",
        expected_duration: Optional[int] = None,
        search_query: Optional[str] = None,
        playlist_name: Optional[str] = None,
        playlist_id: Optional[str] = None,
    ):
        self.title = title
        self.webpage_url = webpage_url
        self.stream_url = stream_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.uploader = uploader
        self.requester = requester
        self.expected_duration = expected_duration if expected_duration is not None else duration
        self.search_query = search_query
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id
        self.is_resolved: bool = stream_url is not None

    @property
    def duration_str(self) -> str:
        return format_duration(self.duration)



class GuildMusicPlayer:
    """Gestiona el reproductor y la cola de música para un servidor específico."""
    def __init__(self, bot: discord.Client, guild_id: int, music_service: "MusicService"):
        self.bot = bot
        self.guild_id = guild_id
        self.music_service = music_service
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.loop_mode: str = "off"  # "off", "track", "queue"
        self.radio_mode: bool = False  # Modo Radio (Autoplay de pistas similares)
        self.last_played: Optional[Track] = None
        self.played_history: List[str] = []
        self.volume: float = 0.8
        self.start_playback_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.total_paused_duration: float = 0.0
        self.is_paused: bool = False
        self.is_loading_next: bool = False
        self.controller_message: Optional[discord.Message] = None
        self.controller_view: Optional[Any] = None
        self._lock = asyncio.Lock()

    @property
    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

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

    def stop(self):
        """Detiene completamente la reproducción, limpia la cola y desactiva el Modo Radio."""
        self.queue.clear()
        self.radio_mode = False
        self.last_played = None
        self.is_paused = False
        self.start_playback_time = 0.0
        self.current = None
        if self.voice_client:
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()

    def jump_to_track(self, position: int) -> Tuple[bool, Optional[Track], int]:
        """
        Salta directamente a la canción en la posición dada (1-indexada).
        Descarta las canciones anteriores.
        Retorna (exito, target_track, discarded_count).
        """
        if position < 1 or position > len(self.queue):
            return False, None, 0

        target_idx = position - 1
        discarded = target_idx
        del self.queue[:target_idx]
        target_track = self.queue[0]

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

        return True, target_track, discarded

    def find_in_queue(self, query: str) -> List[Tuple[int, Track]]:
        """Busca canciones en la cola que coincidan con el texto y retorna [(posicion, track)]."""
        q_clean = query.lower().strip()
        results = []
        for idx, track in enumerate(self.queue):
            if q_clean in track.title.lower() or q_clean in (track.uploader or "").lower():
                results.append((idx + 1, track))
        return results

    def skip_playlist(self) -> Tuple[Optional[str], int, Optional[Track]]:
        """
        Descarta las canciones restantes en cola que pertenezcan a la lista actual.
        Retorna (nombre_playlist_saltada, cantidad_descartadas, siguiente_track).
        """
        current_pl_id = getattr(self.current, "playlist_id", None) if self.current else None
        current_pl_name = (getattr(self.current, "playlist_name", None) if self.current else None) or "Lista Actual"

        discarded = 0
        if current_pl_id:
            while self.queue and getattr(self.queue[0], "playlist_id", None) == current_pl_id:
                self.queue.pop(0)
                discarded += 1
        elif self.queue and getattr(self.queue[0], "playlist_id", None):
            # Si la canción actual no tenía playlist pero la siguiente sí, saltar esa primera lista
            target_pl_id = getattr(self.queue[0], "playlist_id", None)
            current_pl_name = getattr(self.queue[0], "playlist_name", None) or "Lista en cola"
            while self.queue and getattr(self.queue[0], "playlist_id", None) == target_pl_id:
                self.queue.pop(0)
                discarded += 1

        next_track = self.queue[0] if self.queue else None
        return current_pl_name, discarded, next_track

    def get_queued_playlists_summary(self) -> List[Tuple[str, int]]:
        """Devuelve un resumen de las listas que están actualmente en cola [(nombre, cantidad)]."""
        counts = {}
        order = []
        for t in self.queue:
            name = getattr(t, "playlist_name", None)
            if name:
                if name not in counts:
                    counts[name] = 0
                    order.append(name)
                counts[name] += 1
        return [(name, counts[name]) for name in order]

    async def play_next(self):
        """Reproduce la siguiente canción respetando el modo de repetición y resolviendo el stream JIT."""
        async with self._lock:
            if not self.voice_client or not self.voice_client.is_connected():
                return

            # Manejar repetición
            if self.loop_mode == "track" and self.current:
                pass  # Mantiene self.current para repetirla
            elif self.loop_mode == "queue" and self.current:
                self.queue.append(self.current)
                if self.queue:
                    self.current = self.queue.pop(0)
                else:
                    self.current = None
            else:
                if self.current:
                    self.last_played = self.current
                    if self.current.webpage_url:
                        self.played_history.append(self.current.webpage_url)
                    if self.current.title:
                        self.played_history.append(self.current.title)
                    if len(self.played_history) > 60:
                        self.played_history = self.played_history[-60:]

                if self.queue:
                    self.current = self.queue.pop(0)
                elif self.radio_mode and getattr(self, "last_played", None):
                    self.is_loading_next = True
                    try:
                        logger.info(f"Modo Radio activo para guild {self.guild_id}: buscando pista recomendada...")
                        rec_track = await self.music_service.get_radio_recommendation(
                            self.last_played,
                            self.played_history,
                            requester="📻 Meep Radio",
                        )
                        if rec_track:
                            self.current = rec_track
                            if rec_track.webpage_url:
                                self.played_history.append(rec_track.webpage_url)
                            if rec_track.title:
                                self.played_history.append(rec_track.title)
                            logger.info(f"Modo Radio seleccionó y reproduciendo: '{rec_track.title}'")
                        else:
                            self.current = None
                    except Exception as rex:
                        logger.error(f"Error obteniendo recomendación de Radio: {rex}")
                        self.current = None
                    finally:
                        self.is_loading_next = False
                else:
                    self.current = None

            if not self.current:
                # No hay más canciones en la cola ni en la radio
                self.start_playback_time = 0.0
                await self.music_service.update_presence_for_track(None)
                if self.controller_message and self.controller_view:
                    try:
                        from ui.music_views import create_now_playing_embed
                        self.controller_view._sync_buttons()
                        embed = create_now_playing_embed(self)
                        await self.controller_message.edit(embed=embed, view=self.controller_view)
                    except Exception:
                        pass
                return

            # Resolución perezosa (Lazy Loading): si la pista no tiene stream_url, se extrae ahora
            if not self.current.is_resolved or not self.current.stream_url:
                try:
                    resolved = await self.music_service.resolve_stream_for_track(self.current)
                    if not resolved or not resolved.stream_url:
                        logger.warning(f"No se pudo resolver el stream para '{self.current.title}'. Saltando a la siguiente...")
                        self.current = None
                        await self.play_next()
                        return
                    self.current = resolved
                except Exception as ex:
                    logger.error(f"Error resolviendo stream para '{self.current.title}': {ex}", exc_info=True)
                    self.current = None
                    await self.play_next()
                    return

            try:
                # Crear fuente de audio decodificada por FFmpeg
                source = discord.FFmpegPCMAudio(
                    self.current.stream_url,
                    executable=config.FFMPEG_EXE,
                    **FFMPEG_OPTIONS,
                )
                # Aplicar transformador de volumen
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
                await self.music_service.update_presence_for_track(self.current)

                # Actualizar automáticamente el mensaje del embed interactivo en Discord
                if self.controller_message and self.controller_view:
                    try:
                        from ui.music_views import create_now_playing_embed
                        self.controller_view._sync_buttons()
                        embed = create_now_playing_embed(self)
                        await self.controller_message.edit(embed=embed, view=self.controller_view)
                    except Exception as msg_err:
                        logger.debug(f"No se pudo actualizar el mensaje interactivo: {msg_err}")

            except Exception as e:
                logger.error(f"Error al iniciar reproducción de audio: {e}", exc_info=True)
                # Intentar con la siguiente si esta falló
                self.current = None
                await self.play_next()


class MusicService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.players: Dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild_id: int) -> GuildMusicPlayer:
        """Obtiene o inicializa el reproductor de un servidor."""
        if guild_id not in self.players:
            self.players[guild_id] = GuildMusicPlayer(self.bot, guild_id, self)
        return self.players[guild_id]

    async def update_presence_for_track(self, track: Optional[Track] = None):
        """Actualiza la presencia de Discord con la canción actual o el estado por defecto."""
        try:
            if track and track.title:
                clean_title = track.title.replace("\n", " ").strip()
                if len(clean_title) > 120:
                    clean_title = clean_title[:117] + "..."

                clean_uploader = None
                if track.uploader and track.uploader.strip() and track.uploader.strip() not in ["Artista", "Desconocido"]:
                    uploader = track.uploader.strip()
                    if len(uploader) > 100:
                        uploader = uploader[:97] + "..."
                    clean_uploader = f"por {uploader}"

                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name=clean_title,
                    state=clean_uploader,
                )
                await self.bot.change_presence(status=discord.Status.online, activity=activity)
                try:
                    tray_manager.set_status(f"🎵 {clean_title[:30]}")
                except Exception:
                    pass
            else:
                # Comprobar si algún otro servidor sigue reproduciendo
                active_track = None
                for p in self.players.values():
                    if p.is_playing and p.current:
                        active_track = p.current
                        break

                if active_track:
                    await self.update_presence_for_track(active_track)
                else:
                    activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name=getattr(config, "BOT_DEFAULT_STATUS", "Música & League of Legends"),
                        state=getattr(config, "BOT_DESCRIPTION", "Tu compañero privado para League of Legends y Música."),
                    )
                    await self.bot.change_presence(status=discord.Status.online, activity=activity)
                    try:
                        tray_manager.set_status("🟢 En línea")
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error actualizando la presencia de Discord: {e}")


    async def resolve_query(self, query: str, requester: str = "Usuario") -> List[Track]:
        """
        Resuelve una búsqueda de texto, enlace de YouTube (canción o playlist),
        YouTube Music o enlace de Spotify (canción, álbum o playlist).
        Devuelve una lista de objetos Track.
        """
        query = query.strip()

        # 1. Enlace de Spotify
        if "spotify.com" in query:
            return await self._resolve_spotify(query, requester)

        # 2. Enlace de Playlist de YouTube o YouTube Music
        if ("youtube.com" in query or "youtu.be" in query) and ("playlist?list=" in query or "&list=" in query):
            clean_url = sanitize_url(query)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._extract_ytdl_playlist, clean_url, requester)

        # 3. Enlace directo a video de YouTube o YouTube Music
        if query.startswith("http://") or query.startswith("https://"):
            clean_url = sanitize_url(query)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._extract_ytdl_single_url, clean_url, requester)

        # 4. Búsqueda por texto libre (heurística de Audio Limpio)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_clean_query, query, requester)

    def _extract_ytdl_playlist(self, playlist_url: str, requester: str) -> List[Track]:
        """Extrae la lista de canciones de una playlist de YouTube en modo plano rápido."""
        opts = dict(YTDL_BASE_OPTIONS)
        opts["noplaylist"] = False
        opts["extract_flat"] = True

        tracks: List[Track] = []
        with yt_dlp.YoutubeDL(opts) as ytdl:
            try:
                info = ytdl.extract_info(playlist_url, download=False)
                if not info:
                    return []

                playlist_title = info.get("title") or "Playlist de YouTube"
                playlist_id = info.get("id") or f"yt_pl_{int(time.time()*1000)}"

                entries = info.get("entries", [])
                for entry in entries:
                    if not entry:
                        continue
                    vid_id = entry.get("id")
                    title = entry.get("title") or "Pista Desconocida"
                    dur = int(entry.get("duration") or 0)
                    uploader = entry.get("uploader") or entry.get("channel") or "YouTube"
                    thumbnail = entry.get("thumbnail") or ""

                    webpage_url = entry.get("url")
                    if not webpage_url or not webpage_url.startswith("http"):
                        if vid_id:
                            webpage_url = f"https://www.youtube.com/watch?v={vid_id}"
                        else:
                            webpage_url = playlist_url

                    tracks.append(Track(
                        title=title,
                        webpage_url=webpage_url,
                        stream_url=None,  # Resolución diferida
                        duration=dur,
                        thumbnail=thumbnail,
                        uploader=uploader,
                        requester=requester,
                        expected_duration=dur,
                        search_query=None,
                        playlist_name=playlist_title,
                        playlist_id=playlist_id,
                    ))

            except Exception as e:
                logger.error(f"Error extrayendo playlist de YouTube ({playlist_url}): {e}")

        return tracks

    def _extract_ytdl_single_url(self, url: str, requester: str) -> List[Track]:
        """Extrae metadata de un enlace directo de YouTube o YouTube Music."""
        opts = dict(YTDL_BASE_OPTIONS)
        opts["noplaylist"] = True

        with yt_dlp.YoutubeDL(opts) as ytdl:
            try:
                info = ytdl.extract_info(url, download=False)
                if not info:
                    return []

                title = info.get("title", "Audio Desconocido")
                dur = int(info.get("duration", 0))
                thumbnail = info.get("thumbnail", "")
                uploader = info.get("uploader") or info.get("channel") or "YouTube"
                webpage_url = info.get("webpage_url", url)

                # Intentar obtener el stream_url de una vez
                stream_url = self._get_best_audio_stream(info)

                track = Track(
                    title=title,
                    webpage_url=webpage_url,
                    stream_url=stream_url,
                    duration=dur,
                    thumbnail=thumbnail,
                    uploader=uploader,
                    requester=requester,
                    expected_duration=dur,
                )
                return [track]
            except Exception as e:
                logger.error(f"Error extrayendo URL individual {url}: {e}")
                return []

    def _search_clean_query(self, query: str, requester: str) -> List[Track]:
        """Busca una canción por texto utilizando la heurística de Audio Limpio."""
        clean_url, dur, thumb, title, uploader = self._search_clean_youtube_audio(query)
        if not clean_url:
            return []

        track = Track(
            title=title or query,
            webpage_url=clean_url,
            stream_url=None,  # Se resuelve JIT en play_next
            duration=dur,
            thumbnail=thumb,
            uploader=uploader or "YouTube",
            requester=requester,
            expected_duration=dur,
            search_query=query,
        )
        return [track]

    async def _resolve_spotify(self, spotify_url: str, requester: str) -> List[Track]:
        """Extrae metadatos de canciones, listas o álbumes de Spotify mediante el embed público."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_spotify_embed, spotify_url, requester)

    def _parse_spotify_embed(self, url: str, requester: str) -> List[Track]:
        """Parsea el embed público de Spotify y su bloque __NEXT_DATA__."""
        # Limpiar prefijos regionales (ej. /intl-es/, /intl-pt/) para que el embed sea válido
        clean_url = re.sub(r"open\.spotify\.com/(?:embed/)?(?:intl-[a-z]+(?:-[a-z]+)?/)?", "open.spotify.com/embed/", url)
        embed_url = clean_url.split("?")[0]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        try:
            res = requests.get(embed_url, headers=headers, timeout=8)
            if res.status_code != 200:
                logger.warning(f"Error al obtener Spotify embed HTTP {res.status_code} para {url}")
                return []

            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
            if not match:
                logger.warning("No se encontró __NEXT_DATA__ en la respuesta de Spotify embed")
                return []

            data = json.loads(match.group(1))
            entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
            entity_type = entity.get("type", "")
            tracks: List[Track] = []

            if entity_type == "track":
                name = entity.get("name", "Desconocido")
                artists = ", ".join([a.get("name", "") for a in entity.get("artists", []) if a.get("name")])
                full_title = f"{name} - {artists}" if artists else name
                duration_s = int(entity.get("duration", 0)) // 1000
                search_term = f"{name} {artists}".strip()

                cover = ""
                cover_art = entity.get("coverArt", {}).get("sources", [])
                if cover_art:
                    cover = cover_art[0].get("url", "")

                tracks.append(Track(
                    title=full_title,
                    webpage_url=url,
                    stream_url=None,
                    duration=duration_s,
                    thumbnail=cover,
                    uploader=artists or "Spotify",
                    requester=requester,
                    expected_duration=duration_s,
                    search_query=search_term,
                ))

            elif entity_type in ("playlist", "album"):
                track_list = entity.get("trackList", [])
                pl_name = entity.get("name") or ("Álbum de Spotify" if entity_type == "album" else "Playlist de Spotify")
                pl_id = entity.get("id") or f"sp_{entity_type}_{int(time.time()*1000)}"

                cover = ""
                cover_art = entity.get("coverArt", {}).get("sources", [])
                if cover_art:
                    cover = cover_art[0].get("url", "")

                for item in track_list:
                    item_title = item.get("title", "")
                    item_subtitle = item.get("subtitle", "")
                    if not item_title:
                        continue
                    full_title = f"{item_title} - {item_subtitle}" if item_subtitle else item_title
                    duration_s = int(item.get("duration", 0)) // 1000
                    search_term = f"{item_title} {item_subtitle}".strip()

                    track_uri = item.get("uri", "")
                    track_url = f"https://open.spotify.com/track/{track_uri.replace('spotify:track:', '')}" if track_uri else url

                    tracks.append(Track(
                        title=full_title,
                        webpage_url=track_url,
                        stream_url=None,
                        duration=duration_s,
                        thumbnail=cover,
                        uploader=item_subtitle or "Spotify",
                        requester=requester,
                        expected_duration=duration_s,
                        search_query=search_term,
                        playlist_name=pl_name,
                        playlist_id=pl_id,
                    ))

            logger.info(f"Spotify resolvió {len(tracks)} pistas para {url}")
            return tracks


        except Exception as e:
            logger.error(f"Error parseando Spotify embed para {url}: {e}", exc_info=True)
            return []

    def _search_clean_youtube_audio(
        self,
        search_term: str,
        expected_duration: int = 0,
    ) -> Tuple[Optional[str], int, str, str, str]:
        """
        Busca en YouTube con heurística de Audio Limpio.
        Retorna (webpage_url, duration, thumbnail, title, uploader).
        """
        opts = dict(YTDL_BASE_OPTIONS)
        opts["extract_flat"] = True
        opts["noplaylist"] = True

        query = f"ytsearch5:{search_term} audio"
        with yt_dlp.YoutubeDL(opts) as ytdl:
            try:
                info = ytdl.extract_info(query, download=False)
                if not info or not info.get("entries"):
                    info = ytdl.extract_info(f"ytsearch3:{search_term}", download=False)

                entries = [e for e in info.get("entries", []) if e]
                if not entries:
                    return None, 0, "", "", ""

                best_entry = None
                # Si tenemos duración esperada oficial (ej: desde Spotify)
                if expected_duration > 0:
                    topic_candidates = []
                    general_candidates = []
                    for e in entries:
                        e_dur = int(e.get("duration") or 0)
                        uploader = e.get("uploader") or ""
                        channel = e.get("channel") or ""
                        diff = abs(e_dur - expected_duration) if e_dur else 999
                        is_topic = "- Topic" in uploader or "- Topic" in channel

                        # Máxima prioridad: canales de audio oficial de YouTube con duración casi idéntica
                        if is_topic and diff <= 15:
                            topic_candidates.append((diff, e))
                        elif diff <= 20:
                            general_candidates.append((diff, e))
                        else:
                            general_candidates.append((diff + 100, e))

                    if topic_candidates:
                        topic_candidates.sort(key=lambda x: x[0])
                        best_entry = topic_candidates[0][1]
                    elif general_candidates:
                        general_candidates.sort(key=lambda x: x[0])
                        best_entry = general_candidates[0][1]

                # Si no hay duración esperada o no hubo coincidencia estrecha
                if not best_entry and entries:
                    for e in entries:
                        uploader = e.get("uploader") or ""
                        channel = e.get("channel") or ""
                        if "- Topic" in uploader or "- Topic" in channel:
                            best_entry = e
                            break
                    if not best_entry:
                        best_entry = entries[0]

                vid_url = best_entry.get("url")
                if not vid_url or not vid_url.startswith("http"):
                    vid_id = best_entry.get("id")
                    if vid_id:
                        vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                dur = int(best_entry.get("duration") or 0)
                thumb = best_entry.get("thumbnail") or ""
                title = best_entry.get("title") or search_term
                uploader = best_entry.get("uploader") or best_entry.get("channel") or "YouTube"

                return vid_url, dur, thumb, title, uploader

            except Exception as e:
                logger.error(f"Error en búsqueda de audio limpio para '{search_term}': {e}")
                return None, 0, "", "", ""

    def _get_best_audio_stream(self, info: dict) -> Optional[str]:
        """Obtiene la mejor URL directa de streaming de audio desde el diccionario de info."""
        stream_url = info.get("url")
        if stream_url:
            return stream_url

        formats = info.get("formats", [])
        if not formats:
            return None

        # 1. Preferir formatos que sean solo de audio y tengan URL directa
        audio_only = [
            f for f in formats
            if f.get("url")
            and f.get("acodec") not in ("none", None)
            and f.get("vcodec") in ("none", None)
        ]
        if audio_only:
            return audio_only[-1]["url"]

        # 2. Si no hay solo audio, cualquier formato con audio (FFmpeg descarta video con -vn)
        any_audio = [
            f for f in formats
            if f.get("url") and f.get("acodec") not in ("none", None)
        ]
        if any_audio:
            return any_audio[-1]["url"]

        # 3. Fallback a cualquier formato con URL válida
        valid_urls = [f["url"] for f in formats if f.get("url")]
        return valid_urls[-1] if valid_urls else None

    async def resolve_stream_for_track(self, track: Track) -> Optional[Track]:
        """
        Resuelve el stream_url directo de audio para un Track de forma perezosa (Just-in-Time).
        """
        if track.is_resolved and track.stream_url:
            return track

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_stream_worker, track)

    def _extract_stream_worker(self, track: Track) -> Optional[Track]:
        """Worker en hilo secundario que resuelve el stream directo de una pista."""
        target_url = track.webpage_url
        is_direct_yt = ("youtube.com" in target_url or "youtu.be" in target_url) and "playlist" not in target_url

        opts = dict(YTDL_BASE_OPTIONS)
        opts["noplaylist"] = True

        if is_direct_yt:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                try:
                    info = ytdl.extract_info(target_url, download=False)
                    if not info:
                        return None
                    stream_url = self._get_best_audio_stream(info)
                    if stream_url:
                        track.stream_url = stream_url
                        track.is_resolved = True
                        if not track.duration and info.get("duration"):
                            track.duration = int(info["duration"])
                        if not track.thumbnail and info.get("thumbnail"):
                            track.thumbnail = info["thumbnail"]
                        return track
                except Exception as e:
                    logger.error(f"Error extrayendo stream para URL directa {target_url}: {e}")
                    return None
        else:
            # Caso Spotify o búsqueda sin URL de YouTube resuelta
            search_term = track.search_query or track.title
            clean_url, dur, thumb, _, _ = self._search_clean_youtube_audio(search_term, expected_duration=track.expected_duration)
            if not clean_url:
                return None

            with yt_dlp.YoutubeDL(opts) as ytdl:
                try:
                    info = ytdl.extract_info(clean_url, download=False)
                    if not info:
                        return None
                    stream_url = self._get_best_audio_stream(info)
                    if stream_url:
                        track.stream_url = stream_url
                        track.webpage_url = clean_url
                        track.is_resolved = True
                        if dur:
                            track.duration = dur
                        elif info.get("duration"):
                            track.duration = int(info["duration"])
                        if thumb and not track.thumbnail:
                            track.thumbnail = thumb
                        elif info.get("thumbnail") and not track.thumbnail:
                            track.thumbnail = info["thumbnail"]
                        return track
                except Exception as e:
                    logger.error(f"Error extrayendo stream para clean_url {clean_url}: {e}")
                    return None

        return None

    async def resolve_artist_top_tracks(self, artist_name: str, requester: str, count: int = 12) -> List[Track]:
        """Busca las mejores canciones de un artista y las devuelve en bloque."""
        query = f"{artist_name} top tracks greatest hits"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_artist_tracks, query, artist_name, requester, count)

    def _extract_artist_tracks(self, query: str, artist_name: str, requester: str, count: int) -> List[Track]:
        opts = dict(YTDL_BASE_OPTIONS)
        opts["extract_flat"] = True
        opts["noplaylist"] = True

        playlist_title = f"Top Tracks de {artist_name.title()}"
        playlist_id = f"artist_{artist_name.lower().replace(' ', '_')}"

        tracks: List[Track] = []
        with yt_dlp.YoutubeDL(opts) as ytdl:
            try:
                info = ytdl.extract_info(f"ytsearch{count}:{query}", download=False)
                if not info or not info.get("entries"):
                    return []

                for entry in info.get("entries", []):
                    if not entry:
                        continue
                    vid_id = entry.get("id")
                    title = entry.get("title") or f"{artist_name} Song"
                    dur = int(entry.get("duration") or 0)
                    thumbnail = entry.get("thumbnail") or ""
                    uploader = entry.get("uploader") or artist_name
                    webpage_url = entry.get("url")
                    if not webpage_url or not webpage_url.startswith("http"):
                        webpage_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""

                    tracks.append(Track(
                        title=title,
                        webpage_url=webpage_url,
                        stream_url=None,  # JIT
                        duration=dur,
                        thumbnail=thumbnail,
                        uploader=uploader,
                        requester=requester,
                        expected_duration=dur,
                        playlist_name=playlist_title,
                        playlist_id=playlist_id,
                    ))
            except Exception as e:
                logger.error(f"Error extrayendo top tracks para {artist_name}: {e}")


        return tracks

    def extract_clean_artist(self, track: Optional[Track]) -> str:
        """Extrae el nombre limpio del artista de una pista para recomendaciones."""
        if not track:
            return ""

        # 1. Si el canal/uploader es de tipo Topic (generado oficialmente por YouTube Music)
        uploader = (track.uploader or "").strip()
        if "- Topic" in uploader:
            clean = uploader.replace("- Topic", "").strip()
            if clean:
                return clean

        # 2. Si el título tiene formato "Artista - Canción"
        title = track.title or ""
        clean_title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
        if " - " in clean_title:
            artist_part = clean_title.split(" - ")[0].strip()
            if artist_part and len(artist_part) < 40 and not any(w in artist_part.lower() for w in ["top", "best", "hits", "exitos"]):
                return artist_part

        # 3. Uploader si no es genérico
        if uploader and uploader.lower() not in ("youtube", "spotify", "desconocido", "artista", "vevo"):
            if uploader.endswith("VEVO"):
                return uploader[:-4].strip()
            return uploader

        return clean_title.split()[0] if clean_title else "Música"

    def _is_clean_track(self, title: str, duration: int) -> bool:
        """
        Filtro estricto anti-remixes, anti-enganchados y anti-mixes largos.
        Devuelve True solo si es una canción individual de estudio.
        """
        if not title:
            return False

        # Duración de canción de estudio: 85 seg a 460 seg (~7.5 min)
        if duration > 480 or (0 < duration < 85):
            return False

        low = title.lower()
        blacklist = [
            "mix",
            "remix",
            "enganchado",
            "completo",
            "1 hora",
            "2 horas",
            "3 horas",
            "1 hr",
            "2 hr",
            "dj ",
            "dj-",
            "dj_",
            "mashup",
            "bootleg",
            "compilation",
            "recopilatorio",
            "megamix",
            "set ",
            "live set",
            "sesion",
            "sesión",
            "extended mix",
            "tributo",
            "karaoke",
            "instrumental",
            "acapella",
            "disco completo",
            "album completo",
            "álbum completo",
            "best songs",
            "top songs",
            "grandes exitos",
            "grandes éxitos",
        ]
        for bad in blacklist:
            if bad in low:
                return False

        return True

    async def get_radio_recommendation(
        self,
        base_track: Optional[Track],
        played_history: List[str],
        requester: str = "📻 Meep Radio",
    ) -> Optional[Track]:
        """
        Busca y devuelve una canción recomendada del mismo artista o estilo,
        evitando remixes largos y canciones ya reproducidas en la sesión.
        """
        artist = self.extract_clean_artist(base_track)
        if not artist:
            artist = "Pop Latino"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_radio_worker, artist, played_history, requester)

    def _extract_radio_worker(
        self,
        artist: str,
        played_history: List[str],
        requester: str,
    ) -> Optional[Track]:
        opts = dict(YTDL_BASE_OPTIONS)
        opts["extract_flat"] = True
        opts["noplaylist"] = True

        queries = [
            f"ytsearch15:{artist} official audio",
            f"ytsearch10:{artist} - Topic",
        ]

        candidates = []
        with yt_dlp.YoutubeDL(opts) as ytdl:
            for q in queries:
                try:
                    info = ytdl.extract_info(q, download=False)
                    if not info or not info.get("entries"):
                        continue

                    for entry in info.get("entries", []):
                        if not entry:
                            continue

                        vid_id = entry.get("id")
                        vid_url = entry.get("url")
                        if not vid_url or not vid_url.startswith("http"):
                            vid_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""
                        if not vid_url:
                            continue

                        title = entry.get("title") or ""
                        dur = int(entry.get("duration") or 0)
                        uploader = entry.get("uploader") or entry.get("channel") or ""

                        # Comprobar historial por URL o ID
                        if vid_url in played_history or (vid_id and vid_id in played_history):
                            continue

                        # Comprobar similitud de título en historial
                        title_clean = re.sub(r"[^\w\s]", "", title.lower()).strip()
                        if any(title_clean in h.lower() or h.lower() in title_clean for h in played_history if len(h) > 6):
                            continue

                        # Filtro estricto anti-remixes / enganchados
                        if not self._is_clean_track(title, dur):
                            continue

                        priority = 1
                        if "- Topic" in uploader:
                            priority += 3
                        if "official audio" in title.lower() or "audio oficial" in title.lower():
                            priority += 2

                        candidates.append((priority, entry, vid_url, title, dur, uploader))

                    if candidates:
                        break
                except Exception as ex:
                    logger.warning(f"Error consultando query de radio '{q}': {ex}")

        if not candidates:
            return None

        # Ordenar por prioridad y tomar aleatoriamente de los mejores
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_priority = candidates[0][0]
        top_group = [c for c in candidates if c[0] == top_priority]
        chosen = random.choice(top_group)

        _, chosen_entry, chosen_url, chosen_title, chosen_dur, chosen_uploader = chosen
        return Track(
            title=chosen_title,
            webpage_url=chosen_url,
            stream_url=None,  # JIT
            duration=chosen_dur,
            thumbnail=chosen_entry.get("thumbnail") or "",
            uploader=chosen_uploader or artist,
            requester=requester,
            expected_duration=chosen_dur,
            playlist_name=f"📻 Radio de {artist.title()}",
            playlist_id=f"radio_{artist.lower().replace(' ', '_')}",
        )


# Instancia del servicio de música
music_service: Optional[MusicService] = None


def get_music_service(bot: discord.Client) -> MusicService:
    global music_service
    if music_service is None:
        music_service = MusicService(bot)
    return music_service

# Design: Soporte de Playlists (YouTube, YouTube Music y Spotify) y Audio Limpio

## Arquitectura del Módulo de Música

El módulo de música se rediseña para separar la **resolución de metadatos** de la **extracción del flujo de audio directo (streaming)**. Esto permite cargar listas enteras de 50 a 100 canciones en milisegundos, manteniendo la extracción de audio pesada diferida ("lazy") para el momento exacto en que la canción va a sonar.

```
                             [Usuario pega enlace o búsqueda]
                                             |
                                             v
                              +-----------------------------+
                              |      cogs/music_cog.py      |
                              |  (Comandos /play y !p)      |
                              +-----------------------------+
                                             |
                                             v
                              +-----------------------------+
                              |  services/music_service.py  |
                              |      resolve_query()        |
                              +-----------------------------+
                                      /      |      \
                                     /       |       \
                                    /        |        \
    [Spotify URL]                  /         |         \  [Búsqueda de Texto]
  +-------------------------+     /          |          \+-----------------------+
  |  Spotify Public Embed   | <--+           |           +-> Búsqueda de Audio   |
  |  - Canción (track)      |                |               Limpio en YouTube   |
  |  - Playlist (trackList) |                v               con heurística      |
  |  - Álbum (trackList)    |     [YouTube / YouTube Music]  (Topic / duración)  |
  +-------------------------+     | - Video individual      |                    |
               |                  | - music.youtube.com     +--------------------+
               v                  | - Lista de reproducción |              |
     Lista de metadatos           +-------------------------+              |
    (Título, Artista, Duración)              |                             |
               |                             v                             v
               +------------------> [ Cola de Reproducción ] <-------------+
                                    (GuildMusicPlayer.queue)
                                    (Pistas con stream_url diferido)
                                             |
                                    (Al sonar en turno)
                                             v
                              +-----------------------------+
                              |    resolve_stream_url()     |
                              |  Extracción de audio limpia |
                              |  justo a tiempo (JIT)       |
                              +-----------------------------+
                                             |
                                             v
                                  [ discord.FFmpegPCMAudio ]
                                             |
                                             v
                                   [ Canal de Voz Discord ]
```

---

## Componentes Técnicos Detallados

### 1. Extractor Público de Spotify (`_resolve_spotify`)

En lugar de requerir que el usuario cree una aplicación de desarrollador en Spotify (lo que añade fricción de configuración y tokens que expiran), se aprovecha el endpoint de incrustación público (`open.spotify.com/embed/...`) que contiene los datos en formato JSON pre-renderizado (`__NEXT_DATA__`):

* **Detección de tipo de enlace**:
  * `spotify.com/track/<id>`: Pista individual. Se extraen título, artistas y duración exacta en milisegundos.
  * `spotify.com/playlist/<id>`: Lista de reproducción. Se extrae `entity.trackList`, obteniendo la lista completa de canciones con sus artistas y duraciones.
  * `spotify.com/album/<id>`: Álbum. Similar a la playlist, se extrae el listado completo de canciones.
* **Normalización de metadatos**:
  Cada canción se transforma en un objeto `Track` preliminar con su título (`track['title']`), artista (`track['subtitle']` o artistas unidos por coma) y duración en segundos (`track['duration'] // 1000`).
* **Resolución diferida**:
  Para no hacer 50 peticiones a YouTube al momento de encolar, las pistas se guardan en la cola con una bandera `is_resolved = False`. Al momento de reproducirse, se resuelve la mejor versión de audio en YouTube.

### 2. Soporte de Listas de YouTube y YouTube Music (`_extract_ytdl_tracks`)

* **Parámetros de `yt-dlp`**:
  * Se elimina la restricción `"noplaylist": True` global.
  * Si la consulta es una URL con `list=` o perteneciente a una playlist, se pasa `"extract_flat": True` (o `"in_playlist"`), lo cual recupera únicamente la metadata liviana (ID, título, duración, thumbnail) de todas las canciones en menos de 2 segundos sin descargar formatos pesados ni causar errores HTTP 400.
  * Para URLs de `music.youtube.com`, se tratan de forma transparente con `yt-dlp` ya que las reconoce de forma nativa.
  * **Sanitización de URLs**: Se eliminan parámetros de seguimiento innecesarios (como `&si=...`, `&feature=...`) antes de llamar a `yt-dlp` para evitar incompatibilidades en la API de YouTube.

### 3. Heurística de Selección de Audio Limpio (Eliminación de Intros de Video)

Los videos musicales oficiales de YouTube frecuentemente contienen 30 a 90 segundos de diálogo introductorio, bocetos o créditos al final. Para garantizar que se reproduzca la versión de estudio (álbum / audio oficial):

1. **Estrategia de Búsqueda Mejorada**:
   Al resolver una pista desde Spotify o una búsqueda genérica, el término de consulta se optimiza agregando `"audio"` o `"official audio"`.
2. **Priorización de Canales Topic / YouTube Music**:
   YouTube genera automáticamente pistas para YouTube Music bajo el formato `<Nombre del Artista> - Topic` con la descripción *"Auto-generated by YouTube"*. Estas pistas son réplicas exactas del máster de estudio sin ningún segundo de intro de video. El selector de resultados otorgará máxima prioridad a los resultados de estos canales.
3. **Filtro por Duración Esperada**:
   Cuando se conoce la duración oficial (por ejemplo, desde los metadatos de Spotify o de YouTube Music):
   * Si el video candidato dura más de 20 segundos por encima de la duración oficial, se asume que contiene escenas de video / intro teatral y se descarta.
   * Se selecciona el candidato cuya duración tenga la mínima diferencia absoluta respecto a la duración esperada (idealmente diferencia <= 5 segundos).

### 4. Modificaciones a la Clase `Track` y `GuildMusicPlayer`

* **Clase `Track`**:
  ```python
  class Track:
      def __init__(
          self,
          title: str,
          webpage_url: str,
          stream_url: Optional[str] = None,
          duration: int = 0,
          thumbnail: str = "",
          uploader: str = "",
          requester: str = "Desconocido",
          spotify_artist: Optional[str] = None,
      ):
          ...
          self.is_resolved: bool = stream_url is not None
  ```
* **Resolución Just-in-Time en `GuildMusicPlayer.play_next()`**:
  ```python
  if not self.current.is_resolved:
      stream_url = await self.music_service.resolve_stream_for_track(self.current)
      if not stream_url:
          logger.warning(f"No se pudo resolver stream para {self.current.title}, saltando...")
          await self.play_next()
          return
      self.current.stream_url = stream_url
      self.current.is_resolved = True
  ```

### 5. Experiencia de Usuario y Embeds en Discord (`music_cog.py`)

* **Embed para Canción Individual**:
  Mantiene el diseño actual detallado (título, duración, quien lo pidió, carátula).
* **Embed para Playlists / Álbumes**:
  Al detectar que la consulta agregó múltiples canciones (len > 1):
  * **Título**: `📋 Playlist Añadida` o `💿 Álbum Añadido`
  * **Nombre**: Título de la lista (ej: *"Today's Top Hits"*, *"Pop Music 2026"*).
  * **Detalles**: Cantidad de canciones añadidas (ej: `50 pistas`), duración total estimada.
  * **Inicio**: Si el bot no estaba reproduciendo nada, inicia la primera canción y muestra `"🎵 Reproduciendo Ahora: [Pista 1]"` con una nota de que las restantes están en la cola.
* **Comando `/stop` (Slash Command)**:
  * Se registra `@app_commands.command(name="stop", description="Detiene la música, limpia la cola y desconecta al bot.")`.
  * Detiene la reproducción en el `voice_client`, vacía la cola de reproducción del servidor con `player.clear_queue()`, desconecta el bot del canal de voz y envía un mensaje confirmando la detención.
  * Se mantiene compatible con el comando de texto `!stop` (y sus alias `!leave`, `!dc`).


# Design: Meep Bot

## Arquitectura del Sistema

Meep sigue una arquitectura modular desacoplada basada en el patrón de **Cogs** de `discord.py`. El núcleo del bot carga extensiones independientes que manejan eventos, comandos y la lógica de negocio a través de servicios dedicados.

```
+---------------------------------------------------------------+
|                           main.py                             |
|  * Inicializa Bot (Intents: voice, guilds, messages)          |
|  * Sincroniza Slash Commands (tree.sync)                      |
|  * Carga Cogs dinámicamente                                   |
+---------------------------------------------------------------+
                 |                               |
                 v                               v
+-------------------------------+ +-------------------------------+
|      cogs/lol_cog.py          | |      cogs/music_cog.py        |
|  * /champion, /counters       | |  * /play, /artist, /skip      |
|  * /live, /perfil             | |  * /queue, /shuffle, /pause   |
+-------------------------------+ +-------------------------------+
                 |                               |
                 v                               v
+-------------------------------+ +-------------------------------+
|     services/lol_service.py   | |   services/music_service.py   |
|  * Riot DataDragon API        | |  * yt-dlp Audio Extractor     |
|  * Aliases (mf -> MissFortune)| |  * FFmpeg Process Stream      |
|  * Builds & Runas Cache       | |  * Per-guild Music Queue      |
+-------------------------------+ +-------------------------------+
                 |
                 v
+-------------------------------+
|       ui/lol_views.py         |
|  * discord.ui.View            |
|  * Botones [AD] / [AP]        |
+-------------------------------+
```

---

## Estructura de Directorios

```text
bot_discord_2/
├── cogs/
│   ├── lol_cog.py            # Comandos de League of Legends
│   └── music_cog.py          # Comandos de música y reproducción
├── services/
│   ├── lol_service.py        # Conexión con DataDragon y base de builds/runas
│   └── music_service.py      # Extracción con yt-dlp y cola de reproducción
├── ui/
│   └── lol_views.py          # Componentes interactivos (Botones de variantes)
├── config.py                 # Carga de variables de entorno (.env)
├── main.py                   # Punto de entrada del bot
├── iniciar_meep.bat          # Script de arranque en Windows de un solo clic
├── requirements.txt          # Dependencias de Python
├── .env.example              # Plantilla de variables (DISCORD_TOKEN, etc.)
└── openspec/                 # Especificaciones y control OpenSpec
```

---

## Componentes Técnicos

### 1. Módulo LoL (`services/lol_service.py` & `ui/lol_views.py`)
* **DataDragon Integration**:
  * Consulta periódica de la última versión de DataDragon (`https://ddragon.leagueoflegends.com/api/versions.json`).
  * Mapeo de nombres y alias (soporta `mf` -> `MissFortune`, `tf` -> `TwistedFate`, `nunu` -> `Nunu`, `cait` -> `Caitlyn`).
  * Generación de URLs de imágenes para el icono del campeón, árboles de runas e ítems para enriquecer los Discord Embeds.
* **Sistema de Variantes y Botones (`ui/lol_views.py`)**:
  * Implementa `discord.ui.View` con botones `discord.ui.Button` estilizados (ej: estilo primario para la opción activa, secundario para la alternativa).
  * Callback asíncrono `interaction.response.edit_message()` que reemplaza los campos del embed en milisegundos sin enviar mensajes adicionales al canal.

### 2. Módulo de Música (`services/music_service.py`)
* **Pipeline de Audio**:
  * `yt-dlp`: Extrae la URL de streaming en formato directo (`bestaudio/best`) sin descargar el archivo completo al disco duro, minimizando el uso de almacenamiento.
  * Opciones de FFmpeg optimizadas para streaming (`before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'` y `options='-vn'`).
* **Cola de Reproducción (`MusicQueue`)**:
  * Objeto gestor por servidor (`guild_id`) que almacena las pistas en memoria.
  * Soporte para `shuffle` (usando `random.shuffle`), `loop` por canción o por cola completa, y salto automático al terminar la pista mediante el callback `after` de `VoiceClient.play()`.
* **Comando `/artist`**:
  * Utiliza búsqueda de canciones del artista para obtener la lista de top tracks.
  * Inserta la lista en bloque en la cola y notifica al usuario con un embed formateado.

---

## Estrategia de Configuración y Despliegue Local
* Variables en `.env`:
  * `DISCORD_TOKEN`: Token del bot creado en Discord Developer Portal.
  * `RIOT_API_KEY`: Clave de Riot Games (opcional para partidas en vivo / perfiles; DataDragon y builds funcionan sin API key).
  * `BOT_PREFIX`: Prefijo para comandos de texto (por defecto `!`).
* Lanzador en Windows (`iniciar_meep.bat`):
  * Verifica el entorno virtual o instalación de Python 3.12.
  * Instala/actualiza dependencias si es necesario.
  * Ejecuta `python main.py` manteniendo la consola abierta en caso de error.

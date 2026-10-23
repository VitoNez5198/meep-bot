# Tasks: Implementación de Meep Bot

## Fase 1: Entorno Base y Esqueleto del Bot
- [x] 1.1 Crear `requirements.txt` con las dependencias necesarias (`discord.py`, `yt-dlp`, `requests`, `aiohttp`, `python-dotenv`).
- [x] 1.2 Crear `.env.example` y `config.py` para la carga centralizada de configuraciones y tokens.
- [x] 1.3 Crear `main.py` con inicialización de intents de Discord, carga dinámica de Cogs, sincronización de comandos Slash (`tree.sync`) y manejador global de errores.
- [x] 1.4 Crear el script `iniciar_meep.bat` para ejecución local directa en Windows con un solo clic.

## Fase 2: Módulo League of Legends
- [x] 2.1 Implementar `services/lol_service.py`:
  - [x] 2.1.1 Conector a Riot DataDragon para obtener versiones, lista de campeones, nombres normalizados y mapeo de alias comunes (`mf` -> `MissFortune`, `tf` -> `TwistedFate`, etc.).
  - [x] 2.1.2 Proveedor de datos de builds, runas, orden de habilidades e ítems recomendados para la Grieta del Invocador y ARAM.
  - [x] 2.1.3 Estructuración de variantes de juego para ARAM (ej: AD vs AP vs Tanque).
- [x] 2.2 Implementar `ui/lol_views.py`:
  - [x] 2.2.1 Crear clase `BuildVariantView` heredando de `discord.ui.View` con botones interactivos (`discord.ui.Button`) para alternar estilos en el mismo mensaje.
- [x] 2.3 Implementar `cogs/lol_cog.py`:
  - [x] 2.3.1 Comando unificado `/champion <campeón> [modo_o_rol]` (y prefijo `!c`, alias `/build`), con soporte para Grieta por defecto, modo ARAM (`/champion mf aram`), y botones interactivos (`discord.ui.Button`) para alternar variantes de build al instante.
  - [x] 2.3.2 Comando `/counters <campeón>` (y prefijo `!counters`).
  - [x] 2.3.3 Comandos `/live [invocador]` y `/perfil [invocador]` (y prefijos asociados).

## Fase 3: Módulo de Música
- [x] 3.1 Implementar `services/music_service.py`:
  - [x] 3.1.1 Extractor de audio mediante `yt-dlp` en formato directo sin anuncios.
  - [x] 3.1.2 Estructura de cola de reproducción por servidor (`MusicQueue`) con soporte para shuffle, loop y control de volumen.
  - [x] 3.1.3 Resolvedor de top canciones por artista para el comando `/artist`.
- [x] 3.2 Implementar `cogs/music_cog.py`:
  - [x] 3.2.1 Comandos `/play <query>` y `/artist <nombre>` (y prefijos `!p` y `!artist`).
  - [x] 3.2.2 Comandos de control: `/pause`, `/resume`, `/skip` (`!s`), `/stop` / `/leave` (`!dc`).
  - [x] 3.2.3 Comandos de estado: `/queue` (`!q`) y `/nowplaying` (`!np`) con barra visual de progreso.
  - [x] 3.2.4 Comandos de ajuste: `/shuffle` (`!sh`), `/loop` y `/volume <1-100>`.

## Fase 4: Pruebas y Verificación
- [x] 4.1 Probar inicio local mediante `iniciar_meep.bat`.
- [x] 4.2 Verificar registro y sincronización de comandos Slash y prefijos de texto.
- [x] 4.3 Validar respuestas visuales de embeds y comportamiento de botones interactivos de LoL.
- [x] 4.4 Validar reproducción de audio y manejo de cola musical.

## Fase 5: Integración en Barra de Tareas (System Tray) y Autoarranque con Windows
- [x] 5.1 Implementar `services/tray_service.py` con `pystray`:
  - [x] 5.1.1 Icono en el área de notificación (junto al reloj) sin ventana de consola.
  - [x] 5.1.2 Menú contextual con estado (`🟢 En línea`), visor de logs, apertura de carpeta y reinicio/cierre limpio.
  - [x] 5.1.3 Opción de activar/desactivar `🚀 Iniciar con Windows` automáticamente mediante acceso directo en Startup.
- [x] 5.2 Implementar lanzador silencioso `iniciar_meep_segundo_plano.vbs` con `pythonw.exe`.
- [x] 5.3 Configurar logging a archivo rotativo `data/meep.log` para monitoreo en segundo plano.
- [x] 5.4 Documentar el modo segundo plano y autoarranque en `README.md` e `iniciar_meep.bat`.

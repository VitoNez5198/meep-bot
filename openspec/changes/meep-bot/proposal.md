# Proposal: Meep Bot (Companion Privado de LoL y Música)

## Contexto y Motivación

Actualmente, el usuario comparte un servidor privado de Discord con su pareja y amigos cercanos (hasta 4 personas). Al jugar League of Legends o escuchar música en llamadas, se presentan varios problemas:
1. **Impacto en Rendimiento de PC**: Aplicaciones de escritorio como Blitz.gg, Porofessor (Overwolf) o pestañas de Google Chrome consumen demasiada memoria RAM y CPU, provocando tirones y congelamientos ("freezes") en la computadora de su pareja mientras juega.
2. **Dependencia e Inestabilidad de Bots Públicos**: Bots gratuitos masivos de Discord (como Porofessor bot o alternativas similares) sufren caídas frecuentes de servidor o límites de cuota que dejan a los usuarios sin asistencia durante la selección de campeones.
3. **Monetización Agresiva**: Bots populares como MEE6 o servicios de música cobran suscripciones mensuales por funciones esenciales que no justifican el costo para un servidor privado de pocas personas.

## Propósito

Desarrollar **Meep**, un bot de Discord privado, ligero y modular en Python 3.12 que se ejecute localmente en la máquina del usuario mediante un ejecutable/script simple (`iniciar_meep.bat`). Meep proveerá asistencia rápida para League of Legends con cero consumo de RAM para los demás jugadores y un reproductor de música sin anuncios y sin costo.

## Alcance del Proyecto

### 1. Módulo League of Legends (`lol_cog.py`)
* **`/champion <campeón> [modo_o_rol]` (Alias: `!c`, `/build`)**: Consulta unificada de builds y runas. Si se omite el segundo parámetro entrega la build para la Grieta; si se pasa `aram` (ej: `/champion mf aram` o `!c mf aram`) entrega la build de ARAM; y si se pasa un rol (`mid`, `top`, etc.) filtra por carril.
* **Variantes de Build con Botones Interactivos (`discord.ui.Button`)**: Para campeones con múltiples estilos viables en ARAM o Normal (ej: Miss Fortune AD vs AP, Malphite Tanque vs AP), el bot enviará un embed interactivo con botones que permiten alternar la build en el mismo mensaje con un solo clic, además de permitir la sintaxis rápida por texto (`!c mf aram ap`).
* **`/counters <campeón>`**: Lista rápida de los mejores y peores enfrentamientos para facilitar bans y picks.
* **`/live [invocador]`**: Consulta del estado de partida en curso del invocador y rangos de los rivales.
* **`/perfil [invocador]`**: Estadísticas básicas de invocador, rango actual y campeones destacados.

### 2. Módulo de Música (`music_cog.py`)
* **Extracción de Audio Limpia**: Uso de `yt-dlp` y `ffmpeg` para reproducir flujos de audio directamente en canales de voz sin anuncios comerciales.
* **`/play <canción o link>` (Alias `!p`)**: Búsqueda por texto o enlace de YouTube y Spotify.
* **`/artist <nombre>` (Alias `!artist`)**: Búsqueda automática del Top 10-15 canciones más populares de un artista determinado y encolado automático por lote.
* **Gestión de Cola y Reproducción**: Comandos de control directo: `/pause`, `/resume`, `/skip` (`!s`), `/queue` (`!q`), `/nowplaying` (`!np`), `/shuffle` (`!sh`), `/loop`, `/volume` y `/stop` / `/leave` (`!dc`).

### 3. Experiencia de Usuario y Ejecución
* **Soporte Dual de Comandos**: Soporte tanto para Slash Commands (`/`) como para prefijos cortos (`!`).
* **Embeds Visuales**: Presentación enriquecida con iconos oficiales de campeones, runas e ítems de Riot DataDragon.
* **Lanzador Local Simple**: Archivo `.bat` para encender el bot con un doble clic cuando vayan a jugar los fines de semana.

## Fuera de Alcance (Non-Goals)
* Grabador o renderizador de videos de repeticiones de LoL (`.rofl` a MP4), por requerir GPU pesada y el cliente de juego abierto.
* Sistema de niveles y economía (MEE6) en la versión inicial v1 (se mantendrá la arquitectura lista para añadirlo en una fase posterior).
* Dashboard web o hosting comercial multi-tenant.

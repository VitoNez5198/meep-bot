# Spec: Music Player

## Propósito
Proveer un sistema de reproducción de música en canales de voz de Discord de alta fidelidad, sin anuncios, con soporte para búsquedas directas, enlaces de YouTube/Spotify y generación automática de listas de reproducción por artista.

## Requisitos y Comportamiento

### 1. Reproducción Básica
* **Comandos**: `/play <consulta o link>` o `!p <consulta o link>`
* **Entrada**:
  * Término de búsqueda de texto (busca en YouTube Music / YouTube).
  * Enlace de video de YouTube o YouTube Music.
  * Enlace de canción o playlist de Spotify (extrae metadatos y reproduce el audio correspondiente).
* **Comportamiento**:
  * Si el bot no está en un canal de voz, se conecta al canal del usuario que invocó el comando.
  * Si no hay nada sonando, inicia la reproducción inmediatamente.
  * Si ya hay una canción sonando, agrega la pista a la cola de reproducción y confirma con un embed que incluye título, duración y posición en cola.

### 2. Generación de Lista por Artista
* **Comandos**: `/artist <nombre del artista>` o `!artist <nombre del artista>`
* **Comportamiento**:
  * Consulta el catálogo de Spotify o YouTube Music para ubicar al artista.
  * Extrae los **10 a 15 temas más populares** (Top Tracks) de ese artista.
  * Agrega todos los temas en bloque a la cola de reproducción.
  * Envía un mensaje con la lista de temas agregados y la duración estimada total.
  * Si la cola estaba vacía, inicia la reproducción del primer tema de inmediato.

### 3. Controles de Reproducción y Cola
* **`/pause` / `!pause`**: Pausa el flujo de audio actual.
* **`/resume` / `!res`**: Reanuda el audio pausado.
* **`/skip` / `!s`**: Salta la canción actual y pasa a la siguiente pista de la cola. Si la cola está vacía, detiene la reproducción.
* **`/queue` / `!q`**: Muestra las próximas canciones en cola con paginación si supera las 10 canciones.
* **`/nowplaying` / `!np`**: Muestra la canción en curso, artista, carátula y una barra de progreso visual de reproducción (ej: `01:45 🔘───────── 03:20`).
* **`/shuffle` / `!sh`**: Mezcla aleatoriamente las canciones actualmente en cola.
* **`/loop` / `!loop [track | queue | off]`**: Configura la repetición del tema actual o de toda la lista.
* **`/volume <1-100>` / `!vol <1-100>`**: Ajusta el volumen del reproductor.
* **`/stop` o `/leave` / `!dc`**: Detiene la música, vacía la cola y desconecta el bot del canal de voz.

### 4. Filtrado de Publicidad y Rendimiento
* La extracción de audio se realiza a través de `yt-dlp` en formato directo (Opus o AAC), garantizando que no se reproduzcan anuncios de video ni clips publicitarios intercalados.

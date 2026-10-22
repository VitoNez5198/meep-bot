# 🧙‍♂️ Meep Bot — Asistente Privado de Discord (LoL & Música)

> **Tu compañero de juego en Discord para ti y tu polola:** Cero congelamiento de RAM por apps externas, sin publicidad en música y sin pagar suscripciones mensuales a bots de terceros.

---

## 🚀 Inicio Rápido en 3 Pasos

### Paso 1: Configurar el Token de Discord
1. Entra a [Discord Developer Portal](https://discord.com/developers/applications) e inicia sesión.
2. Haz clic en **"New Application"** y ponle de nombre **Meep** (o el que gustes).
3. En el menú de la izquierda ve a **"Bot"**:
   - En **"Privileged Gateway Intents"**, activa:
     - ✅ **Message Content Intent** (para que reconozca comandos cortos como `!c`, `!p`).
     - ✅ **Server Members Intent** (opcional, recomendado).
   - Haz clic en **"Reset Token"** y copia el token generado.
4. En la carpeta de este proyecto, copia el archivo `.env.example` y renómbralo a `.env`.
5. Abre el `.env` con el Bloc de Notas y pega tu token:
   ```env
   DISCORD_TOKEN=tu_token_aqui
   ```

### Paso 2: Invitar a Meep a tu Servidor
1. En el mismo Developer Portal, ve a **OAuth2** -> **URL Generator**.
2. En **SCOPES** marca:
   - ✅ `bot`
   - ✅ `applications.commands` (para los comandos Slash `/`)
3. En **BOT PERMISSIONS** marca:
   - ✅ `Send Messages`
   - ✅ `Embed Links`
   - ✅ `Connect` (Conectar al canal de voz)
   - ✅ `Speak` (Hablar / reproducir música)
4. Copia la URL generada al final, ábrela en tu navegador y selecciona tu servidor de Discord.

### Paso 3: ¡Listo! Encender a Meep
Haz **doble clic en `iniciar_meep.bat`**. ¡Meep entrará a tu Discord de inmediato!

---

## 🎮 Guía de Comandos

### ⚔️ League of Legends
> Todos los comandos muestran runas, habilidades e ítems oficiales de Riot DataDragon con **cero consumo de memoria en la PC de tu polola**.

* **`/champion <campeón> [modo_o_rol]`** (Alias: `!c <campeón>` o `/build`):
  * **Grieta del Invocador (Normal):** `/champion missfortune` o `!c mf`
  * **ARAM:** `/champion missfortune aram` o `!c mf aram`
  * **Botones Interactivos de Estilo:** Si el campeón tiene variantes (ej: Miss Fortune AD vs AP, Malphite Tanque vs AP), Meep muestra botones interactivos en el chat:
    ```
    [ 🏹 AD / Letalidad (Activo) ]   [ 🔮 AP / Poke ]
    ```
    ¡Con un solo clic cambia la build en tiempo real!
* **`/counters <campeón>`** (Alias: `!counters <campeón>`):
  * Muestra los 3 mejores y 3 peores enfrentamientos para planificar picks y bans.
* **`/live [invocador]`** (Alias: `!live`):
  * Consulta la partida en vivo (requiere agregar tu clave gratuita de Riot a `RIOT_API_KEY` en `.env`).

---

### 🎵 Música (Sin Anuncios)
> Extrae audio de alta calidad directamente con `yt-dlp` y `ffmpeg`. Sin cortes publicitarios.

* **`/play <canción o link>`** (Alias: `!p <canción>`):
  * Reproduce canciones por búsqueda de texto o enlaces directos de YouTube / Spotify.
* **`/artist <nombre del artista>`** (Alias: `!artist <artista>`):
  * **¡Modo Grandes Éxitos!** Busca automáticamente las 10-15 canciones más populares del artista y las encola todas de una vez (ideal para jugar 40+ min de Bad Bunny, Dua Lipa, etc.).
* **`/skip`** (`!s`): Salta a la siguiente pista.
* **`/pause` / `/resume`** (`!pause` / `!res`): Pausa y reanuda el audio.
* **`/queue`** (`!q`): Muestra la lista de canciones en espera y duración restante.
* **`/nowplaying`** (`!np`): Muestra qué suena con una barra de progreso visual (`01:23 🔘────── 03:45`).
* **`/shuffle`** (`!sh`): Mezcla aleatoriamente las canciones en cola.
* **`/loop [off/track/queue]`**: Repite la canción actual o toda la lista.
* **`/volume <1-100>`** (`!vol`): Ajusta el volumen.
* **`/disconnect`** (`!dc`): Detiene la música y desconecta al bot del canal de voz.

---

## 🛠️ Estructura del Código
```text
bot_discord_2/
├── cogs/
│   ├── lol_cog.py            # Comandos de LoL (Slash y Prefijos)
│   └── music_cog.py          # Comandos de Música y control de voz
├── services/
│   ├── lol_service.py        # DataDragon, alias y variantes de ARAM
│   └── music_service.py      # yt-dlp, FFmpeg y gestor de colas
├── ui/
│   └── lol_views.py          # Botones interactivos de Discord (discord.ui.Button)
├── config.py                 # Configuración centralizada
├── main.py                   # Inicializador del Bot
├── iniciar_meep.bat          # Lanzador en Windows con doble clic
├── requirements.txt          # Dependencias
└── .env                      # Tus tokens privados
```

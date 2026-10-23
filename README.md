# 🧙‍♂️ Meep Bot — Asistente de Discord (League of Legends & Música)

> **Tu compañero de juego en Discord:** Cero congelamiento de RAM por aplicaciones pesadas en segundo plano, música sin anuncios con botonera interactiva en vivo, modo radio con filtro anti-remixes y estadísticas en tiempo real de OP.GG y Riot DataDragon.

---

## ✨ Características Principales

### ⚔️ League of Legends
* **Builds Instantáneas con Variantes:** Soporte completo para Grieta del Invocador y **ARAM**. Si un campeón tiene múltiples estilos viables (ej. *Miss Fortune AD Letalidad* vs *AP Poke* o *Malphite Tanque* vs *AP One-Shot*), el bot despliega **botones interactivos** para alternar builds y runas con un solo clic.
* **Counters en Vivo desde OP.GG:** Consulta enfrentamientos favorables y desfavorables calculados con datos del parche actual.
* **Perfil de Invocador:** Rango, división, LP, winrate global y campeones más jugados directamente desde OP.GG (soporta LAS, LAN, BR, NA, EUW, KR, etc.).
* **Partida en Vivo:** Muestra información de los jugadores en la partida actual mediante la API de Riot Games.

### 🎵 Música de Alta Fidelidad
* **Fuentes Múltiples:** Reproduce canciones individuales, álbumes o playlists completas de **YouTube**, **YouTube Music** y **Spotify**.
* **Botonera Interactiva en Vivo (`MusicControlView`):** Cada canción muestra una botonera con 6 controles instantáneos:
  ```
  [ ⏸️ Pausar / ▶️ Reanudar ] [ ⏭️ Saltar ] [ 📻 Radio: ON/OFF ] [ 🔀 Mezclar ] [ ⏹️ Detener ] [ 📜 Ver Cola ]
  ```
  El embed y los botones se actualizan automáticamente en tiempo real al cambiar de pista.
* **Modo Radio (Autoplay Inteligente):** Al terminar la cola o activarlo manualmente, el bot busca automáticamente canciones similares del mismo artista o género, aplicando un **filtro inteligente anti-remixes** (descarta mezclas largas de DJ, enganchados de 1 hora y prefiere versiones oficiales de estudio / *Topic*).
* **Modo Grandes Éxitos (`/artist`):** Encola automáticamente las 10 a 15 canciones más populares de cualquier artista.
* **Búsqueda y Salto Rápido:**
  * `/jump <número>` (o `!jump`): Salta directamente a cualquier posición de la cola con mensaje limpio y autocompletado nativo en Discord.
  * `/find <texto>` (o `!find`): Busca coincidencias por título o artista dentro de listas largas y te dice exactamente qué número de posición tienen.
* **Navegación Paginada de Cola (`/queue`):** Navega por páginas con botones `[ ◀️ Anterior ]` y `[ Siguiente ▶️ ]` sin saturar el canal de texto.

### 🖥️ Integración con Windows (System Tray)
* **Ejecución Silenciosa:** Se puede ejecutar en segundo plano sin ventanas de consola visibles mediante `iniciar_meep_segundo_plano.vbs`.
* **Icono en la Bandeja del Sistema (junto al reloj):** Menú contextual con clic derecho para ver estado, abrir logs en vivo, reiniciar, abrir la carpeta del bot y activar el **inicio automático con Windows**.

---

## 🚀 Inicio Rápido

### 1. Requisitos Previos
* **Python 3.10 o superior**: [python.org](https://www.python.org/) (asegúrate de marcar *"Add Python to PATH"* durante la instalación).
* **FFmpeg**: Necesario para la decodificación de audio.
  * Si ya lo tienes instalado en el sistema (`ffmpeg` en el PATH), el bot lo detectará automáticamente.
  * Opcionalmente, puedes colocar `ffmpeg.exe` dentro de una carpeta llamada `bin/` en la raíz del proyecto.

### 2. Instalación de Dependencias
Abre una terminal en la carpeta del proyecto y ejecuta:
```bash
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno (`.env`)
1. Copia el archivo de plantilla `.env.example` y renómbralo como `.env`:
   ```bash
   cp .env.example .env
   ```
2. Abre `.env` con cualquier editor de texto y completa tus credenciales:
   ```env
   # Token de tu bot de Discord (Obligatorio)
   DISCORD_TOKEN=tu_token_aqui

   # Prefijo para comandos de texto tradicionales (Opcional, por defecto es !)
   BOT_PREFIX=!

   # Clave de API de Riot Games (Opcional - solo requerida para /live)
   RIOT_API_KEY=

   # ID de tu Servidor de Discord para registro instantáneo de comandos Slash (Opcional)
   DEV_GUILD_ID=
   ```

### 4. Permisos del Bot en Discord Developer Portal
Al crear y configurar tu bot en [Discord Developer Portal](https://discord.com/developers/applications):
* En la pestaña **Bot** > **Privileged Gateway Intents**, activa:
  * ✅ **Message Content Intent** (necesario para comandos con prefijo como `!c`, `!p`, `!jump`).
  * ✅ **Server Members Intent** (recomendado).
* En **OAuth2** > **URL Generator**, selecciona los scopes:
  * `bot` y `applications.commands`
* Y los permisos mínimos:
  * `Send Messages`, `Embed Links`, `Attach Files`, `Connect`, `Speak`, `Use External Emojis`.

---

## 🕹️ Modos de Ejecución

### Opción A: Modo Silencioso en Bandeja del Sistema (Recomendado)
Haz doble clic en **`iniciar_meep_segundo_plano.vbs`**.
* No se abrirá ninguna ventana negra de consola.
* Aparecerá el icono de Meep en el área de notificación de Windows (junto al reloj).
* Haz **clic derecho en el icono** para:
  * 🟢 Ver estado de conexión.
  * 🚀 **Iniciar con Windows**: Activa o desactiva el arranque automático.
  * 📜 **Ver Logs en vivo**: Abre el archivo `data/meep.log`.
  * 🔄 **Reiniciar Meep**.
  * ❌ **Salir**.

### Opción B: Modo Consola
Haz doble clic en **`iniciar_meep.bat`** o ejecuta:
```bash
python main.py
```
Ideal para ver la consola de depuración en tiempo real mientras realizas pruebas.

---

## 📖 Lista Completa de Comandos

Todos los comandos están disponibles como **Comandos Slash (`/`)** y como **Comandos de Texto con prefijo (`!`)**.

### ⚔️ Comandos de League of Legends
| Comando Slash | Comando Texto | Descripción |
| :--- | :--- | :--- |
| `/champion <campeón> [modo]` | `!c <campeón> [modo]` | Muestra build, runas y habilidades. Soporta alias (`mf`, `tf`, `lee`) y modo `aram`. Despliega botones interactivos si hay variantes de estilo. |
| `/counters <campeón>` | `!counters <campeón>` | Muestra mejores y peores enfrentamientos y winrates de OP.GG. |
| `/perfil <invocador> [servidor]` | `!perfil <invocador> [servidor]` | Muestra elo, división, LP y campeones más jugados de OP.GG (soporta LAS, LAN, NA, KR, etc.). |
| `/live [invocador]` | `!live [invocador]` | Muestra el estado de la partida en vivo (requiere Riot API Key). |

### 🎵 Comandos de Música
| Comando Slash | Comando Texto | Descripción |
| :--- | :--- | :--- |
| `/play <búsqueda o enlace>` | `!p <búsqueda o enlace>` | Reproduce canciones o playlists de YouTube, YouTube Music y Spotify. Muestra la botonera interactiva en vivo. |
| `/artist <artista>` | `!artist <artista>` | Encola automáticamente las 10-15 canciones más populares del artista. |
| `/radio [activar/desactivar]` | `!radio` | Activa o desactiva el modo Radio con autoplay continuo y filtro anti-remixes. |
| `/jump <posición>` | `!jump <posición>` | Salta directamente al número de canción en la cola. Cuenta con autocompletado nativo. |
| `/find <texto>` | `!find <texto>` | Busca canciones o artistas en la cola e indica sus números de posición. |
| `/queue` | `!q` / `!queue` | Muestra la lista de reproducción con botones de paginación interactiva. |
| `/skip` | `!s` / `!skip` | Salta a la siguiente canción en la cola. |
| `/skipplaylist` | `!sp` | Salta todas las canciones restantes de la playlist actual. |
| `/nowplaying` | `!np` | Muestra la canción sonando ahora con barra de progreso interactiva. |
| `/pause` / `/resume` | `!pause` / `!resume` | Pausa o reanuda la reproducción. |
| `/stop` | `!stop` | Detiene la música, desactiva la radio y vacía la cola sin desconectar al bot. |
| `/disconnect` | `!dc` / `!leave` | Detiene la reproducción y desconecta al bot del canal de voz. |
| `/shuffle` | `!sh` / `!shuffle` | Mezcla aleatoriamente las canciones en la cola. |
| `/loop [modo]` | `!loop [modo]` | Configura el modo de repetición (`off`, `track`, `queue`). |
| `/volume <1-100>` | `!vol <1-100>` | Ajusta el volumen del reproductor de audio. |

---

## 📂 Estructura del Repositorio

```text
bot_discord_2/
├── cogs/
│   ├── lol_cog.py                 # Comandos Slash y prefijos de League of Legends
│   └── music_cog.py               # Comandos Slash y prefijos de Música
├── services/
│   ├── emoji_service.py           # Gestor y caché de emojis de aplicación de Discord
│   ├── lol_service.py             # Scraping de OP.GG, DataDragon y alias de campeones
│   ├── music_service.py           # yt-dlp, FFmpeg, motor de cola y algoritmo de radio
│   └── tray_service.py            # Integración de System Tray en Windows y auto-arranque
├── ui/
│   ├── lol_views.py               # Vistas y botones interactivos para builds de LoL
│   └── music_views.py             # Botonera interactiva de reproducción y paginación de cola
├── data/
│   ├── meep_icon.png              # Icono oficial para la bandeja del sistema
│   ├── meep_icon.ico              # Icono en formato ICO para accesos directos
│   └── rank_emojis.json           # Mapeo de emojis para rangos de LoL
├── config.py                      # Constantes globales y lectura de .env
├── main.py                        # Punto de entrada principal e inicializador del bot
├── iniciar_meep.bat               # Lanzador con ventana de consola visible
├── iniciar_meep_segundo_plano.vbs # Lanzador silencioso en bandeja del sistema
├── requirements.txt               # Dependencias de Python
├── .env.example                   # Plantilla de configuración privada
└── .gitignore                     # Exclusión de archivos sensibles, temporales y caché
```

---

## 🔒 Seguridad y Privacidad
* El archivo `.env` está estrictamente ignorado en `.gitignore` para evitar filtraciones accidentales de credenciales o tokens a GitHub.
* Ningún archivo de caché de imágenes, logs ni scripts de prueba temporales (`scratch/`) se sube al repositorio remoto.

"""
Configuración centralizada para el bot Meep.
Carga variables de entorno desde .env y define constantes globales.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables del archivo .env en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Configuración de Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
BOT_PREFIX = os.getenv("BOT_PREFIX", "!").strip()
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID", "").strip()
DEV_GUILD_ID = int(DEV_GUILD_ID) if DEV_GUILD_ID.isdigit() else None

# Configuración de Riot Games API (Opcional para live/perfil)
RIOT_API_KEY = os.getenv("RIOT_API_KEY", "").strip()

# Rutas del sistema
BIN_DIR = BASE_DIR / "bin"
FFMPEG_EXE = "ffmpeg"  # Por defecto busca en PATH, se puede sobreescribir con ruta a bin/ffmpeg.exe

# Si existe ffmpeg.exe dentro de la carpeta bin/ del proyecto, usarlo prioritariamente
local_ffmpeg = BIN_DIR / "ffmpeg.exe"
if local_ffmpeg.exists():
    FFMPEG_EXE = str(local_ffmpeg)

# Colores temáticos para Embeds (Estilo Bardo / Meep místico)
COLOR_MEEP = 0xF1C40F      # Dorado místico
COLOR_LOL = 0x0AC8B9       # Cyan Hextech de League of Legends
COLOR_ARAM = 0x1E90FF      # Azul gélido de Abismo de los Lamentos
COLOR_MUSIC = 0x9B59B6     # Púrpura melódico
COLOR_ERROR = 0xE74C3C     # Rojo de error
COLOR_SUCCESS = 0x2ECC71   # Verde de éxito

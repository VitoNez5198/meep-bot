"""
Servicio de Bandeja del Sistema (System Tray) para Meep Bot.
Permite ejecutar el bot minimizado en el área de notificación de Windows (junto al reloj),
con menú interactivo para ver logs, iniciar con Windows, reiniciar y cerrar.
"""

import os
import sys
import asyncio
import subprocess
import logging
from typing import Optional
import pystray
from PIL import Image, ImageDraw
import discord

logger = logging.getLogger("meep.tray")

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ICON_PATH = os.path.join(PROJECT_DIR, "data", "meep_icon.png")
LOG_PATH = os.path.join(PROJECT_DIR, "data", "meep.log")

STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup"
)
STARTUP_VBS = os.path.join(STARTUP_DIR, "MeepBot.vbs")


def is_autostart_enabled() -> bool:
    """Verifica si el bot está configurado para iniciar automáticamente con Windows."""
    return os.path.exists(STARTUP_VBS)


def set_autostart(enable: bool):
    """Activa o desactiva el inicio automático con Windows."""
    try:
        if enable:
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = "pythonw.exe"

            # Crear VBS silencioso en la carpeta de inicio de Windows
            content = (
                f'Set WshShell = CreateObject("WScript.Shell")\n'
                f'WshShell.CurrentDirectory = "{PROJECT_DIR}"\n'
                f'WshShell.Run """{pythonw}""" & " main.py", 0, False\n'
            )
            with open(STARTUP_VBS, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Inicio automático con Windows ACTIVADO.")
        else:
            if os.path.exists(STARTUP_VBS):
                os.remove(STARTUP_VBS)
                logger.info("Inicio automático con Windows DESACTIVADO.")
    except Exception as e:
        logger.error(f"Error configurando inicio automático con Windows: {e}")


def _ensure_icon_exists() -> str:
    """Asegura que el icono de Meep exista en data/meep_icon.png."""
    if os.path.exists(ICON_PATH):
        return ICON_PATH

    os.makedirs(os.path.dirname(ICON_PATH), exist_ok=True)
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, 58, 58), fill=(245, 185, 66, 255), outline=(210, 140, 20, 255), width=2)
    draw.polygon([(20, 8), (14, 0), (25, 5)], fill=(245, 185, 66, 255))
    draw.polygon([(44, 8), (50, 0), (39, 5)], fill=(245, 185, 66, 255))
    draw.ellipse((20, 24, 28, 36), fill=(30, 20, 50, 255))
    draw.ellipse((36, 24, 44, 36), fill=(30, 20, 50, 255))
    draw.ellipse((22, 26, 26, 30), fill=(255, 255, 255, 255))
    draw.ellipse((38, 26, 42, 30), fill=(255, 255, 255, 255))
    draw.ellipse((14, 34, 20, 38), fill=(255, 130, 120, 180))
    draw.ellipse((44, 34, 50, 38), fill=(255, 130, 120, 180))
    draw.arc((28, 32, 36, 40), start=0, end=180, fill=(30, 20, 50, 255), width=2)
    img.save(ICON_PATH, format="PNG")
    return ICON_PATH


class TrayManager:
    def __init__(self, bot: Optional[discord.Client] = None):
        self.bot = bot
        self.icon: Optional[pystray.Icon] = None
        self._status_text = "🟡 Conectando a Discord..."

    def set_bot(self, bot: discord.Client):
        self.bot = bot

    def _build_menu(self):
        """Construye el menú contextual de la bandeja del sistema."""
        def on_open_logs(icon, item):
            if os.path.exists(LOG_PATH):
                os.startfile(LOG_PATH)
            else:
                os.startfile(PROJECT_DIR)

        def on_open_folder(icon, item):
            os.startfile(PROJECT_DIR)

        def on_toggle_autostart(icon, item):
            new_state = not is_autostart_enabled()
            set_autostart(new_state)
            if self.icon:
                self.icon.menu = self._build_menu()
                self.icon.update_menu()

        def on_restart(icon, item):
            logger.info("Reiniciando Meep Bot...")
            python_exe = sys.executable
            if self.icon:
                self.icon.stop()
            if self.bot and not self.bot.is_closed() and self.bot.loop and self.bot.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.bot.close(), self.bot.loop)
            subprocess.Popen([python_exe, os.path.join(PROJECT_DIR, "main.py")])
            os._exit(0)

        def on_exit(icon, item):
            logger.info("Cerrando Meep Bot desde la bandeja del sistema...")
            if self.icon:
                self.icon.stop()
            if self.bot and not self.bot.is_closed() and self.bot.loop and self.bot.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.bot.close(), self.bot.loop)
            os._exit(0)

        return pystray.Menu(
            pystray.MenuItem(f"Meep Bot ({self._status_text})", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📜 Ver Logs en vivo", on_open_logs),
            pystray.MenuItem("📂 Abrir Carpeta del Bot", on_open_folder),
            pystray.MenuItem(
                "🚀 Iniciar con Windows",
                on_toggle_autostart,
                checked=lambda item: is_autostart_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🔄 Reiniciar Meep", on_restart),
            pystray.MenuItem("❌ Salir", on_exit),
        )

    def set_status(self, text: str):
        self._status_text = text
        if self.icon:
            try:
                self.icon.title = f"Meep Bot - {text}"
                self.icon.menu = self._build_menu()
                self.icon.update_menu()
            except Exception:
                pass

    def start(self):
        """Inicia el icono de la bandeja del sistema en segundo plano."""
        try:
            icon_file = _ensure_icon_exists()
            image = Image.open(icon_file)

            self.icon = pystray.Icon(
                "MeepBot",
                image,
                f"Meep Bot - {self._status_text}",
                menu=self._build_menu()
            )
            self.icon.run_detached()
            logger.info("Icono de bandeja del sistema (System Tray) activado.")
        except Exception as e:
            logger.warning(f"No se pudo iniciar el icono de la bandeja del sistema: {e}")

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


tray_manager = TrayManager()

"""
Servicio de Gestión de Emojis de Discord para Meep Bot.
Crea y administra dinámicamente Application Emojis en Discord para objetos y runas
de League of Legends utilizando rotación LRU (máx 48 emojis).
"""

import io
import re
import unicodedata
import logging
import asyncio
from typing import Dict, List, Optional
import requests
from PIL import Image
import discord

from services.lol_service import lol_service

logger = logging.getLogger("meep.emoji")

DDRAGON_BASE_CDN = "https://ddragon.leagueoflegends.com/cdn"


def _normalize_name(text: str) -> str:
    """Normaliza texto para búsqueda de runas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r"[^a-zA-Z0-9]", "", clean).lower()


class EmojiService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._cache: Dict[str, discord.Emoji] = {}
        self._usage_order: List[str] = []
        self._runes_catalog: Dict[str, str] = {}  # norm_name -> icon_path
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self, version: Optional[str] = None):
        """Carga el catálogo de runas y sincroniza emojis existentes en la aplicación."""
        if not version:
            version = lol_service.latest_version

        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # 1. Cargar catálogo de runas desde DataDragon
            try:
                url = f"{DDRAGON_BASE_CDN}/{version}/data/es_ES/runesReforged.json"
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    trees = res.json()
                    for t in trees:
                        norm_tree = _normalize_name(t.get("name", ""))
                        self._runes_catalog[norm_tree] = t.get("icon", "")
                        for slot in t.get("slots", []):
                            for r in slot.get("runes", []):
                                norm_name = _normalize_name(r.get("name", ""))
                                norm_key = _normalize_name(r.get("key", ""))
                                self._runes_catalog[norm_name] = r.get("icon", "")
                                self._runes_catalog[norm_key] = r.get("icon", "")
                                self._runes_catalog[str(r.get("id"))] = r.get("icon", "")
                    logger.info(f"Catálogo de runas cargado: {len(self._runes_catalog)} variantes.")
            except Exception as e:
                logger.warning(f"Error cargando catálogo de runas: {e}")

            # 2. Sincronizar emojis de la aplicación en Discord
            try:
                app_emojis = await self.bot.fetch_application_emojis()
                for em in app_emojis:
                    self._cache[em.name] = em
                    self._usage_order.append(em.name)
                logger.info(f"EmojiService sincronizado con {len(self._cache)} emojis existentes.")
            except Exception as e:
                logger.warning(f"Error sincronizando emojis de aplicación: {e}")

            self._initialized = True

    async def get_item_emoji(self, item_id: str, version: str) -> str:
        """Obtiene o crea un emoji de Discord para un objeto de LoL."""
        if not self._initialized:
            await self.initialize(version)

        emoji_name = f"i_{item_id}"

        async with self._lock:
            # Si ya está en caché
            if emoji_name in self._cache:
                if emoji_name in self._usage_order:
                    self._usage_order.remove(emoji_name)
                self._usage_order.append(emoji_name)
                return str(self._cache[emoji_name])

            # Si necesitamos hacer espacio (máximo 48 emojis para margen de seguridad)
            if len(self._cache) >= 48 and self._usage_order:
                oldest_name = self._usage_order.pop(0)
                old_em = self._cache.pop(oldest_name, None)
                if old_em:
                    try:
                        await old_em.delete()
                        logger.info(f"Emoji {oldest_name} rotado (eliminado) para liberar espacio.")
                    except Exception as ex:
                        logger.warning(f"Error eliminando emoji antiguo {oldest_name}: {ex}")

            # Descargar y subir el nuevo emoji
            try:
                url = f"{DDRAGON_BASE_CDN}/{version}/img/item/{item_id}.png"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).convert("RGBA").resize((44, 44))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)

                    new_em = await self.bot.create_application_emoji(
                        name=emoji_name,
                        image=buf.getvalue(),
                    )
                    self._cache[emoji_name] = new_em
                    self._usage_order.append(emoji_name)
                    logger.info(f"Creado emoji para item {item_id}: {new_em}")
                    return str(new_em)
            except Exception as e:
                logger.warning(f"No se pudo crear emoji para item {item_id}: {e}")

        # Fallback elegante
        return "📦"

    async def get_rune_emoji(self, rune_name: str, version: str) -> str:
        """Obtiene o crea un emoji de Discord para una runa de LoL."""
        if not self._initialized:
            await self.initialize(version)

        clean_name = _normalize_name(rune_name)
        icon_path = self._runes_catalog.get(clean_name)
        if not icon_path:
            # Buscar coincidencia parcial
            for k, path in self._runes_catalog.items():
                if clean_name in k or k in clean_name:
                    icon_path = path
                    break

        if not icon_path:
            return "🔹"

        # Nombre de emoji alfanumérico corto (máx 32 caracteres)
        emoji_name = f"r_{clean_name[:26]}"

        async with self._lock:
            if emoji_name in self._cache:
                if emoji_name in self._usage_order:
                    self._usage_order.remove(emoji_name)
                self._usage_order.append(emoji_name)
                return str(self._cache[emoji_name])

            if len(self._cache) >= 48 and self._usage_order:
                oldest_name = self._usage_order.pop(0)
                old_em = self._cache.pop(oldest_name, None)
                if old_em:
                    try:
                        await old_em.delete()
                    except Exception:
                        pass

            try:
                url = f"{DDRAGON_BASE_CDN}/img/{icon_path}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).convert("RGBA").resize((44, 44))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)

                    new_em = await self.bot.create_application_emoji(
                        name=emoji_name,
                        image=buf.getvalue(),
                    )
                    self._cache[emoji_name] = new_em
                    self._usage_order.append(emoji_name)
                    return str(new_em)
            except Exception as e:
                logger.warning(f"No se pudo crear emoji para runa {rune_name}: {e}")

        return "🔹"


_emoji_service_instance: Optional[EmojiService] = None


def get_emoji_service(bot: discord.Client) -> EmojiService:
    global _emoji_service_instance
    if _emoji_service_instance is None:
        _emoji_service_instance = EmojiService(bot)
    return _emoji_service_instance

"""
Generador de tarjeta visual gráfica de Objetos y Habilidades para League of Legends.
Utiliza Pillow para componer una imagen con los iconos reales de DataDragon.
"""

import io
import os
import logging
from typing import List, Optional
import requests
from PIL import Image, ImageDraw, ImageFont
import discord

logger = logging.getLogger("meep.card")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "icons")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get_cached_image(url: str, filename: str) -> Image.Image:
    """Descarga y cachea localmente un icono de DataDragon."""
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.exists(filepath):
        try:
            return Image.open(filepath).convert("RGBA")
        except Exception:
            pass

    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(r.content)
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"Error descargando icono desde {url}: {e}")

    # Fallback transparente o gris oscuro
    return Image.new("RGBA", (48, 48), (35, 38, 48, 255))


def generate_build_card_file(
    version: str,
    starter_item_ids: List[str],
    core_item_ids: List[str],
    situational_item_ids: List[str],
    spell_icons: List[str],
) -> Optional[discord.File]:
    """
    Genera un banner visual con los iconos oficiales de los objetos y habilidades.
    Retorna un objeto discord.File listo para adjuntar en un Embed de Discord.
    """
    try:
        width, height = 760, 150
        card = Image.new("RGBA", (width, height), (22, 25, 35, 255))
        draw = ImageDraw.Draw(card)

        # Borde exterior redondeado y sutil estilo Discord Dark
        draw.rounded_rectangle(
            [(0, 0), (width - 1, height - 1)],
            radius=12,
            outline=(45, 55, 75, 255),
            width=2,
        )

        try:
            font_title = ImageFont.truetype("arial.ttf", 12)
            font_badge = ImageFont.truetype("arial.ttf", 10)
        except Exception:
            font_title = ImageFont.load_default()
            font_badge = ImageFont.load_default()

        # -------------------------------------------------------------
        # Sección 1: Starter Items (X: 20)
        # -------------------------------------------------------------
        draw.text((20, 15), "OBJETOS DE INICIO", fill=(160, 175, 200), font=font_title)
        x = 20
        for i_id in starter_item_ids[:4]:
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{i_id}.png"
            img = _get_cached_image(url, f"item_{i_id}.png").resize((44, 44))
            card.paste(img, (x, 40))
            draw.rectangle([(x, 40), (x + 44, 40 + 44)], outline=(60, 70, 90), width=1)
            x += 49

        # Separador 1
        draw.line([(220, 20), (220, 130)], fill=(40, 48, 65), width=1)

        # -------------------------------------------------------------
        # Sección 2: Core Items con Borde Dorado Hextech (X: 235)
        # -------------------------------------------------------------
        draw.text((235, 15), "OBJETOS CORE (ESENCIALES)", fill=(241, 196, 15), font=font_title)
        x = 235
        for i_id in core_item_ids[:3]:
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{i_id}.png"
            img = _get_cached_image(url, f"item_{i_id}.png").resize((48, 48))
            card.paste(img, (x, 38))
            draw.rectangle([(x - 2, 36), (x + 50, 38 + 50)], outline=(241, 196, 15), width=2)
            x += 60

        # Separador 2
        draw.line([(430, 20), (430, 130)], fill=(40, 48, 65), width=1)

        # -------------------------------------------------------------
        # Sección 3: Situacionales (X: 445)
        # -------------------------------------------------------------
        draw.text((445, 15), "SITUACIONALES", fill=(160, 175, 200), font=font_title)
        x = 445
        for i_id in situational_item_ids[:3]:
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{i_id}.png"
            img = _get_cached_image(url, f"item_{i_id}.png").resize((44, 44))
            card.paste(img, (x, 40))
            draw.rectangle([(x, 40), (x + 44, 40 + 44)], outline=(60, 70, 90), width=1)
            x += 49

        # Separador 3
        draw.line([(600, 20), (600, 130)], fill=(40, 48, 65), width=1)

        # -------------------------------------------------------------
        # Sección 4: Habilidades Q, W, E, R (X: 615)
        # -------------------------------------------------------------
        draw.text((615, 15), "HABILIDADES", fill=(10, 200, 185), font=font_title)
        x = 615
        skill_keys = ["Q", "W", "E", "R"]
        for idx, s_icon in enumerate(spell_icons[:4]):
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{s_icon}"
            img = _get_cached_image(url, s_icon).resize((30, 30))
            card.paste(img, (x, 45))
            draw.rectangle([(x, 45), (x + 30, 45 + 30)], outline=(60, 70, 90), width=1)
            draw.text((x + 10, 80), skill_keys[idx], fill=(220, 230, 245), font=font_badge)
            x += 34

        # Convertir a bytes para Discord File
        buf = io.BytesIO()
        card.save(buf, format="PNG")
        buf.seek(0)
        return discord.File(fp=buf, filename="build_card.png")

    except Exception as e:
        logger.error(f"Error generando tarjeta gráfica de build: {e}", exc_info=True)
        return None

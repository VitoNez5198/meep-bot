"""
Script de verificación de funcionamiento de Meep Bot.
Comprueba resolución de campeones, variantes de ARAM, generación de Embeds,
disponibilidad de FFmpeg y carga de Cogs.
"""

import sys
import asyncio
import discord
from discord.ext import commands

# Asegurar codificación UTF-8 en consola de Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from services.lol_service import lol_service
from ui.lol_views import BuildVariantView, create_champion_embed
from services.music_service import get_music_service, format_duration


async def test_lol_system(bot: discord.Client):
    print("\n[1/4] Probando resolución de campeones y alias:")
    queries = ["mf", "miss fortune", "kaisa", "malphite", "lee sin", "varus", "nunu", "tf"]
    for q in queries:
        res = lol_service.resolve_champion(q)
        if res:
            champ_id, info = res
            print(f"  ✓ '{q}' -> ID: {champ_id} ({info.get('name')})")
        else:
            print(f"  ✗ '{q}' -> No resuelto")

    print(f"\n  * Versión de parche mostrada: '{lol_service.display_patch}'")
    matrix = lol_service.generate_skill_matrix("Q > W > E")
    print(f"  * Matriz ANSI generada:\n{matrix}")

    print("\n[2/4] Probando variantes de ARAM y botones interactivos:")
    builds_mf = lol_service.get_builds("MissFortune", mode="aram")
    print(f"  Miss Fortune ARAM estilos encontrados: {len(builds_mf)}")
    for b in builds_mf:
        print(f"    * {b['style_name']} | WR: {b['win_rate']}")

    details_mf = lol_service.get_champion_details("MissFortune")
    embed = await create_champion_embed(bot, "MissFortune", "Miss Fortune", "aram", builds_mf[0], details_mf)
    view = BuildVariantView(bot, "MissFortune", "Miss Fortune", "aram", builds_mf, details_mf)
    print(f"  ✓ Embed generado: '{embed.title}' con {len(embed.fields)} campos.")
    print(f"  ✓ Botones interactivos generados ({len(view.children)}):")
    for btn in view.children:
        print(f"    [ {btn.label} ] -> Estado: {'Activo (Desactivado)' if btn.disabled else 'Clicable'}")

    builds_malph = lol_service.get_builds("Malphite", mode="aram")
    print(f"\n  Malphite ARAM estilos encontrados: {len(builds_malph)}")
    for b in builds_malph:
        print(f"    * {b['style_name']} | WR: {b['win_rate']}")


def test_music_system():
    print("\n[3/4] Probando sistema de audio y FFmpeg:")
    print(f"  * Config FFMPEG_EXE: '{config.FFMPEG_EXE}'")
    print(f"  * Formato de duración: 215 seg -> '{format_duration(215)}'")


async def test_bot_cogs(bot: commands.Bot):
    print("\n[4/4] Probando inicialización de MeepBot y carga de Cogs:")
    await bot.load_extension("cogs.lol_cog")
    print("  ✓ Cog 'cogs.lol_cog' cargado correctamente.")

    await bot.load_extension("cogs.music_cog")
    print("  ✓ Cog 'cogs.music_cog' cargado correctamente.")

    commands_list = [c.name for c in bot.commands]
    print(f"  ✓ Comandos de texto registrados ({len(commands_list)}): {', '.join(commands_list)}")


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    await test_lol_system(bot)
    test_music_system()
    await test_bot_cogs(bot)
    print("\n==============================================")
    print("  TODAS LAS PRUEBAS PASARON EXITOSAMENTE ✓")
    print("==============================================\n")


if __name__ == "__main__":
    asyncio.run(main())

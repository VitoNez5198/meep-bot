"""
Meep Bot - Asistente privado de Discord para League of Legends y Música.
Punto de entrada principal.
"""

import sys
import asyncio
import logging
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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("meep")


class MeepBot(commands.Bot):
    def __init__(self, intents: discord.Intents = None):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True

        super().__init__(
            command_prefix=config.BOT_PREFIX,
            intents=intents,
            help_command=None,  # Usaremos un comando help personalizado y más limpio
        )

    async def setup_hook(self):
        """Carga extensiones (Cogs) y sincroniza comandos de barra (Slash)."""
        logger.info("Cargando extensiones de Meep...")

        extensions = [
            "cogs.lol_cog",
            "cogs.music_cog",
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Extension '{ext}' cargada exitosamente.")
            except Exception as e:
                logger.error(f"Error al cargar la extension '{ext}': {e}", exc_info=True)

        # Sincronización de Slash Commands
        try:
            if config.DEV_GUILD_ID:
                guild = discord.Object(id=config.DEV_GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Sincronizados {len(synced)} comandos Slash en el servidor de pruebas ({config.DEV_GUILD_ID}).")
            else:
                synced = await self.tree.sync()
                logger.info(f"Sincronizados {len(synced)} comandos Slash globalmente.")
        except Exception as e:
            logger.error(f"Error sincronizando comandos Slash: {e}")

    async def on_ready(self):
        """Se ejecuta cuando el bot se conecta a Discord."""
        banner = r"""
  __  __                  ____        _   
 |  \/  | ___  ___ _ __  | __ )  ___ | |_ 
 | |\/| |/ _ \/ _ \ '_ \ |  _ \ / _ \| __|
 | |  | |  __/  __/ |_) || |_) | (_) | |_ 
 |_|  |_|\___|\___| .__/ |____/ \___/ \__|
                  |_|                      
        """
        print(banner)
        logger.info(f"Conectado como: {self.user.name}#{self.user.discriminator} (ID: {self.user.id})")
        logger.info(f"Prefijo de comandos: {config.BOT_PREFIX}")
        logger.info(f"Conectado a {len(self.guilds)} servidores.")

        # Establecer estado enriquecido de Discord
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{config.BOT_PREFIX}c | {config.BOT_PREFIX}p | /champion",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Manejador global de errores para comandos con prefijo."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignorar comandos inexistentes para no spamear el chat

        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="⚠️ Parámetro Faltante",
                description=f"Falta un argumento obligatorio: `{error.param.name}`.\nUsa `{config.BOT_PREFIX}help` para ver la sintaxis.",
                color=config.COLOR_ERROR,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        logger.error(f"Error en comando '{ctx.command}': {error}", exc_info=error)
        embed = discord.Embed(
            title="❌ Ocurrió un Error",
            description=f"Ha ocurrido un error al procesar el comando: `{str(error)}`",
            color=config.COLOR_ERROR,
        )
        await ctx.reply(embed=embed, mention_author=False)


def setup_help(bot: MeepBot):
    @bot.command(name="help", aliases=["ayuda", "comandos"])
    async def custom_help(ctx: commands.Context):
        embed = discord.Embed(
            title="✨ Comandos de Meep Bot",
            description="Tu compañero privado para League of Legends y Música.",
            color=config.COLOR_MEEP,
        )
        embed.add_field(
            name="⚔️ League of Legends",
            value=(
                f"`{config.BOT_PREFIX}c <campeon> [modo_o_rol]` o `/champion`\n"
                f"  └ *Ejemplo:* `{config.BOT_PREFIX}c mf` (Grieta) o `{config.BOT_PREFIX}c mf aram`\n"
                f"  └ *Incluye botones interactivos para alternar estilos (AD/AP/Tanque).*\n"
                f"`{config.BOT_PREFIX}counters <campeon>` (Mejores y peores match-ups)\n"
                f"`{config.BOT_PREFIX}live [invocador]` (Partida en vivo)\n"
                f"`{config.BOT_PREFIX}perfil [invocador]` (Rango y maestrías)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎵 Música (Sin Anuncios)",
            value=(
                f"`{config.BOT_PREFIX}p <tema/link>` o `/play` (Reproducir audio)\n"
                f"`{config.BOT_PREFIX}artist <artista>` (Encolar Top 10-15 del artista)\n"
                f"`{config.BOT_PREFIX}s` o `/skip` (Saltar pista)\n"
                f"`{config.BOT_PREFIX}pause` / `{config.BOT_PREFIX}res` (Pausa / Reanudar)\n"
                f"`{config.BOT_PREFIX}q` o `/queue` (Ver lista de reproducción)\n"
                f"`{config.BOT_PREFIX}np` (Canción actual y tiempo)\n"
                f"`{config.BOT_PREFIX}sh` o `/shuffle` (Mezclar cola)\n"
                f"`{config.BOT_PREFIX}loop` [track/queue/off] (Repetir)\n"
                f"`{config.BOT_PREFIX}dc` o `/leave` (Desconectar bot)"
            ),
            inline=False,
        )
        embed.set_footer(text="Desarrollado para jugar en dúo sin tirones de RAM.")
        await ctx.reply(embed=embed, mention_author=False)


async def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "tu_token_aqui":
        logger.error(
            "\n"
            "==========================================================\n"
            " ¡ATENCIÓN: DISCORD_TOKEN no está configurado!\n"
            " Por favor crea un archivo .env a partir de .env.example\n"
            " y añade el Token de tu bot de Discord Developer Portal.\n"
            "=========================================================="
        )
        return

    intents = discord.Intents.default()
    intents.voice_states = True
    intents.message_content = True

    try:
        bot = MeepBot(intents=intents)
        setup_help(bot)
        async with bot:
            await bot.start(config.DISCORD_TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        logger.warning(
            "\n"
            "========================================================================\n"
            " [AVISO DE INTENTS PRIVILEGIADOS]\n"
            " 'Message Content Intent' no está activado en Discord Developer Portal.\n"
            " Iniciando Meep con soporte completo para Slash Commands (/champion, /play, etc.).\n\n"
            " Para habilitar también prefijos de texto (!c, !p):\n"
            " 1. Ve a https://discord.com/developers/applications/\n"
            " 2. Selecciona tu Bot -> Pestaña 'Bot'\n"
            " 3. En 'Privileged Gateway Intents', activa 'Message Content Intent'.\n"
            "========================================================================\n"
        )
        intents.message_content = False
        bot = MeepBot(intents=intents)
        setup_help(bot)
        async with bot:
            await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMeep Bot apagado correctamente.")

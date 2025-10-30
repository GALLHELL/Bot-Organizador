import discord
import os
import sys
import io
import logging
from discord.ext import commands
from config import TOKEN # Certifique-se de que TOKEN está definido em config.py
import time
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuração do logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="/",
            intents=intents,
            help_command=None,
            owner_id=int(os.getenv('OWNER_ID', 0)), # Certifique-se de que OWNER_ID está definido
        )
        self.logger = logging.getLogger(__name__)
        self._my_cogs = [
            "cogs.admin",
            "cogs.calendario",
            "cogs.raids",
            "cogs.tasks",
            "cogs.guide_channel",
            "cogs.welcome",
            "cogs.ajuda",
            "cogs.missions",
        ]

    async def setup_hook(self):
        await self.load_extensions()
        
    async def load_extensions(self):
        for cog in self._my_cogs:
            try:
                await self.load_extension(cog)
                self.logger.info(f"✅ Cog carregado: {cog}")
            except Exception as e:
                self.logger.error(f"❌ Falha ao carregar cog {cog}: {e}")

bot = MyBot()

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"✅ Conectado em {len(bot.guilds)} servidores")
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar comandos: {e}")

@bot.command(name='sync', hidden=True)
@commands.is_owner()
async def sync_commands(ctx: commands.Context):
    try:
        synced = await bot.tree.sync()
        msg = f"✅ {len(synced)} comandos sincronizados globalmente!"
        if ctx.guild:
            await bot.tree.sync(guild=ctx.guild)
            msg += f"\n✅ Comandos sincronizados no servidor {ctx.guild.name}!"
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {str(e)}")

async def safe_restart():
    await bot.close()
    python = sys.executable
    os.execl(python, python, *sys.argv)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        time.sleep(5)
        asyncio.run(safe_restart())
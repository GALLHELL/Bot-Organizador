# cogs/admin.py

import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands

# Importar utilidades genéricas
from . import utils

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="comando_secretario", description="Mostra todos os comandos e informações do bot")
    async def comando_secretario(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 TODOS OS COMANDOS DO SECRETÁRIO",
            description="Olá! Sou o assistente virtual da guilda. Aqui estão **todos** os comandos disponíveis:",
            color=discord.Color.blue()
        )
        
        # Seção de Funcionalidades Automáticas (ajuste para usar utils. constantes)
        embed.add_field(
            name="🤖 AUTOMAÇÕES",
            value=(
                "• Calendário enviado diariamente às 00:01 e 12:00\n"
                "• Lembretes de Node War (seg/qua/sex às 19:30)\n"
                "• Lembretes de Boss Guild (diários às 09:00 e 18:30)\n"
                f"• Canais de voz automáticos para eventos (Categoria ID: {utils.CATEGORIA_VOZ_ID})\n" # Exemplo de uso
                "• Limpeza diária de eventos passados"
            ),
            inline=False
        )
        
        embed.set_thumbnail(url="https://i.imgur.com/JL1SfQj.png"  )
        embed.set_footer(text=f"Bot desenvolvido para a guilda | Versão 3.0 | {len(self.bot.cogs)} módulos ativos")
    
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))

# cogs/ajuda.py

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import logging

logger = logging.getLogger(__name__)

# IDs para canal e cargo de denúncias
CANAL_DENUNCIA_ID = 1390358261177258146  # Coloque o ID real do canal de denúncias
CARGO_DENUNCIA_ID = 1253825169789681696  # Coloque o ID real do cargo que deve ser mencionado

# IDs configuráveis
CANAL_AJUDA_ID = 1390817125861687407  # Canal onde as ajudas serão enviadas
CARGO_STAFF_ID = 1253825169789681696  # Cargo para menção em PKs
CARGO_EXPERIENTE_ID = 1392313383679950972  # Cargo para menção em Dúvidas
CARGO_MEMBRO_ID = 1253825469858713682  # Cargo para menção em UP e Procuro Grupo

class DenunciaModal(Modal):
    def __init__(self):
        super().__init__(title="🚨 Registrar Denúncia")
        self.relato = TextInput(
            label="Relate o ocorrido",
            style=discord.TextStyle.paragraph,
            placeholder="Descreva o que aconteceu...",
            required=True,
            max_length=1000
        )
        self.add_item(self.relato)

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.guild.get_channel(CANAL_DENUNCIA_ID)
        role_mention = f"<@&{CARGO_DENUNCIA_ID}>"
        embed = discord.Embed(
            title="🚨 Nova Denúncia Recebida",
            description=self.relato.value,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id}")

        if canal:
            await canal.send(content=role_mention, embed=embed)
            await interaction.response.send_message("✅ Denúncia enviada com sucesso!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Canal de denúncias não encontrado.", ephemeral=True)

class DenunciaButton(Button):
    def __init__(self):
        super().__init__(
            label="Denúncia",
            style=discord.ButtonStyle.danger,
            emoji="🚨",
            custom_id="ajuda_denuncia"
        )

    async def callback(self, interaction: discord.Interaction):
        modal = DenunciaModal()
        await interaction.response.send_modal(modal)

class AjudaModal(Modal):
    def __init__(self, tipo_ajuda: str, *args, **kwargs):
        super().__init__(title=f"Ajuda - {tipo_ajuda}", *args, **kwargs)
        self.tipo_ajuda = tipo_ajuda
        
        # Campos comuns
        self.nome_familia = TextInput(
            label="Nome da Família",
            placeholder="Seu nome de família no jogo",
            required=True,
            max_length=50
        )
        self.add_item(self.nome_familia)
        
        # Campos específicos
        if tipo_ajuda == "PK":
            self.player_guilda = TextInput(
                label="Player/Guilda problemático",
                placeholder="Nome do player ou guilda que está causando problemas",
                required=True,
                max_length=100
            )
            self.local = TextInput(
                label="Local do ocorrido",
                placeholder="Ex: Valencia, Grã Florista, etc.",
                required=True,
                max_length=100
            )
            self.servidor = TextInput(
                label="Servidor",
                placeholder="Ex: Arsha, Velia, etc.",
                required=True,
                max_length=50
            )
            self.add_item(self.player_guilda)
            self.add_item(self.local)
            self.add_item(self.servidor)
            
        elif tipo_ajuda == "UP":
            self.level = TextInput(
                label="Seu nível atual",
                placeholder="Ex: 61, 62, etc.",
                required=True,
                max_length=10
            )
            self.buffs = TextInput(
                label="Buffs disponíveis",
                placeholder="Quais buffs você tem? (Ex: Perfume, Livro, etc.)",
                required=False,
                max_length=200
            )
            self.add_item(self.level)
            self.add_item(self.buffs)
            
        elif tipo_ajuda == "Dúvidas":
            self.duvida = TextInput(
                label="Descreva sua dúvida",
                placeholder="Explique detalhadamente sua dúvida",
                style=discord.TextStyle.long,
                required=True,
                max_length=1000
            )
            self.add_item(self.duvida)
            
        elif tipo_ajuda == "Procuro Grupo":
            self.atividade = TextInput(
                label="Qual atividade?",
                placeholder="Ex: Oluns, Orcs, Node War, etc.",
                required=True,
                max_length=100
            )
            self.ap_dp = TextInput(
                label="Seu AP/DP",
                placeholder="Ex: 280/350",
                required=True,
                max_length=20
            )
            self.horario = TextInput(
                label="Horário disponível",
                placeholder="Ex: 20:00 às 22:00",
                required=True,
                max_length=50
            )
            self.add_item(self.atividade)
            self.add_item(self.ap_dp)
            self.add_item(self.horario)

    async def on_submit(self, interaction: discord.Interaction):
        # Configurações baseadas no tipo de ajuda
        configs = {
            "PK": {
                "color": discord.Color.red(),
                "footer": "STAFF será notificada para ajudar com este problema",
                "mention": f"<@&{CARGO_STAFF_ID}>"
            },
            "UP": {
                "color": discord.Color.green(),
                "footer": "Membros disponíveis serão notificados para ajudar",
                "mention": f"<@&{CARGO_MEMBRO_ID}>"
            },
            "Dúvidas": {
                "color": discord.Color.blue(),
                "footer": "Membros experientes serão notificados para responder",
                "mention": f"<@&{CARGO_EXPERIENTE_ID}>"
            },
            "Procuro Grupo": {
                "color": discord.Color.purple(),
                "footer": "Membros disponíveis serão notificados para formar grupo",
                "mention": f"<@&{CARGO_MEMBRO_ID}>"
            }
        }

        # Criar embed
        embed = discord.Embed(
            title=f"📢 Pedido de Ajuda - {self.tipo_ajuda}",
            color=configs[self.tipo_ajuda]["color"]
        )
        
        embed.add_field(name="👤 Nome da Família", value=self.nome_familia.value, inline=False)
        
        if self.tipo_ajuda == "PK":
            embed.add_field(name="🛡️ Player/Guilda", value=self.player_guilda.value, inline=False)
            embed.add_field(name="📍 Local", value=self.local.value, inline=True)
            embed.add_field(name="🌐 Servidor", value=self.servidor.value, inline=True)
            
        elif self.tipo_ajuda == "UP":
            embed.add_field(name="📈 Nível", value=self.level.value, inline=True)
            embed.add_field(name="🧪 Buffs", value=self.buffs.value or "Nenhum", inline=True)
            
        elif self.tipo_ajuda == "Dúvidas":
            embed.add_field(name="❓ Dúvida", value=self.duvida.value, inline=False)
            
        elif self.tipo_ajuda == "Procuro Grupo":
            embed.add_field(name="🎯 Atividade", value=self.atividade.value, inline=True)
            embed.add_field(name="⚔️ AP/DP", value=self.ap_dp.value, inline=True)
            embed.add_field(name="⏰ Horário", value=self.horario.value, inline=True)
        
        embed.set_footer(text=configs[self.tipo_ajuda]["footer"])
        
        # Enviar para o canal de ajuda
        canal_ajuda = interaction.guild.get_channel(CANAL_AJUDA_ID)
        if canal_ajuda:
            mensagem = await canal_ajuda.send(
                content=f"{configs[self.tipo_ajuda]['mention']} {interaction.user.mention} solicitou ajuda!",
                embed=embed
            )
            await mensagem.add_reaction("👍")  # Posso ajudar
            await mensagem.add_reaction("❓")  # Tenho dúvidas
        
        # Confirmar para o usuário
        await interaction.response.send_message(
            f"✅ Seu pedido de ajuda para **{self.tipo_ajuda}** foi enviado para <#{CANAL_AJUDA_ID}>!",
            ephemeral=True
        )

class AjudaButton(Button):
    def __init__(self, tipo_ajuda: str, emoji: str):
        super().__init__(
            label=tipo_ajuda,
            style=discord.ButtonStyle.primary,
            emoji=emoji,
            custom_id=f"ajuda_{tipo_ajuda.lower().replace(' ', '_')}"
        )
        self.tipo_ajuda = tipo_ajuda

    async def callback(self, interaction: discord.Interaction):
        modal = AjudaModal(self.tipo_ajuda)
        await interaction.response.send_modal(modal)

class AjudaView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # Adiciona os 4 botões com emojis
        self.add_item(AjudaButton("PK", "⚔️"))
        self.add_item(AjudaButton("UP", "📈"))
        self.add_item(AjudaButton("Dúvidas", "❓"))
        self.add_item(AjudaButton("Procuro Grupo", "👥"))
        self.add_item(DenunciaButton())

class Ajuda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="ajuda", description="Cria o painel de ajuda com botões interativos")
    @app_commands.checks.has_permissions(administrator=True)
    async def ajuda(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ Sistema de Ajuda da Guilda",
            description=(
                "**Clique em um dos botões abaixo para solicitar ajuda:**\n\n"
                "⚔️ **PK** - Ajuda contra players maliciosos\n"
                "📈 **UP** - Ajuda para upar seu personagem\n"
                "❓ **Dúvidas** - Tire dúvidas sobre o jogo\n"
                "👥 **Procuro Grupo** - Para formar grupo de atividades\n"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Selecione o tipo de ajuda que precisa")
        
        # Envia a mensagem com a view persistente
        await interaction.response.send_message(embed=embed, view=AjudaView())
        
        # Instruções para o administrador
        await interaction.followup.send(
            "✅ Painel de ajuda criado com sucesso! Você pode mover esta mensagem para onde desejar.",
            ephemeral=True
        )

async def setup(bot):
    cog = Ajuda(bot)
    await bot.add_cog(cog)
    bot.add_view(AjudaView())  # Garante que a view persista após reinicializações
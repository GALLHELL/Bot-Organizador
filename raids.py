import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from discord import app_commands
import json
import os
from datetime import datetime
import locale
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

import asyncio
from datetime import datetime

from . import utils

LOCAL_TZ = timezone('America/Sao_Paulo')  # Ajuste conforme seu fuso horário
logger = logging.getLogger(__name__)

# Configurar locale para pt_BR (Linux/Unix)
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.utf-8')
except locale.Error:
    logger.warning("Locale pt_BR.utf-8 não encontrado. Usando padrão do sistema.")

RAIDS = {
    "OLLUN DEKIA 2": {
        "descricao": (
            "**Servidor:** A combinar\n"
            "**Local:** [Cachoeira de Olun](https://bdocodex.com/pt/node/1703/)\n\n"
            "**Consumíveis:**\n"
            "- [Perfume de Coragem](https://bdocodex.com/pt/item/734/)\n"
            "- [Grupo Fármaco da Harmonia - Kamasylvia](https://bdocodex.com/pt/item/1405/)\n\n"
            "**Buffs:**\n"
            "- [Vila Fortalecer o Corpo (90 minutos)](https://bdocodex.com/pt/item/43703/)\n"
            "- [Bênção Bravura (120min)](https://bdocodex.com/pt/item/752017/)\n"
            "- [Bênção Proteção (120min)](https://bdocodex.com/pt/item/752018/)\n\n"
            "**Artefato:** Kabua\n"
            "**Build Cristal:** [Garmoth Planner](https://garmoth.com/crystal-planner/dnwLQ7eNUN)"
        ),
        "canal_id": 1392572117731770549
    },
    "SANTUARIO NORMAL": {
        "descricao": (
            "**Servidor:** A combinar\n"
            "**Local:** [Carolin](https://bdocodex.com/pt/npc/41028/)\n\n"
            "**Consumíveis:**\n"
            "- [Perfume de Coragem](https://bdocodex.com/pt/item/734/)\n"
            "- [Fármaco da Harmonia - Humano](https://bdocodex.com/pt/item/1401/)\n"
            "- [Fármaco da Harmonia - Humanoide](https://bdocodex.com/pt/item/1403/)\n"
            "- [Fármaco da Harmonia - Kamasylvia](https://bdocodex.com/pt/item/1405/)\n"
            "- [Refeição Simples de Cron](https://bdocodex.com/pt/item/9692/)\n\n"
            "**Buffs:**\n"
            "- [Vila Fortalecer o Corpo (90 minutos)](https://bdocodex.com/pt/item/43703/)\n"
            "- [Bênção Bravura (120min)](https://bdocodex.com/pt/item/752017/)\n"
            "- [Bênção Proteção (120min)](https://bdocodex.com/pt/item/752018/)\n\n"
            "**Artefato:** Kabua\n"
            "**Build Cristal:**\n"
            "- [Back ataque / humano](https://garmoth.com/crystal-planner/dnwLQ7eNUN)\n"
            "- [Back ataque / pve](https://garmoth.com/crystal-planner/dnwLQ7eNUN)"
        ),
        "canal_id": 1392572117731770549
    },
    "SANTUARIO DESAFIO": {
        "descricao": (
            "**Servidor:** A combinar\n"
            "**Local:** [Carolin](https://bdocodex.com/pt/npc/41028/)\n\n"
            "**Consumíveis:**\n"
            "- [Perfume de Coragem](https://bdocodex.com/pt/item/734/)\n"
            "- [Fármaco da Harmonia - Humano](https://bdocodex.com/pt/item/1401/)\n"
            "- [Fármaco da Harmonia - Humanoide](https://bdocodex.com/pt/item/1403/)\n"
            "- [Fármaco da Harmonia - Kamasylvia](https://bdocodex.com/pt/item/1405/)\n"
            "- [Refeição Simples de Cron](https://bdocodex.com/pt/item/9692/)\n\n"
            "**Buffs:**\n"
            "- [Vila Fortalecer o Corpo (90 minutos)](https://bdocodex.com/pt/item/43703/)\n"
            "- [Bênção Bravura (120min)](https://bdocodex.com/pt/item/752017/)\n"
            "- [Bênção Proteção (120min)](https://bdocodex.com/pt/item/752018/)\n\n"
            "**Artefato:** Kabua\n"
            "**Build Cristal:**\n"
            "- [Back ataque / humano](https://garmoth.com/crystal-planner/dnwLQ7eNUN)\n"
            "- [Back ataque / pve](https://garmoth.com/crystal-planner/dnwLQ7eNUN)"
        ),
        "canal_id": 1392572117731770549
    },
    "GRAND PIX": {
        "descricao": (
            "**Está afim de viver uma adrenalina onde sua honra será colocada em prova nas pistas do Black Desert?**\n\n"
            "**Requisitos:**\n"
            "- Ter um cavalo de corrida\n"
            "- Mínimo de players: 5\n"
            "- Máximo de players: 10\n\n"
            "Marque seu horário abaixo!"
        ),
        "canal_id": 1392572117731770549
    },
    "DG'S EM GERAL": {
        "descricao": "**Eventos gerais de Dungeon (DG's) para todos os níveis e estilos de grupo.**",
        "canal_id": 1392572117731770549
    }
}

HORARIOS = [f"{h:02d}:00" for h in range(0, 24, 2)]
participantes = {raid: {hora: [] for hora in HORARIOS} for raid in RAIDS}

PARTICIPANTES_FILE = "data/participantes.json"

def salvar_estado():
    """Salva o estado dos participantes e configurações de canal das raids."""
    estado = {
        "participantes": participantes,
        "raids_config": {raid: {"canal_id": info["canal_id"]} for raid, info in RAIDS.items()}
    }
    try:
        os.makedirs(os.path.dirname(PARTICIPANTES_FILE), exist_ok=True)
        with open(PARTICIPANTES_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=4, ensure_ascii=False)
        logger.info("Estado das raids salvo.")
    except Exception as e:
        logger.error(f"Erro ao salvar estado das raids: {e}")

def carregar_estado_raids():
    """Carrega o estado dos participantes e configurações de canal das raids."""
    global participantes
    try:
        if os.path.exists(PARTICIPANTES_FILE):
            with open(PARTICIPANTES_FILE, "r", encoding="utf-8") as f:
                estado = json.load(f)
                for raid, horarios in estado.get("participantes", {}).items():
                    if raid in participantes:
                        for hora, lista in horarios.items():
                            participantes[raid][hora] = lista
                raids_cfg = estado.get("raids_config", {})
                for raid_name, raid_info in raids_cfg.items():
                    if raid_name in RAIDS:
                        RAIDS[raid_name]["canal_id"] = raid_info.get("canal_id")
            logger.info("Estado das raids carregado.")
        else:
            logger.info("Arquivo de estado das raids não encontrado. Inicializando com valores padrão.")
    except Exception as e:
        logger.error(f"Erro ao carregar estado das raids: {e}")

def criar_embed_raid(raid: str) -> discord.Embed:
    """Cria o embed da raid com os horários e participantes."""
    config_raids = {
        "OLLUN DEKIA 2": {
            "color": 0x3498db,
            "emoji": "🌊",
            "thumbnail": "https://cdn-icons-png.flaticon.com/128/3548/3548884.png"
        },
        "SANTUARIO NORMAL": {
            "color": 0x2ecc71,
            "emoji": "🏛️",
            "thumbnail": "https://cdn-icons-png.flaticon.com/128/3548/3548876.png"
        },
        "SANTUARIO DESAFIO": {
            "color": 0xe74c3c,
            "emoji": "⚔️",
            "thumbnail": "https://cdn-icons-png.flaticon.com/128/3549/3549884.png"
        },
        "GRAND PIX": {
            "color": 0xf1c40f,
            "emoji": "🏇",
            "thumbnail": "https://cdn-icons-png.flaticon.com/128/539/539856.png"
        },
        "DG'S EM GERAL": {
            "color": 0x9b59b6,
            "emoji": "🏰",
            "thumbnail": "https://cdn-icons-png.flaticon.com/128/3549/3549871.png"
        }
    }
    
    config = config_raids.get(raid, {
        "color": 0x3498db,
        "emoji": "🎮",
        "thumbnail": "https://i.imgur.com/JL1SfQj.png"
    })
    
    embed = discord.Embed(
        title=f"{config['emoji']} {raid} {config['emoji']}",
        description=RAIDS[raid]["descricao"],
        color=config["color"]
    )
    
    embed.set_thumbnail(url=config["thumbnail"])

    # Dividir HORARIOS em 3 grupos para melhor visualização
    qtd_grupos = 3
    tamanho_grupo = len(HORARIOS) // qtd_grupos
    grupos_horarios = [HORARIOS[i*tamanho_grupo:(i+1)*tamanho_grupo] for i in range(qtd_grupos)]

    # Caso não divida exatamente (ex: len(HORARIOS)%3 != 0), adiciona o restante no último grupo
    resto = len(HORARIOS) % qtd_grupos
    if resto:
        grupos_horarios[-1].extend(HORARIOS[-resto:])
    
    for i, grupo in enumerate(grupos_horarios):
        field_value = ""
        for hora in grupo:
            lista = participantes[raid][hora]
            status = "🔴" if len(lista) >= 5 else "🟢" if lista else "⚪"
            nomes = "\n".join(f"• {nome}" for nome in lista) if lista else "• Vagas disponíveis"
            field_value += f"**{hora}** {status}\n{nomes}\n\n"
        
        embed.add_field(
            name=f"📅 Grupo {i+1}",
            value=field_value,
            inline=True
        )
    
    embed.set_footer(
        text="🔧 Apenas administradores podem gerenciar raids",
        icon_url="https://cdn-icons-png.flaticon.com/128/6024/6024190.png"
    )
    
    return embed

def criar_embed_confirmacao(raid: str, hora: str, user: discord.User) -> discord.Embed:
    """Embed para confirmação de inscrição do usuário na raid."""
    embed = discord.Embed(
        title="✅ Inscrição Confirmada",
        description=f"Olá {user.display_name}, sua participação na raid foi registrada!",
        color=discord.Color.green()
    )
    embed.add_field(name="Raid", value=raid, inline=False)
    embed.add_field(name="Horário", value=hora, inline=False)
    embed.add_field(name="Detalhes", value=RAIDS[raid]["descricao"], inline=False)
    embed.set_footer(text="Você receberá um lembrete 15 minutos antes da raid")
    return embed

def criar_embed_lembrete(raid: str, hora: str) -> discord.Embed:
    """Embed para lembrete 15 minutos antes da raid."""
    embed = discord.Embed(
        title="⏰ Lembrete de Raid",
        description=f"A raid **{raid}** começa em 15 minutos!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Horário", value=hora, inline=False)
    embed.add_field(name="Detalhes", value=RAIDS[raid]["descricao"], inline=False)
    return embed

class HorarioSelect(Select):
    def __init__(self, raid: str):
        options = [
            discord.SelectOption(
                label=hora,
                description=f"{len(participantes[raid][hora])}/5 participantes",
                value=hora,
                emoji="🕒"
            ) for hora in HORARIOS
        ]
        super().__init__(
            placeholder="🕒 Selecione um horário...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"horario_select_{raid}"
        )
        self.raid = raid

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem gerenciar eventos.",
                ephemeral=True
            )
            return
        
        hora = self.values[0]
        user = interaction.user

        # Remove o usuário de todos os horários
        for h in HORARIOS:
            if user.display_name in participantes[self.raid][h]:
                participantes[self.raid][h].remove(user.display_name)
        
        # Adiciona no horário selecionado
        participantes[self.raid][hora].append(user.display_name)
        salvar_estado()

        embed = criar_embed_raid(self.raid)
        view = HorarioView(self.raid)
        await interaction.response.edit_message(embed=embed, view=view)

        try:
            await user.send(embed=criar_embed_confirmacao(self.raid, hora, user))
        except discord.Forbidden:
            await interaction.followup.send(
                "Não foi possível enviar a confirmação por DM. Por favor, habilite mensagens diretas.",
                ephemeral=True
            )

class WithdrawButton(Button):
    def __init__(self, raid: str):
        super().__init__(
            label="❌ Cancelar Inscrição",
            style=discord.ButtonStyle.red,
            custom_id=f"withdraw_{raid}",
            emoji="✖️"
        )
        self.raid = raid

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem gerenciar eventos.",
                ephemeral=True
            )
            return
        
        user = interaction.user
        removido = False
        
        for hora in HORARIOS:
            if user.display_name in participantes[self.raid][hora]:
                participantes[self.raid][hora].remove(user.display_name)
                removido = True
        
        if removido:
            salvar_estado()
            embed = criar_embed_raid(self.raid)
            view = HorarioView(self.raid)
            await interaction.response.edit_message(embed=embed, view=view)
            await interaction.followup.send(
                "✅ Sua inscrição foi cancelada em todos os horários.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ Você não está inscrito em nenhum horário.",
                ephemeral=True
            )

class ResetButton(Button):
    def __init__(self, raid: str):
        super().__init__(
            label="🔄 Resetar Presenças",
            style=discord.ButtonStyle.grey,
            custom_id=f"reset_{raid}",
            emoji="🔄"
        )
        self.raid = raid

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem resetar presenças.",
                ephemeral=True
            )
            return
        
        for hora in HORARIOS:
            participantes[self.raid][hora].clear()
        
        salvar_estado()
        embed = criar_embed_raid(self.raid)
        view = HorarioView(self.raid)
        await interaction.response.edit_message(embed=embed, view=view)
        await interaction.followup.send(
            "✅ Presenças resetadas com sucesso para todos os horários!",
            ephemeral=True
        )

class HorarioView(View):
    def __init__(self, raid: str):
        super().__init__(timeout=None)
        self.raid = raid
        self.add_item(HorarioSelect(raid))
        self.add_item(WithdrawButton(raid))
        self.add_item(ResetButton(raid))

class Raids(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mensagens_eventos = {}
        self.scheduler = None
        self.scheduler_started = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.scheduler_started:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.start()
            self.scheduler_started = True

            hora, minuto = map(int, utils.RESET_HORA.split(":"))
            self.scheduler.add_job(
                self.reset_eventos,
                trigger=CronTrigger(hour=hora, minute=minuto, timezone=LOCAL_TZ),
                id="reset_diario",
                replace_existing=True
            )
            logger.info(f"Scheduler iniciado - reset diário agendado para {utils.RESET_HORA} ({LOCAL_TZ})")

        logger.info("✅ Módulo de Raids carregado")
        carregar_estado_raids()
        self.carregar_mensagens_eventos()

        # Registrar views persistentes
        for raid in RAIDS:
            self.bot.add_view(HorarioView(raid))

        # Restaurar mensagens das raids configuradas
        for raid, info in RAIDS.items():
            canal_id = info.get("canal_id")
            if canal_id:
                try:
                    canal = self.bot.get_channel(canal_id)
                    if not canal:
                        continue
                    msg_id = self.mensagens_eventos.get(str(canal_id))
                    if msg_id:
                        try:
                            await canal.fetch_message(msg_id)
                        except discord.NotFound:
                            embed = criar_embed_raid(raid)
                            view = HorarioView(raid)
                            msg = await canal.send(embed=embed, view=view)
                            self.mensagens_eventos[str(canal_id)] = msg.id
                            self.salvar_mensagens_eventos()
                    else:
                        embed = criar_embed_raid(raid)
                        view = HorarioView(raid)
                        msg = await canal.send(embed=embed, view=view)
                        self.mensagens_eventos[str(canal_id)] = msg.id
                        self.salvar_mensagens_eventos()
                except Exception as e:
                    logger.error(f"Erro ao verificar mensagem da raid {raid}: {e}")

    def carregar_mensagens_eventos(self):
        try:
            if os.path.exists(utils.MENSAGENS_EVENTOS_FILE):
                with open(utils.MENSAGENS_EVENTOS_FILE, 'r', encoding='utf-8') as f:
                    self.mensagens_eventos = json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar mensagens de eventos: {e}")

    def salvar_mensagens_eventos(self):
        try:
            with open(utils.MENSAGENS_EVENTOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.mensagens_eventos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar mensagens de eventos: {e}")

    async def limpar_mensagens_antigas(self, canal_id: int):
        if not utils.LIMPAR_MENSAGENS_ANTIGAS:
            return
        try:
            canal = self.bot.get_channel(canal_id)
            if canal:
                await canal.purge(limit=10, check=lambda m: m.author == self.bot.user)
        except Exception as e:
            logger.error(f"Erro ao limpar mensagens antigas: {e}")

    async def reset_eventos(self):
        logger.info("⏰ Iniciando reset diário de eventos via APScheduler...")

        # Limpa todas as presenças
        for raid in RAIDS:
            for hora in HORARIOS:
                participantes[raid][hora].clear()
        salvar_estado()

        canal = self.bot.get_channel(utils.CANAL_RAIDS_ID)
        if not canal:
            logger.error(f"Canal das raids (ID {utils.CANAL_RAIDS_ID}) não encontrado.")
            return

        # Limpa mensagens antigas do bot (se configurado)
        if utils.LIMPAR_MENSAGENS_ANTIGAS:
            await canal.purge(limit=50, check=lambda m: m.author == self.bot.user)

        # Envia as mensagens separadas, uma para cada raid, no mesmo canal
        for raid in RAIDS:
            embed = criar_embed_raid(raid)
            view = HorarioView(raid)
            msg = await canal.send(embed=embed, view=view)
            # Armazena o ID da mensagem associada a cada raid pelo nome da raid
            self.mensagens_eventos[raid] = msg.id

        # Salva o estado das mensagens enviadas
        self.salvar_mensagens_eventos()

        logger.info("✅ Reset diário de eventos concluído.")
        
    @app_commands.command(name="listar_config_raid", description="Lista os canais configurados para cada raid")
    async def listar_config_raid(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Você precisa ser administrador para usar este comando.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Configuração Atual das RAIDs",
            description="Veja abaixo onde cada RAID está configurada:",
            color=discord.Color.blue()
        )

        for nome, info in RAIDS.items():
            canal_id = info.get("canal_id")
            if canal_id:
                canal = self.bot.get_channel(canal_id)
                canal_mention = canal.mention if canal else f"`ID: {canal_id}` (não encontrado)"
            else:
                canal_mention = "⚠️ *Não configurado*"

            embed.add_field(
                name=f"🛡️ {nome}",
                value=f"Canal: {canal_mention}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="configurar_raid", description="Configura o canal para uma raid")
    @app_commands.choices(raid=[
        app_commands.Choice(name=nome, value=nome) for nome in RAIDS
    ])
    async def configurar_raid(
        self, interaction: discord.Interaction,
        raid: app_commands.Choice[str],
        canal: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Você precisa ser administrador para usar este comando.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        canal_antigo = RAIDS[raid.value]["canal_id"]
        if canal_antigo:
            await self.limpar_mensagens_antigas(canal_antigo)

        RAIDS[raid.value]["canal_id"] = canal.id
        salvar_estado()

        embed = criar_embed_raid(raid.value)
        view = HorarioView(raid.value)
        msg = await canal.send(embed=embed, view=view)
        self.mensagens_eventos[str(canal.id)] = msg.id
        self.salvar_mensagens_eventos()

        await interaction.followup.send(
            f"✅ Raid **{raid.value}** configurada no canal {canal.mention}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Raids(bot))
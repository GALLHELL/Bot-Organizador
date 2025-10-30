import discord
from discord.ext import commands
from discord.ui import View, Button, TextInput, Modal, Select
from discord import app_commands, ButtonStyle, Interaction
import json
import os
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from . import utils
import asyncio
import shutil
import hashlib

logger = logging.getLogger(__name__)
calendario_config = {}

# Lock para proteger acesso concorrente ao arquivo JSON do calendário
_lock = asyncio.Lock()

def carregar_configuracoes_calendario():
    global calendario_config
    try:
        with open("data/calendario_config.json", "r", encoding="utf-8") as f:
            calendario_config = json.load(f)
    except Exception as e:
        print(f"Erro ao carregar config do calendário: {e}")
        calendario_config = {}

def formatar_data_entrada(data_str: str, ano: int) -> datetime | None:
    try:
        partes = data_str.split("/")
        if len(partes) != 2:
            return None
        dia = int(partes[0])
        mes = int(partes[1])
        tz = timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))
        data_naive = datetime(year=ano, month=mes, day=dia)
        data_aware = tz.localize(data_naive)
        return data_aware
    except Exception:
        return None

def gerar_id_evento(evento: dict) -> str:
    base = f"{evento['data']}{evento['hora']}{evento['titulo']}{evento['local']}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()[:8]  # 8 chars do hash

def backup_calendario():
    """
    Faz backup do arquivo de calendário atual, com timestamp.
    """
    try:
        if os.path.exists(utils.CALENDARIO_FILE):
            backup_dir = os.path.join("data", "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"calendario_backup_{timestamp}.json")
            shutil.copy(utils.CALENDARIO_FILE, backup_path)
            logger.info(f"Backup do calendário criado em {backup_path}")
    except Exception as e:
        logger.error(f"Erro ao criar backup do calendário: {e}")

async def carregar_calendario():
    """
    Carrega eventos do arquivo JSON de forma thread-safe.
    """
    async with _lock:
        return await utils.carregar_calendario()

async def salvar_calendario(eventos):
    """
    Salva eventos no arquivo JSON de forma thread-safe, criando backup antes.
    """
    async with _lock:
        backup_calendario()
        await utils.salvar_calendario(eventos)

def nome_dia_semana_pt(dia_ingles: str) -> str:
    nomes = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    return nomes.get(dia_ingles, dia_ingles)

def get_footer_text():
    tz = timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))
    agora = datetime.now(tz)
    return f"Última atualização: {agora.strftime('%d/%m/%Y %H:%M')}"

def formatar_evento_resumo(evento: dict) -> str:
    titulo = evento['titulo']
    if len(titulo) > 30:
        titulo = titulo[:27] + "..."
    return f"{evento['hora']} - {titulo}"

def paginar_lista(itens: list, pagina: int, itens_por_pagina: int = 25):
    """
    Retorna a fatia de itens referente à página.
    """
    start = pagina * itens_por_pagina
    end = start + itens_por_pagina
    return itens[start:end]

class ModalAdicionarEvento(Modal, title="➕ Adicionar Evento"):
    data = TextInput(
        label="Data (DD/MM)",
        placeholder="Ex: 20/05",
        required=True,
        max_length=5
    )
    hora = TextInput(
        label="Hora (HH:MM)",
        placeholder="Ex: 19:00",
        required=True,
        max_length=5
    )
    titulo = TextInput(
        label="Título do Evento",
        placeholder="Ex: Guerra de Guilda",
        required=True,
        max_length=100
    )
    local = TextInput(
        label="Local do Evento",
        placeholder="Ex: Valencia",
        required=True,
        max_length=100
    )
    descricao = TextInput(
        label="Descrição (opcional)",
        placeholder="Detalhes do evento",
        required=False,
        style=discord.TextStyle.long,
        max_length=1000
    )

    async def on_submit(self, interaction: Interaction):
        ano_atual = datetime.now(timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))).year
        data_obj = formatar_data_entrada(self.data.value.strip(), ano_atual)
        if not data_obj:
            await interaction.response.send_message("❌ Formato de data inválido. Use DD/MM.", ephemeral=True)
            return
        if data_obj < datetime.now(data_obj.tzinfo or pytz.UTC):
            # Pode ajustar aqui se quiser só eventos futuros
            pass

        try:
            datetime.strptime(self.hora.value.strip(), "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Formato de hora inválido. Use HH:MM.", ephemeral=True)
            return

        novo_evento = {
            "data": data_obj.strftime("%Y-%m-%d"),
            "hora": self.hora.value.strip(),
            "titulo": self.titulo.value.strip(),
            "local": self.local.value.strip(),
            "descricao": self.descricao.value.strip() if self.descricao.value else "Nenhuma descrição fornecida."
        }

        eventos = await carregar_calendario()
        eventos.append(novo_evento)
        await salvar_calendario(eventos)

        await interaction.response.send_message(
            f"✅ Evento '{self.titulo.value}' adicionado!",
            ephemeral=True
        )

        canal_id = utils.calendario_config.get("canal_id")
        canal = interaction.client.get_channel(canal_id)
        if canal:
            try:
                await enviar_calendario_semanal(interaction.client)
            except Exception as e:
                logger.error(f"Erro ao atualizar calendário: {e}")

class ModalEditarEvento(Modal, title="✏️ Editar Evento"):
    data = TextInput(label="Data (DD/MM)", required=True, max_length=5)
    hora = TextInput(label="Hora (HH:MM)", required=True, max_length=5)
    titulo = TextInput(label="Título do Evento", required=True, max_length=100)
    local = TextInput(label="Local do Evento", required=True, max_length=100)
    descricao = TextInput(label="Descrição (opcional)", required=False, style=discord.TextStyle.long, max_length=1000)

    def __init__(self, evento_original, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evento_original = evento_original

        self.data.default = datetime.strptime(evento_original["data"], "%Y-%m-%d").strftime("%d/%m")
        self.hora.default = evento_original["hora"]
        self.titulo.default = evento_original["titulo"]
        self.local.default = evento_original["local"]
        self.descricao.default = evento_original["descricao"]

    async def on_submit(self, interaction: Interaction):
        ano_atual = datetime.now(timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))).year
        data_obj = formatar_data_entrada(self.data.value.strip(), ano_atual)
        if not data_obj:
            await interaction.response.send_message("❌ Data inválida. Use DD/MM.", ephemeral=True)
            return

        try:
            datetime.strptime(self.hora.value.strip(), "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Hora inválida. Use HH:MM.", ephemeral=True)
            return

        eventos = await carregar_calendario()
        for i, evento in enumerate(eventos):
            if evento == self.evento_original:
                eventos[i] = {
                    "data": data_obj.strftime("%Y-%m-%d"),
                    "hora": self.hora.value.strip(),
                    "titulo": self.titulo.value.strip(),
                    "local": self.local.value.strip(),
                    "descricao": self.descricao.value.strip() or "Nenhuma descrição fornecida."
                }
                break

        await salvar_calendario(eventos)
        await interaction.response.send_message("✅ Evento atualizado com sucesso!", ephemeral=True)

        canal_id = utils.calendario_config.get("canal_id")
        canal = interaction.client.get_channel(canal_id)
        if canal:
            try:
                await enviar_calendario_semanal(interaction.client)
            except Exception as e:
                logger.error(f"Erro ao atualizar calendário: {e}")

class ModalRemoverEvento(Modal, title="❌ Confirmar Remoção"):
    confirmacao = TextInput(
        label="Confirme digitando 'remover'",
        placeholder="remover",
        required=True,
        max_length=10
    )

    def __init__(self, evento_para_remover, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evento_para_remover = evento_para_remover

    async def on_submit(self, interaction: Interaction):
        if self.confirmacao.value.strip().lower() != "remover":
            await interaction.response.send_message("❌ Digite exatamente 'remover'.", ephemeral=True)
            return

        eventos = await carregar_calendario()
        if self.evento_para_remover in eventos:
            eventos.remove(self.evento_para_remover)
            await salvar_calendario(eventos)

            await interaction.response.send_message("✅ Evento removido!", ephemeral=True)

            canal_id = utils.calendario_config.get("canal_id")
            canal = interaction.client.get_channel(canal_id)
            if canal:
                try:
                    await enviar_calendario_semanal(interaction.client)
                except Exception as e:
                    logger.error(f"Erro ao atualizar calendário: {e}")
        else:
            await interaction.response.send_message("❌ Evento não encontrado.", ephemeral=True)

class EventoSelect(Select):
    """
    Select para escolher eventos a editar/remover com paginação.
    """
    def __init__(self, eventos, acao, pagina=0):
        self.eventos = eventos
        self.acao = acao
        self.pagina = pagina
        self.itens_por_pagina = 25
        self.paginas_totais = (len(eventos) - 1) // self.itens_por_pagina + 1

        options = []
        eventos_pagina = paginar_lista(eventos, pagina, self.itens_por_pagina)
        for i, evento in enumerate(eventos_pagina):
            label = f"{evento['titulo']} ({evento['data']} {evento['hora']})"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=str(i)))

        placeholder = f"Selecione um evento ({pagina+1}/{self.paginas_totais})"

        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        indice = int(self.values[0]) + self.pagina * self.itens_por_pagina
        evento_selecionado = self.eventos[indice]

        if self.acao == "editar":
            modal = ModalEditarEvento(evento_selecionado)
            await interaction.response.send_modal(modal)
        elif self.acao == "remover":
            modal = ModalRemoverEvento(evento_selecionado)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Ação desconhecida.", ephemeral=True)

class SelecionarEventoView(View):
    def __init__(self, eventos, acao, pagina=0, timeout=60):
        super().__init__(timeout=timeout)
        self.eventos = eventos
        self.acao = acao
        self.pagina = pagina
        self.itens_por_pagina = 25
        self.paginas_totais = (len(eventos) - 1) // self.itens_por_pagina + 1

        self.select = EventoSelect(eventos, acao, pagina)
        self.add_item(self.select)

        # Botões de paginação se necessário
        if self.paginas_totais > 1:
            self.botao_anterior = Button(label="⬅️ Anterior", style=ButtonStyle.secondary)
            self.botao_proximo = Button(label="➡️ Próximo", style=ButtonStyle.secondary)
            self.botao_anterior.disabled = (pagina == 0)
            self.botao_proximo.disabled = (pagina == self.paginas_totais - 1)
            self.add_item(self.botao_anterior)
            self.add_item(self.botao_proximo)

            self.botao_anterior.callback = self.callback_anterior
            self.botao_proximo.callback = self.callback_proximo

    async def callback_anterior(self, interaction: Interaction):
        nova_pagina = max(0, self.pagina - 1)
        view = SelecionarEventoView(self.eventos, self.acao, nova_pagina)
        await interaction.response.edit_message(content="Selecione o evento:", view=view)

    async def callback_proximo(self, interaction: Interaction):
        nova_pagina = min(self.paginas_totais - 1, self.pagina + 1)
        view = SelecionarEventoView(self.eventos, self.acao, nova_pagina)
        await interaction.response.edit_message(content="Selecione o evento:", view=view)

    async def on_timeout(self):
        # Desabilita todos os componentes após timeout
        for item in self.children:
            item.disabled = True
        try:
            # Edita a mensagem para refletir desabilitação
            await self.message.edit(content="⏰ Tempo expirado para seleção de evento.", view=self)
        except Exception:
            pass

class CalendarioView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def on_timeout(self):
        # Desabilita botões após timeout
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(content="⏰ Painel expirado.", view=self)
        except Exception:
            pass

    @discord.ui.button(label="➕ Adicionar Evento", style=ButtonStyle.green, custom_id="add_event")
    async def botao_adicionar(self, interaction: Interaction, button: Button):
        modal = ModalAdicionarEvento()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✏️ Editar Evento", style=ButtonStyle.blurple, custom_id="edit_event")
    async def botao_editar(self, interaction: Interaction, button: Button):
        eventos = await carregar_calendario()
        if not eventos:
            await interaction.response.send_message("❌ Nenhum evento para editar.", ephemeral=True)
            return

        view = SelecionarEventoView(eventos, acao="editar")
        await interaction.response.send_message("Selecione o evento que deseja editar:", view=view, ephemeral=True)

    @discord.ui.button(label="❌ Remover Evento", style=ButtonStyle.danger, custom_id="remove_event")
    async def botao_remover(self, interaction: Interaction, button: Button):
        eventos = await carregar_calendario()
        if not eventos:
            await interaction.response.send_message("❌ Nenhum evento para remover.", ephemeral=True)
            return

        view = SelecionarEventoView(eventos, acao="remover")
        await interaction.response.send_message("Selecione o evento que deseja remover:", view=view, ephemeral=True)


# Funções de envio calendário, com logging aprimorado e tratamento

async def enviar_calendario_semanal(bot):
    await utils.carregar_configuracoes_calendario() 
    tz = timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))
    now = datetime.now(tz)
    canal_id = utils.calendario_config.get("canal_id")
    if not canal_id:
        logger.warning("Canal do calendário não configurado para envio semanal.")
        return

    canal = bot.get_channel(canal_id)
    if not canal:
        logger.error(f"Canal do calendário (ID: {canal_id}) não encontrado para envio semanal.")
        return

    eventos = await carregar_calendario()
    eventos_por_dia = {}
    for evento in eventos:
        try:
            data_evento = datetime.strptime(evento["data"], "%Y-%m-%d").date()
        except Exception as e:
            logger.error(f"Data inválida no evento '{evento.get('titulo', 'sem título')}': {e}")
            continue
        eventos_por_dia.setdefault(data_evento, []).append(evento)

    dias_ordenados = sorted(eventos_por_dia.keys())

    embed = discord.Embed(
        title="🗓️ Calendário Semanal da Guilda",
        description="Confira os eventos programados para esta semana:",
        color=utils.calendario_config.get("cor_embed", 0xFFA500)
    )
    embed.set_thumbnail(url=utils.calendario_config.get("thumbnail_url", "https://cdn-icons-png.flaticon.com/128/591/591576.png"))
    embed.set_footer(text=get_footer_text())

    for dia in dias_ordenados:
        dia_semana = nome_dia_semana_pt(dia.strftime("%A"))
        data_formatada = f"{dia_semana}, {dia.strftime('%d/%m')}"

        linhas = []
        for evento in eventos_por_dia[dia]:
            linhas.append(f"🕒 **{evento['hora']}** - {evento['titulo']}")

        valor = "\n".join(linhas)
        embed.add_field(name=data_formatada, value=valor, inline=False)

    try:
        await canal.send(embed=embed)
        logger.info("✅ Calendário semanal enviado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao enviar calendário semanal: {e}")

async def enviar_calendario_diario(bot):
    await utils.carregar_configuracoes_calendario() 
    tz = timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))
    now = datetime.now(tz)
    canal_id = utils.calendario_config.get("canal_id")
    cargo_id = utils.calendario_config.get("cargo_mention_id")  # opcional para mencionar cargo

    if not canal_id:
        logger.warning("Canal do calendário não configurado para envio diário.")
        return

    canal = bot.get_channel(canal_id)
    if not canal:
        logger.error(f"Canal do calendário (ID: {canal_id}) não encontrado para envio diário.")
        return

    eventos = await carregar_calendario()
    eventos_do_dia = [e for e in eventos if e.get("data") == now.strftime("%Y-%m-%d")]

    dia_semana = nome_dia_semana_pt(now.strftime("%A"))

    embed = discord.Embed(
        title=f"🗓️ Eventos de Hoje - {dia_semana}, {now.strftime('%d/%m/%Y')}",
        color=utils.calendario_config.get("cor_embed", 0x9B59B6)
    )
    embed.set_thumbnail(url=utils.calendario_config.get("thumbnail_url", "https://cdn-icons-png.flaticon.com/128/591/591576.png"))
    embed.set_footer(text=get_footer_text())

    if eventos_do_dia:
        for evento in eventos_do_dia:
            embed.add_field(
                name=f"🕒 {evento['hora']} - {evento['titulo']}",
                value=f"📍 {evento['local']}\n📝 {evento['descricao']}",
                inline=False
            )
    else:
        embed.add_field(
            name="Nenhum evento programado para hoje.",
            value="Fique atento para novas atualizações!",
            inline=False
        )

    mencao = f"<@&{cargo_id}>" if cargo_id else ""

    try:
        await canal.send(content=mencao, embed=embed)
        logger.info("✅ Calendário diário enviado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao enviar calendário diário: {e}")

def limpar_eventos_antigos():
    """
    Remove eventos cuja data já passou do arquivo de calendário.
    """
    try:
        eventos = utils.carregar_calendario()
        tz = timezone(utils.calendario_config.get("timezone", "America/Sao_Paulo"))
        hoje = datetime.now(tz).date()

        eventos_validos = []
        for e in eventos:
            try:
                data_evento = datetime.strptime(e["data"], "%Y-%m-%d").date()
                if data_evento >= hoje:
                    eventos_validos.append(e)
            except Exception as err:
                logger.error(f"Erro ao interpretar data do evento para limpeza: {err}")

        if len(eventos_validos) < len(eventos):
            utils.salvar_calendario(eventos_validos)
            logger.info(f"🧹 Limpeza realizada: {len(eventos) - len(eventos_validos)} evento(s) removido(s).")
        else:
            logger.info("🧹 Limpeza: Nenhum evento antigo para remover.")

    except Exception as e:
        logger.error(f"Erro ao limpar eventos antigos: {e}")

class Calendario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        utils.carregar_configuracoes_calendario()
        self.scheduler = AsyncIOScheduler(timezone=utils.calendario_config.get("timezone", "America/Sao_Paulo"))
        self.scheduler.add_job(self.enviar_calendario_semanal_job, CronTrigger(day_of_week='sun', hour=9, minute=0))
        self.scheduler.add_job(self.enviar_calendario_diario_job, CronTrigger(hour=9, minute=0))
        self.scheduler.add_job(self.enviar_calendario_diario_job, CronTrigger(hour=15, minute=0))
        self.scheduler.add_job(limpar_eventos_antigos, CronTrigger(hour=4, minute=0))
        self.scheduler.start()

    async def enviar_calendario_semanal_job(self):
        await enviar_calendario_semanal(self.bot)

    async def enviar_calendario_diario_job(self):
        await enviar_calendario_diario(self.bot)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("✅ Módulo de Calendário carregado e pronto.")
        self.bot.add_view(CalendarioView())
        

    @app_commands.command(name="calendario", description="Mostra o calendário de eventos da semana")
    async def mostrar_calendario(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await enviar_calendario_semanal(self.bot)
        await interaction.followup.send("📅 Calendário semanal enviado no canal configurado.", ephemeral=True)

    @app_commands.command(name="configurar_calendario", description="Abre o painel de administração do calendário")
    @app_commands.checks.has_permissions(administrator=True)
    async def configurar_calendario(self, interaction: discord.Interaction):
        await utils.carregar_configuracoes_calendario() 
        eventos = await carregar_calendario()

        embed = discord.Embed(
            title="🗓️ Calendário da Guilda - Administração",
            description="Eventos programados para os próximos dias:",
            color=utils.calendario_config.get("cor_embed", 0x9B59B6)
        )
        embed.set_thumbnail(url=utils.calendario_config.get("thumbnail_url", "https://cdn-icons-png.flaticon.com/128/591/591576.png"))
        embed.set_footer(text=get_footer_text())

        if not eventos:
            embed.description = "Nenhum evento cadastrado no momento."
        else:
            eventos_por_dia = {}
            for evento in eventos:
                try:
                    data_evento = datetime.strptime(evento["data"], "%Y-%m-%d").date()
                except Exception:
                    continue
                eventos_por_dia.setdefault(data_evento, []).append(evento)

            dias_ordenados = sorted(eventos_por_dia.keys())

            for dia in dias_ordenados:
                dia_semana = nome_dia_semana_pt(dia.strftime("%A"))
                data_formatada = f"{dia_semana}, {dia.strftime('%d/%m')}"
                texto = ""
                for evento in eventos_por_dia[dia]:
                    texto += f"⏰ **{evento['hora']}** - {evento['titulo']}\n"
                    texto += f"📍 **Local:** {evento['local']}\n"
                    desc_curta = evento['descricao'][:100] + ("..." if len(evento['descricao']) > 100 else "")
                    texto += f"📝 **Descrição:** {desc_curta}\n\n"

                embed.add_field(name=f"📌 {data_formatada}", value=texto, inline=False)

        view = CalendarioView()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Calendario(bot))

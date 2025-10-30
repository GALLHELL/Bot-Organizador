import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os
from datetime import datetime, timedelta

# --- INÍCIO: Funções de Utils movidas para dentro do Cog ---
# Isso torna o cog autossuficiente e evita erros de importação.

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
MISSIONS_FILE = os.path.join(DATA_DIR, "missions.json")
RANKING_FILE = os.path.join(DATA_DIR, "ranking.json")
HISTORICO_FILE = os.path.join(DATA_DIR, "historico.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- FIM: Funções de Utils ---


# --- DEFINIÇÕES DE XP E RANKS ---
XP_POR_NIVEL = {
    "extra grande": 100,
    "grande": 75,
    "pequeno": 50,
    "vida": 50
}

def get_rank(xp: int):
    if xp >= 1000: return "Lendário", "🏆"
    if xp >= 700:  return "Elite", "💎"
    if xp >= 400:  return "Veterano", "⚔️"
    if xp >= 150:  return "Aprendiz", "🛡️"
    return "Novato", "🌱"

# --- CLASSES DE UI (BOTÕES, MODAIS, VIEWS) ---
class Paginator(View):
    def __init__(self, update_func, custom_id_prefix: str):
        super().__init__(timeout=None)
        self.current_page = 0
        self.total_pages = 1
        self.update_func = update_func
        self.prev_button.custom_id = f"{custom_id_prefix}_prev"
        self.next_button.custom_id = f"{custom_id_prefix}_next"

    def set_page_info(self, current_page: int, total_pages: int):
        self.current_page = current_page
        self.total_pages = total_pages

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = (self.current_page - 1) % self.total_pages
        await self.update_func(interaction, self.current_page)

    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = (self.current_page + 1) % self.total_pages
        await self.update_func(interaction, self.current_page)

class CriarMissaoModal(Modal):
    def __init__(self, nivel: str, cog):
        super().__init__(title=f"Criar Missão - {nivel.title()}")
        self.nivel = nivel
        self.cog = cog
        self.nome = TextInput(label="Nome da missão", placeholder="Ex: Patrulha no Setor Leste", max_length=50)
        self.local = TextInput(label="Local da missão", placeholder="Ex: Antiga fábrica", max_length=50)
        self.horario_inicio = TextInput(label="Horário de início (HH:MM)", placeholder="Ex: 21:00", max_length=5)
        self.duracao_horas = TextInput(label="Duração em horas", placeholder="Ex: 4", max_length=2)
        self.add_item(self.nome); self.add_item(self.local); self.add_item(self.horario_inicio); self.add_item(self.duracao_horas)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.criar_missao(interaction, self.nivel, self.nome.value, self.local.value, self.horario_inicio.value, self.duracao_horas.value)

class MissaoControlView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        for nivel in XP_POR_NIVEL.keys():
            btn = Button(label=nivel.title(), style=discord.ButtonStyle.primary, custom_id=f"criar_missao_{nivel.replace(' ', '_')}")
            async def callback(interaction: discord.Interaction, n=nivel):
                await interaction.response.send_modal(CriarMissaoModal(n, self.cog))
            btn.callback = callback
            self.add_item(btn)
        finalizar_btn = Button(label="Finalizar Missão", style=discord.ButtonStyle.danger, custom_id="iniciar_finalizacao")
        async def finalizar_callback(interaction: discord.Interaction):
            await self.cog.iniciar_finalizacao_manual(interaction)
        finalizar_btn.callback = finalizar_callback
        self.add_item(finalizar_btn)

class MissaoAtivaView(View):
    def __init__(self, missao_id: str, cog):
        super().__init__(timeout=None)
        self.cog = cog
        participar_btn = Button(label="Participar", style=discord.ButtonStyle.success, custom_id=f"participar_{missao_id}")
        async def participar_callback(interaction: discord.Interaction):
            await self.cog.participar_missao(interaction, missao_id)
        participar_btn.callback = participar_callback
        self.add_item(participar_btn)

# --- COG PRINCIPAL DO BOT ---
class MissoesCog(commands.Cog, name="MissoesCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_json(CONFIG_FILE, {})
        self.missions = load_json(MISSIONS_FILE, {})
        self.missions.setdefault("ativas", {})  # ← ESSA LINHA É ESSENCIAL
        self.ranking = load_json(RANKING_FILE, {})
        self.historico = load_json(HISTORICO_FILE, [])

        # As views de paginação agora são atributos do próprio cog
        self.ranking_paginator = Paginator(self._update_ranking_embed, "ranking")
        self.historico_paginator = Paginator(self._update_historico_embed, "historico")
        
        self.check_expired_missions.start()

    def cog_unload(self):
        self.check_expired_missions.cancel()

    def save_all_data(self):
        save_json(CONFIG_FILE, self.config); save_json(MISSIONS_FILE, self.missions); save_json(RANKING_FILE, self.ranking); save_json(HISTORICO_FILE, self.historico)

    @tasks.loop(minutes=1)
    async def check_expired_missions(self):
        now = datetime.now()
        for missao_id, data in list(self.missions.get("ativas", {}).items()):
            end_time_str = data.get("end_time")
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str)
                if now >= end_time:
                    print(f"Missão '{data['nome']}' expirou. Finalizando automaticamente.")
                    await self.finalizar_missao(missao_id, "Finalizada (Automático)")

    @check_expired_missions.before_loop
    async def before_check_expired(self):
        await self.bot.wait_until_ready()

    # --- COMANDOS DE CONFIGURAÇÃO ---
    
    async def _fixar_canal(self, interaction: discord.Interaction, tipo_canal: str, canal: discord.TextChannel):
        self.config[f"canal_{tipo_canal}"] = canal.id
        self.save_all_data()
        await interaction.response.send_message(f"Canal de `{tipo_canal}` fixado em {canal.mention}!", ephemeral=True)

    @app_commands.command(name="fixar_missao", description="Define o canal para o painel e embeds de missões.")
    @app_commands.checks.has_permissions(administrator=True)
    async def fixar_missao(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await self._fixar_canal(interaction, "missao", canal)

    @app_commands.command(name="fixar_historico", description="Define o canal para o painel fixo de histórico.")
    @app_commands.checks.has_permissions(administrator=True)
    async def fixar_historico(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await self._fixar_canal(interaction, "historico", canal)

    @app_commands.command(name="fixar_ranking", description="Define o canal para o painel fixo de ranking.")
    @app_commands.checks.has_permissions(administrator=True)
    async def fixar_ranking(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await self._fixar_canal(interaction, "ranking", canal)

    # --- COMANDO /MISSAO ---

    @app_commands.command(name="missao", description="Cria o painel fixo para criar e gerenciar missões.")
    @app_commands.checks.has_permissions(administrator=True)
    async def missao(self, interaction: discord.Interaction):
        canal_id = self.config.get("canal_missao")
        if not canal_id:
            return await interaction.response.send_message("Canal de missões não configurado. Use `/fixar_missao`.", ephemeral=True)
        
        canal = self.bot.get_channel(canal_id)
        embed = discord.Embed(
            title="Painel de Controle de Missões",
            description=(
                "Use os botões abaixo para gerenciar as missões do servidor.\n\n"
                "▶️ **Criar Missão**: Escolha o nível para abrir um formulário.\n"
                "⏹️ **Finalizar Missão**: Encerra uma missão ativa manualmente."
            ),
            color=discord.Color.dark_green()
        )
        embed.set_thumbnail(url="https://i.imgur.com/0RHV6zY.png" )
        
        view = MissaoControlView(self)
        await canal.send(embed=embed, view=view)
        await interaction.response.send_message(f"Painel de missões criado em {canal.mention}!", ephemeral=True)

    # --- LÓGICA DE MISSÕES ---

    async def criar_missao(self, interaction: discord.Interaction, nivel, nome, local, horario_inicio, duracao_horas):
        await interaction.response.defer(ephemeral=True)
        
        # Validações
        try:
            inicio = datetime.strptime(horario_inicio, "%H:%M").time()
            duracao = int(duracao_horas)
            if not (0 < duracao <= 48): raise ValueError
        except ValueError:
            return await interaction.followup.send("Horário (HH:MM) ou duração (1-48h) inválidos.", ephemeral=True)

        canal_id = self.config.get("canal_missao")
        canal = self.bot.get_channel(canal_id)
        if not canal:
            return await interaction.followup.send("Canal de missões não configurado.", ephemeral=True)

        missao_id = str(interaction.id)
        end_time = datetime.now() + timedelta(hours=duracao)

        # Salva a missão
        self.missions["ativas"][missao_id] = {
            "nome": nome, "local": local, "horario_inicio": horario_inicio,
            "duracao": duracao, "nivel": nivel, "participantes": [],
            "end_time": end_time.isoformat(), "msg_id": None,
            "channel_id": canal_id, "owner_id": interaction.user.id
        }
        
        embed = self.build_mission_embed(missao_id)
        view = MissaoAtivaView(missao_id, self)
        
        msg = await canal.send(embed=embed, view=view)
        self.missions["ativas"][missao_id]["msg_id"] = msg.id
        self.save_all_data()

        await interaction.followup.send(f"Missão '{nome}' criada com sucesso em {canal.mention}!", ephemeral=True)

    async def participar_missao(self, interaction: discord.Interaction, missao_id: str):
        missao = self.missions["ativas"].get(missao_id)
        user_id = str(interaction.user.id)

        if not missao:
            return await interaction.response.send_message("Esta missão não está mais ativa.", ephemeral=True)
        if user_id in missao["participantes"]:
            return await interaction.response.send_message("Você já está participando desta missão.", ephemeral=True)

        missao["participantes"].append(user_id)
        self.save_all_data()

        # Atualiza o embed da missão
        embed = self.build_mission_embed(missao_id)
        await interaction.response.edit_message(embed=embed)

    def build_mission_embed(self, missao_id: str):
        data = self.missions["ativas"][missao_id]
        end_time = datetime.fromisoformat(data['end_time'])
        
        participantes_str = "\n".join(f"<@{p}>" for p in data['participantes']) if data['participantes'] else "Nenhum participante ainda."

        embed = discord.Embed(
            title=f"🚨 Missão Ativa: {data['nome']}",
            description=f"**Nível:** {data['nivel'].title()}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Local", value=data['local'], inline=True)
        embed.add_field(name="Início", value=f"{data['horario_inicio']}h", inline=True)
        embed.add_field(name="Duração", value=f"{data['duracao']}h", inline=True)
        embed.add_field(name="Termina em", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
        embed.add_field(name="👥 Participantes", value=participantes_str, inline=False)
        embed.set_footer(text=f"ID da Missão: {missao_id}")
        return embed

    async def iniciar_finalizacao_manual(self, interaction: discord.Interaction):
        ativas = self.missions["ativas"]
        if not ativas:
            return await interaction.response.send_message("Não há missões ativas para finalizar.", ephemeral=True)

        options = [
            discord.SelectOption(label=f"{data['nome']} ({data['nivel'].title()})", value=mid)
            for mid, data in ativas.items()
        ]
        
        select = Select(placeholder="Escolha a missão para finalizar...", options=options)

        async def select_callback(inter: discord.Interaction):
          missao_id = inter.data['values'][0]
          nome_missao = ativas[missao_id]["nome"]  # ← SALVA ANTES
          await self.finalizar_missao(missao_id, f"Finalizada por {inter.user.display_name}")
          await inter.response.send_message(f"Missão '{nome_missao}' finalizada com sucesso!", ephemeral=True)
          await interaction.delete_original_response()


        select.callback = select_callback
        view = View().add_item(select)
        await interaction.response.send_message("Selecione a missão:", view=view, ephemeral=True)

    async def finalizar_missao(self, missao_id: str, status: str):
        missao = self.missions["ativas"].pop(missao_id, None)
        if not missao: return

        # Apaga o embed da missão ativa
        try:
            canal = self.bot.get_channel(missao["channel_id"])
            msg = await canal.fetch_message(missao["msg_id"])
            await msg.delete()
        except (discord.NotFound, discord.Forbidden, KeyError):
            print(f"Não foi possível deletar a mensagem da missão {missao_id}.")

        # Calcula e distribui XP
        participantes = missao["participantes"]
        xp_total = XP_POR_NIVEL.get(missao["nivel"], 0)
        xp_por_player = xp_total // len(participantes) if participantes else 0

        if xp_por_player > 0:
            for uid in participantes:
                if uid not in self.ranking:
                    self.ranking[uid] = {"xp": 0, "ultima_missao": None}
                self.ranking[uid]["xp"] += xp_por_player
                self.ranking[uid]["ultima_missao"] = missao["nome"]

        # Adiciona ao histórico
        missao_historico = {
            "nome": missao["nome"], "nivel": missao["nivel"],
            "participantes": participantes, "xp_distribuido": xp_por_player,
            "status": status, "timestamp": datetime.now().isoformat()
        }
        self.historico.insert(0, missao_historico) # Insere no início (mais recente)
        
        self.save_all_data()

        # Atualiza os painéis fixos
        await self._update_ranking_embed(None, 0)
        await self._update_historico_embed(None, 0)

    # --- COMANDOS E LÓGICA DE RANKING E HISTÓRICO ---

    async def _update_ranking_embed(self, interaction: discord.Interaction | None, page: int = 0):
        canal_id = self.config.get("canal_ranking")
        if not canal_id: return
        canal = self.bot.get_channel(canal_id)
        if not canal: return

        ranking_sorted = sorted(self.ranking.items(), key=lambda item: item[1].get("xp", 0), reverse=True)
        pag_size = 10
        total_pages = max(1, (len(ranking_sorted) + pag_size - 1) // pag_size)
        page = max(0, min(page, total_pages - 1)) # Garante que a página é válida
        
        start_index = page * pag_size
        end_index = start_index + pag_size
        page_items = ranking_sorted[start_index:end_index]

        embed = discord.Embed(title="🏆 Ranking de Contribuição", color=discord.Color.purple())
        if not page_items:
            embed.description = "O ranking está vazio."
        else:
            for i, (uid, data) in enumerate(page_items, start=start_index + 1):
                rank_name, emoji = get_rank(data.get("xp", 0))
                member = canal.guild.get_member(int(uid))
                nome = member.display_name if member else f"ID: {uid}"
                embed.add_field(
                    name=f"{i}. {emoji} {nome} - {rank_name}",
                    value=f"**XP:** {data.get('xp', 0)} | **Última Missão:** {data.get('ultima_missao', 'N/A')}",
                    inline=False
                )
        embed.set_footer(text=f"Página {page + 1}/{total_pages}")

        view = self.ranking_paginator
        view.set_page_info(page, total_pages)

        if interaction:
            await interaction.response.edit_message(embed=embed, view=view)
        else: # Atualização automática
            msg_id = self.config.get("ranking_embed_id")
            if msg_id:
                try:
                    msg = await canal.fetch_message(msg_id)
                    await msg.edit(embed=embed, view=view)
                except discord.NotFound:
                    self.config["ranking_embed_id"] = None; self.save_all_data()

    @app_commands.command(name="ranking", description="Cria o painel fixo e persistente de ranking.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ranking(self, interaction: discord.Interaction):
        canal_id = self.config.get("canal_ranking")
        if not canal_id: return await interaction.response.send_message("Canal de ranking não configurado.", ephemeral=True)
        canal = self.bot.get_channel(canal_id)
        
        view = self.ranking_paginator
        embed = discord.Embed(title="🏆 Ranking de Contribuição", description="Carregando...", color=discord.Color.purple())
        
        msg = await canal.send(embed=embed, view=view)
        self.config["ranking_embed_id"] = msg.id
        self.save_all_data()
        
        await self._update_ranking_embed(None, 0)
        await interaction.response.send_message(f"Painel de ranking criado em {canal.mention}!", ephemeral=True)

    async def _update_historico_embed(self, interaction: discord.Interaction | None, page: int = 0):
        canal_id = self.config.get("canal_historico")
        if not canal_id: return
        canal = self.bot.get_channel(canal_id)
        if not canal: return

        pag_size = 5
        total_pages = max(1, (len(self.historico) + pag_size - 1) // pag_size)
        page = max(0, min(page, total_pages - 1))
        
        start_index = page * pag_size
        end_index = start_index + pag_size
        page_items = self.historico[start_index:end_index]

        embed = discord.Embed(title="📜 Histórico de Missões", color=discord.Color.gold())
        if not page_items:
            embed.description = "Nenhuma missão no histórico."
        else:
            for item in page_items:
                timestamp = datetime.fromisoformat(item['timestamp'])
                embed.add_field(
                    name=f"✅ {item['nome']} ({item['nivel'].title()})",
                    value=(
                        f"**Finalizada em:** <t:{int(timestamp.timestamp())}:f>\n"
                        f"**Status:** {item['status']}\n"
                        f"**XP por Membro:** {item['xp_distribuido']}\n"
                        f"**Participantes:** {', '.join(f'<@{p}>' for p in item['participantes']) or 'Nenhum'}"
                    ),
                    inline=False
                )
        embed.set_footer(text=f"Página {page + 1}/{total_pages}")

        view = self.historico_paginator
        view.set_page_info(page, total_pages)

        if interaction:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            msg_id = self.config.get("historico_embed_id")
            if msg_id:
                try:
                    msg = await canal.fetch_message(msg_id)
                    await msg.edit(embed=embed, view=view)
                except discord.NotFound:
                    self.config["historico_embed_id"] = None; self.save_all_data()

    @app_commands.command(name="historico", description="Cria o painel fixo e persistente de histórico.")
    @app_commands.checks.has_permissions(administrator=True)
    async def historico(self, interaction: discord.Interaction):
        canal_id = self.config.get("canal_historico")
        if not canal_id: return await interaction.response.send_message("Canal de histórico não configurado.", ephemeral=True)
        canal = self.bot.get_channel(canal_id)
        
        view = self.historico_paginator
        embed = discord.Embed(title="📜 Histórico de Missões", description="Carregando...", color=discord.Color.gold())
        
        msg = await canal.send(embed=embed, view=view)
        self.config["historico_embed_id"] = msg.id
        self.save_all_data()
        
        await self._update_historico_embed(None, 0)
        await interaction.response.send_message(f"Painel de histórico criado em {canal.mention}!", ephemeral=True)

# --- COG PARA GERENCIAR VIEWS PERSISTENTES ---
class ViewManager(commands.Cog, name="ViewManager"):
    def __init__(self, bot, missoes_cog):
        self.bot = bot
        self.ranking_paginator = Paginator(missoes_cog._update_ranking_embed, "ranking")
        self.historico_paginator = Paginator(missoes_cog._update_historico_embed, "historico")

    async def iniciar_views(self):
        missoes_cog = self.bot.get_cog("MissoesCog")

        self.bot.add_view(self.ranking_paginator)
        self.bot.add_view(self.historico_paginator)
        self.bot.add_view(MissaoControlView(missoes_cog))

        missions = load_json(MISSIONS_FILE, {"ativas": {}})
        for missao_id in missions["ativas"]:
            self.bot.add_view(MissaoAtivaView(missao_id, missoes_cog))

        config = load_json(CONFIG_FILE, {})
        if config.get("ranking_embed_id") and config.get("canal_ranking"):
            await missoes_cog._update_ranking_embed(None, 0)

        if config.get("historico_embed_id") and config.get("canal_historico"):
            await missoes_cog._update_historico_embed(None, 0)

# --- FUNÇÃO SETUP (PONTO DE ENTRADA DO COG) ---
async def setup(bot: commands.Bot):
    # Cria uma instância do Cog
    cog = MissoesCog(bot)
    await bot.add_cog(cog)

    # Inicializa ViewManager com carregamento das views e painéis
    view_manager = ViewManager(bot, cog)
    await view_manager.iniciar_views()
    bot.add_cog(view_manager)
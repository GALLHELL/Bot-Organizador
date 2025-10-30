import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from pytz import timezone
import json
import os
import logging

from . import utils
from .raids import RAIDS, HORARIOS, participantes, salvar_estado, criar_embed_raid, criar_embed_lembrete

logger = logging.getLogger(__name__)

DATA_PATH = "data"
CANAL_TEMP_FILE = os.path.join(DATA_PATH, "canais_temporarios.json")

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task_initialized = False
        self.canais_temporarios = {}  # {guild_id: {f"{raid}_{hora}": {"canal_id": id, "criacao": iso_str}}}
        self.load_canais_temporarios()

    def load_canais_temporarios(self):
        if not os.path.exists(DATA_PATH):
            os.makedirs(DATA_PATH)
        if os.path.isfile(CANAL_TEMP_FILE):
            try:
                with open(CANAL_TEMP_FILE, "r", encoding="utf-8") as f:
                    self.canais_temporarios = json.load(f)
                    # Converte chaves de guild para int (pois JSON salva como string)
                    self.canais_temporarios = {int(k): v for k, v in self.canais_temporarios.items()}
                logger.info(f"✅ Canais temporários carregados de {CANAL_TEMP_FILE}")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar canais temporários: {e}")
                self.canais_temporarios = {}
        else:
            self.canais_temporarios = {}

    def save_canais_temporarios(self):
        try:
            with open(CANAL_TEMP_FILE, "w", encoding="utf-8") as f:
                json.dump(self.canais_temporarios, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Canais temporários salvos em {CANAL_TEMP_FILE}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar canais temporários: {e}")

    async def setup_hook(self):
        self.start_tasks()

    def start_tasks(self):
        if self._task_initialized:
            return
        if not self.limpar_canais_task.is_running():
            self.limpar_canais_task.start()
        if not self.reset_task.is_running():
            self.reset_task.start()
        if not self.enviar_lembretes.is_running():
            self.enviar_lembretes.start()
        if not self.deletar_canais_temporarios.is_running():
            self.deletar_canais_temporarios.start()
        if not self.renovar_raids.is_running():
            self.renovar_raids.start()
        self._task_initialized = True
        logger.info("✅ Todas as tarefas foram iniciadas")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._task_initialized:
            self.start_tasks()

    @tasks.loop(minutes=5)
    async def limpar_canais_task(self):
        try:
            tz = timezone("America/Sao_Paulo")
            now = datetime.now(tz)
            for guild in self.bot.guilds:
                for channel in guild.voice_channels:
                    if channel.category and channel.category.id == utils.CATEGORIA_VOZ_ID:
                        if not channel.members:
                            created_at = channel.created_at
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=tz)
                            inactive_time = now - created_at
                            if inactive_time.total_seconds() > utils.TEMPO_VIDA_CANAL * 60:
                                try:
                                    await channel.delete(reason="Limpeza automática de canal temporário")
                                    logger.info(f"♻️ Canal '{channel.name}' deletado por inatividade")
                                except discord.Forbidden:
                                    logger.warning(f"⛔ Sem permissão para deletar canal {channel.name}")
                                except discord.HTTPException as e:
                                    logger.error(f"❌ Erro ao deletar canal: {e}")
        except Exception as e:
            logger.error(f"💥 Erro em limpar_canais_task: {e}")

    @tasks.loop(hours=24)
    async def reset_task(self):
        try:
            tz = timezone("America/Sao_Paulo")
            now = datetime.now(tz)
            if now.strftime("%H:%M") == utils.RESET_HORA:
                logger.info("🔄 Iniciando reset diário...")

                for raid in RAIDS:
                    for hora in HORARIOS:
                        participantes[raid][hora] = []
                salvar_estado()

                raids_cog = self.bot.get_cog("Raids")
                if raids_cog:
                    for raid, info in RAIDS.items():
                        if info.get("canal_id"):
                            try:
                                canal = self.bot.get_channel(info["canal_id"])
                                if canal:
                                    await raids_cog.limpar_mensagens_antigas(info["canal_id"])
                                    embed = criar_embed_raid(raid)
                                    view = raids_cog.HorarioView(raid)
                                    await canal.send(embed=embed, view=view)
                                    logger.info(f"📝 Raid {raid} atualizada")
                            except Exception as e:
                                logger.error(f"⚠️ Erro ao atualizar {raid}: {e}")

                logger.info("✅ Reset diário concluído")
        except Exception as e:
            logger.error(f"💥 Erro no reset_task: {e}")

    @tasks.loop(minutes=1)
    async def enviar_lembretes(self):
        try:
            tz = timezone("America/Sao_Paulo")
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")

            for raid, horarios in participantes.items():
                for hora, users in horarios.items():
                    if not users:
                        continue

                    hora_raid = datetime.strptime(hora, "%H:%M").time()
                    lembrete_time = (datetime.combine(now.date(), hora_raid) - timedelta(minutes=15)).strftime("%H:%M")

                    if current_time == lembrete_time:
                        # Enviar lembretes DM
                        embed = criar_embed_lembrete(raid, hora)
                        for user_id_str in users:
                            try:
                                user = await self.bot.fetch_user(int(user_id_str))
                                if user:
                                    await user.send(embed=embed)
                                    logger.info(f"✉️ Lembrete de {raid} enviado para {user.name}")
                            except Exception as e:
                                logger.error(f"❌ Erro ao enviar lembrete para ID {user_id_str}: {e}")

                        # Criar canal temporário de voz
                        for guild in self.bot.guilds:
                            categoria = discord.utils.get(guild.categories, id=utils.CATEGORIA_VOZ_ID)
                            if categoria:
                                nome_canal = f"Raid {raid} - {hora}"
                                # Verifica se canal já existe na categoria
                                existe = any(c.name == nome_canal for c in categoria.voice_channels)
                                if not existe:
                                    canal = await categoria.create_voice_channel(
                                        name=nome_canal,
                                        reason="Canal temporário para raid",
                                        user_limit=10
                                    )
                                    self.canais_temporarios.setdefault(guild.id, {})
                                    self.canais_temporarios[guild.id][f"{raid}_{hora}"] = {
                                        "canal_id": canal.id,
                                        "criacao": datetime.now(tz).isoformat()
                                    }
                                    self.save_canais_temporarios()
                                    logger.info(f"🎤 Canal temporário criado: {nome_canal} ({canal.id})")

        except Exception as e:
            logger.error(f"💥 Erro em enviar_lembretes: {e}")

    @tasks.loop(minutes=5)
    async def deletar_canais_temporarios(self):
        try:
            tz = timezone("America/Sao_Paulo")
            now = datetime.now(tz)

            for guild_id, canais in list(self.canais_temporarios.items()):
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                for key, info in list(canais.items()):
                    canal = guild.get_channel(info["canal_id"])
                    if not canal:
                        del canais[key]
                        continue

                    criacao = datetime.fromisoformat(info["criacao"])
                    diff = now - criacao
                    if diff.total_seconds() > 2 * 60 * 60:  # 2 horas
                        try:
                            await canal.delete(reason="Expirou canal temporário de raid")
                            logger.info(f"🗑 Canal temporário deletado: {canal.name} ({canal.id})")
                        except Exception as e:
                            logger.error(f"❌ Erro ao deletar canal temporário {canal.id}: {e}")
                        del canais[key]

                if not canais:
                    del self.canais_temporarios[guild_id]

            self.save_canais_temporarios()

        except Exception as e:
            logger.error(f"💥 Erro em deletar_canais_temporarios: {e}")

    @tasks.loop(hours=24)
    async def renovar_raids(self):
        try:
            tz = timezone("America/Sao_Paulo")
            now = datetime.now(tz)
            if now.strftime("%H:%M") == "00:05":
                raids_cog = self.bot.get_cog("Raids")
                if raids_cog:
                    for raid, info in RAIDS.items():
                        if info.get("canal_id"):
                            try:
                                canal = self.bot.get_channel(info["canal_id"])
                                if canal:
                                    await raids_cog.limpar_mensagens_antigas(info["canal_id"])
                                    embed = criar_embed_raid(raid)
                                    view = raids_cog.HorarioView(raid)
                                    await canal.send(embed=embed, view=view)
                                    logger.info(f"🔄 Raid {raid} renovada")
                            except Exception as e:
                                logger.error(f"❌ Erro ao renovar {raid}: {e}")
        except Exception as e:
            logger.error(f"💥 Erro em renovar_raids: {e}")

    def cog_unload(self):
        tasks = [
            self.limpar_canais_task,
            self.reset_task,
            self.enviar_lembretes,
            self.deletar_canais_temporarios,
            self.renovar_raids
        ]
        for task in tasks:
            if task.is_running():
                task.cancel()
        logger.info("⏹️ Todas as tarefas do cog Tasks foram paradas")

async def setup(bot):
    await bot.add_cog(Tasks(bot))

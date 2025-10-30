import json
import os
import logging
import aiofiles

logger = logging.getLogger(__name__)

# --- Variáveis de Configuração Globais ---
CATEGORIA_VOZ_ID = 1253823465962864896  # ID da categoria para canais de voz temporários
TEMPO_VIDA_CANAL = 120  # Tempo em minutos para canais de voz inativos serem deletados
RESET_HORA = "00:30"  # Hora para reset diário de eventos/presenças
CALENDARIO_COR_EMBED = 0x9B59B6  # Cor padrão para embeds do calendário
LIMPAR_MENSAGENS_ANTIGAS = True  # Configuração para limpar mensagens antigas do bot

# Configuração padrão do calendário (pode ser atualizada pelo cog de calendário)
calendario_config = {
    "canal_id": 1390817125861687407,
    "cargo_mention_id": 1391669606564892713,  # ID do cargo para menção, opcional
    "cor_embed": 0x9B59B6,
    "thumbnail_url": "https://i.imgur.com/JL1SfQj.png",
    "timezone": "America/Sao_Paulo"
}

# --- Caminhos de Arquivo de Dados ---
CALENDARIO_FILE = "data/calendario_semanal.json"
CALENDARIO_MSG_FILE = "data/mensagem_calendario.json"
CALENDARIO_CONFIG_FILE = "data/calendario_config.json"
GUIAS_FILE = "data/guias.json"
MSG_JSON_CONFIG_FILE = "data/mensagem_json_config.json"
MENSAGENS_EVENTOS_FILE = "data/mensagens_eventos.json"  # Para o sistema de raids/eventos

# --- Funções Utilitárias Genéricas ---

async def carregar_guias():
    """Carrega os guias do arquivo JSON async."""
    try:
        if os.path.exists(GUIAS_FILE):
            async with aiofiles.open(GUIAS_FILE, 'r', encoding='utf-8') as f:
                conteudo = await f.read()
                return json.loads(conteudo)
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar guias: {e}")
        return {}

async def salvar_guias(guias):
    """Salva os guias no arquivo JSON async."""
    try:
        os.makedirs(os.path.dirname(GUIAS_FILE), exist_ok=True)
        async with aiofiles.open(GUIAS_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(guias, indent=4, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Erro ao salvar guias: {e}")

# --- Funções para o calendário ---

async def carregar_calendario():
    try:
        if os.path.exists(CALENDARIO_FILE):
            async with aiofiles.open(CALENDARIO_FILE, 'r', encoding='utf-8') as f:
                conteudo = await f.read()
                return json.loads(conteudo)
        return []
    except Exception as e:
        logger.error(f"Erro ao carregar calendário: {e}")
        return []

async def salvar_calendario(eventos):
    try:
        os.makedirs(os.path.dirname(CALENDARIO_FILE), exist_ok=True)
        async with aiofiles.open(CALENDARIO_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(eventos, indent=4, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Erro ao salvar calendário: {e}")

async def salvar_mensagem_calendario(msg_id, canal_id):
    try:
        os.makedirs(os.path.dirname(CALENDARIO_MSG_FILE), exist_ok=True)
        async with aiofiles.open(CALENDARIO_MSG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps({"msg_id": msg_id, "canal_id": canal_id}))
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem do calendário: {e}")

async def carregar_mensagem_calendario():
    try:
        if os.path.exists(CALENDARIO_MSG_FILE):
            async with aiofiles.open(CALENDARIO_MSG_FILE, 'r', encoding='utf-8') as f:
                conteudo = await f.read()
                data = json.loads(conteudo)
                return data.get("msg_id"), data.get("canal_id")
        return None, None
    except Exception as e:
        logger.error(f"Erro ao carregar mensagem do calendário: {e}")
        return None, None

async def salvar_configuracoes_calendario():
    try:
        os.makedirs(os.path.dirname(CALENDARIO_CONFIG_FILE), exist_ok=True)
        async with aiofiles.open(CALENDARIO_CONFIG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(calendario_config, indent=4))
    except Exception as e:
        logger.error(f"Erro ao salvar configurações do calendário: {e}")

async def carregar_configuracoes_calendario():
    try:
        if os.path.exists(CALENDARIO_CONFIG_FILE):
            async with aiofiles.open(CALENDARIO_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conteudo = await f.read()
                configuracoes = json.loads(conteudo)
                calendario_config.update(configuracoes)
    except Exception as e:
        logger.error(f"Erro ao carregar configurações do calendário: {e}")

# Define o que será exportado
__all__ = [
    'CATEGORIA_VOZ_ID', 'TEMPO_VIDA_CANAL', 'RESET_HORA', 'CALENDARIO_COR_EMBED',
    'LIMPAR_MENSAGENS_ANTIGAS', 'calendario_config',
    'CALENDARIO_FILE', 'CALENDARIO_MSG_FILE', 'CALENDARIO_CONFIG_FILE',
    'GUIAS_FILE', 'MSG_JSON_CONFIG_FILE', 'MENSAGENS_EVENTOS_FILE',
    'carregar_guias', 'salvar_guias',
    'carregar_calendario', 'salvar_calendario',
    'salvar_mensagem_calendario', 'carregar_mensagem_calendario',
    'salvar_configuracoes_calendario', 'carregar_configuracoes_calendario',
]

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
import uuid
import re
import logging

from .utils import carregar_guias, salvar_guias  # import async do seu utils

logger = logging.getLogger(__name__)

# Modal para adicionar/editar guia com múltiplos links
class GuideModal(Modal):
    def __init__(self, category: str, guide_id: str = None):
        super().__init__(title="📝 Gerenciar Guia")
        self.category = category
        self.guide_id = guide_id

        self.titulo = TextInput(label="Título do Guia", placeholder="Ex: Guia de Farm de Prata", required=True)
        self.links = TextInput(
            label="Links (uma por linha, formato: Nome | URL)",
            style=discord.TextStyle.paragraph,
            placeholder="Exemplo:\nYouTube | https://youtube.com/xyz\nDoc | https://docs.com/abc",
            required=True,
            max_length=1000
        )
        self.add_item(self.titulo)
        self.add_item(self.links)

        # Como é async, não pode chamar direto no init — vamos guardar para carregar depois
        self._initial_data_loaded = False

    async def _load_initial_data(self):
        if self._initial_data_loaded:
            return
        guias = await carregar_guias()
        if self.guide_id is not None and self.category in guias:
            guia = next((g for g in guias[self.category] if g['id'] == self.guide_id), None)
            if guia:
                self.titulo.default = guia['title']
                links_texto = ""
                for l in guia.get('links', []):
                    links_texto += f"{l.get('label','Link')} | {l.get('url','')}\n"
                self.links.default = links_texto.strip()
        self._initial_data_loaded = True

    async def on_submit(self, interaction: discord.Interaction):
        # Certifique-se de carregar os defaults async
        await self._load_initial_data()

        titulo = self.titulo.value.strip()
        raw_links = self.links.value.strip()

        links = []
        for linha in raw_links.splitlines():
            if "|" not in linha:
                await interaction.response.send_message(f"❌ Formato inválido na linha: `{linha}`\nUse: Nome | URL", ephemeral=True)
                return
            label, url = map(str.strip, linha.split("|", 1))
            if not re.match(r'^https?://', url):
                await interaction.response.send_message(f"❌ Link inválido na linha: `{linha}`\nDeve começar com http:// ou https://", ephemeral=True)
                return
            links.append({"label": label, "url": url})

        if not links:
            await interaction.response.send_message("❌ Você precisa adicionar pelo menos um link válido.", ephemeral=True)
            return

        guias = await carregar_guias()
        if self.category not in guias:
            guias[self.category] = []

        if self.guide_id:
            # Editar existente
            for i, g in enumerate(guias[self.category]):
                if g['id'] == self.guide_id:
                    guias[self.category][i]['title'] = titulo
                    guias[self.category][i]['links'] = links
                    break
            msg = "✏️ Guia editado com sucesso!"
            cor = discord.Color.orange()
        else:
            # Adicionar novo
            guias[self.category].append({'id': str(uuid.uuid4()), 'title': titulo, 'links': links})
            msg = "✅ Guia adicionado com sucesso!"
            cor = discord.Color.green()

        await salvar_guias(guias)

        embed = discord.Embed(
            title=msg,
            description=f"**Categoria:** `{self.category}`\n**Título:** {titulo}\n**Links:**\n" + "\n".join([f"[{l['label']}]({l['url']})" for l in links]),
            color=cor
        )
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/5659/5659405.png")
        embed.set_footer(text="Use /guia para visualizar os guias disponíveis.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Botão voltar para lista de categorias
class BackButton(Button):
    def __init__(self, bot: commands.Bot, categories: list, is_admin: bool):
        super().__init__(label="◀️ Voltar", style=discord.ButtonStyle.secondary)
        self.bot = bot
        self.categories = categories
        self.is_admin = is_admin

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 Biblioteca de Guias",
            description="Selecione uma categoria abaixo para visualizar os guias disponíveis.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/5659/5659405.png")
        embed.set_footer(text="Use o menu para navegar entre categorias.")

        view = GuideCategoryView(self.bot, self.categories, self.is_admin)
        await interaction.response.edit_message(embed=embed, view=view)

class GuideViewWithBack(View):
    def __init__(self, bot: commands.Bot, categories: list):
        super().__init__(timeout=900)
        self.bot = bot
        self.categories = categories
        self.add_item(BackButton(bot, categories, is_admin=False))

# Select para categorias na tela inicial
class CategorySelect(Select):
    def __init__(self, bot: commands.Bot, categories: list, is_admin: bool):
        options = [discord.SelectOption(label=c, value=c) for c in categories]
        super().__init__(placeholder="Selecione uma categoria", options=options, min_values=1, max_values=1)
        self.bot = bot
        self.categories = categories
        self.is_admin = is_admin

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        guias = await carregar_guias()
        guias_categoria = guias.get(category, [])

        embed = discord.Embed(
            title=f"📖 Guias: {category}",
            description="Clique nos links abaixo para abrir os guias.\n" +
                        ("Use os botões para gerenciar os guias desta categoria." if self.is_admin else ""),
            color=discord.Color.teal()
        )
        if guias_categoria:
            for guia in guias_categoria:
                links_formatados = "\n".join(f"[{l['label']}]({l['url']})" for l in guia.get('links', []))
                embed.add_field(name=guia['title'], value=links_formatados or "Sem links.", inline=False)
        else:
            embed.description += "\n\n⚠️ Nenhum guia disponível nesta categoria."

        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/5659/5659405.png")

        footer_text = "Use o menu para escolher outra categoria."
        if self.is_admin:
            footer_text += " Use os botões abaixo para adicionar, editar ou remover guias."
        embed.set_footer(text=footer_text)

        if self.is_admin:
            view = GuideManagementViewWithBack(self.bot, category, self.categories, self.is_admin)
        else:
            view = GuideViewWithBack(self.bot, self.categories)  # botão voltar só para usuários comuns

        await interaction.response.edit_message(embed=embed, view=view)

# View para tela inicial (lista de categorias)
class GuideCategoryView(View):
    def __init__(self, bot: commands.Bot, categories: list, is_admin: bool):
        super().__init__(timeout=900)
        self.bot = bot
        self.categories = categories
        self.is_admin = is_admin
        self.add_item(CategorySelect(bot, categories, is_admin))
        if is_admin:
            self.add_item(AddCategoryButton())
            self.add_item(EditCategoryButton())
            self.add_item(DeleteCategoryButton())

# View para visualização da categoria com gerenciador + botão voltar
class GuideManagementViewWithBack(View):
    def __init__(self, bot: commands.Bot, category: str, categories: list, is_admin: bool):
        super().__init__(timeout=900)
        self.bot = bot
        self.category = category
        self.categories = categories
        self.is_admin = is_admin

        self.add_item(BackButton(bot, categories, is_admin))
        self.add_item(AddGuideButton(bot, category))
        self.add_item(EditGuideButton(bot, category))
        self.add_item(RemoveGuideButton(bot, category))

# Botão para adicionar guia
class AddGuideButton(Button):
    def __init__(self, bot: commands.Bot, category: str):
        super().__init__(label="➕ Adicionar Guia", style=discord.ButtonStyle.success)
        self.bot = bot
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        modal = GuideModal(self.category)
        await modal._load_initial_data()  # carregar dados iniciais antes de abrir modal
        await interaction.response.send_modal(modal)

# Botão para editar guia
class EditGuideButton(Button):
    def __init__(self, bot: commands.Bot, category: str):
        super().__init__(label="✏️ Editar Guia", style=discord.ButtonStyle.primary)
        self.bot = bot
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        guias = await carregar_guias()
        guias_categoria = guias.get(self.category, [])
        if not guias_categoria:
            await interaction.response.send_message("⚠️ Nenhum guia para editar nesta categoria.", ephemeral=True)
            return

        options = [discord.SelectOption(label=g['title'], value=g['id']) for g in guias_categoria]
        select = Select(placeholder="Escolha um guia para editar", options=options, max_values=1, min_values=1)

        async def select_callback(select_interaction: discord.Interaction):
            guide_id = select_interaction.data['values'][0]
            modal = GuideModal(self.category, guide_id)
            await modal._load_initial_data()
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Selecione o guia para editar:", view=view, ephemeral=True)

# Botão para remover guia
class RemoveGuideButton(Button):
    def __init__(self, bot: commands.Bot, category: str):
        super().__init__(label="🗑️ Remover Guia", style=discord.ButtonStyle.danger)
        self.bot = bot
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        guias = await carregar_guias()
        guias_categoria = guias.get(self.category, [])
        if not guias_categoria:
            await interaction.response.send_message("⚠️ Nenhum guia para remover nesta categoria.", ephemeral=True)
            return

        options = [discord.SelectOption(label=g['title'], value=g['id']) for g in guias_categoria]
        select = Select(placeholder="Escolha um guia para remover", options=options, max_values=1, min_values=1)

        async def select_callback(select_interaction: discord.Interaction):
            guide_id = select_interaction.data['values'][0]
            guias = await carregar_guias()
            guias[self.category] = [g for g in guias.get(self.category, []) if g['id'] != guide_id]
            await salvar_guias(guias)
            await select_interaction.response.send_message("🗑️ Guia removido com sucesso!", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Selecione o guia para remover:", view=view, ephemeral=True)

# Modal para editar categoria (muda o nome)
class EditCategoryModal(Modal):
    def __init__(self, old_name: str):
        super().__init__(title="✏️ Editar Categoria")
        self.old_name = old_name
        self.nome = TextInput(label="Novo nome da categoria", default=old_name, required=True, max_length=50)
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction):
        novo_nome = self.nome.value.strip()
        if not novo_nome:
            await interaction.response.send_message("❌ Nome inválido.", ephemeral=True)
            return

        guias = await carregar_guias()
        if novo_nome == self.old_name:
            await interaction.response.send_message("⚠️ O nome é o mesmo. Nada foi alterado.", ephemeral=True)
            return

        if novo_nome in guias:
            await interaction.response.send_message(f"❌ A categoria `{novo_nome}` já existe.", ephemeral=True)
            return

        # Renomear a categoria (mudar a chave do dicionário)
        guias[novo_nome] = guias.pop(self.old_name)
        await salvar_guias(guias)
        await interaction.response.send_message(f"✅ Categoria renomeada para `{novo_nome}` com sucesso!", ephemeral=True)

# Modal para apagar categoria (confirmação simples)
class DeleteCategoryModal(Modal):
    def __init__(self, category_name: str):
        super().__init__(title="🗑️ Apagar Categoria")
        self.category_name = category_name
        self.confirm = TextInput(
            label="Digite 'CONFIRMAR' para apagar a categoria",
            placeholder=f"Apagar categoria: {category_name}",
            required=True,
            max_length=20
        )
        self.add_item(self.confirm)

    async def on_submit(self, interaction: discord.Interaction):
        texto = self.confirm.value.strip()
        if texto != "CONFIRMAR":
            await interaction.response.send_message("❌ Confirmação inválida. A categoria NÃO foi apagada.", ephemeral=True)
            return

        guias = await carregar_guias()
        if self.category_name in guias:
            guias.pop(self.category_name)
            await salvar_guias(guias)
            await interaction.response.send_message(f"✅ Categoria `{self.category_name}` apagada com sucesso!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Categoria não encontrada.", ephemeral=True)

# Botão para editar categoria (abre modal para renomear)
class EditCategoryButton(Button):
    def __init__(self):
        super().__init__(label="✏️ Editar Categoria", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        guias = await carregar_guias()
        categorias = list(guias.keys())
        if not categorias:
            await interaction.response.send_message("⚠️ Nenhuma categoria para editar.", ephemeral=True)
            return

        options = [discord.SelectOption(label=c, value=c) for c in categorias]
        select = Select(placeholder="Selecione a categoria para editar", options=options, max_values=1, min_values=1)

        async def select_callback(select_interaction: discord.Interaction):
            categoria = select_interaction.data['values'][0]
            modal = EditCategoryModal(categoria)
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Escolha a categoria para editar:", view=view, ephemeral=True)

# Botão para apagar categoria (abre modal para confirmar exclusão)
class DeleteCategoryButton(Button):
    def __init__(self):
        super().__init__(label="🗑️ Apagar Categoria", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        guias = await carregar_guias()
        categorias = list(guias.keys())
        if not categorias:
            await interaction.response.send_message("⚠️ Nenhuma categoria para apagar.", ephemeral=True)
            return

        options = [discord.SelectOption(label=c, value=c) for c in categorias]
        select = Select(placeholder="Selecione a categoria para apagar", options=options, max_values=1, min_values=1)

        async def select_callback(select_interaction: discord.Interaction):
            categoria = select_interaction.data['values'][0]
            modal = DeleteCategoryModal(categoria)
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Escolha a categoria para apagar:", view=view, ephemeral=True)

# Modal para criar nova categoria
class NewCategoryModal(Modal):
    def __init__(self):
        super().__init__(title="🆕 Criar Nova Categoria")
        self.nome = TextInput(label="Nome da Categoria", placeholder="Digite o nome da nova categoria", required=True, max_length=50)
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome.value.strip()
        if not nome:
            await interaction.response.send_message("❌ Nome inválido.", ephemeral=True)
            return

        guias = await carregar_guias()
        if nome in guias:
            await interaction.response.send_message(f"❌ A categoria `{nome}` já existe.", ephemeral=True)
            return

        guias[nome] = []
        await salvar_guias(guias)
        await interaction.response.send_message(f"✅ Categoria `{nome}` criada com sucesso!", ephemeral=True)

# Botão para abrir modal de nova categoria
class AddCategoryButton(Button):
    def __init__(self):
        super().__init__(label="🆕 Nova Categoria", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        modal = NewCategoryModal()
        await interaction.response.send_modal(modal)

class GuideChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = {}
        self.channel_id = None
        bot.loop.create_task(self._carregar_config())

    async def _carregar_config(self):
        try:
            from .utils import carregar_config
        except ImportError:
            carregar_config = None

        if carregar_config:
            self.config = await carregar_config()
        self.channel_id = self.config.get("guide_channel_id")

    @app_commands.command(name="guia", description="📚 Exibe o painel de guias por categoria.")
    async def guias(self, interaction: discord.Interaction):
        guias = await carregar_guias()
        categorias = list(guias.keys())
        is_admin = interaction.user.guild_permissions.manage_messages
        view = GuideCategoryView(self.bot, categorias, is_admin)
        embed = discord.Embed(
            title="📚 Biblioteca de Guias",
            description="Selecione uma categoria abaixo para visualizar os guias disponíveis.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Use o menu para navegar entre categorias.")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/5659/5659405.png")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="enviar_guias", description="📤 Envia uma embed pública com todos os guias organizados por categoria.")
    async def enviar_guias(self, interaction: discord.Interaction):
        # Verifica permissão do usuário
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
            return

        guias = await carregar_guias()
        if not guias:
            await interaction.response.send_message("⚠️ Nenhum guia cadastrado ainda.", ephemeral=True)
            return

        embeds = []
        for categoria, lista_guias in guias.items():
            if not lista_guias:
                continue

            texto = ""
            for guia in lista_guias:
                titulo = guia.get("title", "Sem Título")
                links = guia.get("links", [])
                links_formatados = "\n".join(f"[{l['label']}]({l['url']})" for l in links)
                texto += f"**{titulo}**\n{links_formatados}\n\n"

            embed = discord.Embed(
                title=f"📖 Guias: {categoria}",
                description=texto.strip() or "Nenhum guia disponível.",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/5659/5659405.png")
            embed.set_footer(text="Use /guia para acessar o painel interativo de navegação.")
            embeds.append(embed)

        MAX_EMBEDS = 10  # limite do Discord por mensagem
        if len(embeds) > MAX_EMBEDS:
            # Se tiver mais de 10 categorias, avisa e só manda as 10 primeiras
            await interaction.response.send_message(
                f"⚠️ Existem muitas categorias ({len(embeds)}). Mostrando as primeiras {MAX_EMBEDS}.", ephemeral=True
            )
            embeds = embeds[:MAX_EMBEDS]

        # Envia todos os embeds juntos, visíveis para todos
        await interaction.response.send_message(embeds=embeds)

async def setup(bot):
    await bot.add_cog(GuideChannel(bot))


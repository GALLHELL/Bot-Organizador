import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import json
import os

GUILD_ID = 1253822715375390780
WELCOME_JSON_PATH = "data/welcome.json"
BIRTHDAY_JSON_PATH = "data/birthdays.json"
PARABENS_CHANNEL_ID = 1390817125861687407
LOG_CHANNEL_ID = 1253822853695012918

def load_config():
    default = {
        "welcome_channel_id": 1253823054824345653,
        "default_role_id": 1253825850269372446,
        "users_changed_nick": []  # Corrigido: vírgula após o item anterior
    }
    
    os.makedirs("data", exist_ok=True)
    
    if not os.path.exists(WELCOME_JSON_PATH):
        with open(WELCOME_JSON_PATH, "w") as f:
            json.dump(default, f, indent=4)
        return default
    else:
        with open(WELCOME_JSON_PATH, "r") as f:
            config = json.load(f)
        
        updated = False
        for key in default:
            if key not in config:
                config[key] = default[key]
                updated = True
        if updated:
            save_config(config)

        return config

def save_config(data):
    with open(WELCOME_JSON_PATH, "w") as f:
        json.dump(data, f, indent=4)

def load_birthdays():
    if not os.path.exists(BIRTHDAY_JSON_PATH):
        with open(BIRTHDAY_JSON_PATH, "w") as f:
            json.dump({}, f, indent=4)
        return {}
    else:
        with open(BIRTHDAY_JSON_PATH, "r") as f:
            return json.load(f)

def save_birthdays(data):
    with open(BIRTHDAY_JSON_PATH, "w") as f:
        json.dump(data, f, indent=4)

async def log_to_discord(bot, message: str, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            if embed:
                await channel.send(content=message, embed=embed)
            else:
                await channel.send(message)
    except Exception as e:
        print(f"Falha ao enviar log: {e}")

class BirthdayModal(discord.ui.Modal, title="🎂 Definir Aniversário"):
    def __init__(self, bot, user_id: int):
        super().__init__()
        self.bot = bot
        self.user_id = str(user_id)
        self.birthday = discord.ui.TextInput(
            label="Digite sua data de aniversário (dd/mm)",
            placeholder="Exemplo: 09/07",
            max_length=5,
            min_length=5,
            required=True
        )
        self.add_item(self.birthday)

    async def on_submit(self, interaction: discord.Interaction):
        data = self.birthday.value
        try:
            datetime.datetime.strptime(data, "%d/%m")
        except ValueError:
            await interaction.response.send_message("❌ Formato inválido! Use DD/MM, exemplo: 09/07", ephemeral=True)
            return

        birthdays = load_birthdays()
        birthdays[self.user_id] = data
        save_birthdays(birthdays)

        await log_to_discord(self.bot, f"Aniversário registrado para <@{self.user_id}>: {data}")
        await interaction.response.send_message(f"✅ Aniversário registrado para {data}!", ephemeral=True)

class BirthdayButtonView(discord.ui.View):
    def __init__(self, bot, *, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot

    @discord.ui.button(label="🎂 Definir Aniversário", style=discord.ButtonStyle.blurple, custom_id="btn_birthday_set")
    async def birthday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BirthdayModal(self.bot, interaction.user.id)
        await interaction.response.send_modal(modal)

class NicknameModal(discord.ui.Modal, title="🛠️ Configurar Nome de Família"):
    def __init__(self, bot, user_id: int):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.nickname = discord.ui.TextInput(
            label="Digite seu nome de Família",
            placeholder="Exemplo: Jogador123",
            min_length=2,
            max_length=32,
            required=True
        )
        self.add_item(self.nickname)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Verifica se já mudou o nick antes
            config = load_config()
            if str(self.user_id) in config.get("users_changed_nick", []):
                await interaction.response.send_message(
                    "❌ Você já definiu seu nome de família anteriormente. Contate um moderador se precisar alterar.",
                    ephemeral=True
                )
                return

            guild = self.bot.get_guild(GUILD_ID)
            member = guild.get_member(self.user_id) if guild else None

            if member:
                await member.edit(nick=self.nickname.value)
                
                # Atualiza a lista de usuários que já mudaram o nick
                config = load_config()
                if "users_changed_nick" not in config:
                     config["users_changed_nick"] = []
                config["users_changed_nick"].append(str(self.user_id))
                save_config(config)

                await interaction.response.send_message(
                    f"✅ Seu nome de família foi definido como: **{self.nickname.value}**\n"
                    "⚠️ Você não poderá alterá-lo novamente por este botão.",
                    ephemeral=True
                )
                await log_to_discord(self.bot, f"{interaction.user.name} definiu seu apelido para: {self.nickname.value}")

                # Desabilita o botão na mensagem original
                view = WelcomeView(self.bot, self.user_id)
                for child in view.children:
                    if child.custom_id == "btn_nickname_set":
                        child.disabled = True
                try:
                    await interaction.message.edit(view=view)
                except Exception as e:
                    await log_to_discord(self.bot, f"Erro ao atualizar a view após mudar o nick: {e}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Não tenho permissão para alterar seu nome de família. Por favor, contate um moderador.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ocorreu um erro: {str(e)}",
                ephemeral=True
            )

class WelcomeView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id

    @discord.ui.button(label="🎂 Definir Aniversário", style=discord.ButtonStyle.blurple, custom_id="btn_birthday_set")
    async def birthday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BirthdayModal(self.bot, interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🛠️ Definir seu nome de família", style=discord.ButtonStyle.green, custom_id="btn_nickname_set")
    async def nickname_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se já mudou o nick antes
        config = load_config()
        if str(self.user_id) in config.get("users_changed_nick", []):
            await interaction.response.send_message(
                "❌ Você já definiu seu nome de família anteriormente. Contate um moderador se precisar alterar.",
                ephemeral=True
            )
            return

        modal = NicknameModal(self.bot, interaction.user.id)
        await interaction.response.send_modal(modal)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.welcome_channel_id = self.config.get("welcome_channel_id", 1253823054824345653)
        self.default_role_id = self.config.get("default_role_id", 1253825850269372446)
        self.rules_channel_id = 1253822853695012917
        self.parabens_channel_id = 1390817125861687407

        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        await log_to_discord(self.bot, "✅ Bot está pronto e operacional")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID or member.bot:
            return
            
        try:
            default_role = member.guild.get_role(self.default_role_id)
            if default_role:
                await member.add_roles(default_role)
                await log_to_discord(self.bot, f"Cargo padrão '{default_role.name}' atribuído a {member.display_name}")

            welcome_channel = self.bot.get_channel(self.welcome_channel_id)
            if welcome_channel:
                embed = discord.Embed(
                    title=f"🌟 Bem-vindo(a), {member.display_name}! 🌟",
                    description=(
                        f"{member.mention} acabou de entrar na nossa comunidade!\n\n"
                        f"📜 Leia as regras em <#{self.rules_channel_id}>\n"
                        f"🎖️ Cargo inicial: **{default_role.name if default_role else 'Membro'}**"
                    ),
                    color=0x1ABC9C,
                    timestamp=datetime.datetime.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"ID: {member.id} • Bot")
                await welcome_channel.send(embed=embed)

            try:
                dm_embed = discord.Embed(
                    title="🎉 Seja muito bem-vindo(a)!",
                    description=(
                        "Olá, aventureiro(a)! 👋\n\n"
                        "Você acabou de entrar em nossa guilda Bravura do Black Desert e estamos felizes em te receber!\n\n"
                        "**ATENÇÃO:** Você **DEVE** definir seu nome de família abaixo!\n\n"
                        "🛠️ **Como definir seu nome de família:**\n"
                        "1. Clique no botão 'Definir seu nome de família'\n"
                        "2. Digite o nome que deseja usar\n"
                        "3. Envie o formulário\n\n"
                        "⚠️ **Importante:**\n"
                        "• Só pode ser definido **UMA VEZ**\n"
                        "• Escolha com cuidado!\n"
                        "• Este será seu nome permanente na guilda\n\n"
                        "Aqui você encontrará ajuda, eventos organizados, atividades em grupo, dungeons, Node Wars, e muito mais.\n\n"
                        "📚 Comandos úteis:\n\n"
                        "/calendario — Veja os eventos da semana\n"
                        "/guia — Acesse guias úteis da guilda\n"
                        "/raids — Participe das nossas atividades em grupo\n"
                        "/aniversario - Para verificar os aniversariantes do Mês\n\n"
                        "​⁉️​ Não esqueça de habilitar para ver todos os canais (Clique no nome do servidor --> depois seleciona Mostrar todos os canais)​⁉️​\n\n"
                        "Se tiver qualquer dúvida, procure um Líder ou Oficial. Estamos aqui para te ajudar! ❤️"
                    ),
                    color=0x5865F2,
                    timestamp=datetime.datetime.utcnow()
                )
                dm_embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/128/14170/14170236.png")
                dm_embed.set_footer(text="Bot • Boas-vindas")
                
                # Verifica se já mudou o nick antes
                config = load_config()
                view = WelcomeView(self.bot, member.id)
                if str(member.id) in config.get("users_changed_nick", []):
                    for child in view.children:
                        if child.custom_id == "btn_nickname_set":
                            child.disabled = True
                
                await member.send(embed=dm_embed, view=view)
            except discord.Forbidden:
                await log_to_discord(self.bot, f"Não foi possível enviar DM para {member.name}")

        except Exception as e:
            await log_to_discord(self.bot, f"Erro no sistema de boas-vindas: {str(e)}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            channel = self.bot.get_channel(self.welcome_channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"👋 Adeus, {member.display_name}!",
                    description="Esperamos que volte um dia! 🌟",
                    color=0xE74C3C,
                    timestamp=datetime.datetime.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text="Bot • Saída")
                await channel.send(embed=embed)
            await log_to_discord(self.bot, f"{member.display_name} saiu do servidor")
        except Exception as e:
            await log_to_discord(self.bot, f"Erro na mensagem de saída: {str(e)}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.guild.id != GUILD_ID or message.author.bot:
            return
        
        embed = discord.Embed(
            title="🗑️ Mensagem Apagada",
            description=f"Mensagem de {message.author.mention} foi deletada em <#{message.channel.id}>",
            color=0xff0000,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Conteúdo", value=message.content[:1024] or "*(vazio ou mídia)*", inline=False)
        embed.set_footer(text=f"ID: {message.author.id}")
        await log_to_discord(self.bot, "", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.guild.id != GUILD_ID or before.author.bot or before.content == after.content:
            return
            
        embed = discord.Embed(
            title="✏️ Mensagem Editada",
            description=f"Mensagem de {before.author.mention} editada em <#{before.channel.id}>",
            color=0xffff00,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Antes", value=before.content[:1024] or "*(vazio ou mídia)*", inline=False)
        embed.add_field(name="Depois", value=after.content[:1024] or "*(vazio ou mídia)*", inline=False)
        embed.set_footer(text=f"ID: {before.author.id}")
        await log_to_discord(self.bot, "", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.guild.id != GUILD_ID or member.bot:
            return
            
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="🎤 Entrou em Voz",
                description=f"{member.mention} entrou no canal de voz {after.channel.mention}",
                color=0x00ff00,
                timestamp=datetime.datetime.utcnow()
            )
            await log_to_discord(self.bot, "", embed)
            
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="🎤 Saiu de Voz",
                description=f"{member.mention} saiu do canal de voz {before.channel.mention}",
                color=0xff0000,
                timestamp=datetime.datetime.utcnow()
            )
            await log_to_discord(self.bot, "", embed)
            
        elif before.channel != after.channel:
            embed = discord.Embed(
                title="🎤 Movido em Voz",
                description=f"{member.mention} mudou de {before.channel.mention} para {after.channel.mention}",
                color=0x0000ff,
                timestamp=datetime.datetime.utcnow()
            )
            await log_to_discord(self.bot, "", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.guild.id != GUILD_ID or before.bot:
            return
            
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Nickname Alterado",
                color=0x00ffff,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Antes", value=before.nick or before.name, inline=True)
            embed.add_field(name="Depois", value=after.nick or after.name, inline=True)
            embed.set_author(name=f"{before.name} (ID: {before.id})", icon_url=before.display_avatar.url)
            await log_to_discord(self.bot, "", embed)
            
        if before.roles != after.roles:
            added = [role for role in after.roles if role not in before.roles]
            removed = [role for role in before.roles if role not in after.roles]
            
            if added or removed:
                embed = discord.Embed(
                    title="🎭 Cargos Alterados",
                    description=f"Alteração de cargos para {after.mention}",
                    color=0x800080,
                    timestamp=datetime.datetime.utcnow()
                )
                
                if added:
                    embed.add_field(name="Adicionados", value=", ".join([r.mention for r in added]), inline=False)
                if removed:
                    embed.add_field(name="Removidos", value=", ".join([r.mention for r in removed]), inline=False)
                    
                await log_to_discord(self.bot, "", embed)

    @app_commands.command(name="set_welcome", description="Configura o sistema de boas-vindas")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome(self, interaction: discord.Interaction, 
                         canal: discord.TextChannel = None, 
                         cargo: discord.Role = None):
        updated = False
        if canal:
            self.welcome_channel_id = canal.id
            self.config["welcome_channel_id"] = canal.id
            updated = True
        if cargo:
            self.default_role_id = cargo.id
            self.config["default_role_id"] = cargo.id
            updated = True

        if updated:
            save_config(self.config)

        await log_to_discord(self.bot, f"Configurações de boas-vindas atualizadas por {interaction.user.name}")
        await interaction.response.send_message(
            f"✅ Configurações atualizadas:\n"
            f"Canal: {canal.mention if canal else 'Não alterado'}\n"
            f"Cargo: {cargo.mention if cargo else 'Não alterado'}",
            ephemeral=True
        )

    @app_commands.command(name="ver_aniversario", description="Veja os aniversários registrados")
    async def ver_aniversario(self, interaction: discord.Interaction):
        birthdays = load_birthdays()
        if not birthdays:
            await interaction.response.send_message("🎂 Nenhum aniversário foi registrado ainda.", ephemeral=True)
            return

        guild = interaction.guild or self.bot.get_guild(GUILD_ID)
        lines = []
        for user_id, date in birthdays.items():
            member = guild.get_member(int(user_id)) or await self.bot.fetch_user(int(user_id))
            if member:
                lines.append(f"{member.mention} — **{date}**")

        content = "\n".join(lines) if lines else "🎂 Nenhum aniversário encontrado."
        embed = discord.Embed(
            title="📅 Aniversários Registrados",
            description=content,
            color=0xFFC0CB
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=datetime.timezone.utc))
    async def check_birthdays(self):
        today = datetime.datetime.utcnow().strftime("%d/%m")
        birthdays = load_birthdays()
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            await log_to_discord(self.bot, "⚠️ Guild não encontrada para verificar aniversários")
            return

        for user_id, data in birthdays.items():
            if data == today:
                member = guild.get_member(int(user_id))
                if member:
                    embed = discord.Embed(
                        title="🎉 Feliz Aniversário! 🎂",
                        description=f"Hoje é o aniversário do(a) {member.mention}! Que seu dia seja incrível! 🥳",
                        color=0xFFD700,
                        timestamp=datetime.datetime.utcnow()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text="Bot • Parabéns!")
                    try:
                        channel = guild.get_channel(self.parabens_channel_id)
                        if channel:
                            await channel.send(embed=embed)
                        await member.send(embed=embed)
                        await log_to_discord(self.bot, f"Parabéns enviados para {member.display_name} pelo aniversário!")
                    except discord.Forbidden:
                        await log_to_discord(self.bot, f"Não foi possível enviar mensagem de aniversário para {member.display_name}")

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Welcome(bot))
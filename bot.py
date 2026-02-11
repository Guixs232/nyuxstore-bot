import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
import aiosqlite
import os
import random
import string
import asyncio
from datetime import datetime, timedelta
import pytz

# Pega das variáveis de ambiente da Railway
TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_ID_STR = os.environ.get('ADMIN_ID', '1134304730835861504')

# Verifica se o token existe
if not TOKEN:
    print("❌ ERRO: DISCORD_TOKEN não encontrado!")
    print("Verifique se a variável está configurada na Railway.")
    exit(1)

ADMIN_ID = int(ADMIN_ID_STR)

print(f"✅ Token carregado: {TOKEN[:20]}...")
print(f"✅ Admin ID: {ADMIN_ID}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class Database:
    def __init__(self):
        self.db_path = "nyux_store.db"
    
    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS contas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jogo TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    login TEXT NOT NULL,
                    senha TEXT NOT NULL,
                    adicionado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usado_por INTEGER DEFAULT NULL,
                    usado_em TIMESTAMP DEFAULT NULL,
                    status TEXT DEFAULT 'disponivel'
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_code TEXT UNIQUE NOT NULL,
                    duracao TEXT NOT NULL,
                    cargo TEXT NOT NULL,
                    criado_por INTEGER NOT NULL,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usado_por INTEGER DEFAULT NULL,
                    usado_em TIMESTAMP DEFAULT NULL,
                    ativa INTEGER DEFAULT 1
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                )
            ''')
            await db.commit()
    
    async def add_conta(self, jogo, categoria, login, senha):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO contas (jogo, categoria, login, senha) VALUES (?, ?, ?, ?)",
                (jogo.strip().title(), categoria.strip().title(), login, senha)
            )
            await db.commit()
    
    async def buscar_conta(self, nome_jogo):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM contas WHERE jogo LIKE ? AND status = 'disponivel' LIMIT 1",
                (f"%{nome_jogo}%",)
            )
            return await cursor.fetchone()
    
    async def get_contas_por_categoria(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT categoria, jogo, login, senha FROM contas WHERE status = 'disponivel' ORDER BY categoria, jogo"
            )
            return await cursor.fetchall()
    
    async def marcar_conta_usada(self, conta_id, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE contas SET status = 'usada', usado_por = ?, usado_em = ? WHERE id = ?",
                (user_id, datetime.now(), conta_id)
            )
            await db.commit()
    
    async def criar_key(self, duracao, cargo, admin_id):
        key_code = f"NYUX-STORE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO keys (key_code, duracao, cargo, criado_por) VALUES (?, ?, ?, ?)",
                    (key_code, duracao, cargo, admin_id)
                )
                await db.commit()
                return key_code
            except:
                return await self.criar_key(duracao, cargo, admin_id)
    
    async def validar_key(self, key_code, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM keys WHERE key_code = ? AND ativa = 1 AND usado_por IS NULL",
                (key_code,)
            )
            key = await cursor.fetchone()
            if key:
                await db.execute(
                    "UPDATE keys SET usado_por = ?, usado_em = ? WHERE id = ?",
                    (user_id, datetime.now(), key[0])
                )
                await db.commit()
                return key
            return None
    
    async def set_config(self, chave, valor):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
                (chave, valor)
            )
            await db.commit()
    
    async def get_config(self, chave):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT valor FROM config WHERE chave = ?", (chave,))
            result = await cursor.fetchone()
            return result[0] if result else None

db = Database()

class AdicionarContaModal(Modal, title="➕ Adicionar Nova Conta"):
    jogo = TextInput(label="Nome do Jogo", placeholder="Ex: Assassin's Creed Shadows", required=True)
    categoria = TextInput(label="Categoria", placeholder="Ex: Ação, Aventura, Corrida", required=True)
    login = TextInput(label="Login Steam", placeholder="Usuário da conta", required=True)
    senha = TextInput(label="Senha Steam", placeholder="Senha da conta", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await db.add_conta(self.jogo.value, self.categoria.value, self.login.value, self.senha.value)
        await interaction.response.send_message(
            f"✅ Conta adicionada!\n🎮 **{self.jogo.value}**\n📂 Categoria: {self.categoria.value}", 
            ephemeral=True
        )

class BuscarJogoModal(Modal, title="🔍 Buscar Jogo"):
    nome = TextInput(label="Nome do Jogo", placeholder="Digite o nome do jogo...", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        conta = await db.buscar_conta(self.nome.value)
        if conta:
            embed = discord.Embed(
                title=f"🎮 {conta[1]}",
                description="Conta encontrada! Aproveite seu jogo.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 Login", value=f"`{conta[3]}`", inline=False)
            embed.add_field(name="🔒 Senha", value=f"`{conta[4]}`", inline=False)
            embed.add_field(name="⚠️ Aviso", value="Mude para **MODO OFFLINE** antes de jogar!", inline=False)
            embed.set_footer(text="NyuxStore")
            
            await db.marcar_conta_usada(conta[0], interaction.user.id)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Jogo não encontrado ou não disponível.", 
                ephemeral=True
            )

class ResgatarKeyModal(Modal, title="🎁 Resgatar Key"):
    key = TextInput(label="Sua Key", placeholder="NYUX-STORE-XXXXX", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        key_data = await db.validar_key(self.key.value.upper(), interaction.user.id)
        if key_data:
            cargo_nome = key_data[3]
            cargo = discord.utils.get(interaction.guild.roles, name=cargo_nome)
            
            if cargo:
                await interaction.user.add_roles(cargo)
                await interaction.response.send_message(
                    f"✅ **Key resgatada!**\n🏆 Cargo: {cargo.mention}\n⏰ Duração: {key_data[2]}", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("⚠️ Cargo não encontrado.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Key inválida.", ephemeral=True)

class PainelAdminView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="➕ Adicionar Conta", style=discord.ButtonStyle.green, custom_id="admin_add")
    async def add_conta(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        await interaction.response.send_modal(AdicionarContaModal())
    
    @discord.ui.button(label="🔑 Gerar Key", style=discord.ButtonStyle.blurple, custom_id="admin_key")
    async def gerar_key(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        
        class KeyModal(Modal, title="🔑 Gerar Key"):
            duracao = TextInput(label="Duração", placeholder="7d, 1m, 1a, lifetime", required=True)
            cargo = TextInput(label="Cargo", placeholder="Vip Pack", required=True)
            
            async def on_submit(modal_self, interaction: discord.Interaction):
                key = await db.criar_key(modal_self.duracao.value, modal_self.cargo.value, interaction.user.id)
                await interaction.response.send_message(f"🔑 Key gerada:\n`{key}`", ephemeral=True)
        
        await interaction.response.send_modal(KeyModal())
    
    @discord.ui.button(label="📊 Estatísticas", style=discord.ButtonStyle.gray, custom_id="admin_stats")
    async def stats(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        
        async with aiosqlite.connect(db.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM contas WHERE status = 'disponivel'")
            disponiveis = (await cursor.fetchone())[0]
            
            cursor = await conn.execute("SELECT COUNT(*) FROM contas")
            total = (await cursor.fetchone())[0]
            
            cursor = await conn.execute("SELECT COUNT(*) FROM keys WHERE usado_por IS NULL")
            keys_ativas = (await cursor.fetchone())[0]
        
        embed = discord.Embed(title="📊 Estatísticas NyuxStore", color=discord.Color.blue())
        embed.add_field(name="🎮 Jogos Disponíveis", value=str(disponiveis), inline=True)
        embed.add_field(name="📊 Total de Jogos", value=str(total), inline=True)
        embed.add_field(name="🔑 Keys Ativas", value=str(keys_ativas), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PainelVipView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔍 Buscar Jogo", style=discord.ButtonStyle.green, custom_id="vip_buscar")
    async def buscar(self, interaction: discord.Interaction, button: Button):
        tem_cargo = any(role.name == "Vip Pack" for role in interaction.user.roles)
        if not tem_cargo and interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Precisa do cargo @Vip Pack!", ephemeral=True)
        await interaction.response.send_modal(BuscarJogoModal())
    
    @discord.ui.button(label="🎁 Resgatar Key", style=discord.ButtonStyle.blurple, custom_id="vip_resgatar")
    async def resgatar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ResgatarKeyModal())

class PainelPublicoView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 Resgatar Key", style=discord.ButtonStyle.green, custom_id="pub_resgatar")
    async def resgatar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ResgatarKeyModal())

class NyuxBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        await db.init()
        self.add_view(PainelAdminView())
        self.add_view(PainelVipView())
        self.add_view(PainelPublicoView())
    
    async def on_ready(self):
        print(f'✅ Bot online: {self.user}')
        print(f'✅ ID: {self.user.id}')
        await self.tree.sync()
        print('✅ Comandos sincronizados')

bot = NyuxBot()

@bot.tree.command(name="painel_admin", description="[ADMIN] Painel administrativo")
async def painel_admin(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Apenas dono!", ephemeral=True)
    
    embed = discord.Embed(
        title="🔧 PAINEL ADMIN - NYUXSTORE",
        description="Gerencie sua loja de contas Steam",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, view=PainelAdminView(), ephemeral=True)

@bot.tree.command(name="painel_vip", description="[VIP] Acesse seus jogos")
async def painel_vip(interaction: discord.Interaction):
    tem_cargo = any(role.name == "Vip Pack" for role in interaction.user.roles)
    if not tem_cargo and interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Precisa do @Vip Pack!", ephemeral=True)
    
    embed = discord.Embed(
        title="🎮 PAINEL VIP - NYUXSTORE",
        description=f"Olá {interaction.user.mention}! Acesse seus jogos.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=PainelVipView(), ephemeral=True)

@bot.tree.command(name="setup", description="[ADMIN] Painel público")
async def setup(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
    
    embed = discord.Embed(
        title="🎮 NYUXSTORE",
        description="🎁 Resgate sua key e acesse jogos premium!",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=PainelPublicoView())
    await interaction.response.send_message("✅ Painel enviado!", ephemeral=True)

print("🚀 Iniciando bot...")
bot.run(TOKEN)
            

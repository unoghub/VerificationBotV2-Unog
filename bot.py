import os
from dotenv import load_dotenv
import discord
import discord.ext.commands 
from tinydb import TinyDB, Query
from random import choice

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_NAME = 'verification_bot_db.json'
VERIFICATION_CODES_TABLE_NAME = 'verification_codes'
CATEGORIES_TABLE_NAME = 'categories'
colors = 0x7ac943, 0x563795, 0x2193c7

client = discord.ext.commands.Bot(command_prefix="/", intents=discord.Intents.all())

@client.event
async def on_ready():
    await client.tree.sync()

@client.command()
async def tree(ctx):
    await client.tree.sync()

@client.hybrid_command(name="register", with_app_command=True, description="Rol almak için kodu giriniz.", aliases=['kayit', 'kayıt', 'onay'])
@discord.app_commands.describe(verification_code = "Doğrulama kodu girin.")
async def register(ctx, verification_code: str):
    msg = ctx.message.clean_content
    msg_split = msg.split()

    if len(msg_split) == 1:
        await ctx.reply("Syntax: /register <verification-code>", delete_after=10, ephemeral=True, mention_author=True)
        return

    db = TinyDB(DB_NAME)
    table = db.table(VERIFICATION_CODES_TABLE_NAME)
    Data = Query()

    verificationData = table.get(Data.code == verification_code)

    if verificationData is None:
        await ctx.reply("Bu kod bulunamadı. Kontrol ediniz.", delete_after=10, ephemeral=True, mention_author=True)
        return

    memberId = verificationData.get("memberId")
    if memberId is not None:
        if memberId != ctx.author.id:
            await ctx.reply("Kodunuz daha önce kullanılmış!", delete_after=10, ephemeral=True, mention_author=True)
            return

    await ctx.reply("Başarılı!", delete_after=10, ephemeral=True, mention_author=True)

    try:
        await apply_category_roles(ctx, ctx.author, verificationData.get('category'))
    except Exception as e:
        await ctx.reply(f"Hata: lütfen bunu organizatörlere yollayın!\n {e} \nlütfen bunu organizatörlere yollayın!", ephemeral=True, mention_author=True)
        return
    try:
        await ctx.author.edit(nick=verificationData.get('nick'))
    except Exception as e:
        await ctx.reply(f"Hata: lütfen bunu organizatörlere yollayın!\n {e} \nlütfen bunu organizatörlere yollayın!", ephemeral=True, mention_author=True)
        return
    useCount = verificationData.get("useCount")
    if useCount is not None:
        useCount += 1
    else:
        useCount = 1

    table.update({'useCount': useCount, 'memberId': ctx.author.id}, Data.code == verification_code)


@client.hybrid_command(name="add_user", with_app_command=True, description="Kayıt için kullanıcı oluştur.")
@discord.app_commands.describe(nick_name = "Kullanıcı adı girin.", category_name = "Kategori adı girin.", verification_code = "Doğrulama kodu girin.")
async def add_user(ctx, nick_name: str, category_name: str, verification_code: str):
    if not is_user_admin(ctx.author):
        return

    db = TinyDB(DB_NAME)
    categories = db.table(CATEGORIES_TABLE_NAME)
    Data = Query()
    if categories.get(Data.category_name == category_name.casefold()) is None:
        await ctx.reply(f'Kategori "{category_name}" bulunamadı.\nLütfen listeden tam isim giriniz. /list_category\nYoksa kategori oluşturabilirsin. /add_category',
                         delete_after=15, ephemeral=True, mention_author=True)
        return

    verification_table = db.table(VERIFICATION_CODES_TABLE_NAME)
    Data = Query()
    if verification_table.get(Data.code == verification_code):
        await ctx.reply(f'Kod "{verification_code}" kullanımda.\nLütfen farklı bir kod giriniz.', delete_after=30, ephemeral=True, mention_author=True)
        return
    if verification_table.search(Data.nick == nick_name):
        verification_table.update({'category': category_name, 'code': verification_code}, Data.nick == nick_name)
    else:
        verification_table.upsert({'nick': nick_name, 'category': category_name, 'code': verification_code}, Data.code == verification_table)

    await ctx.reply(f'Kullanıcı kaydedildi.', delete_after=15, ephemeral=True, mention_author=True)


@client.hybrid_command(name="check_code", with_app_command=True, description="Kod kontrolu.")
@discord.app_commands.describe(verification_code = "Doğrulama kodu girin.")
async def check_code(ctx, verification_code: str):
    if not is_user_admin(ctx.author):
        return
    
    db = TinyDB(DB_NAME)
    table = db.table(VERIFICATION_CODES_TABLE_NAME)

    embed = discord.Embed(title="Kod kontrolu", color=choice(colors), url="https://unog.dev")
    checkingCode = verification_code
    Data = Query()
    verificationData = table.get(Data.code == checkingCode)
    respondTxt = ""
    if verificationData is None:
        respondTxt += f"`{checkingCode}` Bulunamadı."
    else:
        usage = verificationData.get("useCount")
        if usage is not None:
            memberId = verificationData.get("memberId")
            user: discord.Member = await ctx.guild.fetch_member(memberId)
            if user is not None:
                usageRespond = f"{user.mention} {usage} kere kullandı."
            else:
                usageRespond = f"Bilinmeyen bir kişi({memberId}) {usage} kere kullandı."
        else:
            usageRespond = "Hiç kullanılmamış."
        respondTxt += usageRespond
    embed.add_field(name=f"**{verificationData.get('category')}**: `{verificationData.get('code')}` ", value=f"{verificationData.get('nick')}\n{respondTxt}", inline=False)
    await ctx.reply(embed=embed, mention_author=True)


@client.hybrid_command(name="clear_usage", with_app_command=True, description="Kod kullanımını sıfırla.")
@discord.app_commands.describe(verification_code = "Doğrulama kodu girin.")
async def clear_usage(ctx, verification_code: str):
    if not is_user_admin(ctx.author):
        return
    db = TinyDB(DB_NAME)
    table = db.table(VERIFICATION_CODES_TABLE_NAME)
    Data = Query()

    table.update({'useCount': 0, 'memberId': None}, Data.code == verification_code)
    embed = discord.Embed(title="Kod kullanımı sıfırlandı.", description=f"Kod: `{verification_code}`\nİsim: `{table.get(Data.code == verification_code).get('nick')}`\nKategori: `{table.get(Data.code == verification_code).get('category')}`", color=choice(colors))
    await ctx.reply(embed=embed, mention_author=True)

  

@client.hybrid_command(name="add_category", with_app_command=True, description="Kayıt için kategori oluştur.")
@discord.app_commands.describe(category_name = "Kategori adı girin.", category_roles = "Kategori için rol girin.")
async def add_category(ctx, category_name: str, category_roles: discord.Role):
    if not is_user_admin(ctx.author):
        return


    db = TinyDB(DB_NAME)
    table = db.table(CATEGORIES_TABLE_NAME)
    Data = Query()

    if table.get(Data.category_name == category_name.casefold()):
        if not (str(category_roles.id) in table.get(Data.category_name == category_name.casefold()).get('roles')):
            table.update({'roles': table.get(Data.category_name == category_name.casefold()).get('roles') + "+" + str(category_roles.id)}, Data.category_name == category_name.casefold())
    else:
        table.upsert({'category_name': category_name.casefold(), 'roles': str(category_roles.id)},
                    Data.category_name == category_name.casefold())
    await ctx.reply(f'Katagori "{category_name}" tanımlandı.', delete_after=15, ephemeral=True, mention_author=True)

@client.hybrid_command(name="remove_category", with_app_command=True, description="Katergori sil.")
@discord.app_commands.describe(category_name = "Kategori adı girin.")
async def remove_category(ctx, category_name: str):
    if not is_user_admin(ctx.author):
        return

    db = TinyDB(DB_NAME)
    table = db.table(CATEGORIES_TABLE_NAME)
    Data = Query()

    try:
        table.remove(Data.category_name == category_name.casefold())
        await ctx.reply(f'Katagori "{category_name}" silindi.', delete_after=15, ephemeral=True, mention_author=True)
    except KeyError:
        await ctx.reply(f'Katagori "{category_name}" bulunamadı.', delete_after=15, ephemeral=True, mention_author=True)

@client.hybrid_command(name="list_category", with_app_command=True, description="Katergorileri listele.")
async def list_category(ctx):
    if not is_user_admin(ctx.author):
        return
    db = TinyDB(DB_NAME)
    table = db.table(CATEGORIES_TABLE_NAME)
    embed = discord.Embed(title="Kategoriler", color=choice(colors), url="https://unog.dev")

    for category in table.all():
        roles = category.get('roles').split("+")
        role = ""
        for i in roles:
            role += (discord.utils.get(ctx.guild.roles, id=int(i))).mention + "\n"
        embed.add_field(name=category.get('category_name'), value=role, inline=False)

    await ctx.reply(embed=embed, mention_author=True)


@client.command()
async def clear(ctx, number: int):
    if not is_user_admin(ctx.author):
        return
    deger = number
    await ctx.reply(f"{deger} mesaj siliniyor..")
    try:
        await ctx.message.delete()
    except:
        pass
    await ctx.channel.purge(limit=1 + deger)

def is_user_admin(user: discord.Member):
    return user.guild_permissions.administrator

async def apply_category_roles(ctx, user: discord.Member, category: str):
    db = TinyDB(DB_NAME)
    table = db.table(CATEGORIES_TABLE_NAME)
    Data = Query()
    categoryData = table.get(Data.category_name == category.casefold())

    if categoryData is not None:
        roles = []
        for roleId in categoryData.get('roles').split('+'):
            role = discord.utils.get(ctx.guild.roles, id=int(roleId))
            roles.append(role)
        await user.add_roles(*roles)
    else:
        await ctx.reply("Hata kodu 236! Organizatörlere bildirin.", delete_after=10, ephemeral=True, mention_author=True)


client.run(BOT_TOKEN)

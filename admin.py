import asyncio
import discord
from discord.member import Member
import discord_slash
import logging
import os
import random
import re
import sqlite3
import string
import sys
from discord import flags
from dotenv import load_dotenv
from emails import email_sender
from flask import Flask, render_template
from threading import Thread
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext

validations_db_file = 'validations.db'

validation_code_len = 6

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("DISCORD_TOKEN env var not set! Exiting")
    exit(1)

_ids = os.getenv('GUILD_IDS') or ""
_guild_ids = [int(id) for id in _ids.split('.') if id != ""]
guild_ids = _guild_ids if len(_guild_ids) else None

_ids = os.getenv('ROLE_IDS') or ""
_role_ids = [int(id) for id in _ids.split('.') if id != ""]
role_ids = {}
_tmp_ids = os.getenv('TMP_ROLE_IDS') or ""
_tmp_role_ids = [int(id) for id in _tmp_ids.split('.') if id != ""]
tmp_role_ids = {}
_i = 0
for guild in guild_ids:
    role_ids[guild] = _role_ids[_i]
    tmp_role_ids[guild] = _tmp_role_ids[_i]
    _i += 1


# Initialize db
if not os.path.exists(validations_db_file):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    cur.execute(f"""
    CREATE TABLE validations (
        user int NOT NULL, 
        guild int NOT NULL, 
        state int NOT NULL, 
        token varchar({validation_code_len}),
        email varchar(255),
        PRIMARY KEY (user)
    );""")
    con.commit()
    con.close()


bot = commands.Bot(command_prefix="/", self_bot=True, intents=discord.Intents.all())
slash = SlashCommand(bot, sync_commands=True)
app = Flask(__name__)
app.logger.root.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL') or 'DEBUG'))
app.logger.addHandler(logging.StreamHandler(sys.stdout))

email = email_sender(dry_run=True)
valid_email_orgs = ['afterverse.com']
_orgs = "(" + "|".join(valid_email_orgs) + ")" 
valid_email_prog = re.compile(f"[a-zA-Z0-9.]+@{_orgs}")
def _validate_email(email):
    return valid_email_prog.match(email) is not None

# validations_in_progress = {}

VALIDATION_STATE_START = 0
VALIDATION_STATE_GOT_EMAIL = 1
VALIDATION_STATE_FINISHED = 2

HOLY_GRAIL_ROLE_ID = os.getenv('ROLE_ID')

def exists_validation(user):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = len(cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchall()) > 0
    con.close()
    return res

def get_validation(user):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
    con.close()
    return {
        "user": res[0],
        "guild": res[1],
        "state": res[2],
        "token": res[3],
        "email": res[4]
    }

def set_token(user, token):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = cur.execute("UPDATE validations SET token=:t WHERE user=:id", {"id": user, "t":token})
    con.commit()
    con.close()

def set_state(user, state):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = cur.execute("UPDATE validations SET state=:s WHERE user=:id", {"id": user, "s":state})
    con.commit()
    con.close()

def set_email(user, email):
    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = cur.execute("UPDATE validations SET email=:e WHERE user=:id", {"id": user, "e":email})
    con.commit()
    con.close()

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")

@bot.event
async def on_member_join(member: discord.Member):
    app.logger.debug(f"{member} just joined! ({member.guild.id})")
    
    _guild = member.guild
    _role = _guild.get_role(tmp_role_ids[_guild.id])
    await member.add_roles(_role)

    await _handle_joined(member)

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.id != bot.user.id:
        if isinstance(msg.channel, discord.DMChannel):
            await _handle_dm(msg)
            return

        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")
        content = msg.content

        if content == "firstlogin":
            await _handle_joined(msg.author)

async def _handle_joined(member: discord.Member):
    if exists_validation(member.id):
        app.logger.debug("Validation in progress")
        return
    _dm = member.dm_channel
    if _dm is None:
        app.logger.debug(f"Creating DM with {member.id}")
        _dm = await member.create_dm()

    con = sqlite3.connect('validations.db')
    cur = con.cursor()
    res = cur.execute("INSERT INTO validations VALUES (?, ?, ?, ?, ?)", [member.id, member.guild.id, VALIDATION_STATE_START, "", ""])
    con.commit()
    con.close()
    await __request_email(member, True)

async def _handle_dm(msg: discord.Message):
    if not exists_validation(msg.author.id):
        app.logger.debug(f"Got DM from unexpected user {msg.author.id}/{msg.author}")
        return

    # _validation = validations_in_progress[msg.author.id]
    _validation = get_validation(msg.author.id)
    # app.logger.debug("Got validation data = " + str(_validation))

    if _validation['state'] == VALIDATION_STATE_START:
        await __handle_validation_start(msg) # Check if is a valid email

    elif _validation['state'] == VALIDATION_STATE_GOT_EMAIL:
        await __handle_validation_code(msg) # Check if it is the expected code

    elif _validation['state'] == VALIDATION_STATE_FINISHED:
        app.logger.debug(f'Validation already complete for user {msg.author.id}/{msg.author}') # Nothing more to do
        
    else:
        app.logger.warning(f'Unknown validation state {_validation["state"]}')
    
async def __request_email(member: discord.Member, first_time):
    _msg_start = "Olá Braver! " if first_time else ""
    await member.dm_channel.send(f"{_msg_start}Por favor me diga o seu email da AV para que eu possa te dar acesso ao server")

async def __handle_validation_start(msg: discord.Message):
    if _validate_email(msg.content): # Valid email, send code

        __token = ''.join(random.SystemRandom().choice(string.digits) for _ in range(validation_code_len))
        app.logger.debug(f"Generated token {__token} to validate user {msg.author.id}")

        set_token(msg.author.id, __token)
        set_state(msg.author.id, VALIDATION_STATE_GOT_EMAIL)

        # __email_content = render_template(
        #     'validation.html',
        #     name=str(msg.author),
        #     authToken=__token
        # )

        # email.send(
        #     msg.content,
        #     "Discord account validation",
        #     __email_content
        # )

        # validations_in_progress[msg.author.id]['state'] = VALIDATION_STATE_GOT_EMAIL
        await msg.channel.send("Beleza! Agora por favor cheque seu email e me diga o código que eu te enviei")
    else:
        await msg.channel.send("Este não parece ser um endereço de email válido...")
        await __request_email(msg.author, False)

async def __handle_validation_code(msg: discord.Message):
    _validation = get_validation(msg.author.id)

    if _validation['token'] == msg.content: # Valid code
        await msg.channel.send("Tudo certo! Vou te dar acesso ao server...")
        async with msg.channel.typing():
            __guild = _validation['guild']
            _guild = bot.get_guild(__guild)
            _role = _guild.get_role(role_ids[__guild])
            _tmp_role = _guild.get_role(tmp_role_ids[__guild])
            _member = _guild.get_member(msg.author.id)

            # Add new role
            await _member.add_roles(_role)

            # Remove temporary role
            await _member.remove_roles(_tmp_role)

            set_state(msg.author.id, VALIDATION_STATE_FINISHED)
        await msg.channel.send("Prontinho! Novamente seja bem vindo(a), Braver!")
    else:
        await msg.channel.send("Hmm... esse código não é válido, por favor tente novamente")

bot.run(TOKEN)

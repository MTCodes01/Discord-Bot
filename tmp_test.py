import asyncio
from discord.ext import commands
import discord

bot = commands.Bot('!', intents=discord.Intents.default())

@bot.group()
async def foo(ctx): pass

@foo.command()
async def bar(ctx): pass

print(bot.get_command('foo bar'))

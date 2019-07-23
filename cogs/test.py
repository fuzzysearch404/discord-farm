import discord
from utils.usertools import generategameuserid
from discord.ext import commands, tasks


class Test(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.statusloop.start()

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id

    @commands.command()
    async def ping(self, ctx):
        await ctx.send('ponh')

    @tasks.loop(seconds=1800)
    async def statusloop(self):
        await self.client.change_presence(activity=discord.Activity(name='Early beta', type=2))
        print('Bot status updated')

    @statusloop.before_loop
    async def before_statusloop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.statusloop.cancel()


def setup(client):
    client.add_cog(Test(client))

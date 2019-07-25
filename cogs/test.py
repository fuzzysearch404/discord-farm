import discord
from discord.ext import commands, tasks


class Test(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.statusloop.start()

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

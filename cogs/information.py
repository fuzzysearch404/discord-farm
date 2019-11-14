import discord
from discord.ext import commands, tasks


class Information(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.statusloop.start()

    @commands.command()
    async def news(self, ctx):
        with open('files/news.txt', "r", encoding='utf-8') as f:
            lines = f.read()
        embed = discord.Embed(title='\ud83d\udcf0News', colour=789613, description=lines)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def ping(self, ctx):
        await ctx.send('ponh')

    @commands.command()
    async def invite(self, ctx):
        await ctx.send("Support server: https://discord.gg/6PtAXVN" \
        "\nInvite: <https://discordapp.com/oauth2/authorize?client_id=526436949481881610&scope=bot&permissions=313408>")

    @commands.command()
    async def donate(self, ctx):
        await ctx.send("Any donations are appreciated <3\n https://www.paypal.me/fuzzysearch")

    @tasks.loop(seconds=1800)
    async def statusloop(self):
        await self.client.change_presence(activity=discord.Activity(name='%commands Open beta', type=2))

    @statusloop.before_loop
    async def before_statusloop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.statusloop.cancel()


def setup(client):
    client.add_cog(Information(client))

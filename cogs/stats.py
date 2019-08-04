from discord.ext import commands
from discord import Embed, Color


class Stats(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group()
    async def top(self, ctx):
        if ctx.invoked_subcommand:
            return

        client = self.client
        query = """SELECT * FROM users WHERE guildid = $1
            ORDER BY xp DESC LIMIT 10;"""
        users = await client.db.fetch(query, ctx.guild.id)
        fmt = ""
        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                name = 'Nav serverī'
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{name}:` {element['xp']} {client.xp}\n"
        embed = Embed(title=f'{client.xp}Top 10 pieredze:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command()
    async def xp(self, ctx):
        client = self.client
        query = """SELECT * FROM users WHERE guildid = $1
            ORDER BY xp DESC LIMIT 10;"""
        users = await client.db.fetch(query, ctx.guild.id)
        fmt = ""
        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                name = 'Nav serverī'
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{name}:` {element['xp']} {client.xp}\n"
        embed = Embed(title=f'{client.xp}Top 10 pieredze:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command()
    async def money(self, ctx):
        client = self.client
        query = """SELECT * FROM users WHERE guildid = $1
        ORDER BY money DESC LIMIT 10;"""
        users = await client.db.fetch(query, ctx.guild.id)
        fmt = ""
        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                name = 'Nav serverī'
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{name}:` {element['money']} {client.gold}\n"
        embed = Embed(title=f'{client.gold}Top 10 zelts:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command()
    async def gems(self, ctx):
        client = self.client
        query = """SELECT * FROM users WHERE guildid = $1
            ORDER BY gems DESC LIMIT 10;"""
        users = await client.db.fetch(query, ctx.guild.id)
        fmt = ""
        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                name = 'Nav serverī'
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{name}:` {element['gems']} {client.gem}\n"
        embed = Embed(title=f'{client.gem}Top 10 supernaudas:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Stats(client))
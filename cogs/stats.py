from discord.ext import commands, tasks
from discord import Embed, Color
from typing import Optional

STATS_REFRESH_SECONDS = 3630

class Topplayer:
    __slots__ = ('user', 'value')

    def __init__(self, user, value):
        self.user = user
        self.value = value


class Stats(commands.Cog, name="Top Player Statistics"):
    """
    Get some statistics about the TOP players.
    Statistics are being updated hourly.
    """
    def __init__(self, client):
        self.client = client
        self.xp = []
        self.gold = []
        self.gems = []
        self.refreshstats.start()

    @tasks.loop(seconds=STATS_REFRESH_SECONDS)
    async def refreshstats(self):
        await self.update_xp_top()
        await self.update_gold_top()
        await self.update_gems_top()

    @refreshstats.before_loop
    async def before_refreshstats(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.refreshstats.cancel()

    async def update_xp_top(self):
        new_data = []
        client = self.client

        query = """SELECT * FROM profile
            ORDER BY xp DESC LIMIT 10;"""
        users = await client.db.fetch(query)

        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                user = await client.fetch_user(element['userid'])
                if user is not None:
                    name = user.name
                else: name = "Unknown farmer"

            stats = Topplayer(name, element['xp'])
            new_data.append(stats)
        
        self.xp = new_data

    async def update_gold_top(self):
        new_data = []
        client = self.client

        query = """SELECT * FROM profile
            ORDER BY money DESC LIMIT 10;"""
        users = await client.db.fetch(query)

        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                user = await client.fetch_user(element['userid'])
                if user is not None:
                    name = user.name
                else: name = "Unknown farmer"

            stats = Topplayer(name, element['money'])
            new_data.append(stats)
        
        self.gold = new_data

    async def update_gems_top(self):
        new_data = []
        client = self.client

        query = """SELECT * FROM profile
            ORDER BY gems DESC LIMIT 10;"""
        users = await client.db.fetch(query)

        for element in users:
            user = client.get_user(element['userid'])
            if user is not None:
                name = user.name
            else:
                user = await client.fetch_user(element['userid'])
                if user is not None:
                    name = user.name
                else: name = "Unknown farmer"

            stats = Topplayer(name, element['gems'])
            new_data.append(stats)
        
        self.gems = new_data

    @commands.group()
    async def top(self, ctx, *, category: Optional[int] = 0):
        """
        \ud83c\udfc6 Shows top farmers. Categories: `xp`, `gold`, `gems`.
        """
        if ctx.invoked_subcommand:
            return

        fmt = ""
        for element in self.xp:
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{element.user}:` {element.value} {self.client.xp}\n"
        embed = Embed(title=f'{self.client.xp}Top 10 experience:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command()
    async def xp(self, ctx):
        """
        \ud83c\udfc6 Shows farmers with the most experience.
        """
        fmt = ""
        for element in self.xp:
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{element.user}:` {element.value} {self.client.xp}\n"
        embed = Embed(title=f'{self.client.xp}Top 10 experience:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command(aliases=['money'])
    async def gold(self, ctx):
        """
        \ud83c\udfc6 Shows farmers with the most gold.
        """
        fmt = ""
        for element in self.gold:
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{element.user}:` {element.value} {self.client.gold}\n"
        embed = Embed(title=f'{self.client.gold}Top 10 gold:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)

    @top.command(aliases=['diamonds'])
    async def gems(self, ctx):
        """
        \ud83c\udfc6 Shows farmers with the most gems.
        """
        fmt = ""
        for element in self.gems:
            fmt = fmt + f"\N{SMALL ORANGE DIAMOND}`{element.user}:` {element.value} {self.client.gem}\n"
        embed = Embed(title=f'{self.client.gem}Top 10 gems:', description=fmt, colour=Color.dark_orange())
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Stats(client))

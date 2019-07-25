import utils.embeds as emb
from discord.ext import commands
from utils import usertools

DEFAULT_XP = 0
DEFAULT_MONEY = 30
DEFAULT_GEMS = 3
DEFAULT_TILES = 2


class Registration(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def start(self, ctx):
        connection = await self.client.db.acquire()
        async with connection.transaction():
            query = """INSERT INTO users(id, guildid, userid, xp,
            money, gems, tiles, usedtiles)
            VALUES($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT DO NOTHING;"""
            result = await self.client.db.execute(
                query, usertools.generategameuserid(ctx.author), ctx.guild.id, ctx.author.id,
                DEFAULT_XP, DEFAULT_MONEY, DEFAULT_GEMS, DEFAULT_TILES, 0
                )
        await self.client.db.release(connection)
        if result[-1:] != '0':
            embed = emb.congratzembed(
                "Tavs profils ir izveidots!\n"
                "\u2139Pamācību un komandas atradīsi ar komandu `%tutorial`.")
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed('Tev jau ir profils!')
            await ctx.send(embed=embed)

    @commands.command()
    async def tutorial(self, ctx):
        pass


def setup(client):
    client.add_cog(Registration(client))

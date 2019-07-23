import utils.embeds as emb
from discord.ext import commands
from utils import usertools

DEFAULT_XP = 0
DEFAULT_MONEY = 150
DEFAULT_GEMS = 10
DEFAULT_TILES = 3


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
                DEFAULT_XP, DEFAULT_MONEY, DEFAULT_GEMS, DEFAULT_TILES, DEFAULT_TILES
                )
        await self.client.db.release(connection)
        if result[-1:] != '0':
            await ctx.send('\ud83c\udd97')
        else:
            embed = emb.errorembed('Tev jau ir profils!')
            await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Registration(client))

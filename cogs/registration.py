import utils.embeds as emb
from discord.ext import commands
from utils import usertools
from utils.paginator import Pages

DEFAULT_XP = 0
DEFAULT_MONEY = 30
DEFAULT_GEMS = 3
DEFAULT_TILES = 2
DEFAULT_FACTORY_SLOTS = 2


class Registration(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.loadtutorial()

    @commands.command()
    async def start(self, ctx):
        connection = await self.client.db.acquire()
        async with connection.transaction():
            query = """INSERT INTO users(id, guildid, userid, xp,
            money, gems, tiles, usedtiles, factoryslots)
            VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT DO NOTHING;"""
            result = await self.client.db.execute(
                query, usertools.generategameuserid(ctx.author), ctx.guild.id, ctx.author.id,
                DEFAULT_XP, DEFAULT_MONEY, DEFAULT_GEMS, DEFAULT_TILES, 0, DEFAULT_FACTORY_SLOTS
                )
        await self.client.db.release(connection)
        if result[-1:] != '0':
            embed = emb.congratzembed(
                "Tavs profils ir izveidots!\n"
                "\u2139Komandas atradīsi ar komandu `%commands`.",
                ctx
            )
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed('Tev jau ir profils!', ctx)
            await ctx.send(embed=embed)

    def loadtutorial(self):
        try:
            with open('files/tutorial.txt', 'r') as f:
                string = f.read()
                self.words = string.split("(*)")
        except Exception as e:
            print(e)
            self.words = ['error loading tutorial :(']

    @commands.command(aliases=['cmd'])
    async def commands(self, ctx):
        try:
            p = Pages(ctx, entries=self.words, per_page=1, show_entry_count=False)
            p.embed.title = '\ud83e\udd55Bota komandas'
            p.embed.color = 13144332
            await p.paginate()
        except Exception as e:
            print(e)


def setup(client):
    client.add_cog(Registration(client))

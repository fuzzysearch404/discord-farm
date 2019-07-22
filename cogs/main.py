import discord
from discord.ext import commands
from utils.time import secstotime
from utils.item import finditembyname


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def info(self, ctx, possibleitem):
        try:
            possibleitem = int(possibleitem)
        except ValueError:
            pass

        if isinstance(possibleitem, int):
            try:
                item = self.client.allitems[possibleitem]
            except KeyError:
                return await ctx.send("Neatradu tādu lietu\ud83e\udd14")
        elif isinstance(possibleitem, str):
            item = finditembyname(self.client, possibleitem)
            if not item:
                return await ctx.send("Neatradu tādu lietu\ud83e\udd14")

        if item.type == 'crop':
            await self.cropinfo(ctx, item)

    async def cropinfo(self, ctx, crop):
        embed = discord.Embed(title=f'{crop.name.capitalize()} {crop.emoji}', description=f'**ID:** {crop.id}', colour=851836)
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=crop.level)
        embed.add_field(name='\ud83c\udf1fNovācot dod', value=f'{crop.xp} xp/gab.')
        embed.add_field(name='\ud83d\udd70Dīgst, aug', value=secstotime(crop.grows))
        embed.add_field(name='\ud83d\udd70Novācams', value=secstotime(crop.dies))
        embed.add_field(name='\ud83d\udcb0Sēklu cena', value=f'{crop.cost}\ud83d\udcb0 vai {crop.scost}\ud83d\udc8e\n')
        embed.add_field(name='\u2696Ražas apjoms', value=f'{crop.amount} gab.')
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{crop.minprice} - {crop.maxprice} /gab. \ud83d\udcb0\n')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value=f'{crop.marketprice}\ud83d\udcb0/gab.\n')

        embed.set_thumbnail(url=crop.img)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Main(client))

import discord
from discord.ext import commands
from utils.time import secstotime
from utils.crop import findcropbyname


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def crop(self, ctx, possiblecrop):
        try:
            possiblecrop = int(possiblecrop)
        except ValueError:
            pass

        if isinstance(possiblecrop, int):
            try:
                crop = self.client.crops[possiblecrop]
            except KeyError:
                return await ctx.send("Neatradu tādu augu\ud83e\udd14")
        elif isinstance(possiblecrop, str):
            crop = findcropbyname(self.client, possiblecrop)
            if not crop:
                return await ctx.send("Neatradu tādu augu\ud83e\udd14")
        embed = discord.Embed(title=f'{crop.name.capitalize()} {crop.emoji}', description=f'**ID:** {crop.id}', colour=851836)
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=crop.level)
        embed.add_field(name='\ud83c\udf1fNovācot dod', value=f'{crop.xp} xp/gab.')
        embed.add_field(name='\ud83d\udd70Dīgst, aug', value=secstotime(crop.grows))
        embed.add_field(name='\ud83d\udd70Novācams', value=secstotime(crop.dies))
        embed.add_field(name='\ud83d\udcb0Sēklu cena', value=f'{crop.cost} \ud83d\udcb0 vai {crop.scost} \ud83d\udc8e\n')
        embed.add_field(name='\u2696Ražas apjoms', value=f'{crop.amount} gab.')
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{crop.minprice} - {crop.maxprice} /gab. \ud83d\udcb0\n')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value='0/gab.')

        embed.set_thumbnail(url=crop.img)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Main(client))

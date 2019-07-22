import datetime
import discord
from utils.paginator import Pages
from discord.ext import commands, tasks


class Shop(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.refreshshop.start()
        self.lastrefresh = datetime.datetime.now()

    @tasks.loop(seconds=3600)
    async def refreshshop(self):
        self.lastrefresh = datetime.datetime.now()
        for crop in self.client.crops.values():
            crop.getmarketprice()

    @refreshshop.before_loop
    async def before_refreshshop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.refreshshop.cancel()

    @commands.group()
    async def shop(self, ctx):
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(title='Izvēlies kategoriju', colour=822472)
        embed.add_field(name='\ud83c\udf3e Augu sēklas', value='`%shop crops`')
        embed.add_field(name='\ud83c\udf33 Koki', value='`soon`')
        embed.add_field(name='\ud83d\udc14 Dzīvnieki', value='`soon`')
        embed.add_field(name='\ud83c\udfed Ražotnes', value='`soon`')
        await ctx.send(embed=embed)

    @shop.command()
    async def crops(self, ctx):
        items = []
        for crop in self.client.crops.values():
            item = f"""{crop.emoji}**{crop.name2.capitalize()}**
            {crop.cost}\ud83d\udcb0  vai  {crop.scost}\ud83d\udc8e
            \ud83d\uded2 `%buy {crop.id}` \u2139 `%crop {crop.id}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf3e Augu sēklas'
            p.embed.color = 822472
            await p.paginate()
        except Exception as e:
            print(e)


def setup(client):
    client.add_cog(Shop(client))

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
        client = self.client
        for cropseed in client.cropseeds.values():
            crop = cropseed.getchild(client)
            item = f"""{cropseed.emoji}**{cropseed.name2.capitalize()}** \ud83d\udd31{crop.level}
            {cropseed.cost}{client.gold}  vai  {cropseed.scost}{client.gem}
            \ud83d\uded2 `%buy {cropseed.id}` \u2139 `%info {cropseed.id}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf3e Augu sēklas'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)


def setup(client):
    client.add_cog(Shop(client))

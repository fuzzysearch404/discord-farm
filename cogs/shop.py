import datetime
import discord
import utils.embeds as emb
from utils.usertools import generategameuserid
from utils.paginator import Pages
from utils.item import finditem
from discord.ext import commands, tasks


class Shop(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.refreshshop.start()
        self.lastrefresh = datetime.datetime.now()

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id

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

    @commands.command()
    async def buy(self, ctx, possibleitem):
        item = await finditem(self.client, ctx, possibleitem)
        if not item:
            return

        if not item.type or item.type == 'crop':
            embed = emb.errorembed("Šī prece netiek pārdota mūsu bodē \ud83d\ude26")
            return await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Shop(client))

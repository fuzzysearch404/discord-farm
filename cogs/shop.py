import datetime
import discord
import asyncio
import utils.embeds as emb
from utils import usertools
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
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
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
        embed.add_field(name='\u2b50 Citi', value='`%shop special`')
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

    @shop.command()
    async def special(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        embed = discord.Embed(title='\u2b50 Citi', color=82247)
        embed.add_field(
            name=f'{client.tile}Paplašināt zemi',
            value=f"""\ud83c\udd95 {profile['tiles']} \u2192 {profile['tiles'] + 1} platība
            {client.gem}{usertools.tilescost(profile['tiles'])}
            \ud83d\uded2 `%expand`"""
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def buy(self, ctx, *, possibleitem):
        client = self.client

        item = await finditem(client, ctx, possibleitem)
        if not item:
            return

        if not item.type or item.type == 'crop':
            embed = emb.errorembed("Šī prece netiek pārdota mūsu bodē \ud83d\ude26")
            return await ctx.send(embed=embed)

        buyer = await usertools.getprofile(client, ctx.author)
        if usertools.getlevel(buyer['xp'])[0] < item.level:
            embed = emb.errorembed("Pārāk zems līmenis, lai iegādātos šo preci")
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f'{item.emoji}**{item.name.capitalize()}**\nPreces ID: {item.id}'
        )
        buyembed.add_field(
            name='Cena',
            value=f'{client.gold}{item.cost} vai {client.gem}{item.scost}'
        )
        buyembed.add_field(
            name='Daudzums',
            value="""Ievadi daudzumu ar cipariem čatā.
            Lai atceltu, ieraksti čatā `X`."""
        )
        buyembed.set_footer(
            text=f"{ctx.author} Zelts: {buyer['money']} SN: {buyer['gems']}",
            icon_url=ctx.author.avatar_url,
        )
        buyinfomessage = await ctx.send(embed=buyembed)

        def check(m):
            return m.author == ctx.author

        try:
            entry = await client.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = emb.errorembed('Gaidīju pārāk ilgi. Darījums atcelts.')
            await ctx.send(embed=embed, delete_after=15)
            await buyinfomessage.delete()

        try:

            if entry is None:
                return await buyinfomessage.delete()
            elif entry.clean_content.lower() == 'x':
                await buyinfomessage.delete()
                return await entry.delete()

            await entry.delete()
        except discord.HTTPException:
            pass

        try:
            amount = int(entry.clean_content)
        except ValueError:
            embed = emb.errorembed('Nederīgs daudzums. Nākošreiz ieraksti skaitli')
            return await ctx.send(embed=embed, delete_after=15)

        buyembed.set_field_at(
            index=2,
            name='Daudzums',
            value=amount
        )
        buyembed.add_field(
            name='Summa',
            value=f'{client.gold}{item.cost * amount} vai {client.gem}{item.scost * amount}'
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
        await buyinfomessage.edit(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)
        await buyinfomessage.add_reaction(client.gem)
        await buyinfomessage.add_reaction('\u274c')

        allowedemojis = ('\u274c', client.gem, client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in allowedemojis

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = emb.errorembed('Gaidīju pārāk ilgi. Darījums atcelts.')
            await ctx.send(embed=embed, delete_after=15)
            return await buyinfomessage.delete()

        if str(reaction.emoji) == client.gold:
            await self.buywithgold(ctx, buyer, item, amount)
        elif str(reaction.emoji) == client.gem:
            await self.buywithgems(ctx, buyer, item, amount)

    async def buywithgold(self, ctx, buyer, item, amount):
        client = self.client
        total = item.cost * amount
        if buyer['money'] < total:
            embed = emb.errorembed('Tev nepietiek zelts.')
            return await ctx.send(embed=embed)

        query = """SELECT money FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, buyer['id'])
        if usergold['money'] < total:
            embed = emb.errorembed('Tev nepietiek zelts.')
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givemoney(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"Tu nopirki {amount}x{item.emoji} par {total}{self.client.gold}")
        await ctx.send(embed=embed)

    async def buywithgems(self, ctx, buyer, item, amount):
        client = self.client
        total = item.scost * amount
        if buyer['gems'] < total:
            embed = emb.errorembed('Tev nepietiek supernaudu.')
            return await ctx.send(embed=embed)

        query = """SELECT gems FROM users
        WHERE id = $1;"""

        usergems = await client.db.fetchrow(query, buyer['id'])
        if usergems['gems'] < total:
            embed = emb.errorembed('Tev nepietiek supernaudu.')
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givegems(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"Tu nopirki {amount}x{item.emoji} par {total}{self.client.gem}")
        await ctx.send(embed=embed)

    @commands.command()
    async def expand(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f"{client.tile} {profile['tiles']} \u2192 {profile['tiles'] + 1}"
        )
        buyembed.add_field(
            name='Cena',
            value=f"{client.gem}{usertools.tilescost(profile['tiles'])}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = emb.errorembed('Gaidīju pārāk ilgi. Darījums atcelts.')
            return await ctx.send(embed=embed, delete_after=15)

        profile = await usertools.getprofile(client, ctx.author)

        gemstopay = usertools.tilescost(profile['tiles'])

        if profile['gems'] < gemstopay:
            embed = emb.errorembed('Tev nepietiek supernaudu.')
            return await ctx.send(embed=embed)

        await usertools.addfields(client, ctx.author, 1)
        await usertools.givegems(client, ctx.author, gemstopay * -1)
        embed = emb.congratzembed(f"Tava lauku platība tagad ir {profile['tiles'] + 1}")
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Shop(client))

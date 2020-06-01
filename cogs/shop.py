import datetime
import discord
import asyncio
import utils.embeds as emb
from utils import usertools
from utils import boosttools
from utils.time import secstotime
from utils.paginator import Pages
from utils.item import finditem
from discord.ext import commands, tasks

REFRESH_SHOP_SECONDS = 3600


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
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @tasks.loop(seconds=REFRESH_SHOP_SECONDS)
    async def refreshshop(self):
        self.lastrefresh = datetime.datetime.now()
        for crop in self.client.crops.values():
            crop.getmarketprice()
        for item in self.client.items.values():
            item.getmarketprice()
        for citem in self.client.crafteditems.values():
            citem.getmarketprice()

    @refreshshop.before_loop
    async def before_refreshshop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.refreshshop.cancel()

    @commands.group()
    async def shop(self, ctx):
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(title='Select a category', colour=822472)
        embed.add_field(name='\ud83c\udf3e Crop seeds', value='`%shop crops`')
        embed.add_field(name='\ud83c\udf33 Tree plants', value='`%shop trees`')
        embed.add_field(name='\ud83d\udc14 Animals', value='`%shop animals`')
        embed.add_field(name='\ud83c\udfe6 Services', value='`%shop boosts`')
        embed.add_field(name='\u2b50 Other', value='`%shop special`')
        embed.add_field(name='\u2696 Market', value='`%market`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @shop.command()
    async def crops(self, ctx):
        items = []
        client = self.client
        for cropseed in client.cropseeds.values():
            crop = cropseed.getchild(client)
            item = f"""{cropseed.emoji}**{cropseed.name.capitalize()}** \ud83d\udd31{crop.level}
            {cropseed.cost}{client.gold}  or  {cropseed.scost}{client.gem}
            \ud83d\uded2 `%buy {cropseed.name}` \u2139 `%info {cropseed.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf3e Crop seeds'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @shop.command()
    async def animals(self, ctx):
        items = []
        client = self.client
        for animal in client.animals.values():
            item = f"""{animal.emoji}**{animal.name.capitalize()}** \ud83d\udd31{animal.level}
            {animal.cost}{client.gold}  or  {animal.scost}{client.gem}
            \ud83d\uded2 `%buy {animal.name}` \u2139 `%info {animal.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83d\udc14 Animals'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @shop.command()
    async def trees(self, ctx):
        items = []
        client = self.client
        for tree in client.trees.values():
            item = f"""{tree.emoji}**{tree.name.capitalize()}** \ud83d\udd31{tree.level}
            {tree.cost}{client.gold}  or  {tree.scost}{client.gem}
            \ud83d\uded2 `%buy {tree.name}` \u2139 `%info {tree.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf33 Tree plants'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @shop.command()
    async def boosts(self, ctx):
        embed = discord.Embed(title='\ud83c\udfe6 Services', color=82247)
        embed.add_field(
            name='\ud83d\udc29Squealer',
            value="""Protects your field. Or does it?
            `%dog 1`"""
            )
        embed.add_field(
            name='\ud83d\udc36Saliva Toby',
            value="""Protects your land, but sometimes likes to play around.
            `%dog 2`"""
            )
        embed.add_field(
            name='\ud83d\udc15Rex',
            value="""Protects your farm and your heart.
            `%dog 3`"""
            )
        embed.add_field(
            name='\ud83d\udc31Leo',
            value="""Keeps your harvest fresh. Don't ask me how...
            `%cat`"""
            )
        await ctx.send(embed=embed)

    @commands.group()
    async def market(self, ctx):
        if ctx.invoked_subcommand:
            return

        embed = discord.Embed(title='Choose a category', colour=1563808)
        embed.add_field(name='\ud83c\udf3e Harvest', value='`%market crops`')
        embed.add_field(name='\ud83d\udce6 Products', value='`%market items`')
        embed.add_field(name='\ud83d\udd39 Other products', value='`%market other`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @market.command(name='crops')
    async def mcrops(self, ctx):
        items = []
        client = self.client

        refreshin = datetime.datetime.now() - self.lastrefresh
        refreshin = secstotime(REFRESH_SHOP_SECONDS - refreshin.seconds)
        items.append(f'\u23f0Market prices are going to refresh in {refreshin}\n')

        for x in client.crops.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Currently buying for: {x.marketprice}{client.gold}/item.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Market: \ud83c\udf3eCrops'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @market.command(name='items')
    async def mitems(self, ctx):
        items = []
        client = self.client

        refreshin = datetime.datetime.now() - self.lastrefresh
        refreshin = secstotime(REFRESH_SHOP_SECONDS - refreshin.seconds)
        items.append(f'\u23f0Market prices are going to refresh in {refreshin}\n')

        for x in client.crafteditems.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Currently buying for: {x.marketprice}{client.gold}/item.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Tirgus: \ud83d\udce6Products'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @market.command(name='other')
    async def mother(self, ctx):
        items = []
        client = self.client

        refreshin = datetime.datetime.now() - self.lastrefresh
        refreshin = secstotime(REFRESH_SHOP_SECONDS - refreshin.seconds)
        items.append(f'\u23f0Market prices are going to refresh in {refreshin}\n')

        for x in client.items.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Currently buying for: {x.marketprice}{client.gold}/item.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Tirgus: \ud83d\udd39 Other products'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @shop.command()
    async def special(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        embed = discord.Embed(title='\u2b50 Other', color=82247)
        embed.add_field(
            name=f'{client.tile}Expand field \ud83d\udd313',
            value=f"""\ud83c\udd95 {profile['tiles']} \u2192 {profile['tiles'] + 1} tiles
            {client.gem}{usertools.upgradecost(profile['tiles'])}
            \ud83d\uded2 `%expand`"""
        )
        embed.add_field(
            name=f'\ud83c\udfedFactory upgrade \ud83d\udd313',
            value=f"""\ud83c\udd95 {profile['factoryslots']} \u2192 {profile['factoryslots'] + 1} capacity
            {client.gem}{usertools.upgradecost(profile['factoryslots'])}
            \ud83d\uded2 `%upgrade`"""
        )
        embed.add_field(
            name=f'\ud83c\udfeaShop upgrade',
            value=f"""\ud83c\udd95 {profile['storeslots']} \u2192 {profile['storeslots'] + 1} selling capacity
            {client.gold}{usertools.storeupgcost(profile['storeslots'])}
            \ud83d\uded2 `%addslot`"""
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['b'])
    async def buy(self, ctx, *, possibleitem):
        client = self.client

        customamount = False
        try:
            possibleamount = possibleitem.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            possibleitem = possibleitem.rsplit(' ', 1)[0]
            if amount > 0 and amount < 2147483647:
                customamount = True
        except Exception:
            pass

        item = await finditem(client, ctx, possibleitem)
        if not item:
            return

        forbiddentypes = ('crop', 'crafteditem', 'item')

        if not item.type or item.type in forbiddentypes:
            embed = emb.errorembed(f"This item ({item.emoji}{item.name.capitalize()}) is not being sold in our shop \ud83d\ude26", ctx)
            return await ctx.send(embed=embed)

        buyer = await usertools.getprofile(client, ctx.author)
        if usertools.getlevel(buyer['xp'])[0] < item.level:
            embed = emb.errorembed(f"Too low level to buy {item.emoji}{item.name.capitalize()}", ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f'{item.emoji}**{item.name.capitalize()}**\n ID: {item.id}'
        )
        buyembed.add_field(
            name='Price',
            value=f'{client.gold}{item.cost} or {client.gem}{item.scost}'
        )
        if not customamount:
            buyembed.add_field(
                name='Amount',
                value="""Please enter the amount in the chat.
                To cancel, type `X`."""
            )
        buyembed.set_footer(
            text=f"{ctx.author} Gold: {buyer['money']} Gems: {buyer['gems']}",
            icon_url=ctx.author.avatar_url,
        )
        if not customamount:
            buyinfomessage = await ctx.send(embed=buyembed)

            def check(m):
                return m.author == ctx.author

            try:
                entry = None
                entry = await client.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                embed = emb.errorembed('Too long. Purchase canceled.', ctx)
                await ctx.send(embed=embed)

            try:
                if not entry:
                    return
                elif entry.clean_content.lower() == 'x':
                    await buyinfomessage.delete()
                    return await entry.delete()

                await buyinfomessage.delete()
                await entry.delete()
            except discord.HTTPException:
                pass

            try:
                amount = int(entry.clean_content)
                if amount < 1 or amount > 2147483647:
                    embed = emb.errorembed('Invalid amount. Start purchase all over again.', ctx)
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed('Invalid amount. Next time enter a valid amount', ctx)
                return await ctx.send(embed=embed)

            buyembed.set_field_at(
                index=2,
                name='Amount',
                value=amount
            )
        else:
            buyembed.add_field(
                name='Amount',
                value=amount
            )
        buyembed.add_field(
            name='Total',
            value=f'{client.gold}{item.cost * amount} or {client.gem}{item.scost * amount}'
        )
        buyembed.add_field(name='Confirmation', value='React with payment method to finish the purchase')
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)
        await buyinfomessage.add_reaction(client.gem)
        await buyinfomessage.add_reaction('\u274c')

        allowedemojis = ('\u274c', client.gem, client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in allowedemojis and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await buyinfomessage.clear_reactions()

        if str(reaction.emoji) == client.gold:
            await self.buywithgold(ctx, buyer, item, amount)
        elif str(reaction.emoji) == client.gem:
            await self.buywithgems(ctx, buyer, item, amount)

    async def buywithgold(self, ctx, buyer, item, amount):
        client = self.client
        total = item.cost * amount
        if buyer['money'] < total:
            embed = emb.errorembed('You do not have enough gold', ctx)
            return await ctx.send(embed=embed)

        query = """SELECT money FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, buyer['id'])
        if usergold['money'] < total:
            embed = emb.errorembed('You do not have enough gold', ctx)
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givemoney(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"You purchased {amount}x{item.emoji}{item.name.capitalize()} for {total}{self.client.gold}", ctx)
        await ctx.send(embed=embed)

    async def buywithgems(self, ctx, buyer, item, amount):
        client = self.client
        total = item.scost * amount
        if buyer['gems'] < total:
            embed = emb.errorembed('You do not have enough gems', ctx)
            return await ctx.send(embed=embed)

        query = """SELECT gems FROM users
        WHERE id = $1;"""

        usergems = await client.db.fetchrow(query, buyer['id'])
        if usergems['gems'] < total:
            embed = emb.errorembed('You do not have enough gems', ctx)
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givegems(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"You purchased {amount}x{item.emoji}{item.name.capitalize()} for {total}{self.client.gem}", ctx)
        await ctx.send(embed=embed)

    @commands.command(aliases=['s'])
    async def sell(self, ctx, *, possibleitem):
        client = self.client

        customamount = False
        try:
            possibleamount = possibleitem.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            possibleitem = possibleitem.rsplit(' ', 1)[0]
            if amount > 0 and amount < 2147483647:
                customamount = True
        except Exception:
            pass

        item = await finditem(client, ctx, possibleitem)
        if not item:
            return

        allowedtypes = ('crop', 'crafteditem', 'item')

        if not item.type or item.type not in allowedtypes:
            embed = emb.errorembed(f"This item ({item.emoji}{item.name.capitalize()}) can not be sold in the market \ud83d\ude26", ctx)
            return await ctx.send(embed=embed)

        hasitem = await usertools.checkinventoryitem(client, ctx.author, item)
        if not hasitem:
            embed = emb.errorembed(f"You do not have ({item.emoji}{item.name.capitalize()}) in your warehouse!", ctx)
            return await ctx.send(embed=embed)
        else:
            alreadyhas = hasitem['amount']

        sellembed = discord.Embed(title='Selling details', colour=9309837)
        sellembed.add_field(
            name='Item',
            value=f'{item.emoji}**{item.name.capitalize()}**\nItem ID: {item.id}'
        )
        sellembed.add_field(
            name='Price',
            value=f'{client.gold}{item.marketprice}'
        )
        sellembed.set_footer(
            text=ctx.author, icon_url=ctx.author.avatar_url
        )

        if not customamount:
            sellembed.add_field(
                name='Amount',
                value=f"""Please enter the amount in the chat
                To cancel, type `X`.
                You have {alreadyhas}{item.emoji}."""
            )

            sellinfomessage = await ctx.send(embed=sellembed)

        if not customamount:
            def check(m):
                return m.author == ctx.author

            try:
                entry = None
                entry = await client.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                embed = emb.errorembed('Too long. Selling canceled', ctx)
                await ctx.send(embed=embed, delete_after=15)

            try:
                if not entry:
                    return
                elif entry.clean_content.lower() == 'x':
                    await sellinfomessage.delete()
                    return await entry.delete()

                await entry.delete()
                await sellinfomessage.delete()
            except discord.HTTPException:
                pass

            try:
                amount = int(entry.clean_content)
                if amount < 1 or amount > 2147483647:
                    embed = emb.errorembed('Invalid amount. Selling canceled', ctx)
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed('Invalid amount. Selling canceled', ctx)
                return await ctx.send(embed=embed)

            sellembed.set_field_at(
                index=2,
                name='Amount',
                value=amount
            )
        else:
            sellembed.add_field(
                name='Amount',
                value=amount
            )
        sellembed.add_field(
            name='Total',
            value=f'{client.gold}{item.marketprice * amount}'
        )
        sellembed.add_field(
            name='Confirmation',
            value='React with payment method to finish selling these items'
        )
        sellinfomessage = await ctx.send(embed=sellembed)
        await sellinfomessage.add_reaction('\u2705')
        await sellinfomessage.add_reaction('\u274c')

        allowedemojis = ('\u274c', '\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in allowedemojis and reaction.message.id == sellinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await sellinfomessage.clear_reactions()

        if str(reaction.emoji) == '\u274c':
            return

        await self.sellwithgold(ctx, item, amount)

    async def sellwithgold(self, ctx, item, amount):
        client = self.client
        total = item.marketprice * amount

        hasitem = await usertools.checkinventoryitem(client, ctx.author, item)
        if not hasitem:
            embed = emb.errorembed(f"You do not have {item.emoji}{item.name.capitalize()} in your warehouse!", ctx)
            return await ctx.send(embed=embed)

        if amount > hasitem['amount']:
            embed = emb.errorembed(f"You only have {hasitem['amount']}x {item.emoji}{item.name.capitalize()} in yout warehouse!", ctx)
            return await ctx.send(embed=embed)

        await usertools.removeitemfrominventory(client, ctx.author, item, amount)
        await usertools.givemoney(client, ctx.author, total)

        embed = emb.confirmembed(f"You sold {amount}x{item.emoji}{item.name.capitalize()} for {total}{self.client.gold}", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def expand(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        if usertools.getlevel(profile['xp'])[0] < 3:
            embed = emb.errorembed('Land expansion is avaiable from level 3.', ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"{client.tile} {profile['tiles']} \u2192 {profile['tiles'] + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gem}{usertools.upgradecost(profile['tiles'])}"
        )
        buyembed.add_field(name='Confirmation', value='React with the payment method')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await buyinfomessage.clear_reactions()

        profile = await usertools.getprofile(client, ctx.author)

        gemstopay = usertools.upgradecost(profile['tiles'])

        if profile['gems'] < gemstopay:
            embed = emb.errorembed('You do not have enough gems', ctx)
            return await ctx.send(embed=embed)

        await usertools.addfields(client, ctx.author, 1)
        await usertools.givegems(client, ctx.author, gemstopay * -1)
        embed = emb.congratzembed(f"You now have {profile['tiles'] + 1} field tiles", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def upgrade(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        if usertools.getlevel(profile['xp'])[0] < 3:
            embed = emb.errorembed('Factory upgrades are avaiable from level 3', ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"\ud83c\udfed\ud83d\udce6 {profile['factoryslots']} \u2192 {profile['factoryslots'] + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gem}{usertools.upgradecost(profile['factoryslots'])}"
        )
        buyembed.add_field(name='Confirmation', value='React with the payment method')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await buyinfomessage.clear_reactions()

        profile = await usertools.getprofile(client, ctx.author)

        gemstopay = usertools.upgradecost(profile['factoryslots'])

        if profile['gems'] < gemstopay:
            embed = emb.errorembed('You do not have enough gems', ctx)
            return await ctx.send(embed=embed)

        await usertools.addfactoryslots(client, ctx.author, 1)
        await usertools.givegems(client, ctx.author, gemstopay * -1)
        embed = emb.congratzembed(f"Your factory has now {profile['factoryslots'] + 1} production slots", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def addslot(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        buyembed = discord.Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"\ud83c\udfea {profile['storeslots']} \u2192 {profile['storeslots'] + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gold}{usertools.storeupgcost(profile['storeslots'])}"
        )
        buyembed.add_field(name='Confirmation', value='React with the payment method')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gold and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await buyinfomessage.clear_reactions()

        profile = await usertools.getprofile(client, ctx.author)

        goldtopay = usertools.storeupgcost(profile['storeslots'])

        if profile['money'] < goldtopay:
            embed = emb.errorembed('Not enough gems', ctx)
            return await ctx.send(embed=embed)

        await usertools.addstoreslots(client, ctx.author, 1)
        await usertools.givemoney(client, ctx.author, goldtopay * -1)
        embed = emb.congratzembed(f"Your shop now has {profile['storeslots'] + 1} selling slots", ctx)
        await ctx.send(embed=embed)

    @commands.group()
    async def dog(self, ctx):
        if ctx.invoked_subcommand:
            return
        embed = emb.errorembed("`%dog 1-3`", ctx)
        await ctx.send(embed=embed)

    @dog.command(name='1')
    async def dog1(self, ctx):
        message, gp = await self.prepareboostinfo(ctx, 1, '\ud83d\udc29')
        await self.assignboost(ctx, message, gp, '\ud83d\udc29', 1)

    @dog.command(name='2')
    async def dog2(self, ctx):
        message, gp = await self.prepareboostinfo(ctx, 2, '\ud83d\udc36')
        await self.assignboost(ctx, message, gp, '\ud83d\udc36', 2)

    @dog.command(name='3')
    async def dog3(self, ctx):
        message, gp = await self.prepareboostinfo(ctx, 3, '\ud83d\udc15')
        await self.assignboost(ctx, message, gp, '\ud83d\udc15', 3)

    @commands.command()
    async def cat(self, ctx):
        message, gp = await self.prepareboostinfo(ctx, 4, '\ud83d\udc31')
        await self.assignboost(ctx, message, gp, '\ud83d\udc31', 4)

    async def prepareboostinfo(self, ctx, dog, emoji):
        client = self.client
        profile = await usertools.getprofile(self.client, ctx.author)
        goldprices = boosttools.getboostgoldprices(profile['tiles'], dog)

        embed = discord.Embed(title=f'Get {emoji}')
        embed.add_field(
            name='For 1 day',
            value=f"{goldprices[1]}{client.gold}"
            )
        embed.add_field(
            name='For 3 days',
            value=f"{goldprices[3]}{client.gold}"
            )
        embed.add_field(
            name='For 7 days',
            value=f"{goldprices[7]}{client.gold}"
            )
        message = await ctx.send(embed=embed)
        await message.add_reaction('1\u20e3')
        await message.add_reaction('3\u20e3')
        await message.add_reaction('7\u20e3')

        return message, goldprices

    async def assignboost(self, ctx, message, gp, emoji, dog):
        client = self.client

        emojis = {
            '1\u20e3': gp[1],
            '3\u20e3': gp[3],
            '7\u20e3': gp[7]
        }

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in emojis and reaction.message.id == message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        await message.delete()

        settings = emojis[str(reaction.emoji)]

        buyembed = discord.Embed(title='Purchase details')
        buyembed.add_field(
            name='Item',
            value=f"{emoji} {str(reaction.emoji)[0]} days"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gold}{settings}"
        )
        buyembed.add_field(name='Confirmation', value='React with the payment method')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)

        aemojis = (client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in aemojis and reaction.message.id == buyinfomessage.id

        try:
            breaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        if str(breaction.emoji) == client.gold:
            await self.boostbuywithgold(ctx, settings, dog, emoji, int(str(reaction.emoji)[0]))

    async def boostbuywithgold(self, ctx, gold, dog, emoji, duration):
        client = self.client
        query = """SELECT money FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if usergold['money'] < gold:
            embed = emb.errorembed('You do not have enough gold', ctx)
            return await ctx.send(embed=embed)

        await usertools.givemoney(client, ctx.author, gold * -1)

        await boosttools.addboost(client, ctx.author, dog, duration)

        embed = emb.confirmembed(f"You paid {emoji} to help your farm", ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Shop(client))

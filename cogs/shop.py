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
        embed = discord.Embed(title='Izvēlies kategoriju', colour=822472)
        embed.add_field(name='\ud83c\udf3e Augu sēklas', value='`%shop crops`')
        embed.add_field(name='\ud83c\udf33 Koki', value='`%shop trees`')
        embed.add_field(name='\ud83d\udc14 Dzīvnieki', value='`%shop animals`')
        embed.add_field(name='\u2696 Tirgus', value='`%market`')
        embed.add_field(name='\ud83c\udfe6 Pakalpojumi', value='`%shop boosts`')
        embed.add_field(name='\u2b50 Citi', value='`%shop special`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @shop.command()
    async def crops(self, ctx):
        items = []
        client = self.client
        for cropseed in client.cropseeds.values():
            crop = cropseed.getchild(client)
            item = f"""{cropseed.emoji}**{cropseed.name.capitalize()}** \ud83d\udd31{crop.level}
            {cropseed.cost}{client.gold}  vai  {cropseed.scost}{client.gem}
            \ud83d\uded2 `%buy {cropseed.name}` \u2139 `%info {cropseed.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf3e Augu sēklas'
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
            {animal.cost}{client.gold}  vai  {animal.scost}{client.gem}
            \ud83d\uded2 `%buy {animal.name}` \u2139 `%info {animal.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83d\udc14 Dzīvnieki'
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
            {tree.cost}{client.gold}  vai  {tree.scost}{client.gem}
            \ud83d\uded2 `%buy {tree.name}` \u2139 `%info {tree.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\ud83c\udf33 Koki'
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @shop.command()
    async def boosts(self, ctx):
        embed = discord.Embed(title='\ud83c\udfe6 Pakalpojumi', color=82247)
        embed.add_field(
            name='\ud83d\udc29Kvešķētājs',
            value="""Sargā lauku, it kā sargā.
            `%dog 1`"""
            )
        embed.add_field(
            name='\ud83d\udc36Siekalainais Tobis',
            value="""Sargā lauku, bet patīk spēlēties.
            `%dog 2`"""
            )
        embed.add_field(
            name='\ud83d\udc15Reksis',
            value="""Apsargā lauku un tavu sirdsapziņu.
            `%dog 3`"""
            )
        embed.add_field(
            name='\ud83d\udc31',
            value='`???`'
            )
        await ctx.send(embed=embed)

    @commands.group()
    async def market(self, ctx):
        if ctx.invoked_subcommand:
            return

        embed = discord.Embed(title='Izvēlies kategoriju', colour=1563808)
        embed.add_field(name='\ud83c\udf3e Raža', value='`%market crops`')
        embed.add_field(name='\ud83d\udce6 Produkti', value='`%market items`')
        embed.add_field(name='\ud83d\udd39 Citi Produkti', value='`%market other`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @market.command(name='crops')
    async def mcrops(self, ctx):
        items = []
        client = self.client

        refreshin = datetime.datetime.now() - self.lastrefresh
        refreshin = secstotime(REFRESH_SHOP_SECONDS - refreshin.seconds)
        items.append(f'\u23f0Tirgus cenas atjaunosies pēc {refreshin}\n')

        for x in client.crops.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Pašlaik iepērkam par: {x.marketprice}{client.gold}/gab.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Tirgus: \ud83c\udf3eRaža'
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
        items.append(f'\u23f0Tirgus cenas atjaunosies pēc {refreshin}\n')

        for x in client.crafteditems.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Pašlaik iepērkam par: {x.marketprice}{client.gold}/gab.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Tirgus: \ud83d\udce6Produkti'
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
        items.append(f'\u23f0Tirgus cenas atjaunosies pēc {refreshin}\n')

        for x in client.items.values():
            item = f"""{x.emoji}**{x.name.capitalize()}**
            Pašlaik iepērkam par: {x.marketprice}{client.gold}/gab.
            \u2696 `%sell {x.name}` \u2139 `%info {x.name}`\n"""
            items.append(item)
        try:
            p = Pages(ctx, entries=items, per_page=3, show_entry_count=False)
            p.embed.title = '\u2696 Tirgus: \ud83d\udd39 Citi produkti'
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
            name=f'{client.tile}Paplašināt zemi \ud83d\udd313',
            value=f"""\ud83c\udd95 {profile['tiles']} \u2192 {profile['tiles'] + 1} platība
            {client.gem}{usertools.upgradecost(profile['tiles'])}
            \ud83d\uded2 `%expand`"""
        )
        embed.add_field(
            name=f'\ud83c\udfedUzlabot rūpnīcu \ud83d\udd313',
            value=f"""\ud83c\udd95 {profile['factoryslots']} \u2192 {profile['factoryslots'] + 1} ražotspēja
            {client.gem}{usertools.upgradecost(profile['factoryslots'])}
            \ud83d\uded2 `%upgrade`"""
        )
        embed.add_field(
            name=f'\ud83c\udfeaUzlabot veikalu',
            value=f"""\ud83c\udd95 {profile['storeslots']} \u2192 {profile['storeslots'] + 1} pārdošanas apjoms
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
            embed = emb.errorembed(f"Šī prece ({item.emoji}{item.name.capitalize()}) netiek pārdota mūsu bodē \ud83d\ude26", ctx)
            return await ctx.send(embed=embed)

        buyer = await usertools.getprofile(client, ctx.author)
        if usertools.getlevel(buyer['xp'])[0] < item.level:
            embed = emb.errorembed(f"Pārāk zems līmenis, lai iegādātos {item.emoji}{item.name2.capitalize()}", ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f'{item.emoji}**{item.name.capitalize()}**\n ID: {item.id}'
        )
        buyembed.add_field(
            name='Cena',
            value=f'{client.gold}{item.cost} vai {client.gem}{item.scost}'
        )
        if not customamount:
            buyembed.add_field(
                name='Daudzums',
                value="""Ievadi daudzumu ar cipariem čatā.
                Lai atceltu, ieraksti čatā `X`."""
            )
        buyembed.set_footer(
            text=f"{ctx.author} Zelts: {buyer['money']} SN: {buyer['gems']}",
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
                embed = emb.errorembed('Gaidīju pārāk ilgi. Darījums atcelts.', ctx)
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
                    embed = emb.errorembed('Nederīgs daudzums. Sāc pirkumu par jaunu.', ctx)
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed('Nederīgs daudzums. Nākošreiz ieraksti skaitli', ctx)
                return await ctx.send(embed=embed)

            buyembed.set_field_at(
                index=2,
                name='Daudzums',
                value=amount
            )
        else:
            buyembed.add_field(
                name='Daudzums',
                value=amount
            )
        buyembed.add_field(
            name='Summa',
            value=f'{client.gold}{item.cost * amount} vai {client.gem}{item.scost * amount}'
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
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
            embed = emb.errorembed('Tev nepietiek zelts. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        query = """SELECT money FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, buyer['id'])
        if usergold['money'] < total:
            embed = emb.errorembed('Tev nepietiek zelts. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givemoney(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"Tu nopirki {amount}x{item.emoji}{item.name2.capitalize()} par {total}{self.client.gold}", ctx)
        await ctx.send(embed=embed)

    async def buywithgems(self, ctx, buyer, item, amount):
        client = self.client
        total = item.scost * amount
        if buyer['gems'] < total:
            embed = emb.errorembed('Tev nepietiek supernaudu. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        query = """SELECT gems FROM users
        WHERE id = $1;"""

        usergems = await client.db.fetchrow(query, buyer['id'])
        if usergems['gems'] < total:
            embed = emb.errorembed('Tev nepietiek supernaudu. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        await usertools.givegems(client, ctx.author, total * -1)

        embed = emb.confirmembed(f"Tu nopirki {amount}x{item.emoji}{item.name2.capitalize()} par {total}{self.client.gem}", ctx)
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
            embed = emb.errorembed(f"Šī prece ({item.emoji}{item.name.capitalize()}) netiek iepirkta tirgū \ud83d\ude26", ctx)
            return await ctx.send(embed=embed)

        hasitem = await usertools.checkinventoryitem(client, ctx.author, item)
        if not hasitem:
            embed = emb.errorembed(f"Tev nav ({item.emoji}{item.name.capitalize()}) noliktavā!", ctx)
            return await ctx.send(embed=embed)
        else:
            alreadyhas = hasitem['amount']

        sellembed = discord.Embed(title='Darījuma detaļas', colour=9309837)
        sellembed.add_field(
            name='Prece',
            value=f'{item.emoji}**{item.name.capitalize()}**\nPreces ID: {item.id}'
        )
        sellembed.add_field(
            name='Cena',
            value=f'{client.gold}{item.marketprice}'
        )
        sellembed.set_footer(
            text=ctx.author, icon_url=ctx.author.avatar_url
        )

        if not customamount:
            sellembed.add_field(
                name='Daudzums',
                value=f"""Ievadi daudzumu ar cipariem čatā.
                Lai atceltu, ieraksti čatā `X`.
                Tev ir {alreadyhas}{item.emoji}."""
            )

            sellinfomessage = await ctx.send(embed=sellembed)

        if not customamount:
            def check(m):
                return m.author == ctx.author

            try:
                entry = None
                entry = await client.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                embed = emb.errorembed('Gaidīju pārāk ilgi. Darījums atcelts.', ctx)
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
                    embed = emb.errorembed('Nederīgs daudzums. Sāc pārdošanu par jaunu.', ctx)
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed('Nederīgs daudzums. Nākošreiz ieraksti skaitli', ctx)
                return await ctx.send(embed=embed)

            sellembed.set_field_at(
                index=2,
                name='Daudzums',
                value=amount
            )
        else:
            sellembed.add_field(
                name='Daudzums',
                value=amount
            )
        sellembed.add_field(
            name='Summa',
            value=f'{client.gold}{item.marketprice * amount}'
        )
        sellembed.add_field(
            name='Apstiprinājums',
            value='Lai pabeigtu darījumu, nospied atbilstošo reakciju'
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
            embed = emb.errorembed(f"Tev nav {item.emoji}{item.name.capitalize()} noliktavā!", ctx)
            return await ctx.send(embed=embed)

        if amount > hasitem['amount']:
            embed = emb.errorembed(f"Tev ir tikai {hasitem['amount']}x {item.emoji}{item.name.capitalize()} noliktavā!", ctx)
            return await ctx.send(embed=embed)

        await usertools.removeitemfrominventory(client, ctx.author, item, amount)
        await usertools.givemoney(client, ctx.author, total)

        embed = emb.confirmembed(f"Tu pārdevi {amount}x{item.emoji}{item.name2.capitalize()} par {total}{self.client.gold}", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def expand(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        if usertools.getlevel(profile['xp'])[0] < 3:
            embed = emb.errorembed('Zemes paplašināšana ir pieejama no 3.līmeņa.', ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f"{client.tile} {profile['tiles']} \u2192 {profile['tiles'] + 1}"
        )
        buyembed.add_field(
            name='Cena',
            value=f"{client.gem}{usertools.upgradecost(profile['tiles'])}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
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
            embed = emb.errorembed('Tev nepietiek supernaudu. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.addfields(client, ctx.author, 1)
        await usertools.givegems(client, ctx.author, gemstopay * -1)
        embed = emb.congratzembed(f"Tava lauku platība tagad ir {profile['tiles'] + 1}", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def upgrade(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        if usertools.getlevel(profile['xp'])[0] < 3:
            embed = emb.errorembed('Rūpnīcas uzlabošana ir pieejama no 3.līmeņa.', ctx)
            return await ctx.send(embed=embed)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f"\ud83c\udfed\ud83d\udce6 {profile['factoryslots']} \u2192 {profile['factoryslots'] + 1}"
        )
        buyembed.add_field(
            name='Cena',
            value=f"{client.gem}{usertools.upgradecost(profile['factoryslots'])}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
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
            embed = emb.errorembed('Tev nepietiek supernaudu. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.addfactoryslots(client, ctx.author, 1)
        await usertools.givegems(client, ctx.author, gemstopay * -1)
        embed = emb.congratzembed(f"Tava rūpnīcas ražotspēja tagad ir {profile['factoryslots'] + 1}", ctx)
        await ctx.send(embed=embed)

    @commands.command()
    async def addslot(self, ctx):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)

        buyembed = discord.Embed(title='Pirkuma detaļas', colour=9309837)
        buyembed.add_field(
            name='Prece',
            value=f"\ud83c\udfea {profile['storeslots']} \u2192 {profile['storeslots'] + 1}"
        )
        buyembed.add_field(
            name='Cena',
            value=f"{client.gold}{usertools.storeupgcost(profile['storeslots'])}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
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
            embed = emb.errorembed('Tev nepietiek supernaudu. Sāc pirkumu par jaunu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.addstoreslots(client, ctx.author, 1)
        await usertools.givemoney(client, ctx.author, goldtopay * -1)
        embed = emb.congratzembed(f"Tava veikala pārdošanas apjoms tagad ir {profile['storeslots'] + 1}", ctx)
        await ctx.send(embed=embed)

    @commands.group()
    async def dog(self, ctx):
        if ctx.invoked_subcommand:
            return
        embed = emb.errorembed("`%dog 1 - 3`", ctx)
        await ctx.send(embed=embed)

    @dog.command(name='1')
    async def dog1(self, ctx):
        message, gp, dp = await self.preparedoginfo(ctx, 1, '\ud83d\udc29')
        await self.assigndog(ctx, message, gp, dp, '\ud83d\udc29', 1)

    @dog.command(name='2')
    async def dog2(self, ctx):
        message, gp, dp = await self.preparedoginfo(ctx, 2, '\ud83d\udc36')
        await self.assigndog(ctx, message, gp, dp, '\ud83d\udc36', 2)

    @dog.command(name='3')
    async def dog3(self, ctx):
        message, gp, dp = await self.preparedoginfo(ctx, 3, '\ud83d\udc15')
        await self.assigndog(ctx, message, gp, dp, '\ud83d\udc15', 3)

    async def preparedoginfo(self, ctx, dog, emoji):
        client = self.client
        profile = await usertools.getprofile(self.client, ctx.author)
        goldprices = boosttools.getdoggoldprices(profile['tiles'], dog)
        gemprices = boosttools.getdoggemprices(profile['tiles'], dog)

        embed = discord.Embed(title=f'Noalgot suni {emoji}')
        embed.add_field(
            name='Uz 1 dienu',
            value=f"{goldprices[1]}{client.gold} vai {gemprices[1]}{client.gem}"
            )
        embed.add_field(
            name='Uz 3 dienām',
            value=f"{goldprices[3]}{client.gold} vai {gemprices[3]}{client.gem}"
            )
        embed.add_field(
            name='Uz 7 dienām',
            value=f"{goldprices[7]}{client.gold} vai {gemprices[7]}{client.gem}"
            )
        message = await ctx.send(embed=embed)
        await message.add_reaction('1\u20e3')
        await message.add_reaction('3\u20e3')
        await message.add_reaction('7\u20e3')

        return message, goldprices, gemprices

    async def assigndog(self, ctx, message, gp, dp, emoji, dog):
        client = self.client

        emojis = {
            '1\u20e3': (gp[1], dp[1]),
            '3\u20e3': (gp[3], dp[3]),
            '7\u20e3': (gp[7], dp[7])
        }

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in emojis and reaction.message.id == message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        await message.delete()

        settings = emojis[str(reaction.emoji)]

        buyembed = discord.Embed(title='Pirkuma detaļas')
        buyembed.add_field(
            name='Prece',
            value=f"{emoji} {str(reaction.emoji)[0]} dienas"
        )
        buyembed.add_field(
            name='Cena',
            value=f"{client.gold}{settings[0]} vai {client.gem}{settings[1]}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)
        await buyinfomessage.add_reaction(client.gem)

        aemojis = (client.gem, client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in aemojis and reaction.message.id == buyinfomessage.id

        try:
            breaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        if str(breaction.emoji) == client.gold:
            await self.dogbuywithgold(ctx, settings[0], dog, emoji, int(str(reaction.emoji)[0]))
        elif str(breaction.emoji) == client.gem:
            await self.dogbuywithgems(ctx, settings[1], dog, emoji, int(str(reaction.emoji)[0]))

    async def dogbuywithgold(self, ctx, gold, dog, emoji, duration):
        client = self.client
        query = """SELECT money FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if usergold['money'] < gold:
            embed = emb.errorembed('Tev nepietiek zelts.', ctx)
            return await ctx.send(embed=embed)

        await usertools.givemoney(client, ctx.author, gold * -1)

        await boosttools.adddog(client, ctx.author, dog, duration)

        embed = emb.confirmembed(f"Tu noalgoji {emoji} apsargāt laukus", ctx)
        await ctx.send(embed=embed)

    async def dogbuywithgems(self, ctx, gems, dog, emoji, duration):
        client = self.client
        query = """SELECT gems FROM users
        WHERE id = $1;"""

        usergold = await client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if usergold['gems'] < gems:
            embed = emb.errorembed('Tev nepietiek supernaudu.', ctx)
            return await ctx.send(embed=embed)

        await usertools.givegems(client, ctx.author, gems * -1)

        await boosttools.adddog(client, ctx.author, dog, duration)

        embed = emb.confirmembed(f"Tu noalgoji {emoji} apsargāt laukus", ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Shop(client))

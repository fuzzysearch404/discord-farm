import asyncio
from discord.ext import commands
from discord import Embed
from discord import HTTPException
from typing import Optional
from utils import usertools
from utils import embeds as emb
from utils.item import finditem
from utils.paginator import Pages
from utils.convertors import MemberID


class Trades(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @commands.command(aliases=['as'])
    async def allstores(self, ctx):
        information = []
        users = {}

        client = self.client
        storedata = await usertools.getguildstore(client, ctx.guild)
        if not storedata:
            embed = emb.errorembed(f'Šajā serverī neviens neko nepārdod :(', ctx)
            return await ctx.send(embed=embed)

        for object in storedata:
            userid = usertools.splitgameuserid(object['userid'], ctx)

            user = ctx.guild.get_member(userid)
            if not user:
                continue

            try:
                users[user].append(client.allitems[object['itemid']])
            except KeyError:
                users[user] = [client.allitems[object['itemid']]]

        for user, items in users.items():
            string, count = '', 0
            for i in items:
                if count < 5:
                    count += 1
                    string += i.emoji
                else:
                    string += f'+{len(items) - 5}'
                    break

            information.append(f"\ud83c\udfea `%store {user}`\n" + string + '\n')

        try:
            p = Pages(ctx, entries=information, per_page=5, show_entry_count=False)
            p.embed.title = f'\ud83d\udecd{ctx.guild} servera aktīvie veikali'
            p.embed.color = 7995937
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command()
    async def store(self, ctx, *, member: Optional[MemberID] = None):
        crops, citems, items = {}, {}, {}
        information = []

        member = member or ctx.author
        client = self.client
        storedata = await usertools.getuserstore(client, member)
        if not storedata:
            embed = emb.errorembed(f'{member} neko nepārdod', ctx)
            return await ctx.send(embed=embed)
        for object in storedata:
            try:
                item = client.allitems[object['itemid']]

                if item.type == 'crop':
                    crops[object] = item
                elif item.type == 'crafteditem':
                    citems[object] = item
                elif item.type == 'item':
                    items[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        if len(crops) > 0:
            information.append('**Raža:**')
            for data, item in crops.items():
                fmt = f"""{item.emoji}**{item.name.capitalize()}** x{data['amount']}
                {client.gold}{data['money']} \ud83d\uded2 `%trade {data['id']}`\n"""
                information.append(fmt)
        if len(citems) > 0:
            information.append('**Produkcija:**')
            for data, item in citems.items():
                fmt = f"""{item.emoji}**{item.name.capitalize()}** x{data['amount']}
                {client.gold}{data['money']} \ud83d\uded2 `%trade {data['id']}`\n"""
                information.append(fmt)
        if len(items) > 0:
            information.append('**Dzīvnieku produkti:**')
            for data, item in items.items():
                fmt = f"""{item.emoji}**{item.name.capitalize()}** x{data['amount']}
                {client.gold}{data['money']} \ud83d\uded2 `%trade {data['id']}`\n"""
                information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=5, show_entry_count=False)
            p.embed.title = f'\ud83c\udfea{member} veikals'
            p.embed.color = 7995937
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command()
    async def trade(self, ctx, id: int):
        client = self.client

        tradedata = await usertools.gettrade(client, id)
        if not tradedata:
            embed = emb.errorembed("Kāds jau ir nopircis šos produktus vai nepareizs ID", ctx)
            return await ctx.send(embed=embed)

        profile = await usertools.getprofile(client, ctx.author)
        level = usertools.getlevel(profile['xp'])[0]
        ownerid = usertools.splitgameuserid(tradedata['userid'], ctx)

        item = client.allitems[tradedata['itemid']]

        if level < item.level:
            embed = emb.errorembed("Pārāk zems līmenis, lai iegādātos šos produktus", ctx)
            return await ctx.send(embed=embed)

        if tradedata['money'] > profile['money'] and ownerid != ctx.author.id:
            embed = emb.errorembed("Tev nepietiek zelts, lai iegādātos šos produktus", ctx)
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Pirkuma detaļas', color=8052247)
        buyembed.set_footer(
            text=f"{ctx.author} Zelts: {profile['money']} SN: {profile['gems']}",
            icon_url=ctx.author.avatar_url,
        )
        buyembed.add_field(
            name='Produkti',
            value=f"{tradedata['amount']}x{item.emoji}{item.name.capitalize()}"
        )
        buyembed.add_field(
            name='Summa',
            value=f"{client.gold}{tradedata['money']}"
        )
        buyembed.add_field(name='Apstiprinājums', value='Norādi ar reakciju valūtu')
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)
        await buyinfomessage.add_reaction('\u274c')

        allowedemojis = ('\u274c', client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in allowedemojis and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await buyinfomessage.clear_reactions()

        if not str(reaction.emoji) == client.gold:
            return

        query = """SELECT money FROM users
        WHERE id = $1;"""

        selfbuy = ownerid == ctx.author.id

        usergold = await client.db.fetchrow(query, profile['id'])
        if usergold['money'] < tradedata['money'] and not selfbuy:
            embed = emb.errorembed('Tev nepietiek zelts, lai iegādātos šos produktus', ctx)
            return await ctx.send(embed=embed)

        tradedata = await usertools.gettrade(client, id)
        if not tradedata:
            embed = emb.errorembed('Upsī! Kāds jau paspēja nopirkt šīs lietas pirms tevis', ctx)
            return await ctx.send(embed=embed)

        await usertools.deletetrade(client, tradedata['id'])
        await usertools.additemtoinventory(client, ctx.author, item, tradedata['amount'])

        if not selfbuy:
            await usertools.givemoney(client, ctx.author, tradedata['money'] * -1)
            await usertools.givemoney(client, tradedata['userid'], tradedata['money'])

        if selfbuy:
            sum = 0
        else:
            sum = tradedata['money']
        embed = emb.confirmembed(f"Tu nopirki {tradedata['amount']}x{item.emoji}{item.name2.capitalize()} par {sum}{client.gold}", ctx)
        await ctx.send(embed=embed)

        if selfbuy:
            return
        owner = ctx.guild.get_member(ownerid)
        if not owner:
            return
        embed = emb.confirmembed(
            f"{ctx.author} nopirka no tevis {tradedata['amount']}x{item.emoji}{item.name2.capitalize()} par {tradedata['money']}{client.gold}",
            ctx, pm=True
        )
        await owner.send(embed=embed)

    @commands.command(aliases=['a'])
    async def add(self, ctx, *, possibleitem):
        client = self.client

        try:
            possibleamount = possibleitem.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            possibleitem = possibleitem.rsplit(' ', 1)[0]
            if not amount > 0 or amount > 2147483647:
                return
        except Exception:
            embed = emb.errorembed(
                "Lūdzu, norādi arī daudzumu\n"
                f"Piemēram 10 - `%add {possibleitem} 10`",
                ctx)
            return await ctx.send(embed=embed)

        profile = await usertools.getprofile(client, ctx.author)
        slots = profile['storeslots']
        usedslots = await usertools.getstoreslotcount(client, ctx.author)

        if not usedslots:
            pass
        elif usedslots >= slots:
            embed = emb.errorembed(
                "Tavs veikals ir pilns! Gaidi, lai kāds nopērk kaut ko"
                ", vai uzlabo veikalu ar `%addslot`", ctx
            )
            return await ctx.send(embed=embed)

        item = await finditem(client, ctx, possibleitem)
        if not item:
            return

        allowedtypes = ('crop', 'crafteditem', 'item')

        if not item.type or item.type not in allowedtypes:
            embed = emb.errorembed(f"Tu nevari pārdot {item.emoji}{item.name.capitalize()}", ctx)
            return await ctx.send(embed=embed)

        hasitem = await usertools.checkinventoryitem(client, ctx.author, item)
        if not hasitem:
            embed = emb.errorembed(f"Tev nav ({item.emoji}{item.name.capitalize()}) noliktavā!", ctx)
            return await ctx.send(embed=embed)

        minprice = item.minprice * amount
        maxprice = item.maxprice * amount
        maxprice = maxprice + int(maxprice * 0.43)

        sellembed = Embed(title='Pievienot veikalam', colour=8052247)
        sellembed.add_field(
            name='Prece',
            value=f'{item.emoji}**{item.name.capitalize()}**\nPreces ID: {item.id}'
        )
        sellembed.set_footer(
            text=ctx.author, icon_url=ctx.author.avatar_url
        )
        sellembed.add_field(
            name='Daudzums',
            value=amount
        )
        sellembed.add_field(
            name=f'Cenas diapazons',
            value=f"**{minprice} - {maxprice} {client.gold}**"
        )
        sellembed.add_field(
            name=f'{client.gold}Cena',
            value=f"""
            Ievadi cenu ar cipariem čatā.
            Lai atceltu, ieraksti čatā `X`.
            """
        )
        sellinfomessage = await ctx.send(embed=sellembed)

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
        except HTTPException:
            pass

        try:
            price = int(entry.clean_content)
            if price < 1:
                embed = emb.errorembed('Nederīga cena. Sāc pārdošanu par jaunu.', ctx)
                return await ctx.send(embed=embed)
        except ValueError:
            embed = emb.errorembed('Nederīga cena. Nākošreiz ieraksti skaitli', ctx)
            return await ctx.send(embed=embed)

        if price > maxprice or price < minprice:
            embed = emb.errorembed(
                'Nederīga cena.\n'
                f'Šī prece ir pārdodama par **{minprice} - {maxprice} {client.gold}**',
                ctx
            )
            return await ctx.send(embed=embed)

        sellembed.remove_field(index=2)
        sellembed.remove_field(index=2)
        sellembed.add_field(
            name='Iespējamā peļņa',
            value=f'{client.gold}{price}'
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
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=10.0)
        except asyncio.TimeoutError:
            return await sellinfomessage.clear_reactions()

        if str(reaction.emoji) == '\u274c':
            return

        await self.addtomarket(ctx, item, amount, price)

    async def addtomarket(self, ctx, item, amount, price):
        client = self.client

        hasitem = await usertools.checkinventoryitem(client, ctx.author, item)
        if not hasitem:
            embed = emb.errorembed(f"Tev nav {item.emoji}{item.name.capitalize()} noliktavā!", ctx)
            return await ctx.send(embed=embed)

        if amount > hasitem['amount']:
            embed = emb.errorembed(f"Tev ir tikai {hasitem['amount']}x {item.emoji}{item.name.capitalize()} noliktavā!", ctx)
            return await ctx.send(embed=embed)

        await usertools.removeitemfrominventory(client, ctx.author, item, amount)

        connection = await client.db.acquire()
        async with connection.transaction():
            userid = usertools.generategameuserid(ctx.author)
            query = """INSERT INTO store(guildid, userid, itemid, amount, money)
            VALUES ($1, $2, $3, $4, $5);"""
            await client.db.execute(query, ctx.guild.id, userid, item.id, amount, price)
        await client.db.release(connection)

        embed = emb.confirmembed(f"Tu ieliki pārdošanā {amount}x{item.emoji}{item.name2.capitalize()} par {price}{self.client.gold}", ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Trades(client))

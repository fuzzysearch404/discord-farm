import utils.embeds as emb
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
from utils import usertools
from utils.item import finditem
from utils.time import secstotime
from utils.paginator import Pages
from utils.convertors import MemberID


class Planting(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @commands.command()
    async def field(self, ctx, member: Optional[MemberID] = None):
        crops = {}
        information = []

        member = member or ctx.author
        client = self.client
        fielddata = await usertools.getuserfield(client, member)
        if not fielddata:
            embed = emb.errorembed(f'{member} nav apstrādātu lauku', ctx)
            return await ctx.send(embed=embed)
        for object in fielddata:
            try:
                item = client.allitems[object['itemid']]

                if item.type == 'crop':
                    crops[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        if len(crops) > 0:
            information.append('**Augi:**')
            for data, item in crops.items():
                status = self.getcropstate(item, data['ends'], data['dies'])[1]
                fmt = f"{item.emoji}**{item.name.capitalize()}** x{data['amount']} - {status}"
                information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=10, show_entry_count=False)
            p.embed.title = f'{member} lauki'
            p.embed.color = 976400
            await p.paginate()
        except Exception as e:
            print(e)

    def getcropstate(self, item, ends, dies):
        now = datetime.now()
        if ends > now:
            parent = item.getparent(self.client)
            half = parent.grows / 2
            secsdelta = ends - now
            if secsdelta.seconds > half:
                status = f'Dīgst {secstotime(secsdelta.seconds - half)}'
                stype = 'grow1'
            else:
                status = f'Aug {secstotime(secsdelta.seconds)}'
                stype = 'grow2'
        elif dies > now:
            secsdelta = dies - now
            status = f'Jānovāc {secstotime(secsdelta.seconds)} laikā'
            stype = 'ready'
        else:
            status = 'Sapuvis'
            stype = 'dead'

        return stype, status

    @commands.command(aliases=['h'])
    async def harvest(self, ctx):
        items = {}
        todelete = []
        unique = {}

        client = self.client
        fielddata = await usertools.getuserfield(client, ctx.author)
        if not fielddata:
            embed = emb.errorembed("Tev nav apstādātu lauku", ctx)
            return await ctx.send(embed=embed)
        for object in fielddata:
            try:
                item = client.allitems[object['itemid']]
                items[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        for data, item in items.items():
            status = self.getcropstate(item, data['ends'], data['dies'])[0]
            if status == 'grow1' or status == 'grow2':
                continue
            elif status == 'ready':
                xp = item.xp * data['amount']
                await usertools.givexpandlevelup(client, ctx, xp)
                await usertools.additemtoinventory(client, ctx.author, item, data['amount'])
                if item in unique:
                    unique[item] = (unique[item][0] + data['amount'], unique[item][1] + xp)
                else:
                    unique[item] = (data['amount'], xp)

            todelete.append(data['id'])

        if len(todelete) > 0:
            connection = await client.db.acquire()
            async with connection.transaction():
                query = """DELETE FROM planted WHERE id = $1;"""
                for item in todelete:
                    await client.db.execute(query, item)
            await client.db.release(connection)

        await usertools.addusedfields(client, ctx.author, len(todelete) * -1)

        if not unique.items() and len(todelete) > 0:
            embed = emb.confirmembed("Tu novāci sobojājušās lietas", ctx)
            await ctx.send(embed=embed)
        elif unique.items():
            information = ''
            for key, value in unique.items():
                information += f"{key.emoji}**{key.name2.capitalize()}** x{value[1]} +{value[0]}{client.xp}"
            embed = emb.confirmembed(f"Tu novāci: {information}", ctx)
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed("Tev nav gatavas produkcijas, kuru novākt!", ctx)
            await ctx.send(embed=embed)

    @commands.command(aliases=['p'])
    async def plant(self, ctx, *, possibleitem):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)
        usedtiles = profile['usedtiles']
        tiles = profile['tiles']

        customamount = False
        try:
            possibleamount = possibleitem.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            possibleitem = possibleitem.rsplit(' ', 1)[0]
            customamount = True
        except Exception:
            pass

        if not customamount:
            if usedtiles >= tiles:
                embed = emb.errorembed(
                    "Tev nav vietas, kur stādīt! Atbrīvo to vai nopērc papildus teritoriju ar `%expand`.",
                    ctx
                )
                return await ctx.send(embed=embed)
        else:
            if usedtiles + amount > tiles:
                embed = emb.errorembed(
                    "Tev nav tik daudz vietas, kur stādīt! Atbrīvo to vai nopērc papildus teritoriju ar `%expand`.",
                    ctx
                )
                return await  ctx.send(embed=embed)

        item = await finditem(self.client, ctx, possibleitem)
        if not item:
            return
        if item.type != 'cropseed':
            embed = emb.errorembed(f"Šo lietu ({item.emoji}{item.name2.capitalize()}) nevar iestādīt. Stādi sēklas!", ctx)
            return await ctx.send(embed=embed)

        inventorydata = await usertools.checkinventoryitem(client, ctx.author, item)
        if not inventorydata:
            embed = emb.errorembed(
                f"Tavā noliktavā nav {item.emoji}{item.name.capitalize()}. Tu vari iegādāties lietas ar komandu `%shop`.",
                ctx
            )
            return await ctx.send(embed=embed)

        if customamount:
            if inventorydata['amount'] < amount:
                embed = emb.errorembed(
                    f"Tavā noliktavā ir tikai {inventorydata['amount']}x{item.emoji}{item.name.capitalize()}. Tu vari iegādāties lietas ar komandu `%shop`.",
                    ctx
                )
                return await ctx.send(embed=embed)
            elif not amount > 0:
                embed = emb.errorembed(
                    f"Nederīgs daudzums!",
                    ctx
                )
                return await ctx.send(embed=embed)

            await usertools.removeitemfrominventory(client, ctx.author, item, amount)
        else:
            await usertools.removeitemfrominventory(client, ctx.author, item, 1)

        itemchild = item.getchild(client)
        now = datetime.now().replace(microsecond=0)
        ends = now + timedelta(seconds=item.grows)
        dies = ends + timedelta(seconds=item.dies)

        userid = usertools.generategameuserid(ctx.author)

        connection = await client.db.acquire()
        async with connection.transaction():
            query = """INSERT INTO planted(itemid, userid, amount, ends, dies, robbed)
            VALUES($1, $2, $3, $4, $5, $6)"""
            if not customamount:
                await client.db.execute(
                    query, itemchild.id, userid, item.amount,
                    ends, dies, False
                )
            else:
                for i in range(amount):
                    await client.db.execute(
                        query, itemchild.id, userid, item.amount,
                        ends, dies, False
                    )
        await client.db.release(connection)

        if not customamount:
            await usertools.addusedfields(client, ctx.author, 1)

            embed = emb.confirmembed(
                f"Tu iestādīji {item.emoji}{item.name.capitalize()}.\n"
                f"Izaugs par {item.amount}x {itemchild.emoji}**{itemchild.name.capitalize()}**\n"
                f"Nogatavosies: `{ends}` Sabojāsies: `{dies}`",
                ctx
                )
        else:
            await usertools.addusedfields(client, ctx.author, amount)

            embed = emb.confirmembed(
                f"Tu iestādīji {amount}x{item.emoji}{item.name.capitalize()}.\n"
                f"Izaugs par {item.amount * amount}x {itemchild.emoji}**{itemchild.name.capitalize()}**\n"
                f"Nogatavosies: `{ends}` Sabojāsies: `{dies}`",
                ctx
            )
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Planting(client))

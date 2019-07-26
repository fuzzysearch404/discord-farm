from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
from utils import embeds as emb
from utils import usertools
from utils.item import finditem, convertmadefrom
from utils.paginator import Pages
from utils.time import secstotime
from utils.convertors import MemberID


class Factory(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @commands.command()
    async def factory(self, ctx, member: Optional[MemberID] = None):
        allitems = {}
        information = []
        member = member or ctx.author
        client = self.client

        factorydata = await usertools.getuserfactory(client, member)
        if not factorydata:
            embed = emb.errorembed(f'{member} neko neražo', ctx)
            return await ctx.send(embed=embed)

        for object in factorydata:
            try:
                item = client.allitems[object['itemid']]
                allitems[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        for data, item in allitems.items():
            status = self.getitemstate(item, data['start'], data['ends'])[1]
            fmt = f"{item.emoji}**{item.name2.capitalize()}** - {status}"
            information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=10, show_entry_count=False)
            p.embed.title = f'\ud83c\udfed{member} rūpnīca'
            p.embed.color = 13110284
            await p.paginate()
        except Exception as e:
            print(e)

    def getitemstate(self, item, starts, ends):
        now = datetime.now()
        if starts > now:
            status = 'Gaida ražošanu'
            stype = 'queue'
        elif ends > now:
            secsdelta = ends - now
            status = f'Ražo {secstotime(secsdelta.seconds)}'
            stype = 'making'
        elif ends < now:
            status = 'Gatavs'
            stype = 'ready'

        return stype, status

    @commands.command()
    async def make(self, ctx, *, possibleitem):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)
        slots = await usertools.checkfactoryslots(client, ctx.author)

        if not slots > 0:
            embed = emb.errorembed(
                "Tev nav vietas rūpnīcā! Atbrīvo to vai uzlabo rūpnīcu ar `%upgrade`.",
                ctx
            )
            return await ctx.send(embed=embed)

        fitem = await finditem(self.client, ctx, possibleitem)
        if not fitem:
            return
        if fitem.type != 'crafteditem':
            embed = emb.errorembed("Šo lietu nevar ražot", ctx)
            return await ctx.send(embed=embed)

        if fitem.level > usertools.getlevel(profile['xp'])[0]:
            embed = emb.errorembed(
                f"Šo produktu var ražot tikai no \ud83d\udd31{fitem.level}.līmeņa.",
                ctx
            )
            return await ctx.send(embed=embed)

        needed = convertmadefrom(client, fitem.madefrom)
        neededstr = ''

        for item, amount in needed.items():
            itemdata = await usertools.checkinventoryitem(client, ctx.author, item)
            if itemdata:
                useramount = itemdata['amount']
            else:
                useramount = 0
            if not itemdata or useramount < amount:
                neededstr += f"\n{item.emoji}{item.name2.capitalize()} {useramount}/{amount}, "

        if len(neededstr) > 0:
            embed = emb.errorembed(
                f"Tev nav pietiekami daudz materiālu: {neededstr[:-2]}",
                ctx
            )
            return await ctx.send(embed=embed)

        for item, amount in needed.items():
            await usertools.removeitemfrominventory(
                client, ctx.author, item, amount
            )

        now = datetime.now().replace(microsecond=0)
        olditem = await usertools.getoldestfactoryitem(client, ctx.author)
        if not olditem:
            starts = now
        else:
            starts = olditem['ends']
        ends = starts + timedelta(seconds=fitem.time)

        connection = await client.db.acquire()
        async with connection.transaction():
            query = """INSERT INTO factory(userid, itemid, start, ends)
            VALUES($1, $2, $3, $4)"""
            await client.db.execute(
                query, usertools.generategameuserid(ctx.author), fitem.id,
                starts, ends
            )
        await client.db.release(connection)

        embed = emb.confirmembed(
            f"Tu pievienoji ražošanai {fitem.emoji}{fitem.name.capitalize()}.\n"
            f"Ražošana sāksies: `{starts}` Beigsies: `{ends}`",
            ctx
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['c'])
    async def collect(self, ctx):
        items = {}
        unique = {}
        todelete = []

        client = self.client
        factdata = await usertools.getuserfactory(client, ctx.author)
        if not factdata:
            embed = emb.errorembed("Tu neko neražo", ctx)
            return await ctx.send(embed=embed)
        for object in factdata:
            try:
                item = client.allitems[object['itemid']]
                items[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        for data, item in items.items():
            status = self.getitemstate(item, data['start'], data['ends'])[0]
            if status == 'queue' or status == 'making':
                continue
            elif status == 'ready':
                xp = item.xp
                await usertools.givexpandlevelup(client, ctx, xp)
                await usertools.additemtoinventory(client, ctx.author, item, 1)
                if item in unique:
                    unique[item] = (unique[item][0] + 1, unique[item][1] + xp)
                else:
                    unique[item] = (1, xp)

            todelete.append(data['id'])

        if len(todelete) > 0:
            connection = await client.db.acquire()
            async with connection.transaction():
                query = """DELETE FROM factory WHERE id = $1;"""
                for item in todelete:
                    await client.db.execute(query, item)
            await client.db.release(connection)

        if unique.items():
            information = ''
            for key, value in unique.items():
                information += f"{key.emoji}**{key.name2.capitalize()}** x{value[0]} +{value[1]}{client.xp}"
            embed = emb.confirmembed(f"Tu ieguvi: {information}", ctx)
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed("Tev nav gatavas produkcijas!", ctx)
            await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Factory(client))

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

    @commands.command(aliases=['fa'])
    async def factory(self, ctx, *, member: Optional[MemberID] = None):
        allitems = {}
        information = []
        member = member or ctx.author
        client = self.client

        factorydata = await usertools.getuserfactory(client, member)
        if not factorydata:
            embed = emb.errorembed(f'{member} does not produce anything', ctx)
            return await ctx.send(embed=embed)

        for object in factorydata:
            try:
                item = client.allitems[object['itemid']]
                allitems[object] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        for data, item in allitems.items():
            status = self.getitemstate(item, data['start'], data['ends'])[1]
            fmt = f"{item.emoji}**{item.name.capitalize()}** - {status}"
            information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=10, show_entry_count=False)
            p.embed.title = f"\ud83c\udfed{member}'s factory"
            p.embed.color = 13110284
            await p.paginate()
        except Exception as e:
            print(e)

    def getitemstate(self, item, starts, ends):
        now = datetime.now()
        if starts > now:
            status = 'Waiting in queue'
            stype = 'queue'
        elif ends > now:
            secsdelta = ends - now
            status = f'In production {secstotime(secsdelta.seconds)}'
            stype = 'making'
        elif ends < now:
            status = 'Ready to collect'
            stype = 'ready'

        return stype, status

    @commands.command()
    async def make(self, ctx, *, possibleitem):
        client = self.client
        profile = await usertools.getprofile(client, ctx.author)
        slots = await usertools.checkfactoryslots(client, ctx.author)

        customamount = False
        try:
            possibleamount = possibleitem.rsplit(' ', 1)[1]
            reqamount = int(possibleamount)
            possibleitem = possibleitem.rsplit(' ', 1)[0]
            if reqamount > 0 and reqamount < 2147483647:
                customamount = True
        except Exception:
            pass

        if not customamount:
            if not slots > 0:
                embed = emb.errorembed(
                    "Your factory is full! Free up some space or upgrade the factory with `%upgrade`.",
                    ctx
                )
                return await ctx.send(embed=embed)
        else:
            if slots < reqamount:
                embed = emb.errorembed(
                    "Your factory is full! Free up some space or upgrade the factory with `%upgrade`.",
                    ctx
                )
                return await ctx.send(embed=embed)
            if not reqamount > 0:
                embed = emb.errorembed(
                    "Invalid amount!",
                    ctx
                )
                return await ctx.send(embed=embed)

        fitem = await finditem(self.client, ctx, possibleitem)
        if not fitem:
            return
        if fitem.type != 'crafteditem':
            embed = emb.errorembed(f"This thing ({fitem.emoji}{fitem.name.capitalize()}) cannot be produced.", ctx)
            return await ctx.send(embed=embed)

        if fitem.level > usertools.getlevel(profile['xp'])[0]:
            embed = emb.errorembed(
                f"{fitem.emoji}{fitem.name.capitalize()} can be produced starting from level \ud83d\udd31{fitem.level}",
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
            if not customamount:
                if not itemdata or useramount < amount:
                    neededstr += f"\n{item.emoji}{item.name.capitalize()} {useramount}/{amount}, "
            else:
                if not itemdata or useramount < amount * reqamount:
                    neededstr += f"\n{item.emoji}{item.name.capitalize()} {useramount}/{amount * reqamount}, "

        if len(neededstr) > 0:
            embed = emb.errorembed(
                f"You don't have enough materials: {neededstr[:-2]}",
                ctx
            )
            return await ctx.send(embed=embed)

        for item, amount in needed.items():
            if customamount:
                amount = amount * reqamount
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

        userid = usertools.generategameuserid(ctx.author)

        connection = await client.db.acquire()
        async with connection.transaction():
            if not customamount:
                query = """INSERT INTO factory(userid, itemid, start, ends)
                VALUES($1, $2, $3, $4)"""
                await client.db.execute(
                    query, userid, fitem.id,
                    starts, ends
                )
            else:
                for i in range(reqamount):
                    query = """INSERT INTO factory(userid, itemid, start, ends)
                    VALUES($1, $2, $3, $4)"""
                    await client.db.execute(
                        query, userid, fitem.id,
                        starts, ends
                    )
                    if i != reqamount:
                        starts = ends
                        ends = starts + timedelta(seconds=fitem.time)
        await client.db.release(connection)

        if not customamount:
            embed = emb.confirmembed(
                f"You added {fitem.emoji}{fitem.name.capitalize()} to the production queue.\n",
                ctx
            )
        else:
            embed = emb.confirmembed(
                f"You added {reqamount}x{fitem.emoji}{fitem.name.capitalize()} to the production queue.\n",
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
            embed = emb.errorembed("You do not produce anything", ctx)
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
                information += f"{key.emoji}**{key.name.capitalize()}** x{value[0]} +{value[1]}{client.xp}"
            embed = emb.confirmembed(f"You got: {information}", ctx)
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed("There is no production ready yet!", ctx)
            await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Factory(client))

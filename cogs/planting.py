import datetime
import utils.embeds as emb
from discord.ext import commands
from typing import Optional
from utils import usertools
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
        return userid['userid'] == ctx.author.id

    @commands.command()
    async def field(self, ctx, member: Optional[MemberID] = None):
        crops = {}
        information = []

        member = member or ctx.author
        client = self.client
        fielddata = await usertools.getuserfield(client, member)
        if not fielddata:
            embed = emb.errorembed(f'{member} nav apstrādātu lauku')
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
                fmt = f"{item.emoji}**{item.name2.capitalize()}** x{data['amount']} - {status}"
                information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=10, show_entry_count=False)
            p.embed.title = f'{member} lauki'
            p.embed.color = 976400
            await p.paginate()
        except Exception as e:
            print(e)

    def getcropstate(self, item, ends, dies):
        now = datetime.datetime.now()
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

    @commands.command()
    async def harvest(self, ctx):
        items = {}
        information = []

        client = self.client
        fielddata = await usertools.getuserfield(client, ctx.author)
        if not fielddata:
            embed = emb.errorembed("Tev nav apstādātu lauku")
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
                pass
            else:
                pass

        await ctx.send(information)

    @commands.command()
    async def plant(self, ctx):
        pass


def setup(client):
    client.add_cog(Planting(client))

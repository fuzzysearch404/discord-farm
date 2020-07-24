from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta

from utils import checks
from utils import embeds as emb
from utils.paginator import Pages
from utils.time import secstotime
from utils.convertors import MemberID
from classes import user as userutils
from classes.item import finditem


class Factory(commands.Cog):
    """
    In your factory you can craft some of your items to some new items.
    Doesn't that sound fun already?

    Unlike in farm, factory can produce only one item per time, but
    you can queue the next items to produce, depending on  your factory capacity.
    Another benefit is that items do not get rotten in the factory.
    Crafted items usually have more gold and experience value 
    than the regular items.
    """
    def __init__(self, client):
        self.client = client

    def get_item_state(self, item, starts, ends):
        now = datetime.now()
        if starts > now:
            status = 'Waiting in queue for production'
            stype = 'queue'
        elif ends > now:
            secsdelta = ends - now
            status = f'In production {secstotime(secsdelta.total_seconds())}'
            stype = 'making'
        elif ends < now:
            status = 'Ready to collect'
            stype = 'ready'

        return stype, status

    @commands.command(aliases=['fa'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def factory(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83c\udfed Shows your or someone's factory information.

        With this command you can check what are you producing and
        what items are queued next.

        Additional parameters:
        `member` - some user in your server. (tagged user or user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        allitems = {}
        information = []
        member = member or ctx.author

        factorydata = await useracc.get_factory()
        if not factorydata:
            embed = emb.errorembed(f'{member} is not producing anything in the factory', ctx)
            return await ctx.send(embed=embed)

        usedcap = 0

        for data in factorydata:
            usedcap += 1
            try:
                item = client.allitems[data['itemid']]
                allitems[data] = item
            except KeyError:
                raise Exception(f"Could not find item {data['itemid']}")

        information.append(
            f"\ud83d\udce6 Used factory's capacity: {usedcap}/{useracc.factoryslots}\n"
            f"\ud83d\udc68\u200d\ud83c\udfed Factory workers: {useracc.factorylevel} "
            f"({useracc.factorylevel * 5}% faster production)\n"
        )

        for data, item in allitems.items():
            status = self.get_item_state(item, data['starts'], data['ends'])[1]
            fmt = f"{item.emoji}**{item.name.capitalize()}** - {status}"
            information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=15, show_entry_count=False)
            p.embed.title = f"\ud83c\udfed{member}'s factory"
            p.embed.color = 13110284
            p.embed.set_footer(
                text="Collect items with the %collect command", 
                icon_url=ctx.author.avatar_url
            )
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command(aliases=['craft', 'produce'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def make(self, ctx, *, item_search, amount: Optional[int] = 1):
        """
        \ud83d\udce6 Starts crafting an item or adds it to the production queue.

        Parameters:
        `item_search` - item to lookup for to make. (item's name or ID).
        Additional parameters:
        `amount` - specify how many items to make.

        Usage examples for crafting 2 green salad items:
        `%make green salad 2` - by using item's name.
        `%make 701 2` - by using item's ID.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        usedslots = await useracc.check_used_factory_slots()

        customamount = False
        try:
            possibleamount = item_search.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            item_search = item_search.rsplit(' ', 1)[0]
            if amount > 0 and amount < 2147483647:
                customamount = True
        except Exception:
            pass

        if not customamount:
            if usedslots >= useracc.factoryslots:
                embed = emb.errorembed(
                    "Your factory is full! Free up some space or upgrade the factory with `%upgrade`.",
                    ctx
                )
                return await ctx.send(embed=embed)
        else:
            if usedslots + amount > useracc.factoryslots:
                embed = emb.errorembed(
                    "Your factory is full! Free up some space or upgrade the factory with `%upgrade`.",
                    ctx
                )
                return await ctx.send(embed=embed)

        item = await finditem(client, ctx, item_search)
        if not item:
            return

        if item.type != 'crafteditem':
            embed = emb.errorembed(
                f"Sorry, you can't produce {item.emoji}{item.name.capitalize()} in the factory.",
                ctx
            )
            return await ctx.send(embed=embed)

        if item.level > useracc.level:
            embed = emb.errorembed(
                f"You need experience level {item.level} to start making {item.emoji}{item.name.capitalize()}!",
                ctx
            )
            return await ctx.send(embed=embed)

        reqitemsstr = ""

        for req_item, req_amount in item.craftedfrom.items():
            itemdata = await useracc.check_inventory_item(req_item)
            if not itemdata: useramount = 0
            else: useramount = itemdata['amount']

            if not customamount:
                if useramount < req_amount:
                    reqitemsstr += f"\n{req_item.emoji}{req_item.name.capitalize()} {useramount}/{req_amount}, "
            else:
                if useramount < req_amount * amount:
                    reqitemsstr += f"\n{req_item.emoji}{req_item.name.capitalize()} {useramount}/{amount * req_amount}, "

        if len(reqitemsstr) > 0:
            embed = emb.errorembed(
                f"You don't have enough raw materials for {amount}x {item.emoji} {reqitemsstr[:-2]}",
                ctx
            )
            return await ctx.send(embed=embed)

        for req_item, req_amount in item.craftedfrom.items():
            total = req_amount
            if customamount:
                total = total * amount
            await useracc.remove_item_from_inventory(req_item, total)

        now = datetime.now().replace(microsecond=0)
        olditem = await useracc.get_oldest_factory_item()
        if not olditem: starts = now
        else:
            oldends = olditem['ends']
            if oldends > now: starts = oldends
            else: starts = now

        def get_production_time():
            return item.time - int((item.time / 100) * (useracc.factorylevel * 5))

        ends = starts + timedelta(seconds=get_production_time())

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                if not customamount:
                    query = """INSERT INTO factory(userid, itemid, starts, ends)
                    VALUES($1, $2, $3, $4)"""
                    await client.db.execute(
                        query, useracc.userid, item.id, starts, ends
                    )
                else:
                    for i in range(amount):
                        query = """INSERT INTO factory(userid, itemid, starts, ends)
                        VALUES($1, $2, $3, $4)"""
                        await client.db.execute(
                            query, useracc.userid, item.id, starts, ends
                        )
                        starts = ends
                        ends = starts + timedelta(seconds=get_production_time())

        if not customamount:
            embed = emb.confirmembed(
                f"You added {item.emoji}{item.name.capitalize()} to the production queue.\n",
                ctx
            )
        else:
            embed = emb.confirmembed(
                f"You added {amount}x{item.emoji}{item.name.capitalize()} to the production queue.\n",
                ctx
            )
        await ctx.send(embed=embed)

    @commands.command(aliases=['c'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def collect(self, ctx):
        """
        \ud83d\ude9a Collects crafted items from your factory.

        Note: You can only collect items which are ready.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        items, unique, todelete = {}, {}, []

        factdata = await useracc.get_factory()
        if not factdata:
            embed = emb.errorembed(
                "You are not producing anything in your factory",
                ctx
            )
            return await ctx.send(embed=embed)
        for data in factdata:
            try:
                item = client.allitems[data['itemid']]
                items[data] = item
            except KeyError:
                raise Exception(f"Could not find item {data['itemid']}")

        for data, item in items.items():
            status = self.get_item_state(item, data['starts'], data['ends'])[0]
            if status == 'queue' or status == 'making':
                continue
            elif status == 'ready':
                xp = item.xp
                await useracc.give_xp_and_level_up(xp, ctx)
                await useracc.add_item_to_inventory(item, 1)
                if item in unique:
                    unique[item] = (unique[item][0] + 1, unique[item][1] + xp)
                else:
                    unique[item] = (1, xp)

            todelete.append(data['id'])

        if len(todelete) > 0:
            async with self.client.db.acquire() as connection:
                async with connection.transaction():
                    query = """DELETE FROM factory WHERE id = $1;"""
                    for item in todelete:
                        await client.db.execute(query, item)

        if unique.items():
            information = ''
            for key, value in unique.items():
                information += f"{key.emoji}**{key.name.capitalize()}** x{value[0]} +{value[1]}{client.xp}"
            embed = emb.confirmembed(
                f"You collected items from the factory: {information}",
                ctx
            )
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed(
                "There is no production ready yet in the factory!",
                ctx
            )
            embed.set_footer(
                text="Check your item crafting times with the %factory command."
            )
            await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Factory(client))

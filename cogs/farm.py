import utils.embeds as emb
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
from random import choice, randint
from utils import checks
from utils.time import secstotime
from utils.paginator import Pages
from utils.convertors import MemberID
from classes.item import finditem
from classes import user as userutils
from classes.boost import boostvalid

class Farm(commands.Cog, name="Actual Farm"):
    """
    Commands for seed planting, animal and tree growing.

    Each item has their growing time and time period while
    the item is not rotten. Items can only be harvested when
    they are grown enough. Rotten items take up your farm's space,
    but they are discarded automatically when you harvest your field.
    Trees, bushes and animals have multiple collection cycles,
    so you have to collect their items multiple times.
    """
    def __init__(self, client):
        self.client = client
        self.growable_items = (
            'cropseed', 'animal', 'tree'
        )
        self.not_growable_items = (
            'crop', 'animalproduct', 'treeproduct'
        )

    def get_crop_state(self, item, ends, dies):
        """Calculates time between now and item status."""
        now = datetime.now()
        if ends > now:
            parent = item.madefrom
            half = parent.grows / 2
            secsdelta = ends - now
            if secsdelta.total_seconds() > half:
                status = f'Sprouting {secstotime(secsdelta.total_seconds() - half)}'
                stype = 'grow1'
            else:
                status = f'Growing {secstotime(secsdelta.total_seconds())}'
                stype = 'grow2'
        elif dies > now:
            secsdelta = dies - now
            status = f'Harvestable for {secstotime(secsdelta.total_seconds())}'
            stype = 'ready'
        else:
            status = 'Rotten crops'
            stype = 'dead'

        return stype, status

    def get_animal_or_tree_state(self, ends, dies):
        """Calculates time between now and item status."""
        now = datetime.now()
        if ends > now:
            secsdelta = ends - now
            status = f'Growing {secstotime(secsdelta.total_seconds())}'
            stype = 'grow1'
        elif dies > now:
            secsdelta = dies - now
            status = f'Collectable for {secstotime(secsdelta.total_seconds())}'
            stype = 'ready'
        else:
            status = 'Rotten production'
            stype = 'dead'

        return stype, status

    @commands.command(aliases=['field', 'f'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def farm(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83c\udf3e Shows your or someone's farm field with all growing plants and animals.

        Used to see what are you or someone else growing right now.
        Displays item quantities, statuses and grow timers.

        Additional parameters:
        `member` - some user in your server. (tagged user or user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        cat = False
        catdata = await useracc.get_boosts()
        if catdata:
            cat = boostvalid(catdata['cat'])

        member = member or ctx.author

        fielddata = await useracc.get_field()
        if not fielddata:
            embed = emb.errorembed(f'{member} is not growing anything right now', ctx)
            embed.set_footer(text="Plant and grow items with the %plant command.")
            return await ctx.send(embed=embed)

        crops, animals, trees = {}, {}, {}
        information = []

        if cat:
            information.append("\u2139\ufe0f Farm's items can be harvested even if they are rotten, "
            " thanks to player's cat \ud83d\udc31")
        if client.field_guard:
            information.append("\u2139\ufe0f For a short period of time, farm's items can be harvested "
            "even if they are rotten, thanks to farm guard \ud83d\udee1\ufe0f")

        usedtiles = 0

        for plant in fielddata:
            try:
                item = client.allitems[plant['itemid']]
                usedtiles += plant['fieldsused']

                if item.type == 'crop':
                    crops[plant] = item
                elif item.type == 'animal':
                    animals[plant] = item
                elif item.type == 'tree':
                    trees[plant] = item
            except KeyError:
                raise Exception(f"Could not find item {plant['itemid']}")

        information.append(f"{client.tile} Farm's used space tiles: {usedtiles}/{useracc.tiles}")

        if len(crops) > 0:
            information.append('__**Crops:**__')
            for data, item in crops.items():
                status = self.get_crop_state(item, data['ends'], data['dies'])[1]
                fmt = f"{item.emoji}**{item.name.capitalize()}** x{data['amount']} - {status}"
                information.append(fmt)
        if len(trees) > 0:
            information.append('__**Trees:**__')
            for data, item in trees.items():
                child = item.expandsto
                status = self.get_animal_or_tree_state(data['ends'], data['dies'])[1]
                fmt = f"{item.emoji}**{item.name.capitalize()}** {data['iterations']}.lvl"
                fmt += f" (x{data['amount']}{child.emoji}) - {status}"
                information.append(fmt)
        if len(animals) > 0:
            information.append('__**Animals:**__')
            for data, item in animals.items():
                child = item.expandsto
                status = self.get_animal_or_tree_state(data['ends'], data['dies'])[1]
                fmt = f"{item.emoji}**{item.name.capitalize()}** {data['iterations']}.lvl"
                fmt += f" (x{data['amount']}{child.emoji}) - {status}"
                information.append(fmt)

        try:
            p = Pages(ctx, entries=information, per_page=15, show_entry_count=False)
            p.embed.title = f"{member}'s farm field"
            p.embed.color = 976400
            p.embed.set_footer(
                text="Harvest and collect items with the %harvest command",
                icon_url=ctx.author.avatar_url
            )
            await p.paginate()
        except Exception as e:
            print(e)

    async def check_crops(self, client, useracc, crops, ctx, unique, todelete, cat):
        for data, item in crops.items():
            status = self.get_crop_state(item, data['ends'], data['dies'])[0]
            if status == 'grow1' or status == 'grow2':
                continue
            elif status == 'ready' or status == 'dead' and (cat or client.field_guard):
                amount = data['amount']
                xp = item.xp * amount
                await useracc.give_xp_and_level_up(xp, ctx)
                await useracc.add_item_to_inventory(item, amount)
                if item in unique:
                    unique[item] = (unique[item][0] + amount, unique[item][1] + xp)
                else:
                    unique[item] = (amount, xp)

            todelete.append(data['id'])

    async def check_animals_or_trees(self, client, useracc, crops, ctx, unique, todelete, deaditem, cat):
        for data, item in crops.items():
            status = self.get_animal_or_tree_state(data['ends'], data['dies'])[0]
            if status == 'grow1':
                continue
            elif status == 'ready' or status == 'dead' and (cat or client.field_guard):
                child = item.expandsto
                amount = data['amount']
                xp = child.xp * amount
                
                await useracc.give_xp_and_level_up(xp, ctx)
                await useracc.add_item_to_inventory(child, amount)
                if item in unique:
                    unique[item] = (unique[item][0] + amount, unique[item][1] + xp)
                else:
                    unique[item] = (amount, xp)
            elif status == 'dead':
                deaditem = True

            if data['iterations'] > 1:
                await self.setnextcycle(client, data['id'], item, data)
            else:
                todelete.append(data['id'])

        return deaditem

    async def setnextcycle(self, client, id, item, data):
        now = datetime.now().replace(microsecond=0)
        ends = now + timedelta(seconds=item.grows)
        dies = ends + timedelta(seconds=item.dies)
        child = item.expandsto

        async with client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE planted
                SET ends = $1, dies = $2, iterations = $3,
                amount = $4, robbedfields=0 WHERE id = $5;"""
            await client.db.execute(query, ends, dies, data['iterations'] - 1, child.amount * data['fieldsused'], id)

    @commands.command(aliases=['h'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def harvest(self, ctx):
        """
        \ud83d\udc68\u200d\ud83c\udf3e Collects crops, tree production and animal produced items.

        Note: You can only collect items which are ready or rotten.
        Rotten items are instantly discarded.
        Trees, bushes and animals have multiple collection cycles - after item
        collection they may remain on the field for a few times and grow again.
        (depending on the cycle level)
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        fielddata = await useracc.get_field()
        if not fielddata:
            embed = emb.errorembed("You are not growing anything", ctx)
            embed.set_footer(text="Plant and grow items with the %plant command.")
            return await ctx.send(embed=embed)

        crops, animals, trees, unique = {}, {}, {}, {}
        todelete, deaditem, cat = [], False, False

        for data in fielddata:
            try:
                item = client.allitems[data['itemid']]
                if item.type == 'crop':
                    crops[data] = item
                elif item.type == 'animal':
                    animals[data] = item
                elif item.type == 'tree':
                    trees[data] = item
            except KeyError:
                raise Exception(f"Could not find item {object['itemid']}")

        
        catdata = await useracc.get_boosts()
        if catdata:
            cat = boostvalid(catdata['cat'])

        if crops:
            await self.check_crops(client, useracc, crops, ctx, unique, todelete, cat)
        if animals:
            deaditem = await self.check_animals_or_trees(
                client, useracc, animals, ctx, unique, todelete, deaditem, cat
            )
        if trees:
            deaditem = await self.check_animals_or_trees(
                client, useracc, trees, ctx, unique, todelete, deaditem, cat
            )

        if len(todelete) > 0:
            async with client.db.acquire() as connection:
                async with connection.transaction():
                    query = """DELETE FROM planted WHERE id = $1;"""
                    for item in todelete:
                        await client.db.execute(query, item)

        if not unique.items() and (len(todelete) > 0 or deaditem):
            embed = emb.confirmembed("You removed the rotten production from your field. \u267b\ufe0f", ctx)
            embed.set_footer(text="Next time check your item growing times with the %farm command.")
            await ctx.send(embed=embed)
        elif unique.items():
            information = ''
            for key, value in unique.items():
                if key.type == 'animal' or key.type == 'tree':
                    key = key.expandsto
                information += f"{key.emoji}**{key.name.capitalize()}** x{value[0]} +{value[1]}{client.xp}"
            embed = emb.confirmembed(f"You harvested: {information}", ctx)
            embed.set_footer(text="Items are now moved to your %inventory.")
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed("You don't have anything to harvest or collect yet!", ctx)
            embed.set_footer(text="Check your item growing times with the %farm command.")
            await ctx.send(embed=embed)

    async def plant_crop_seeds(self, client, item, ctx, customamount, amount, useracc):
        itemchild = item.expandsto
        now = datetime.now().replace(microsecond=0)
        ends = now + timedelta(seconds=item.grows)
        dies = ends + timedelta(seconds=item.dies)

        async with client.db.acquire() as connection:
            async with connection.transaction():
                query = """INSERT INTO planted(itemid, userid, amount, ends, dies, fieldsused)
                VALUES($1, $2, $3, $4, $5, $6);"""
                if not customamount:
                    await client.db.execute(
                        query, itemchild.id, useracc.userid, itemchild.amount,
                        ends, dies, 1
                    )
                else:
                    await client.db.execute(
                        query, itemchild.id, useracc.userid, itemchild.amount * amount,
                        ends, dies, amount
                    )

        if not customamount:
            embed = emb.confirmembed(
                f"You planted {item.emoji}{item.name.capitalize()}.\n"
                f"That will grow into {itemchild.amount}x {itemchild.emoji}**{itemchild.name.capitalize()}**\n",
                ctx
                )
        else:
            embed = emb.confirmembed(
                f"You planted {amount}x{item.emoji}{item.name.capitalize()}.\n"
                f"That will grow into {itemchild.amount * amount}x {itemchild.emoji}**{itemchild.name.capitalize()}**\n",
                ctx
            )
        await ctx.send(embed=embed)

    async def plant_animal_or_tree(self, client, item, ctx, customamount, amount, useracc):
        itemchild = item.expandsto
        now = datetime.now().replace(microsecond=0)
        ends = now + timedelta(seconds=item.grows)
        dies = ends + timedelta(seconds=item.dies)

        async with client.db.acquire() as connection:
            async with connection.transaction():
                query = """INSERT INTO planted(itemid, userid, amount, ends, dies, fieldsused, iterations)
                VALUES($1, $2, $3, $4, $5, $6, $7);"""
                if not customamount:
                    await client.db.execute(
                        query, item.id, useracc.userid, itemchild.amount,
                        ends, dies, 1, item.amount
                    )
                else:
                    await client.db.execute(
                        query, item.id, useracc.userid, itemchild.amount * amount,
                        ends, dies, amount, item.amount
                    )

        if not customamount:
            embed = emb.confirmembed(
                f"You started to grow {item.emoji}{item.name.capitalize()}.\n"
                f"Will produce {itemchild.amount}x {itemchild.emoji}**"
                f" {itemchild.name.capitalize()}** ({item.amount} times).\n",
                ctx
                )
        else:
            embed = emb.confirmembed(
                f"You started to grow {amount}x{item.emoji}{item.name.capitalize()}.\n"
                f"Will produce {itemchild.amount * amount}x {itemchild.emoji}**"
                f" {itemchild.name.capitalize()}** ({item.amount} times).\n",
                ctx
            )
        await ctx.send(embed=embed)

    @commands.command(aliases=['p', 'grow', 'g'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def plant(self, ctx, *, search, amount: Optional[int] = 1):
        """
        \ud83c\udf31 Plants seeds and trees, grows animals on your field.

        Parameters:
        `search` - item to lookup for to plant/grow (item's name or ID).
        Additional parameters:
        `amount` - specify how many items to plant/grow (the actual seeds, plants).
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        customamount = False
        try:
            possibleamount = search.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            search = search.rsplit(' ', 1)[0]
            if amount > 0 and amount < 2147483647:
                customamount = True
        except Exception:
            pass

        usedtiles = await useracc.get_used_field_count()

        if not customamount:
            if usedtiles >= useracc.tiles:
                embed = emb.errorembed(
                    "Not enough farm space. Free up your field or expand it with the `%upgrade farm` command.",
                    ctx
                )
                embed.set_footer(text="Harvest your field with the %harvest command")
                return await ctx.send(embed=embed)
        else:
            if usedtiles + amount > useracc.tiles:
                embed = emb.errorembed(
                    "Not enough farm space. Free up your field or expand it with the `%upgrade farm` command.",
                    ctx
                )
                embed.set_footer(text="Harvest your field with the %harvest command")
                return await ctx.send(embed=embed)

        item = await finditem(client, ctx, search)
        if not item:
            return

        itemtype = item.type
        if itemtype in self.growable_items:
            pass
        elif itemtype in self.not_growable_items:
            item = item.madefrom
        else:
            embed = emb.errorembed(f"Sorry, you can't grow {item.emoji}{item.name.capitalize()} on the field!", ctx)
            return await ctx.send(embed=embed)

        inventorydata = await useracc.check_inventory_item(item)
        if not inventorydata:
            embed = emb.errorembed(
                f"You don't have {item.emoji}{item.name.capitalize()} in your warehouse. Buy some items in the shop `%shop`.",
                ctx
            )
            return await ctx.send(embed=embed)

        if customamount:
            if inventorydata['amount'] < amount:
                embed = emb.errorembed(
                    f"You only have {inventorydata['amount']}x{item.emoji}{item.name.capitalize()} in your warehouse",
                    ctx
                )
                return await ctx.send(embed=embed)
            elif not amount > 0 or not amount < 2147483647:
                embed = emb.errorembed(
                    f"Invalid amount!",
                    ctx
                )
                return await ctx.send(embed=embed)

            await useracc.remove_item_from_inventory(item, amount)
        else:
            await useracc.remove_item_from_inventory(item, 1)

        if item.type == 'cropseed':
            await self.plant_crop_seeds(client, item, ctx, customamount, amount, useracc)
        elif item.type == 'animal' or item.type == 'tree':
            await self.plant_animal_or_tree(client, item, ctx, customamount, amount, useracc)

    @commands.command()
    @checks.embed_perms()
    @checks.user_cooldown(3600)
    @checks.avoid_maintenance()
    async def fish(self, ctx):
        """
        \ud83c\udfa3 [Unlocks from level 17] Go fishing!
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        if useracc.level < 17:
            embed = emb.errorembed("\ud83c\udfa3Fishing unlocks from experience level 17.", ctx)
            return await ctx.send(embed=embed)

        FISH_AMOUNT_TYPES = ('none', 'low', 'medium', 'high')
        FISH_AMOUNTS = {'low': 5, 'medium': 10, 'high': 20}

        fish = client.specialitems[600] # ID 600 -> Fish item

        mode = choice(FISH_AMOUNT_TYPES)
        if mode == 'none':
            embed = emb.errorembed("Unlucky! You did not catch any fishes this time. \ud83d\ude14", ctx)
            return await ctx.send(embed=embed)
        amount = randint(1, FISH_AMOUNTS[mode])

        await useracc.give_xp_and_level_up(fish.xp * amount, ctx)
        await useracc.add_item_to_inventory(fish, amount)

        embed = emb.congratzembed(f"Amazing! You cought **{amount} fishes!** \ud83d\udc1f +{fish.xp * amount}{client.xp}", ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Farm(client))

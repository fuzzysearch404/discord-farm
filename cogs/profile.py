import utils.embeds as emb
from random import randint, choice
from typing import Optional
from datetime import datetime
from discord import Embed
from discord.ext import commands
from utils.time import secstotime
from utils.paginator import Pages
from utils.convertors import MemberID
from utils import checks
from classes.item import finditem, crafted_from_to_string
from classes import user as userutils
from classes.boost import boostvalid


class Profile(commands.Cog, name="Profile and Item Statistics"):
    """
    Commands for your profile management and information about game's items.
    """
    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['prof', 'account'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def profile(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83c\udfe0 Shows your or someone's farm information.

        Useful command for your overall progress tracking.
        
        Additional parameters:
        `member` - some user in your server. (username, username#1234, user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        member = member or ctx.author

        query = """SELECT sum(amount) FROM inventory
        WHERE userid = $1;"""
        inventory = await client.db.fetchrow(query, useracc.userid)
        inventory = inventory[0]
        if not inventory:
            inventory = 0

        embed = Embed(title=f"{member}'s profile", colour=7871678)
        embed.add_field(
            name=f'\ud83d\udd31 {useracc.level}. level',
            value=f"{client.xp}{useracc.xp}/{useracc.nextlevelxp}"
        )
        embed.add_field(name=f'{client.gold}Gold', value=useracc.money)
        embed.add_field(name=f'{client.gem}Gems', value=useracc.gems)
        embed.add_field(
            name='\ud83d\udd12Warehouse',
            value=f"\u25aa{inventory} inventory items"
            f"\n\u2139`%inventory {member}`"
        )
        
        query = """SELECT ends, (SELECT SUM(fieldsused) FROM planted WHERE userid = $1) 
        FROM planted WHERE userid = $1 
        ORDER BY ends LIMIT 1;"""
        fielddata = await client.db.fetchrow(query, useracc.userid)
        if not fielddata:
            nearestharvest = '-'
            freetiles = useracc.tiles
        else:
            nearestharvest = fielddata[0]
            if nearestharvest > datetime.now():
                nearestharvest = nearestharvest - datetime.now()
                nearestharvest = secstotime(nearestharvest.total_seconds())
            else:
                nearestharvest = '\u2705'
            freetiles = useracc.tiles - fielddata[1]
        embed.add_field(
            name='\ud83c\udf31Farm',
            value=f"{client.tile}{freetiles}/{useracc.tiles} free tiles"
            f"\n\u23f0Next harvest: {nearestharvest}"
            f"\n\u2139`%farm {member}`"
        )

        if useracc.level > 2:
            query = """SELECT ends FROM factory
            WHERE userid = $1 ORDER BY ends;"""
            nearestprod = await client.db.fetchrow(query, useracc.userid)
            if not nearestprod:
                nearestprod = '-'
            else:
                if nearestprod[0] > datetime.now():
                    nearestprod = nearestprod[0] - datetime.now()
                    nearestprod = secstotime(nearestprod.total_seconds())
                else:
                    nearestprod = '\u2705'
            factorytext = f"\ud83d\udce6Max. production cap.: {useracc.factoryslots}"
            factorytext += f"\n\ud83d\udc68\u200d\ud83c\udfedWorkers: {useracc.factorylevel}/10"
            factorytext += f"\n\u23f0Next production: {nearestprod}"
            factorytext += f"\n\u2139`%factory {member}`"
        else:
            factorytext = "Unlocks at level 3."

        used_trade_slots = await useracc.get_used_store_slot_count()

        embed.add_field(
            name='\ud83c\udfedFactory',
            value=factorytext
        )
        embed.add_field(
            name='\ud83e\udd1dServer trades',
            value=(
                f"Used trading cap.: {used_trade_slots}/{useracc.storeslots}\n"
                f'`%trades {member}`'
            )
        )
        embed.add_field(
            name='\u2b06Boosters',
            value=f'`%boosts {member}`'
        )
        embed.add_field(
            name='\ud83d\ude9cAlliance',
            value='Coming in future updates...'
        )

        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['boosts'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def boosters(self, ctx, *, member: Optional[MemberID] = None):
        """
        \u2b06 Lists your or someone elses boosters.

        Boosters speed up your overall game progression in various ways.

        Additional parameters:
        `member` - some user in your server. (username, username#1234, user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        member = member or ctx.author

        embed = Embed(title=f"\u2b06 {member}'s boosters", color=817407)

        boostdata = await useracc.get_boosts()
        
        if not boostdata:
            embed.description = "\u274c No active boosters"
        else:
            embed.description = ''
            now = datetime.now()
            dog1, dog2, dog3 = boostdata['dog1'], boostdata['dog2'], boostdata['dog3']
            cat = boostdata['cat']
            if boostvalid(dog1):
                deltasecs = (dog1 - now).total_seconds()
                embed.description += f'\ud83d\udc29 Squealer - **{secstotime(deltasecs)}** remaining\n'
            if boostvalid(dog2):
                deltasecs = (dog2 - now).total_seconds()
                embed.description += f'\ud83d\udc36 Saliva Toby - **{secstotime(deltasecs)}** remaining\n'
            if boostvalid(dog3):
                deltasecs = (dog3 - now).total_seconds()
                embed.description += f'\ud83d\udc15 Rex - **{secstotime(deltasecs)}** remaining\n'
            if boostvalid(cat):
                deltasecs = (cat - now).total_seconds()
                embed.description += f'\ud83d\udc31 Leo - **{secstotime(deltasecs)}** remaining\n'
            if embed.description == '':
                embed.description = "\u274c No active boosters"

        await ctx.send(embed=embed)

    @commands.command(aliases=['daily'])
    @checks.embed_perms()
    @checks.user_cooldown(82800)
    @checks.avoid_maintenance()
    async def dailybonus(self, ctx):
        """
        \ud83c\udfb0 Get some items for free every day.
        
        Possible rewards: All items, gold, gems.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        mode = randint(1, 30)
        if mode == 1:
            await useracc.give_gems(1)

            embed = emb.congratzembed(f"You won 1{client.gem}!", ctx)
        elif mode <= 8:
            moneywon = randint(1, useracc.level * 100)
            await useracc.give_money(moneywon)

            embed = emb.congratzembed(f"You won {moneywon}{client.gold}!", ctx)
        else:
            suitableitems = useracc.find_all_items_unlocked()

            item = choice(suitableitems)
            amount = randint(1, 3)

            await useracc.add_item_to_inventory(item, amount)

            embed = emb.congratzembed(
                f"You won {amount}x {item.emoji}{item.name.capitalize()}!",
                ctx
            )
        await ctx.send(embed=embed)

    @commands.command(aliases=['inv', 'warehouse'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def inventory(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83d\udd12 Shows your or someone's farm's inventory.

        Useful to see what items you or someone else owns in their warehouse.

        Additional parameters:
        `member` - some user in your server. (username, username#1234, user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        member = member or ctx.author

        cropseeds, crops, crafteditems, animals, trees, special = {}, {}, {}, {}, {}, {}

        inventory = await useracc.get_inventory()
        if not inventory:
            embed = emb.errorembed(f"{member} has an empty warehouse", ctx)
            return await ctx.send(embed=embed)
        for item, value in inventory.items():
            itemtype = item.type
            if itemtype == 'cropseed':
                cropseeds[item] = value
            elif itemtype == 'crop' or itemtype == 'treeproduct':
                crops[item] = value
            elif itemtype == 'crafteditem' or itemtype == 'animalproduct':
                crafteditems[item] = value
            elif itemtype == 'animal':
                animals[item] = value
            elif itemtype == 'tree':
                trees[item] = value
            elif itemtype == 'special':
                special[item] = value
        await self.embedinventory(ctx, member, cropseeds, crops, crafteditems, animals, trees, special)

    async def embedinventory(self, ctx, member, cropseeds, crops, crafteditems, animals, trees, special):
        items = []

        if cropseeds:
            items.append('__**Crop seeds:**__')
            self.cycle_item_dict(cropseeds, items)
        if trees:
            items.append('__**Trees and bushes:**__')
            self.cycle_item_dict(trees, items)
        if animals:
            items.append('__**Animals:**__')
            self.cycle_item_dict(animals, items)
        if crops:
            items.append('__**Harvested items:**__')
            self.cycle_item_dict(crops, items)
        if crafteditems:
            items.append('__**Produced items:**__')
            self.cycle_item_dict(crafteditems, items)
        if special:
            items.append('__**Special items:**__')
            self.cycle_item_dict(special, items)

        try:
            p = Pages(ctx, entries=items, per_page=16, show_entry_count=False)
            p.embed.title = f"{member}'s warehouse"
            p.embed.color = 7871678
            await p.paginate()
        except Exception as e:
            print(e)

    def cycle_item_dict(self, dic, item_list):
        iter, string = 0, ""
        for key, value in dic.items():
            iter += 1
            string += f'{key.emoji}{key.name.capitalize()} x{value} '
            if iter == 3:
                item_list.append(string)
                iter, string = 0, ""
        if iter > 0:
            item_list.append(string)

    @commands.command(aliases=['all', 'unlocked'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def allitems(self, ctx):
        """
        \ud83d\udd0d Shows all unlocked items for your level.

        Useful to check what items you can grow or make.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        texts = []
        items = useracc.find_all_items_unlocked()

        for item in items:
            item = f"ID:{item.id} {item.emoji}{item.name.capitalize()}"
            texts.append(item)
        texts.append("\u2139Get detailed information about an item - `%item ID or name`")
        try:
            p = Pages(ctx, entries=texts, per_page=16, show_entry_count=False)
            p.embed.title = 'Unlocked items for your level:'
            p.embed.color = 846046
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command(aliases=['i', 'info'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def item(self, ctx, *, search):
        """
        \ud83c\udf7f Shows detailed information about an item.

        This command is useful to get various information about any
        item in the game e.g. prices, growing times, xp rewards etc.

        Parameters:
        `search` - item to lookup for. (item's name or ID)
        """
        item = await finditem(self.client, ctx, search)
        if not item:
            return

        itemtype = item.type

        if itemtype == 'cropseed':
            await self.cropseedinfo(ctx, item)
        elif itemtype == 'crop' or itemtype == 'treeproduct':
            await self.cropinfo(ctx, item)
        elif itemtype == 'crafteditem':
            await self.craftediteminfo(ctx, item)
        elif itemtype == 'animalproduct':
            await self.animalproductinfo(ctx, item)
        elif itemtype == 'animal':
            await self.animalinfo(ctx, item)
        elif itemtype == 'tree':
            await self.treeinfo(ctx, item)
        elif itemtype == 'special':
            await self.specialinfo(ctx, item)

    async def cropseedinfo(self, ctx, cropseed):
        client = self.client
        crop = cropseed.expandsto

        embed = Embed(
            title=f'{cropseed.name.capitalize()} {cropseed.emoji}',
            description=f'\ud83c\udf31**Seed ID:** {cropseed.id} \ud83c\udf3e**Crop ID:** {crop.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=crop.level)
        embed.add_field(name=f'{client.xp}When harvested gives', value=f'{crop.xp} xp/per item.')
        embed.add_field(name='\ud83d\udd70Sprouting, grows', value=secstotime(cropseed.grows))
        embed.add_field(name='\ud83d\udd70Harvestable for', value=secstotime(cropseed.dies))
        embed.add_field(name='\ud83d\udcb0Seeds price', value=f'{cropseed.gold_cost}{client.gold}')
        embed.add_field(name=f'{crop.emoji}Grows into', value=f'`%item {crop.name}`')
        embed.add_field(name='\u2696Harvest volume', value=f'{crop.amount} items')
        embed.add_field(name=f'{cropseed.emoji}Grow', value=f'`%plant {cropseed.name}`')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def cropinfo(self, ctx, crop):
        client = self.client
        cropseed = crop.madefrom

        embed = Embed(
            title=f'{crop.name.capitalize()} {crop.emoji}',
            description=f'\ud83c\udf3e**Vegetable/Fruit ID:** {crop.id} \ud83c\udf31**Seed/Tree/Bush ID:** {cropseed.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=crop.level)
        embed.add_field(name=f'{cropseed.emoji}Grows from', value=f'`%item {cropseed.name}`')
        embed.add_field(name='\ud83d\uded2Market price', value=f'{crop.minprice} - {crop.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{crop.marketprice}{client.gold}/item.\n')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def craftediteminfo(self, ctx, item):
        client = self.client

        embed = Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Product ID:** {item.id}',
            colour=851836
        )

        craftedfrom = crafted_from_to_string(client, item.craftedfrom)

        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name=f'{client.xp}When produced gives', value=f'{item.xp} xp/item.')
        embed.add_field(name='\ud83d\udcdcRequired materials', value=craftedfrom)
        embed.add_field(name='\ud83d\udd70Production duration', value=secstotime(item.time))
        embed.add_field(name='\ud83d\uded2Market price', value=f'{item.minprice} - {item.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{item.marketprice}{client.gold}/item.\n')
        embed.add_field(name=f'{item.emoji}Produce', value=f'`%make {item.name}`')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def animalproductinfo(self, ctx, item):
        client = self.client
        animal = item.madefrom

        embed = Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Product ID:** {item.id}',
            colour=851836
        )

        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name=f'{animal.emoji}Collectable from', value=f'`%item {animal.name}`')
        embed.add_field(name='\ud83d\uded2Market price', value=f'{item.minprice} - {item.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{item.marketprice}{client.gold}/item.\n')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def animalinfo(self, ctx, item):
        client = self.client
        product = item.expandsto

        embed = Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'{item.emoji}**Animal ID:** {item.id} {product.emoji}**Product ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\u23e9Produces', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}When produced gives', value=f'{product.xp} xp/per item')
        embed.add_field(name='\ud83d\udd70Grows', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Collectable', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Price', value=f'{item.gold_cost}{client.gold}')
        embed.add_field(name='\u2696Collection cycles', value=f'{item.amount}')
        embed.add_field(name=f'{item.emoji}Grow', value=f'`%grow {item.name}`')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def treeinfo(self, ctx, item):
        client = self.client
        product = item.expandsto

        embed = Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83c\udf33**Tree/Bush ID:** {item.id} {product.emoji}**Product ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\u23e9Produces (per cycle)', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}When harvested gives', value=f'{product.xp} xp/per item')
        embed.add_field(name='\ud83d\udd70Grows', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Is harvestable', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Plant price', value=f'{item.gold_cost}{client.gold}')
        embed.add_field(name='\u2696Harvest cycles', value=f'{item.amount}')
        embed.add_field(name=f'{item.emoji}Plant', value=f'`%plant {item.name}`')

        embed.set_thumbnail(url=product.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def specialinfo(self, ctx, item):
        client = self.client

        embed = Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'{item.emoji}**Item ID:** {item.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\ud83d\uded2Market price', value=f'{item.minprice} - {item.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{item.marketprice}{client.gold}/item.\n')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Profile(client))
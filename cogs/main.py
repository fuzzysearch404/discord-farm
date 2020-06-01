import discord
import asyncio
import utils.embeds as emb
from random import randint, choice
from utils import usertools
from utils import time
from typing import Optional
from datetime import datetime
from discord.ext import commands
from utils.time import secstotime
from utils.item import finditem, madefromtostring
from utils.paginator import Pages
from utils.convertors import MemberID


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @commands.command(aliases=['daily'])
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def dailybonus(self, ctx):
        client = self.client
        suitableitems = []

        profile = await usertools.getprofile(client, ctx.author)
        level = usertools.getlevel(profile['xp'])[0]

        mode = randint(1, 30)
        if mode == 1:
            gemswon = randint(1, 3)
            await usertools.givegems(client, ctx.author, gemswon)

            embed = emb.congratzembed(f"You won {gemswon} {client.gem}", ctx)
        elif mode <= 8:
            moneywon = randint(1, level * 300)
            await usertools.givemoney(client, ctx.author, moneywon)

            embed = emb.congratzembed(f"You won {moneywon} {client.gold}", ctx)
        else:
            for item in client.allitems.values():
                if item.level <= level:
                    suitableitems.append(item)

            item = choice(suitableitems)
            amount = randint(1, 4)

            await usertools.additemtoinventory(client, ctx.author, item, amount)

            embed = emb.congratzembed(
                f"You won {amount}x{item.emoji}{item.name.capitalize()}",
                ctx
            )
        await ctx.send(embed=embed)

    @dailybonus.error
    async def dailybonus_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = time.secstotime(error.retry_after)
            embed = emb.errorembed(f"Next daily bonus in \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    @commands.command(aliases=['profils', 'prof'])
    async def profile(self, ctx, *, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        userprofile = await usertools.getprofile(client, member)
        if not userprofile:
            embed = emb.errorembed(f"{member} does not have a game account", ctx)
            return await ctx.send(embed=embed)

        genuserid = usertools.generategameuserid(member)

        query = """SELECT sum(amount) FROM inventory
        WHERE userid = $1;"""
        inventory = await client.db.fetchrow(query, genuserid)
        if not inventory[0]:
            inventory = 0
        else:
            inventory = inventory[0]

        level, lvlmax = usertools.getlevel(userprofile['xp'])
        embed = discord.Embed(title=f"{member}'s farm", colour=10521800)
        embed.add_field(
            name=f'\ud83d\udd31 {level}. level',
            value=f"{client.xp}{userprofile['xp']}/{lvlmax}"
        )
        embed.add_field(name=f'{client.gold}Gold', value=userprofile['money'])
        embed.add_field(name=f'{client.gem}Gems', value=userprofile['gems'])
        embed.add_field(
            name='\ud83d\udd12Warehouse',
            value=f"\u25aa{inventory} inventory items"
            f"\n\u2139`%inventory {member}`"
        )
        query = """SELECT ends FROM planted
        WHERE userid = $1 ORDER BY ends;"""
        nearestharvest = await client.db.fetchrow(query, genuserid)
        if not nearestharvest:
            nearestharvest = '-'
        else:
            if nearestharvest[0] > datetime.now():
                nearestharvest = nearestharvest[0] - datetime.now()
                nearestharvest = secstotime(nearestharvest.seconds)
            else:
                nearestharvest = '\u2705'
        embed.add_field(
            name='\ud83c\udf31Field',
            value=f"{client.tile}{userprofile['tiles'] - userprofile['usedtiles']}/{userprofile['tiles']} free tiles"
            f"\n\u23f0Next harvest: {nearestharvest}"
            f"\n\u2139`%field {member}`"
        )

        if level > 2:
            query = """SELECT ends FROM factory
            WHERE userid = $1 ORDER BY ends;"""
            nearestprod = await client.db.fetchrow(query, genuserid)
            if not nearestprod:
                nearestprod = '-'
            else:
                if nearestprod[0] > datetime.now():
                    nearestprod = nearestprod[0] - datetime.now()
                    nearestprod = secstotime(nearestprod.seconds)
                else:
                    nearestprod = '\u2705'
            factorytext = f"\ud83d\udce6Max. production cap.: {userprofile['factoryslots']}"
            factorytext += f"\n\u23f0Next production: {nearestprod}"
            factorytext += f"\n\u2139`%factory {member}`"
        else:
            factorytext = "Avaiable from level 3."
        embed.add_field(
            name='\ud83d\udecdStore',
            value=f'`%store {member}`'
        )
        embed.add_field(
            name='\u2b06Boosters',
            value=f'`%boosts {member}`'
        )
        embed.add_field(
            name='\ud83c\udfedFactory',
            value=factorytext
        )

        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['inv'])
    async def inventory(self, ctx, *, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        cropseeds, crops, crafteditems, animals, trees = {}, {}, {}, {}, {}

        inventory = await usertools.getinventory(client, member)
        if not inventory:
            embed = emb.errorembed(f"{member} has empty warehouse", ctx)
            return await ctx.send(embed=embed)
        for item, value in inventory.items():
            if item.type == 'cropseed':
                cropseeds[item] = value
            elif item.type == 'crop':
                crops[item] = value
            elif item.type == 'crafteditem' or item.type == 'item':
                crafteditems[item] = value
            elif item.type == 'animal':
                animals[item] = value
            elif item.type == 'tree':
                trees[item] = value
        await self.embedinventory(ctx, member, cropseeds, crops, crafteditems, animals, trees)

    async def embedinventory(self, ctx, member, cropseeds, crops, crafteditems, animals, trees):
        items = []

        if cropseeds:
            items.append('__**Crop seeds:**__')
            self.cycledict(cropseeds, items)
        if trees:
            items.append('__**Trees:**__')
            self.cycledict(trees, items)
        if crops:
            items.append('__**Harvest items:**__')
            self.cycledict(crops, items)
        if crafteditems:
            items.append('__**Production items:**__')
            self.cycledict(crafteditems, items)
        if animals:
            items.append('__**Animals:**__')
            self.cycledict(animals, items)

        try:
            p = Pages(ctx, entries=items, per_page=10, show_entry_count=False)
            p.embed.title = f"{member}'s warehouse"
            p.embed.color = 10521800
            await p.paginate()
        except Exception as e:
            print(e)

    def cycledict(self, dic, list):
        iter, string = 0, ""
        for key, value in dic.items():
            iter += 1
            string += f'{key.emoji}**{key.name.capitalize()}** x{value} '
            if iter == 3:
                list.append(string)
                iter, string = 0, ""
        if iter > 0:
            list.append(string)

    @commands.command(aliases=['i'])
    async def info(self, ctx, *, possibleitem):
        item = await finditem(self.client, ctx, possibleitem)
        if not item:
            return

        if item.type == 'cropseed':
            await self.cropseedinfo(ctx, item)
        elif item.type == 'crop':
            await self.cropinfo(ctx, item)
        elif item.type == 'crafteditem':
            await self.craftediteminfo(ctx, item)
        elif item.type == 'item':
            await self.iteminfo(ctx, item)
        elif item.type == 'animal':
            await self.animalinfo(ctx, item)
        elif item.type == 'tree':
            await self.treeinfo(ctx, item)

    async def cropseedinfo(self, ctx, cropseed):
        client = self.client
        crop = cropseed.getchild(client)

        embed = discord.Embed(
            title=f'{cropseed.name.capitalize()} {cropseed.emoji}',
            description=f'\ud83c\udf31**Seed ID:** {cropseed.id} \ud83c\udf3e**Crop ID:** {crop.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=crop.level)
        embed.add_field(name=f'{client.xp}When harvested gives', value=f'{crop.xp} xp/per item.')
        embed.add_field(name='\ud83d\udd70Sprouting, grows', value=secstotime(cropseed.grows))
        embed.add_field(name='\ud83d\udd70Is harvestable', value=secstotime(cropseed.dies))
        embed.add_field(name='\ud83d\udcb0Seeds price', value=f'{cropseed.cost}{client.gold} or {cropseed.scost}{client.gem}')
        embed.add_field(name='\u2696Harvest size', value=f'{cropseed.amount} items.')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def cropinfo(self, ctx, crop):
        client = self.client
        cropseed = crop.getparent(client)

        embed = discord.Embed(
            title=f'{crop.name.capitalize()} {crop.emoji}',
            description=f'\ud83c\udf3e**Vegetable/Fruit ID:** {crop.id} \ud83c\udf31**Seed/Tree ID:** {cropseed.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=crop.level)
        embed.add_field(name='\ud83d\uded2Market price', value=f'{crop.minprice} - {crop.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{crop.marketprice}{client.gold}/item.\n')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def craftediteminfo(self, ctx, item):
        client = self.client

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Product ID:** {item.id}',
            colour=851836
        )

        madefrom = madefromtostring(client, item.madefrom)

        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name=f'{client.xp}When produced gives', value=f'{item.xp} xp/item.')
        embed.add_field(name='\ud83d\udcdcNeeded materials', value=madefrom)
        embed.add_field(name='\ud83d\udd70Production duration', value=secstotime(item.time))
        embed.add_field(name='\ud83d\uded2Market price', value=f'{item.minprice} - {item.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{item.marketprice}{client.gold}/item.\n')
        embed.add_field(name='\ud83c\udfedProduce', value=f'`%make {item.name}`')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def iteminfo(self, ctx, item):
        client = self.client

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Product ID:** {item.id}',
            colour=851836
        )

        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\ud83d\uded2Market price', value=f'{item.minprice} - {item.maxprice} /item. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Current market price', value=f'{item.marketprice}{client.gold}/item.\n')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def animalinfo(self, ctx, item):
        client = self.client
        product = item.getchild(client)

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'{item.emoji}**Animal ID:** {item.id} {product.emoji}**Product ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\u23e9Produces', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}When produced gives', value=f'{item.xp * product.amount} xp')
        embed.add_field(name='\ud83d\udd70Grows', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Collectable', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Price', value=f'{item.cost}{client.gold} or {item.scost}{client.gem}')
        embed.add_field(name='\u2696Collection cycles', value=f'{item.amount}')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def treeinfo(self, ctx, item):
        client = self.client
        product = item.getchild(client)

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83c\udf33**Tree ID:** {item.id} {product.emoji}**Product ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Required level', value=item.level)
        embed.add_field(name='\u23e9Produces', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}When produced gives', value=f'{item.xp * product.amount} xp')
        embed.add_field(name='\ud83d\udd70Grows', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Is harvestable', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Tree price', value=f'{item.cost}{client.gold} or {item.scost}{client.gem}')
        embed.add_field(name='\u2696Harvest cycles', value=f'{item.amount}')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['all'])
    async def allitems(self, ctx):
        items, texts = [], []
        client = self.client

        profile = await usertools.getprofile(client, ctx.author)
        level = usertools.getlevel(profile['xp'])[0]

        for item in client.allitems.values():
            if item.level <= level:
                items.append(item)

        for item in items:
            item = f"ID:{item.id} {item.emoji}{item.name.capitalize()}"
            texts.append(item)
        texts.append("\u2139Information about item - `%info ID or item name`")
        try:
            p = Pages(ctx, entries=texts, per_page=12, show_entry_count=False)
            p.embed.title = 'Unlocked items:'
            p.embed.color = 846046
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command()
    async def resetacc(self, ctx):
        embed = emb.errorembed(
            "Do you really want to delete your account? This **cannot** be undone!!",
            ctx
        )
        message = await ctx.send(embed=embed)
        await message.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705'

        try:
            reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return message.clear_reactions()

        await usertools.deleteacc(self.client, ctx.author)
        embed = emb.confirmembed('Your account is deleted. If you want, you can start all over again with `%start`', ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Main(client))

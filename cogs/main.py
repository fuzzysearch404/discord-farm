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

        for item in client.allitems.values():
            if item.level <= level:
                suitableitems.append(item)

        item = choice(suitableitems)
        if item.type == 'animal' or item.type == 'tree' or item.type == 'crafteditem':
            amount = randint(1, int(level * 1.2))
        else:
            amount = randint(1, level * 3)

        await usertools.additemtoinventory(client, ctx.author, item, amount)

        embed = emb.congratzembed(
            f"Tu laimēji {amount}x{item.emoji}{item.name2.capitalize()}",
            ctx
        )
        await ctx.send(embed=embed)

    @dailybonus.error
    async def dailybonus_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = time.secstotime(error.retry_after)
            embed = emb.errorembed(f"Nākošais dienas bonuss pēc \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    @commands.command(aliases=['profils'])
    async def profile(self, ctx, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        userprofile = await usertools.getprofile(client, member)
        if not userprofile:
            embed = emb.errorembed(f"{member} nav spēles profila", ctx)
            return await ctx.send(embed=embed)

        query = """SELECT sum(amount) FROM inventory
        WHERE userid = $1;"""
        inventory = await client.db.fetchrow(query, usertools.generategameuserid(member))
        if not inventory[0]:
            inventory = 0
        else:
            inventory = inventory[0]

        level, lvlmax = usertools.getlevel(userprofile['xp'])
        embed = discord.Embed(title=f'{member} ferma', colour=10521800)
        embed.add_field(
            name=f'\ud83d\udd31 {level}. līmenis',
            value=f"{client.xp}{userprofile['xp']}/{lvlmax}"
        )
        embed.add_field(name=f'{client.gold}Zelts', value=userprofile['money'])
        embed.add_field(name=f'{client.gem}Supernaudas', value=userprofile['gems'])
        embed.add_field(
            name='\ud83d\udd12Noliktava',
            value=f"\u25aa{inventory} lietas"
            f"\n\u2139`%inventory {member}`"
        )
        query = """SELECT ends FROM planted
        WHERE userid = $1 ORDER BY ends;"""
        nearestharvest = await client.db.fetchrow(query, usertools.generategameuserid(member))
        if not nearestharvest:
            nearestharvest = '-'
        else:
            if nearestharvest[0] > datetime.now():
                nearestharvest = nearestharvest[0] - datetime.now()
                nearestharvest = secstotime(nearestharvest.seconds)
            else:
                nearestharvest = '\u2705'
        embed.add_field(
            name='\ud83c\udf31Lauks',
            value=f"{client.tile}{userprofile['tiles'] - userprofile['usedtiles']}/{userprofile['tiles']} brīva platība"
            f"\n\u23f0Nākošā raža: {nearestharvest}"
            f"\n\u2139`%field {member}`"
        )

        if level > 2:
            query = """SELECT ends FROM factory
            WHERE userid = $1 ORDER BY ends;"""
            nearestprod = await client.db.fetchrow(query, usertools.generategameuserid(member))
            if not nearestprod:
                nearestprod = '-'
            else:
                if nearestprod[0] > datetime.now():
                    nearestprod = nearestprod[0] - datetime.now()
                    nearestprod = secstotime(nearestprod.seconds)
                else:
                    nearestprod = '\u2705'
            factorytext = f"\ud83d\udce6Max. ražošanas apjoms: {userprofile['factoryslots']}"
            factorytext += f"\n\u23f0Nākošā produkcija: {nearestprod}"
            factorytext += f"\n\u2139`%factory {member}`"
        else:
            factorytext = "Pieejams no 3.līmeņa"
        embed.add_field(
            name='\ud83c\udfedRūpnīca',
            value=factorytext
        )
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['inv'])
    async def inventory(self, ctx, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        cropseeds, crops, crafteditems, animals, trees = {}, {}, {}, {}, {}

        inventory = await usertools.getinventory(client, member)
        if not inventory:
            embed = emb.errorembed(f"{member} nav nekā noliktavā", ctx)
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
            items.append('__**Augu sēklas:**__')
            self.cycledict(cropseeds, items)
        if trees:
            items.append('__**Koki:**__')
            self.cycledict(trees, items)
        if crops:
            items.append('__**Raža:**__')
            self.cycledict(crops, items)
        if crafteditems:
            items.append('__**Produkti:**__')
            self.cycledict(crafteditems, items)
        if animals:
            items.append('__**Dzīvnieki:**__')
            self.cycledict(animals, items)

        try:
            p = Pages(ctx, entries=items, per_page=10, show_entry_count=False)
            p.embed.title = f'{member} noliktava'
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
            description=f'\ud83c\udf31**Sēklu ID:** {cropseed.id} \ud83c\udf3e**Auga ID:** {crop.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=crop.level)
        embed.add_field(name=f'{client.xp}Novācot dod', value=f'{crop.xp} xp/gab.')
        embed.add_field(name='\ud83d\udd70Dīgst, aug', value=secstotime(cropseed.grows))
        embed.add_field(name='\ud83d\udd70Novācams', value=secstotime(cropseed.dies))
        embed.add_field(name='\ud83d\udcb0Sēklu cena', value=f'{cropseed.cost}{client.gold} vai {cropseed.scost}{client.gem}')
        embed.add_field(name='\u2696Ražas apjoms', value=f'{cropseed.amount} gab.')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def cropinfo(self, ctx, crop):
        client = self.client
        cropseed = crop.getparent(client)

        embed = discord.Embed(
            title=f'{crop.name.capitalize()} {crop.emoji}',
            description=f'\ud83c\udf3e**Dārzeņa/Augļa ID:** {crop.id} \ud83c\udf31**Sēklu/Koka ID:** {cropseed.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=crop.level)
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{crop.minprice} - {crop.maxprice} /gab. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value=f'{crop.marketprice}{client.gold}/gab.\n')

        embed.set_thumbnail(url=crop.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def craftediteminfo(self, ctx, item):
        client = self.client

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Produkta ID:** {item.id}',
            colour=851836
        )

        madefrom = madefromtostring(client, item.madefrom)

        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=item.level)
        embed.add_field(name=f'{client.xp}Ražojot dod', value=f'{item.xp} xp/gab.')
        embed.add_field(name='\ud83d\udcdcNepieciešamie materiāli', value=madefrom)
        embed.add_field(name='\ud83d\udd70Ražošanas laiks', value=secstotime(item.time))
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{item.minprice} - {item.maxprice} /gab. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value=f'{item.marketprice}{client.gold}/gab.\n')
        embed.add_field(name='\ud83c\udfedRažot', value=f'`%make {item.name}`')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def iteminfo(self, ctx, item):
        client = self.client

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83d\udce6**Produkta ID:** {item.id}',
            colour=851836
        )

        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=item.level)
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{item.minprice} - {item.maxprice} /gab. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value=f'{item.marketprice}{client.gold}/gab.\n')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def animalinfo(self, ctx, item):
        client = self.client
        product = item.getchild(client)

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'{item.emoji}**Dzīvnieka ID:** {item.id} {product.emoji}**Produkta ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=item.level)
        embed.add_field(name='\u23e9Izaudzē produktu', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}Novācot dod', value=f'{item.xp * product.amount} xp')
        embed.add_field(name='\ud83d\udd70Aug', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Novācams', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Dzīvnieka cena', value=f'{item.cost}{client.gold} vai {item.scost}{client.gem}')
        embed.add_field(name='\u2696Novākšanas cikli', value=f'{item.amount}')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    async def treeinfo(self, ctx, item):
        client = self.client
        product = item.getchild(client)

        embed = discord.Embed(
            title=f'{item.name.capitalize()} {item.emoji}',
            description=f'\ud83c\udf33**Koka ID:** {item.id} {product.emoji}**Produkta ID:** {product.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=item.level)
        embed.add_field(name='\u23e9Izaudzē produktu', value=f"**{product.amount}x** {product.emoji}{product.name.capitalize()}")
        embed.add_field(name=f'{client.xp}Novācot dod', value=f'{item.xp * product.amount} xp')
        embed.add_field(name='\ud83d\udd70Aug', value=secstotime(item.grows))
        embed.add_field(name='\ud83d\udd70Novācams', value=secstotime(item.dies))
        embed.add_field(name='\ud83d\udcb0Koka cena', value=f'{item.cost}{client.gold} vai {item.scost}{client.gem}')
        embed.add_field(name='\u2696Novākšanas cikli', value=f'{item.amount}')

        embed.set_thumbnail(url=item.img)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def resetacc(self, ctx):
        embed = emb.errorembed(
            "Vai tiešām izdzēst profilu? Tiks dzēsti pilnīgi **VISI** tavi dati!!",
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
        embed = emb.confirmembed('Tavs profils ir dzēsts. Lai sāktu spēli no jauna, lieto `%start`', ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Main(client))

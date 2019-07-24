import discord
import utils.embeds as emb
from utils import usertools
from typing import Optional
from datetime import datetime
from discord.ext import commands
from utils.time import secstotime
from utils.item import finditem
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
        return userid['userid'] == ctx.author.id

    @commands.command()
    async def profile(self, ctx, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        userprofile = await usertools.getprofile(client, member)
        if not userprofile:
            embed = emb.errorembed("Šim lietotājam nav spēles profila")
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
            value=f"""\u25aa{inventory} lietas
            \u2139`%inventory {member}`"""
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
            value=f"""{client.tile}{userprofile['tiles'] - userprofile['usedtiles']}/{userprofile['tiles']} brīva platība
            \u23f0Nākošā raža: {nearestharvest}
            \u2139`%field {member}`"""
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def inventory(self, ctx, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client
        cropseeds = {}
        crops = {}
        inventory = await usertools.getinventory(client, member)
        if not inventory:
            embed = emb.errorembed("Šim lietotājam nav nekā noliktavā")
            return await ctx.send(embed=embed)
        for item, value in inventory.items():
            if item.type == 'cropseed':
                cropseeds[item] = value
            if item.type == 'crop':
                crops[item] = value
        await self.embedinventory(ctx, member, cropseeds, crops)

    async def embedinventory(self, ctx, member, cropseeds, crops):
        items = []

        if cropseeds:
            items.append('__**Augu sēklas:**__')
            self.cycledict(cropseeds, items)
        if crops:
            items.append('__**Raža:**__')
            self.cycledict(crops, items)

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
            string += f'{key.emoji}**{key.name2.capitalize()}** x{value} '
            if iter == 3:
                list.append(string)
                iter, string = 0, ""
        if iter > 0:
            list.append(string)

    @commands.command()
    async def info(self, ctx, *, possibleitem):
        item = await finditem(self.client, ctx, possibleitem)
        if not item:
            return

        if item.type == 'cropseed':
            await self.cropseedinfo(ctx, item)
        elif item.type == 'crop':
            await self.cropinfo(ctx, item)

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
        await ctx.send(embed=embed)

    async def cropinfo(self, ctx, crop):
        client = self.client
        cropseed = crop.getparent(client)

        embed = discord.Embed(
            title=f'{crop.name.capitalize()} {crop.emoji}',
            description=f'\ud83c\udf3e**Auga ID:** {crop.id} \ud83c\udf31**Sēklu ID:** {cropseed.id}',
            colour=851836
        )
        embed.add_field(name='\ud83d\udd31Nepiciešamais līmenis', value=crop.level)
        embed.add_field(name='\ud83d\uded2Tirgus cena', value=f'{crop.minprice} - {crop.maxprice} /gab. {client.gold}')
        embed.add_field(name='\ud83d\udcc8Pašreizējā tirgus cena', value=f'{crop.marketprice}{client.gold}/gab.\n')

        embed.set_thumbnail(url=crop.img)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Main(client))

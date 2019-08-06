from discord import Embed
from discord.ext import commands
from datetime import datetime
from typing import Optional
from random import randint, choice
from utils import usertools
from utils import embeds as emb
from utils.time import secstotime
from utils.paginator import Pages
from utils.usertools import splitgameuserid
from utils.convertors import MemberID


class Heists(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def scout(self, ctx):
        client = self.client

        query = """SELECT * FROM planted
        WHERE ends < $1 AND dies > $1
        AND NOT robbed AND guildid = $2;"""

        data = await client.db.fetch(query, datetime.now(), ctx.guild.id)

        if len(data) < 1:
            embed = emb.errorembed("Šajā apkārtnē nav paretināmu lauku", ctx)
            return await ctx.send(embed=embed)

        users, information = [], []
        for item in data:
            userid = item['userid']
            if userid not in users:
                users.append(userid)

        for user in users:
            userid = splitgameuserid(user, ctx)
            user = ctx.guild.get_member(userid)
            if not user:
                continue
            information.append(f"{client.tile} `%heist {user}`")

        try:
            p = Pages(ctx, entries=information, per_page=10, show_entry_count=False)
            p.embed.title = 'Retināmie lauki'
            p.embed.color = 8052050
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command(aliases=['rob'])
    @commands.cooldown(1, 900, commands.BucketType.user)
    async def heist(self, ctx, *, member: MemberID):
        if not member or member == ctx.author:
            return

        client = self.client

        query = """SELECT * FROM planted
        WHERE ends < $1 AND dies > $1
        AND NOT robbed AND userid = $2;"""

        field = await client.db.fetch(query, datetime.now(), usertools.generategameuserid(member))
        if not field:
            embed = emb.errorembed("Šim spēlētājam nav ko paretināt.", ctx)
            return await ctx.send(embed=embed)

        query = """SELECT * FROM boosts WHERE userid = $1 LIMIT 1;"""
        boostdata = await client.db.fetchrow(query, usertools.generategameuserid(member))

        dog2, dog1 = False, False
        if boostdata:

            if boostdata['dog3']:
                if self.boostvalid(boostdata['dog3']):
                    embed = emb.errorembed("Šo teritoriju apsargā MILZĪGS suns!", ctx)
                    return await ctx.send(embed=embed)

            if boostdata['dog2']:
                if self.boostvalid(boostdata['dog2']):
                    dog2 = True

            if boostdata['dog1']:
                if self.boostvalid(boostdata['dog1']):
                    dog1 = True

        if dog2:
            chance = 3
        elif dog1:
            chance = 6
        else:
            chance = False

        await self.trytoheist(ctx, field, member, chance)

    async def trytoheist(self, ctx, field, member, chance):
        client = self.client
        win, cought = [], False
        for _ in range(len(field)):
            data = choice(field)
            field.remove(data)
            if chance:
                number = randint(1, chance)
                if number == 1:
                    cought = True
                    break
                else:
                    win.append(data)
            else:
                win.append(data)

        wonitems = {}
        connection = await client.db.acquire()
        async with connection.transaction():
            for item in win:
                cnt, iter = item['amount'], None
                amount = cnt - int(cnt * 0.2)
                witem = client.allitems[item['itemid']]
                try:
                    if witem.type == 'tree' or witem.type == 'animal':
                        iter = item['iterations']
                        witem = witem.getchild(client)
                    if iter:
                        wonitems[witem] += (cnt * iter) - (amount * iter)
                    else:
                        wonitems[witem] += cnt - amount
                except KeyError:
                    if iter:
                        wonitems[witem] = (cnt * iter) - (amount * iter)
                    else:
                        wonitems[witem] = cnt - amount

                query = """UPDATE planted SET amount = $1,
                robbed = TRUE WHERE id = $2"""
                await client.db.execute(query, amount, item['id'])
        await client.db.release(connection)

        for item, amnt in wonitems.items():
            await usertools.additemtoinventory(client, ctx.author, item, amnt)

        information = ''
        for key, value in wonitems.items():
            information += f"{key.emoji}**{key.name2.capitalize()}** x{value}"

        try:
            if len(information) > 0:
                embed = emb.errorembed(f"{ctx.author} paretināja tavu lauku: {information}", ctx, pm=True)
                await member.send(embed=embed)
        except Exception:
            pass

        if cought and not len(win) > 0:
            embed = emb.errorembed("Tevi noķēra suns! :(", ctx)
            return await ctx.send(embed=embed)
        elif cought:
            embed = emb.confirmembed(f"Tevi noķēra suns, bet tu paspēji paņemt: {information}", ctx)
            return await ctx.send(embed=embed)
        else:
            embed = emb.congratzembed(f"Tu paņēmi mazliet no visa: {information}", ctx)
            return await ctx.send(embed=embed)

    @heist.error
    async def offer_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = secstotime(error.retry_after)
            embed = emb.errorembed(f"Tev pakaļ dzenās kaimiņu suns vēl \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    @scout.error
    async def scout_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = secstotime(error.retry_after)
            embed = emb.errorembed(f"Tavs spiegs \ud83d\udd75 ir pusceļā mājās \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    def boostvalid(self, date):
        if not date:
            return False
        return date > datetime.now()

    @commands.command(aliases=['boosters', 'boost'])
    async def boosts(self, ctx, *, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client

        embed = Embed(title=f'\u2b06{member} boosteri', color=817407)

        query = """SELECT * FROM boosts WHERE userid = $1;"""
        data = await client.db.fetchrow(query, usertools.generategameuserid(member))
        if not data:
            embed.description = "Nav aktīvu boosteru"
        else:
            embed.description = ''
            dog1 = data['dog1']
            if self.boostvalid(dog1):
                embed.description += f'\ud83d\udc29 Līdz `{dog1}`'
            dog2 = data['dog2']
            if self.boostvalid(dog2):
                embed.description += f'\ud83d\udc36 Līdz `{dog2}`'
            dog3 = data['dog3']
            if self.boostvalid(dog3):
                embed.description += f'\ud83d\udc15 Līdz `{dog3}`'
            if not dog1 and dog2 and dog3:
                embed.description = "Nav aktīvu boosteru"

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Heists(client))

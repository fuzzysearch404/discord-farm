from discord import Embed
from discord.ext import commands
from datetime import datetime
from typing import Optional
from random import randint, choice
from utils import usertools
from utils import embeds as emb
from utils.boosttools import boostvalid
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
            embed = emb.errorembed("There is nothing to steal in this area right now", ctx)
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
            p.embed.title = 'Robbable farms'
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
            embed = emb.errorembed("This player has nothing to steal from.", ctx)
            return await ctx.send(embed=embed)

        query = """SELECT * FROM boosts WHERE userid = $1 LIMIT 1;"""
        boostdata = await client.db.fetchrow(query, usertools.generategameuserid(member))

        dog2, dog1 = False, False
        if boostdata:

            if boostdata['dog3']:
                if boostvalid(boostdata['dog3']):
                    embed = emb.errorembed("This farm is being guarded by a HUGE dog!", ctx)
                    return await ctx.send(embed=embed)

            if boostdata['dog2']:
                if boostvalid(boostdata['dog2']):
                    dog2 = True

            if boostdata['dog1']:
                if boostvalid(boostdata['dog1']):
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
            information += f"{key.emoji}**{key.name.capitalize()}** x{value}"

        try:
            if len(information) > 0:
                embed = emb.errorembed(f"{ctx.author} robbed your farm: {information}", ctx, pm=True)
                await member.send(embed=embed)
        except Exception:
            pass

        if cought and not len(win) > 0:
            embed = emb.errorembed("You got cought by the dog! :(", ctx)
            return await ctx.send(embed=embed)
        elif cought:
            embed = emb.confirmembed(f"You got cought by the dog, but you managed to grab: {information}", ctx)
            return await ctx.send(embed=embed)
        else:
            embed = emb.congratzembed(f"You got a bit from everyhing: {information}", ctx)
            return await ctx.send(embed=embed)

    @heist.error
    async def offer_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = secstotime(error.retry_after)
            embed = emb.errorembed(f"You are still being chased by neighbor's dog \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    @scout.error
    async def scout_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = secstotime(error.retry_after)
            embed = emb.errorembed(f"Your loyal spy \ud83d\udd75 is half way home \u23f0{cooldwtime}", ctx)
            await ctx.send(embed=embed)

    @commands.command(aliases=['boosters', 'boost'])
    async def boosts(self, ctx, *, member: Optional[MemberID] = None):
        member = member or ctx.author
        client = self.client

        embed = Embed(title=f'\u2b06{member} boosters', color=817407)

        query = """SELECT * FROM boosts WHERE userid = $1;"""
        data = await client.db.fetchrow(query, usertools.generategameuserid(member))
        if not data:
            embed.description = "No active boosters"
        else:
            embed.description = ''
            dog1d = data['dog1']
            dog1 = boostvalid(dog1d)
            if dog1:
                embed.description += f'\ud83d\udc29 until `{dog1d}`\n'
            dog2d = data['dog2']
            dog2 = boostvalid(dog2d)
            if dog2:
                embed.description += f'\ud83d\udc36 until `{dog2d}`\n'
            dog3d = data['dog3']
            dog3 = boostvalid(dog3d)
            if dog3:
                embed.description += f'\ud83d\udc15 until `{dog3d}`\n'
            catd = data['cat']
            cat = boostvalid(catd)
            if cat:
                embed.description += f'\ud83d\udc31 Līdz `{catd}`\n'
            if not dog1 and not dog2 and not dog3 and not cat:
                embed.description = "No active boosters"

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Heists(client))

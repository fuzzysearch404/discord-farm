from discord import Embed, HTTPException
from discord.ext import commands
from datetime import datetime
from random import randint, choice
from utils import checks
from utils import embeds as emb
from utils.time import secstotime
from utils.paginator import Pages
from utils.convertors import MemberID
from classes import user as userutils
from classes.boost import boostvalid

class Looting(commands.Cog):
    """
    Do you see someone having quite a lot good stuff in their farm?
    If you are evil enough, you can try to grab some stuff.
    Just be careful with their dogs!
    Also they will see that you took their stuff, so don't ruin
    your friendships...
    """
    def __init__(self, client):
        self.client = client


    @commands.command(aliases=['rob', 'steal'])
    @checks.embed_perms()
    @checks.user_cooldown(600)
    @checks.avoid_maintenance()
    async def loot(self, ctx, *, member: MemberID):
        """
        \ud83d\udd75\ufe0f Try to loot someone's farm field.

        Gets some grown items from someones farm field.
        Lootable item amount depends on farm's dog boosters.
        You can't loot rotten items. 

        Parameters:
        `member` - some user in your server. (username, username#1234, user's ID)
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        if member == ctx.author:
            return await ctx.send("You can't loot yourself! Why should you?")

        targetdata = await checks.check_account_data(ctx, lurk=member)
        if not targetdata: return
        client = self.client
        targetacc = userutils.User.get_user(targetdata, client)

        query = """SELECT * FROM planted
        WHERE ends < $1 AND dies > $1
        AND NOT robbed AND userid = $2;"""

        field = await client.db.fetch(query, datetime.now(), targetacc.userid)
        if not field:
            embed = emb.errorembed(
                "This player has nothing to loot or is already fully robbed.",
                ctx
            )
            return await ctx.send(embed=embed)

        boostdata = await targetacc.get_boosts()

        chance = False
        if boostdata:
            if boostvalid(boostdata['dog3']):
                embed = emb.errorembed("This farm is being guarded by a HUGE dog!", ctx)
                return await ctx.send(embed=embed)
            elif boostvalid(boostdata['dog2']): chance = 3
            elif boostvalid(boostdata['dog1']): chance = 6

        win, cought = [], False
        
        for _ in range(len(field)):
            data = choice(field)
            field.remove(data)
            if chance:
                if randint(1, chance) == 1:
                    cought = True
                    break
                else:
                    win.append(data)
            else:
                win.append(data)

        wonitems = {}
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                for item in win:
                    cnt = item['amount']
                    amount = cnt - int(cnt * 0.2)
                    if amount == cnt: amount -= 1
                    
                    witem = client.allitems[item['itemid']]
                    if witem.type != 'crop':
                        witem = witem.expandsto

                    try:
                        wonitems[witem] += cnt - amount
                    except KeyError:
                        wonitems[witem] = cnt - amount

                    query = """UPDATE planted SET amount = $1,
                    robbed = TRUE WHERE id = $2"""
                    await client.db.execute(query, amount, item['id'])

        information = ''
        for item, amnt in wonitems.items():
            await useracc.add_item_to_inventory(item, amnt)
            information += f"{item.emoji}**{item.name.capitalize()}** x{amnt} "
        
        if targetacc.notifications and len(information) > 0:
            try:
                embed = emb.errorembed(f"{ctx.author} robbed your farm: {information}", ctx, pm=True)
                await member.send(embed=embed)
            except HTTPException:
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


def setup(client):
    client.add_cog(Looting(client))

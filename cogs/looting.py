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
        `member` - some user in your server. (tagged user or user's ID)
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
        AND robbedfields < fieldsused AND userid = $2;"""

        fielddata = await client.db.fetch(query, datetime.now(), targetacc.userid)
        if not fielddata:
            embed = emb.errorembed(
                "This player has nothing to loot currently, or is already robbed too much.",
                ctx
            )
            return await ctx.send(embed=embed)

        boostdata = await targetacc.get_boosts()

        dog_chance = False
        if boostdata:
            if boostvalid(boostdata['dog3']):
                embed = emb.errorembed("This farm is being guarded by a HUGE dog, and it can't be robbed!", ctx)
                return await ctx.send(embed=embed)
            elif boostvalid(boostdata['dog2']): dog_chance = 4
            elif boostvalid(boostdata['dog1']): dog_chance = 8

        field, cought, field_volume = [], False, 0

        for data in fielddata:
            for _ in range(data['fieldsused'] - data['robbedfields']):
                field.append(data)

        won, wonitems = {}, {}

        for _ in range(len(field)):
            data = choice(field)
            field.remove(data)
            if dog_chance:
                if randint(1, dog_chance) == 1:
                    cought = True
                    break
                else:
                    try:
                        won[data] += 1
                    except KeyError:
                        won[data] = 1
            else:
                try:
                    won[data] += 1
                except KeyError:
                    won[data] = 1

        if won:
            async with self.client.db.acquire() as connection:
                async with connection.transaction():
                    for robitem, robfields in won.items():
                        witem = client.allitems[robitem['itemid']]
                        if witem.type != 'crop':
                            witem = witem.expandsto

                        item_amount_on_field = robitem['amount']
                        amount_per_field = int(item_amount_on_field / robitem['fieldsused'])
                        robbed_per_field = int(witem.amount * 0.2) or 1
                        cnt = robbed_per_field * robfields
                        amount = item_amount_on_field - cnt

                        try:
                            wonitems[witem] += cnt
                        except KeyError:
                            wonitems[witem] = cnt

                        query = """UPDATE planted SET amount = $1,
                        robbedfields = robbedfields + $2 WHERE id = $3"""
                        await client.db.execute(query, amount, robfields, robitem['id'])

        information = ''
        for item, amnt in wonitems.items():
            await useracc.add_item_to_inventory(item, amnt)
            information += f"{item.emoji}**{item.name.capitalize()}** x{amnt} "
        
        if targetacc.notifications and len(information) > 0:
            try:
                embed = emb.errorembed(f"{ctx.author} managed to rob items from your farm: {information}", ctx, pm=True)
                await member.send(embed=embed)
            except HTTPException:
                pass

        if cought and not len(wonitems) > 0:
            embed = emb.errorembed("You've got cought by the dog! :(", ctx)
            return await ctx.send(embed=embed)
        elif cought:
            embed = emb.confirmembed(f"You've got cought by the dog, but you somehow managed to grab: {information}", ctx)
            return await ctx.send(embed=embed)
        else:
            embed = emb.congratzembed(f"You've got a bit from everyhing: {information}", ctx)
            return await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Looting(client))

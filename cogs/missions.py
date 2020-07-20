from asyncio import TimeoutError
from discord.ext import commands
from discord import Embed
from utils import embeds as emb
from utils import time
from utils import checks
from classes import user as userutils
from classes import mission as missionutils


class Missions(commands.Cog, name="Mission"):
    """
    Earn gold and experience, by completing missions.

    Missions require selling multiple items to various businesses
    and you get rewarded with big gold and experience rewards.
    Doing these missions is not mandatory.
    Mission complexity increases by your experience level, but
    you also get better rewards.
    """
    def __init__(self, client):
        self.client = client

    def createrequestdesign(self, request):
        client = self.client
        string = f'\ud83d\udcd1 {request.buisness}\nOrder:\n'
        money = request.moneyaward
        xp = request.xpaward

        for req in request.requests:
            item = req[0]
            string += f"{item.emoji}{item.name.capitalize()} x{req[1]}\n"
        string += f"\nReward: {client.gold}{money} {client.xp}{xp}"

        return string

    async def create_missions(self, useracc, missions):
        mpl = missionutils.missions_per_level(useracc.level)
        if not missions:
            rrange = mpl
        else:
            rrange = mpl - len(missions)

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                for i in range(rrange):
                    request = missionutils.Mission.generate(self.client, useracc.level)
                    string = request.exportstring()
                    query = """INSERT INTO missions(userid, requests, money, xp, buisness)
                    VALUES ($1, $2, $3, $4, $5)"""
                    await self.client.db.execute(
                        query, useracc.userid, string,
                        request.moneyaward, request.xpaward, request.buisness
                    )

    async def finish_mission(self, useracc, mission, missionid, ctx):
        client = self.client
        required_items = ''

        for task in mission.requests:
            item = task[0]
            itemdata = await useracc.check_inventory_item(item)
            if not itemdata or itemdata['amount'] < task[1]:
                required_items += f"{item.emoji}{item.name.capitalize()}, "

        if len(required_items) > 0:
            embed = emb.errorembed(
                f"You don't have enough: {required_items[:-2]}, to complete this mission!",
                ctx
            )
            return await ctx.send(embed=embed)

        for task in mission.requests:
            await useracc.remove_item_from_inventory(task[0], task[1])

        if missionid != 'offer':
            async with self.client.db.acquire() as connection:
                async with connection.transaction():
                    query = """DELETE FROM missions WHERE id = $1;"""
                    await client.db.execute(query, missionid)

        await useracc.give_xp_and_level_up(mission.xpaward, ctx)
        await useracc.give_money(mission.moneyaward)
        embed = emb.congratzembed(
            "You completed the mission and got "
            f"{mission.moneyaward}{client.gold} and {mission.xpaward}{client.xp}",
            ctx
        )
        await ctx.send(embed=embed)

    @commands.command()
    @checks.user_cooldown(3600)
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def offer(self, ctx):
        """
        \ud83d\udd8b\ufe0f Get hourly urgent offer with increased rewards.

        There is no time to think (well, there are 30 seconds).
        Complete this request mission and earn huge rewards.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        request = missionutils.Mission.generate(client, useracc.level, boosted=True)
        requestdesign = self.createrequestdesign(request)

        embed = Embed(
            title='\ud83d\udccbSpecial request mission',
            color=15171850, description=requestdesign
        )
        embed.description += (
            '\n\n\ud83d\udd8bDo you accept this mission?\n\u23f0'
            'Quick! You only have 30 seconds to decide.'
        )
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        offermsg = await ctx.send(embed=embed)
        await offermsg.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705'

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await offermsg.clear_reactions()
            else: return

        if str(reaction.emoji) == '\u274c':
            return

        await self.finish_mission(useracc, request, 'offer', ctx)

    @commands.group(aliases=['orders'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def missions(self, ctx):
        """
        \ud83d\udcdd Check out your main missions.

        These missions have no time limit.
        """
        if ctx.invoked_subcommand:
            return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        missions = await useracc.get_missions()
        if not missions or len(missions) < missionutils.missions_per_level(useracc.level):
            await self.create_missions(useracc, missions)

        missions = await useracc.get_missions()
        tasks, i, emoji = {}, 0, '\u20e3'

        embed = Embed(
            title='\ud83d\uddc3Order missions',
            description='Stuck doing these order missions? Try `%missions refresh`',
            color=15171850
        )
        for mission in missions:
            i += 1
            missionid = mission['id']
            mission = missionutils.Mission.importstring(
                client, mission['buisness'], mission['money'],
                mission['xp'], mission['requests']
            )
            tasks[f'{i}{emoji}'] = (mission, missionid)
            requestdesign = self.createrequestdesign(mission)
            embed.add_field(name=f'\ud83d\udcdd Order #{i}', value=requestdesign)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)

        message = await ctx.send(embed=embed)
        for j in range(i):
            await message.add_reaction(f'{j+1}{emoji}')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji).endswith(emoji) and reaction.message.id == message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await message.clear_reactions()
            else: return

        await self.finish_mission(
            useracc, tasks[str(reaction.emoji)][0], tasks[str(reaction.emoji)][1], ctx
        )

    @missions.command()
    @checks.user_cooldown(18000)
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def refresh(self, ctx):
        """
        \ud83d\udd01 Stuck doing mission orders? Refresh them and get new ones!
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """DELETE FROM missions WHERE userid = $1;"""
                await self.client.db.execute(query, ctx.author.id)

        await self.missions.invoke(ctx)


def setup(client):
    client.add_cog(Missions(client))

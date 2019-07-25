import asyncio
from discord.ext import commands
from discord import Embed
from utils import usertools
from utils import embeds as emb
from utils import events
from utils import time

MISSION_SLOTS = 3


class Requests(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def cog_check(self, ctx):
        query = """SELECT userid FROM users WHERE id = $1;"""
        userid = await self.client.db.fetchrow(query, usertools.generategameuserid(ctx.author))
        if not userid:
            return False
        return userid['userid'] == ctx.author.id and not self.client.disabledcommands

    @commands.group()
    async def requests(self, ctx):
        if ctx.invoked_subcommand:
            return

        client = self.client
        missions = await usertools.getmissions(client, ctx.author)
        if not missions or len(missions) < MISSION_SLOTS:
            await self.createmissions(ctx.author, missions)

        missions = await usertools.getmissions(client, ctx.author)
        tasks = {}
        i = 0
        emoji = '\u20e3'
        embed = Embed(title='\ud83d\uddc3Pasūtījumi', color=15171850)
        for mission in missions:
            i += 1
            missionid = mission['id']
            mission = events.Mission.importstring(
                client, mission['money'], mission['xp'], mission['requests']
            )
            tasks[f'{i}{emoji}'] = (mission, missionid)
            requestdesign = self.createrequestdesign(mission)
            embed.add_field(name=f'\ud83d\udcdd Pasūtījums nr.{i}', value=requestdesign)
        embed.set_footer(text='Nepatīk pasūtījumi? Lieto %requests refresh')

        message = await ctx.send(embed=embed)
        for j in range(i):
            await message.add_reaction(f'{j+1}{emoji}')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji).endswith(emoji)

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        await self.finishmission(tasks[str(reaction.emoji)][0], tasks[str(reaction.emoji)][1], ctx)

    async def finishmission(self, mission, missionid, ctx):
        client = self.client
        needed = ''

        for task in mission.requests:
            item = task[0]
            itemdata = await usertools.checkinventoryitem(client, ctx.author, item)
            if not itemdata or itemdata['amount'] < task[1]:
                needed += f"{item.emoji}{item.name2.capitalize()}, "

        if len(needed) > 0:
            embed = emb.errorembed(
                f"Tev nav pietiekoši daudz {needed[:-2]}, lai izpildītu pasūtījumu!"
            )
            return await ctx.send(embed=embed)

        for task in mission.requests:
            await usertools.removeitemfrominventory(
                client, ctx.author, task[0], task[1]
            )

        connection = await client.db.acquire()
        async with connection.transaction():
            query = """DELETE FROM missions WHERE id = $1;"""
            await client.db.execute(query, missionid)
        await client.db.release(connection)

        await usertools.givexpandlevelup(client, ctx, mission.xpaward)
        await usertools.givemoney(client, ctx.author, mission.moneyaward)
        embed = emb.congratzembed(
            "Tu izpildīji pasūtījumu un ieguvi"
            f" {client.xp}{mission.xpaward} {client.gold}{mission.moneyaward}")
        await ctx.send(embed=embed)

    async def createmissions(self, member, missions):
        client = self.client
        profile = await usertools.getprofile(client, member)

        if not missions:
            rrange = MISSION_SLOTS
        else:
            rrange = MISSION_SLOTS - len(missions)

        connection = await client.db.acquire()
        async with connection.transaction():
            for i in range(rrange):
                level = usertools.getlevel(profile['xp'])[0]
                request = events.Mission.generate(self.client, level)
                string = request.exportstring()
                query = """INSERT INTO missions(userid, requests, money, xp)
                VALUES ($1, $2, $3, $4)"""
                await client.db.execute(
                    query, usertools.generategameuserid(member), string,
                    request.moneyaward, request.xpaward
                )
        await client.db.release(connection)

    @requests.command()
    @commands.cooldown(1, 21600, commands.BucketType.user)
    async def refresh(self, ctx):
        client = self.client

        connection = await client.db.acquire()
        async with connection.transaction():
            query = """DELETE FROM missions WHERE userid = $1;"""
            await client.db.execute(query, usertools.generategameuserid(ctx.author))
        await client.db.release(connection)
        embed = emb.confirmembed("Uzdevumi atjaunoti! \ud83d\udc4c")
        await ctx.send(embed=embed)

    @refresh.error
    async def refresh_handler(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldwtime = time.secstotime(error.retry_after)
            embed = emb.errorembed(f"Tu varēsi atjaunot uzdevumus tikai pēc \u23f0{cooldwtime}")
            await ctx.send(embed=embed)

    def createrequestdesign(self, request):
        client = self.client
        string = ''
        money = request.moneyaward
        xp = request.xpaward

        for req in request.requests:
            item = req[0]
            string += f"{item.emoji}{item.name2.capitalize()} x{req[1]}\n"
        string += f"{client.gold}{money} {client.xp}{xp}"

        return string


def setup(client):
    client.add_cog(Requests(client))

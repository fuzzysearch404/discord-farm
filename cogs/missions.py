from asyncio import TimeoutError
from discord.ext import commands
from discord import Embed, HTTPException
from datetime import datetime, timedelta

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

    def create_request_design(self, request):
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
                    request = missionutils.Mission.generate(useracc)
                    string = request.export_as_string()
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
            try:
                return await ctx.reply_message.edit(embed=embed)
            except HTTPException:
                return
        
        if missionid != 'offer':
            async with self.client.db.acquire() as connection:
                async with connection.transaction():
                    query = """DELETE FROM missions WHERE id = $1;"""
                    del_results = await client.db.execute(query, missionid)
                    if del_results[-1:] != "1":
                        embed = emb.errorembed(
                            f"You have already completed this mission or some error occured!",
                            ctx
                        )
                        try:
                            return await ctx.reply_message.edit(embed=embed)
                        except HTTPException:
                            return

        for task in mission.requests:
            await useracc.remove_item_from_inventory(task[0], task[1])

        await useracc.give_xp_and_level_up(mission.xpaward, ctx)
        await useracc.give_money(mission.moneyaward)
        
        embed = emb.congratzembed(
            "You completed the mission and got "
            f"{mission.moneyaward}{client.gold} and {mission.xpaward}{client.xp}",
            ctx
        )
        try:
            await ctx.reply_message.edit(embed=embed)
        except HTTPException:
            pass

    @commands.command(aliases=["off"])
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

        request = missionutils.Mission.generate(useracc, boosted=True)
        requestdesign = self.create_request_design(request)

        embed = Embed(
            title='\ud83d\udccbSpecial request mission',
            color=15171850, description=requestdesign
        )
        embed.description += (
            '\n\n\ud83d\udd8bDo you accept this mission?\n\u23f0'
            'Quick! You only have 30 seconds to decide.'
        )
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        reply_message = await ctx.send(embed=embed)
        ctx.reply_message = reply_message # To pass it to outside function
        await reply_message.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705'

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await reply_message.clear_reactions()
            else: return

        if str(reaction.emoji) == '\u274c':
            return

        await self.finish_mission(useracc, request, 'offer', ctx)

    @commands.group(aliases=["orders", "mi"])
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
            mission = missionutils.Mission.import_as_string(
                client, mission['buisness'], mission['money'],
                mission['xp'], mission['requests']
            )
            tasks[f'{i}{emoji}'] = (mission, missionid)
            requestdesign = self.create_request_design(mission)
            embed.add_field(name=f'\ud83d\udcdd Order #{i}', value=requestdesign)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)

        reply_message = await ctx.send(embed=embed)
        ctx.reply_message = reply_message # To pass it to outside function
        for j in range(i):
            await reply_message.add_reaction(f'{j+1}{emoji}')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji).endswith(emoji) and reaction.message.id == reply_message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await reply_message.clear_reactions()
            else: return

        try: # If user adds own number reaction...
            mission_data = tasks[str(reaction.emoji)]
        except KeyError:
            return

        await self.finish_mission(
            useracc, mission_data[0], mission_data[1], ctx
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

    async def fetch_exports_data(self, ctx):
        data = await self.client.redis.execute(
            "GET", f"export:{ctx.author.id}"
        )
        if not data:
            return None

        return missionutils.ExportMission.import_from_json(self.client, data)

    def create_export_design(self, export, current_level=0):
        gold_emoji = self.client.gold
        xp_emoji = self.client.xp
        item = export.item

        text = (
            f"{export.port}\n{item.emoji}{item.name.capitalize()}\n"
            f"\ud83d\udce6 Package size: {export.amount}x{item.emoji}\n\n"
        )

        for i in range(12):
            level = i + 1
            rewards = export.calc_reward_for_shipment(level)
            
            if level != current_level + 1:
                text += f"{level}x\ud83d\udce6{gold_emoji}{rewards[0]}{xp_emoji}{rewards[1]}\n"
            else:
                text += f"__**{level}x\ud83d\udce6{gold_emoji}{rewards[0]}{xp_emoji}{rewards[1]}**__\n"

        return text

    @commands.group(aliases=["export", "ex"])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def exports(self, ctx):
        """
        \ud83d\udea2 Export contract missions.

        Sign a contract and load a ship with resources.
        Each item package you load into a ship gives you some XP and gold rewards and increases the next reward 
        you will get.

        Each ship is loadable for 6 hours.
        You can load a package every 30 minutes.
        You can sign contracts every 1 hour, however, you can only have 1 active contract at a time.
        """
        if ctx.invoked_subcommand:
            return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        embed = Embed(color=15171850)

        export = await self.fetch_exports_data(ctx)
        if not export:
            embed.title = "**No active exports...** \ud83d\ude34"
            embed.description = (
                f"\ud83d\udd8b\ufe0fSign an export contract with `{ctx.prefix}exports start`\n"
                "\u2139\ufe0fExports are time limited missions with increasing rewards, however "
                "you only need to gather a single type of items, but in large quantities."
            )
            
            return await ctx.send(embed=embed)
        else:
            leave_time = export.ends - datetime.now()
            leaves = time.secstotime(leave_time.total_seconds())
            embed.title = "\ud83d\udea2Export ship"
            embed.description = (
                f"\ud83d\udce6Load the items into the export ship with the `{ctx.prefix}exports load` command!\n"
                "\u2934\ufe0fYou get higher rewards for each package you load into the export ship.\n"
                f"\u23f2\ufe0fYou can load a package every 30 minutes."
            )
            embed.add_field(name="\ud83d\udcddActive export", value=self.create_export_design(export, export.shipped))
            embed.add_field(name="\ud83d\udce6Loaded packages", value=export.shipped)
            embed.add_field(name="\ud83d\udd50Ship leaves after", value=leaves)
            await ctx.send(embed=embed)

    @exports.command()
    @checks.user_cooldown(3600)
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def start(self, ctx):
        """
        \ud83d\udd8b\ufe0f Starts a new export mission.

        This command has a cooldown, so if you don't choose
        an export mission, you will have to wait.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        existing_data = await self.fetch_exports_data(ctx)
        if existing_data:
            embed = emb.errorembed(
                "You already have an active export contract!",
                ctx
            )
            return await ctx.send(embed=embed)
        
        embed = Embed(title="\ud83d\udea2Sign an export contract", color=15171850)
        embed.description = (
            "\ud83d\udd8b\ufe0fPlease sign one of these contracts!\n"
            "\u2139\ufe0f**Note: If you don't accept any of these contracts, you will have to wait an hour cooldown!**"
        )

        emoji, export_options = "\ufe0f\u20e3", {}
        for i in range(3):
            export = missionutils.ExportMission.generate(useracc)
            embed.add_field(name="\ud83d\udea2Contract #" + str(i + 1), value=self.create_export_design(export))
            export_options[str(i + 1) + emoji] = export

        reply_message = await ctx.send(embed=embed)
        for em in export_options.keys():
            await reply_message.add_reaction(em)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji).endswith(emoji) and reaction.message.id == reply_message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=60.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await reply_message.clear_reactions()
            else: return

        try: # If user added own number emoji
            export = export_options[str(reaction.emoji)]
        except KeyError:
            return

        existing_data = await self.fetch_exports_data(ctx)
        if existing_data:
            return

        await self.client.redis.execute(
            "SET", f"export:{ctx.author.id}", export.export_as_json(), "EX", missionutils.EXPORT_DURATION
        )

        await self.exports.invoke(ctx)

        
    @exports.command()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def load(self, ctx):
        """
        \ud83d\udce6 Loads a package into the export ship.

        You must have an active export contract to load items to the ship.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        export = await self.fetch_exports_data(ctx)
        if not export:
            embed = emb.errorembed(
                f"You don't have an active export contract! Sign one with `{ctx.prefix}exports start`.",
                ctx
            )
            return await ctx.send(embed=embed)

        cooldown = await checks.get_user_cooldown(ctx, "export_load")
        if cooldown:
            return await ctx.send(
                f"\u274c The export ship is busy loading your last package! You have to wait **{time.secstotime(cooldown)}**!"
            )

        item = export.item

        itemdata = await useracc.check_inventory_item(item)
        if not itemdata or itemdata["amount"] < export.amount:
            embed = emb.errorembed(
                f"You don't have enough **{item.emoji}{item.name.capitalize()}** for loading the export package!",
                ctx
            )
            return await ctx.send(embed=embed)

        export.shipped += 1

        await checks.set_user_cooldown(ctx, 1800, "export_load")
        await useracc.remove_item_from_inventory(item, export.amount)

        rewards = export.calc_reward_for_shipment()
        await useracc.give_money(rewards[0])
        await useracc.give_xp_and_level_up(rewards[1], ctx)

        mission_ends = export.ends - datetime.now()

        remaining_seconds = int(mission_ends.total_seconds())
        if remaining_seconds >= 1:
            export.ends = datetime.now() + timedelta(seconds=remaining_seconds)
            await self.client.redis.execute(
                "SET", f"export:{ctx.author.id}", export.export_as_json(), "EX", remaining_seconds
            )

        embed = emb.congratzembed(
            "You loaded a package to the export ship and got "
            f"{rewards[0]}{client.gold} and {rewards[1]}{client.xp}",
            ctx
        )

        await ctx.send(embed=embed)
        

def setup(client):
    client.add_cog(Missions(client))

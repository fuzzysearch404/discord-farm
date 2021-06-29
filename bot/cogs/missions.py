import discord
import jsonpickle
from discord.ext import commands

from .utils import time
from .utils import embeds
from .utils import checks
from .utils import pages
from core import game_missions


class Missions(commands.Cog):
    """
    Earn various rewards, by completing missions.

    Missions require gathering multiple items for various businesses
    and for that you get rewarded with big gold and experience rewards.
    Doing these missions is not mandatory, but highly recommended.
    Mission complexity increases by your experience level, but
    you also get better rewards.
    """
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    def parse_mission_data(
        self,
        ctx,
        mission: game_missions.BusinessMission
    ) -> game_missions.BusinessMission:
        requests = []
        for request in mission.requests:
            item = ctx.items.find_item_by_id(request.item_id)
            requests.append((item, request.amount))

        mission.requests = requests

        if mission.chest:
            chest = ctx.items.find_chest_by_id(mission.chest)

            mission.chest = chest

        return mission

    def format_mission(self, mission: game_missions.BusinessMission) -> str:
        fmt = f"\ud83d\udcd1 {mission.name}\nRequest:\n"

        for req in mission.requests:
            item, amount = req[0], req[1]
            fmt += f"**{item.full_name} x{amount}**\n"

        fmt += "\n\ud83d\udcb0 Rewards:\n**"

        if mission.gold_reward:
            fmt += f"{mission.gold_reward} {self.bot.gold_emoji} "

        if mission.xp_reward:
            fmt += f"{mission.xp_reward} {self.bot.xp_emoji}"

        if mission.chest:
            fmt += f"\n\ud83c\udf81 Bonus: 1x {mission.chest.emoji} "

        return fmt + "**"

    async def complete_business_mission(
        self,
        ctx,
        mission: game_missions.BusinessMission,
        mission_msg: discord.Message,
        mission_id: int
    ) -> None:
        """Requires a mission instance with parsed item and chest data"""
        missing_items = []

        # mission_id -1 = temp. mission
        async with ctx.acquire() as conn:
            if mission_id != -1:

                query = """
                        SELECT payload FROM missions
                        WHERE id = $1;
                        """

                payload = await conn.fetchval(query, mission_id)

                # If user tries to complete already completed mission, after
                # a long prompt.
                if not payload:
                    return await mission_msg.edit(content="Already completed!")

            user_items = await ctx.user_data.get_all_items(ctx, conn=conn)

        if user_items:
            for req in mission.requests:
                item, amount = req[0], req[1]

                try:
                    item_data = next(
                        x for x in user_items if x['item_id'] == item.id
                    )

                    if item_data['amount'] < amount:
                        missing_items.append(
                            (item, amount - item_data['amount'])
                        )
                except StopIteration:
                    missing_items.append((item, amount))
        else:
            missing_items = mission.requests

        if missing_items:
            fmt = ""
            for item, amount in missing_items:
                fmt += f"{item.full_name} x{amount}, "

            return await mission_msg.edit(
                embed=embeds.error_embed(
                    title=(
                        "You are missing items to complete this mission!"
                    ),
                    text=(
                        "Unfortunately we can't deliver this package to "
                        "our customer, becuase you are missing these "
                        f"requested items: **{fmt[:-2]}**! "
                    ),
                    ctx=ctx
                )
            )

        async with ctx.acquire() as conn:
            async with conn.transaction():
                if mission_id != -1:
                    query = """
                            DELETE FROM missions
                            WHERE id = $1;
                            """

                    await conn.execute(query, mission_id)

                for item, amount in mission.requests:
                    await ctx.user_data.remove_item(
                        ctx, item.id, amount, conn=conn
                    )

                if mission.chest:
                    await ctx.user_data.give_item(
                        ctx, mission.chest.id, 1, conn=conn
                    )

                ctx.user_data.gold += mission.gold_reward
                await ctx.user_data.give_xp_and_level_up(
                    ctx, mission.xp_reward
                )

                await ctx.users.update_user(ctx.user_data, conn=conn)

        fmt = ""

        if mission.gold_reward:
            fmt += f"{mission.gold_reward} {self.bot.gold_emoji} "

        if mission.xp_reward:
            fmt += f"{mission.xp_reward} {self.bot.xp_emoji} "

        if mission.chest:
            fmt += (
                f"1x {mission.chest.emoji} {mission.chest.name.capitalize()} "
                "chest"
            )

        await mission_msg.edit(
            embed=embeds.success_embed(
                title="Mission completed! \ud83d\udc4f",
                text=(
                    "Well done! \ud83d\ude0e The customer was very satisfied "
                    "with your service and sent these as for the "
                    f"reward: **{fmt}**"
                ),
                ctx=ctx
            )
        )

    @commands.group(aliases=["orders", "mission", "mi"], case_insensitive=True)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def missions(self, ctx):
        """
        \ud83d\udcdd View your current order missions.

        Order missions have no time limit, so you can finish these
        missions whenever you like.
        If you don't like your current missions, you canget new ones
        every 5 hours with **{prefix}missions refresh**
        """
        if ctx.invoked_subcommand:
            return

        if ctx.user_data.level < 10:
            mission_count = 3
        elif ctx.user_data.level < 20:
            mission_count = 4
        elif ctx.user_data.level < 30:
            mission_count = 5
        else:
            mission_count = 6

        missions = []

        async with ctx.acquire() as conn:
            query = """
                    SELECT id, payload FROM missions
                    WHERE user_id = $1;
                    """

            existing_missions = await conn.fetch(query, ctx.author.id)

            for existing in existing_missions:
                decoded = jsonpickle.decode(existing['payload'])
                missions.append((existing['id'], decoded))

            for _ in range(mission_count - len(existing_missions)):
                new_mission = game_missions.BusinessMission.generate(ctx)
                encoded = jsonpickle.encode(new_mission)

                query = """
                        INSERT INTO missions (user_id, payload)
                        VALUES ($1, $2)
                        RETURNING id;
                        """

                id = await conn.fetchval(query, ctx.author.id, encoded)

                missions.append((id, new_mission))

        embed = discord.Embed(
            title="\ud83d\udcdd Your order missions",
            description=(
                "\ud83d\udc69\u200d\ud83d\udcbc Hey boss! \ud83d\udc4b We "
                "have these orders from our local business partners.\n"
                "\ud83d\udcbc Click a button below to complete some of "
                "these orders!\n\ud83d\udd01 Don't like any of these orders? "
                f"Get new orders with **{ctx.prefix}missions refresh** "
                "every 5 hours."
            ),
            color=discord.Color.from_rgb(148, 148, 148)
        )

        emoji_assigned_to_missions = {}

        counter = 0
        for id, mission in missions:
            counter += 1

            mission = self.parse_mission_data(ctx, mission)
            emoji_assigned_to_missions[counter] = (id, mission)

            embed.add_field(
                name=f"\ud83d\udcdd Order: {counter}\ufe0f\u20e3",
                value=self.format_mission(mission)
            )

        menu = pages.NumberSelection(embed=embed, count=mission_count)
        result, msg = await menu.prompt(ctx)

        if not result:
            return

        result = emoji_assigned_to_missions[result]

        await self.complete_business_mission(
            ctx=ctx,
            mission=result[1],
            mission_msg=msg,
            mission_id=result[0]
        )

    @missions.command(aliases=["reload", "new"])
    @checks.user_cooldown(18000)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def refresh(self, ctx):
        """
        \ud83d\udd01 Stuck doing order missions? Refresh them and get new ones!
        """
        async with ctx.acquire() as conn:
            query = """
                    DELETE FROM missions
                    WHERE user_id = $1;
                    """

            await conn.execute(query, ctx.author.id)

        await self.missions.invoke(ctx)

    @commands.command(aliases=["off"])
    @checks.user_cooldown(3600)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def offer(self, ctx):
        """
        \ud83d\udd8b\ufe0f Hourly mission

        Similar as **{prefix}missions**, only this mission has very short
        availability period and better rewards. Complete it or it is gone.
        """
        mission = game_missions.BusinessMission.generate(
            ctx,
            reward_multiplier=1.175
        )
        mission = self.parse_mission_data(ctx, mission)

        embed = discord.Embed(
            title="\ud83d\udd8b\ufe0f Urgent order offer!",
            description=(
                "\ud83d\udc69\u200d\ud83d\udcbb Boss, quick! This business "
                "partner is urgently looking for these items and is "
                "going to pay extra rewards:\n**\u23f0 "
                "You only have a few seconds to decide if you approve!**"
            ),
            color=discord.Color.from_rgb(198, 20, 9)
        )

        embed.add_field(
            name="\u2757 Urgent offer:",
            value=self.format_mission(mission)
        )

        menu = pages.ConfirmPrompt(pages.CONFIRM_CHECK_BUTTON, embed=embed)
        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        await self.complete_business_mission(
            ctx=ctx,
            mission=mission,
            mission_msg=msg,
            mission_id=-1
        )

    async def fetch_exports_data(self, ctx):
        return await self.bot.redis.execute_command(
            "GET", f"export:{ctx.author.id}"
        )

    def format_export_reward(
        self,
        ctx,
        export: game_missions.ExportMission,
        level: int
    ) -> str:
        rewards = export.rewards_for_shipment(level)

        fmt = (
            f"{rewards[0]} {ctx.bot.gold_emoji} "
            f"{rewards[1]} {ctx.bot.xp_emoji}"
        )

        chest = rewards[2]
        if chest:
            chest = ctx.items.find_chest_by_id(chest)
            fmt += f" 1x {chest.emoji}"

        return fmt

    def format_export(
        self,
        ctx,
        export: game_missions.ExportMission
    ) -> str:
        item = export.item

        text = (
            f"{export.port_name}\n{item.full_name}\n"
            f"\ud83d\udce6 Package size: "
            f"{export.amount}x {item.emoji}\n\n"
        )

        if export.shipments < 10:
            next_fmt = self.format_export_reward(
                ctx, export, export.shipments + 1
            )
            if export.shipments:
                text += f"\ud83d\udcb0 __**Next reward:**__\n{next_fmt}\n"
            else:
                text += f"\ud83d\udcb0 **First reward:**\n{next_fmt}\n"

            if export.shipments != 9:
                last_fmt = self.format_export_reward(ctx, export, 10)
                text += f"\ud83d\udcb0 **Final reward:**\n{last_fmt}\n"
        else:
            text += (
                "**The cargo ship is already fully loaded! "
                "It's waiting for departing to the high seas!** \ud83d\udc4c"
            )

        return text

    @commands.group(case_insensitive=True, aliases=["exports", "ex"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def export(self, ctx):
        """
        \ud83d\udea2 Export contract missions

        Sign a contract and load a cargo ship with as much resources as
        you can, before it leaves your port.
        Each item package you load into the ship gives you increasing XP and
        gold rewards.

        Each cargo ship is loadable for 6 hours.
        You can load a package every 30 minutes.
        You can sign contracts every 1 hour, however, you can only have
        only one active contract at a time.
        """
        if ctx.invoked_subcommand:
            return

        embed = discord.Embed(color=discord.Color.from_rgb(34, 102, 153))

        current_export = await self.fetch_exports_data(ctx)
        if not current_export:
            embed.title = "\u2693 No currently active export \ud83d\ude34"
            embed.description = (
                "\ud83d\udd8b\ufe0f Sign an export contract with **"
                f"{ctx.prefix}export start**\n\ud83d\udea2 Exports are time "
                "limited missions with increasing rewards, however you only "
                "need to gather a single type of items, but in large "
                "quantities, and as much as you can, before the cargo ship "
                "leaves your local port.\n\ud83d\udd16 You can only have one "
                "export contract active per a time and you can choose "
                "a contract once per hour."
            )
        else:
            ttl = await self.bot.redis.execute_command(
                "TTL", f"export:{ctx.author.id}"
            )
            leave_time = time.seconds_to_time(ttl)

            export = jsonpickle.decode(current_export)

            embed.title = "\ud83d\udea2 Load the cargo ship"
            embed.description = (
                "\ud83d\udce6 Load items into the cargo ship "
                f"with the **{ctx.prefix}export load** command!\n"
                "\u2934\ufe0f You will get higher rewards for each package "
                "you load into the cargo ship.\n"
                "\u23f2\ufe0f You can load a package every 30 minutes."
            )
            embed.add_field(
                name="\u2693 Current contract",
                value=self.format_export(ctx, export)
            )
            embed.add_field(
                name="\ud83d\udce6 Loaded packages",
                value=f"{export.shipments} of 10"
            )
            embed.add_field(
                name="\ud83d\udd50 Cargo ship leaves in",
                value=leave_time
            )

        await ctx.reply(embed=embed)

    @export.command()
    @checks.user_cooldown(3600)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def start(self, ctx):
        """
        \ud83d\udd8b\ufe0f Starts a new export mission

        This command has a cooldown, so if you don't choose
        an export mission, you will have to wait a hour.
        """
        existing_data = await self.fetch_exports_data(ctx)

        if existing_data:
            return await self.export.invoke(ctx)

        embed = discord.Embed(
            title="\u270f\ufe0f Please choose an export contract",
            description=(
                "\u26f4\ufe0f Welcome to the port! \ud83d\udc77 We have these "
                "three cargo ships leaving to high seas today and "
                "they have the following offers:\n"
                "\ud83d\udd50 You can only choose one and if you don't "
                "choose any, you will have to wait an hour for new contracts."
            ),
            color=discord.Color.from_rgb(217, 158, 130)
        )
        embed.set_footer(text=(
                "\u23f1\ufe0f Choose a contract quickly, "
                "because you have limited time to do so"
            ))

        emoji_assigned_to_exports = {}

        for num in range(3):
            num += 1

            export = game_missions.ExportMission.generate(ctx)
            emoji_assigned_to_exports[num] = export

            embed.add_field(
                name=f"\ud83d\udcdd Contract: {num}\ufe0f\u20e3",
                value=self.format_export(ctx, export)
            )

        menu = pages.NumberSelection(embed=embed, count=3)
        result, msg = await menu.prompt(ctx)

        if not result:
            return

        result = emoji_assigned_to_exports[result]

        await self.bot.redis.execute_command(
            "SET", f"export:{ctx.author.id}",
            jsonpickle.encode(result), "EX", 21600
        )

        await self.export.invoke(ctx)

    @export.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def load(self, ctx):
        """
        \ud83d\udce6 Loads a package into the cargo ship

        You must have an active export contract to load items to the ship.
        """
        export = await self.fetch_exports_data(ctx)

        if not export:
            return await self.export.invoke(ctx)

        export = jsonpickle.decode(export)

        if export.shipments >= 10:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="The cargo ship is already full! \ud83d\udce6",
                    text=(
                        "We can't load another package, because the cargo "
                        "ship has reached it's maximum cargo capacity! "
                        "\ud83d\udc77\nAnyways, well done! We now have to "
                        "wait until it leaves the port! You don't have to do "
                        "anything tho, you can just watch as it enters the "
                        "sea, if you wish. \ud83c\udf05"
                    ),
                    ctx=ctx
                )
            )

        cooldown = await checks.get_user_cooldown(ctx, "export_load")
        if cooldown:
            cd = time.seconds_to_time(cooldown)

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "Package loading onto cargo ship in progress! "
                        "\ud83d\udea2\ud83d\udce6"
                    ),
                    text=(
                        "We have to wait for your last package to "
                        "get loaded onto the cargo ship! Please check "
                        f"back again after **{cd}**, it should be done "
                        "by that time. \ud83d\udc77"
                    ),
                    ctx=ctx
                )
            )

        item, amount = export.item, export.amount

        async with ctx.acquire() as conn:
            item_data = await ctx.user_data.get_item(ctx, item.id, conn=conn)

            if not item_data or item_data['amount'] < amount:
                if item_data:
                    missing_amount = amount - item_data['amount']
                else:
                    missing_amount = amount

                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="Not enough items for this package!",
                        text=(
                            "We can't load this package onto the cargo ship! "
                            "\ud83d\udc77 The cargo ship's capacity should be "
                            "used effectively, so the package must be full to "
                            f"the top.\n**You are missing: {missing_amount}x "
                            f"{item.full_name}**"
                        ),
                        ctx=ctx
                    )
                )

            rewards = export.rewards_for_shipment()
            ctx.user_data.gold += rewards[0]

            await ctx.user_data.give_xp_and_level_up(
                ctx, rewards[1]
            )

            async with conn.transaction():
                await ctx.user_data.remove_item(
                    ctx, item.id, amount, conn=conn
                )

                await ctx.users.update_user(ctx.user_data, conn=conn)

                # Award chest
                if rewards[2]:
                    await ctx.user_data.give_item(
                        ctx, rewards[2], 1, conn=conn
                    )

        ttl = await self.bot.redis.execute_command(
            "TTL", f"export:{ctx.author.id}"
        )
        # Just in case if it somehow already ended
        ttl = ttl or 0

        export.shipments += 1
        await self.bot.redis.execute_command(
            "SET", f"export:{ctx.author.id}",
            jsonpickle.encode(export), "EX", ttl
        )

        await checks.set_user_cooldown(ctx, 1800, "export_load")

        chest = rewards[2]
        if chest:
            chest = ctx.items.find_chest_by_id(chest)
            chest = f"1x {chest.emoji} {chest.name.capitalize()} chest"

        await ctx.reply(
            embed=embeds.success_embed(
                title="Package is being loaded onto the cargo ship!",
                text=(
                    "Well done! \ud83d\udc4d We started loading your package: "
                    f"**{amount}x {item.full_name}** "
                    "onto the cargo ship!\n**You received: "
                    f"{rewards[0]} {ctx.bot.gold_emoji} {rewards[1]} "
                    f"{ctx.bot.xp_emoji} {chest or ''}**"
                ),
                ctx=ctx
            )
        )


def setup(bot):
    bot.add_cog(Missions(bot))

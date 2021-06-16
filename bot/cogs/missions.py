import discord
import jsonpickle
from discord.ext import commands

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
            fmt += f"**{item.emoji} {item.name.capitalize()} x{amount}**\n"

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
                fmt += f"{item.emoji} {item.name.capitalize()} x{amount}, "

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

        menu = pages.MissionSelection(embed=embed, count=mission_count)
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


def setup(bot):
    bot.add_cog(Missions(bot))

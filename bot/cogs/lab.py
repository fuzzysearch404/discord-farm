import discord
from discord.ext import commands, menus

from .utils import time
from .utils import embeds
from .utils import pages
from .utils import checks
from .utils import converters
from core import game_items
from core import modifications


class LabSource(menus.ListPageSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        lab_cooldown
    ):
        super().__init__(entries, per_page=12)
        self.target = target_user
        self.lab_cooldown = lab_cooldown

    async def format_page(self, menu, page):
        target = self.target

        embed = discord.Embed(
            title=f"\ud83e\uddec {target.nick or target.name}'s laboratory",
            color=discord.Color.from_rgb(146, 102, 204),
            description=(
                "Welcome to the secret laboratory! "
                "\ud83d\udc68\u200d\ud83d\udd2c\nHere you can genetically "
                "modify your plants and animals (animals don't get hurt) "
                "to grow faster, be collectable for longer and "
                "produce a larger volume of items. \ud83e\udda0\n"
                f"Use the **{menu.ctx.prefix}modifications** command to "
                "see the available upgrades for an item. \ud83d\udd0d\n"
                f"For example: \"{menu.ctx.prefix}modifications lettuce\"\n\n"
            )
        )

        if self.lab_cooldown:
            embed.description += (
                "\ud83e\uddf9 This laboratory is closed for "
                f"a maintenance: **{self.lab_cooldown}**\n\n"
            )

        if not page:
            embed.description += (
                "\ud83e\uddeb **No items have been modified yet...**"
            )
        else:
            header = (
                "\ud83e\uddea __**Currently upgraded items:**__\n"
                "| \ud83c\udff7\ufe0f Item | \ud83d\udd70 Growing time |"
                " \ud83d\udd70 Harvesting time | \u2696\ufe0f Volume |\n\n"
            )

            embed.description += header + "\n".join(page)

            embed.set_footer(
                text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
            )

        return embed


class Lab(commands.Cog):
    """
    Are your crops growing too slow? Are you too slow to collect the
    harvest? There is a solution - genetic modifications.
    You can upgrade your seeds, trees and bushes, even your
    animals in your laboratory.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    def calculate_mod_cost(
        self,
        item: game_items.PurchasableItem,
        level: int
    ) -> int:
        return int(round(item.gold_price * (level ** 1.55), -1))

    def calculate_mod_cooldown(self, level: int) -> int:
        return 60 + int(round((level ** 4.9362), -1))  # Max (10): 1 day

    @commands.command(aliases=["lab"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def laboratory(self, ctx, *, member: discord.Member = None):
        """
        \ud83e\uddea Lists the upgraded items

        You can upgrade items to reduce their growing durations,
        increase their collection durations and increase their
        harvest volume.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `laboratory` - view your lab
        {prefix} `laboratory @user` - view user's lab
        """
        if member:
            user = await checks.get_other_member(ctx, member)
            target_user = member
        else:
            user = ctx.user_data
            target_user = ctx.author

        query = """
                SELECT * FROM modifications
                WHERE user_id = $1;
                """

        async with ctx.acquire() as conn:
            mod_data = await conn.fetch(query, target_user.id)

        entries = []

        for data in mod_data:
            item = ctx.items.find_item_by_id(data['item_id'])

            entries.append(
                f"**{item.full_name}:** "
                f"\ud83d\udd70 {data['time1']}/10 "
                f"\ud83d\udd70 {data['time2']}/10 "
                f"\u2696\ufe0f {data['volume']}/10"
            )

        lab_cooldown = await checks.get_user_cooldown(
            ctx, "recent_research", other_user_id=user.user_id
        )
        if lab_cooldown:
            lab_cooldown = time.seconds_to_time(lab_cooldown)

        paginator = pages.MenuPages(
            source=LabSource(entries, target_user, lab_cooldown)
        )

        await paginator.start(ctx)

    async def perform_modification(
        self,
        ctx,
        msg: discord.Message,
        item: game_items.PlantableItem,
        mod_type: str
    ) -> None:
        cooldown = await checks.get_user_cooldown(ctx, "recent_research")
        if cooldown:
            cooldown = time.seconds_to_time(cooldown)

            return await msg.edit(
                embed=embeds.error_embed(
                    title=(
                        "The laboratory is under a maintenance! \ud83e\uddf9"
                    ),
                    text=(
                        "We are still cleaning things up "
                        "after your last item's upgrade!\n"
                        f"Please come again in: **{cooldown}** \u23f0"
                    ),
                    ctx=ctx
                )
            )

        async with ctx.acquire() as conn:
            mods = await ctx.user_data.get_item_modification(
                ctx, item.id, conn=conn
            )

            current_level = mods[mod_type] if mods else 0

            if current_level >= 10:
                return await msg.edit(
                    embed=embeds.error_embed(
                        title="Already upgraded to the maximum level!",
                        text=(
                            "You have reached the last possible "
                            "modification level for this property "
                            f"of **{item.full_name}**!\n"
                            "Maybe after some ten or couple hundred years "
                            "the science is going to allow going futher than "
                            "this... \ud83d\udc69\u200d\ud83d\udd2c"
                        ),
                        ctx=ctx
                    )
                )

            gold_cost = self.calculate_mod_cost(item, current_level + 1)
            user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

            if gold_cost > user_data.gold:
                return await msg.edit(
                    embed=embeds.no_money_embed(ctx, user_data, gold_cost)
                )

            async with conn.transaction():
                user_data.gold -= gold_cost

                await ctx.users.update_user(user_data, conn=conn)

                query = f"""
                        INSERT INTO modifications
                        (user_id, item_id, {mod_type})
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, item_id)
                        DO UPDATE
                        SET {mod_type} = modifications.{mod_type} + $3;
                        """

                await conn.execute(query, user_data.user_id, item.id, 1)

        cooldown = self.calculate_mod_cooldown(current_level + 1)
        await checks.set_user_cooldown(ctx, cooldown, "recent_research")

        await msg.edit(
            embed=embeds.congratulations_embed(
                title="Modification successful!",
                text=(
                    "Our experiments went smoothly and we are so happy "
                    "to tell you that your modification has been applied "
                    f"to your **{item.full_name}**! "
                    "\ud83c\udf8a\n If you are ready to test it out, go "
                    "ahead, grow some of those! \ud83e\udd20"
                ),
                ctx=ctx
            )
        )

    @commands.command(name="modifications", aliases=["mods"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def item_modifications(self, ctx, *, item: converters.Item):
        """
        \ud83e\uddec Apply modifications to your items

        __Arguments__:
        `item` - item to show upgrades for (item's name or ID)

        __Usage examples__:
        {prefix} `modifications lettuce` - by using item's name
        {prefix} `modifications 1` - by using item's ID
        """
        if not isinstance(item, game_items.PlantableItem):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="This item can't be genetically modified",
                    text=(
                        "With a deep regret, I have to tell you that "
                        f"**{item.full_name}** can't be "
                        f"upgraded!\nThe science has not developed so "
                        "far yet... \ud83d\udc68\u200d\ud83d\udd2c\n"
                        "You can only upgrade items that you can grow "
                        "in your farm. \ud83c\udf31"
                    ),
                    ctx=ctx
                )
            )

        if ctx.user_data.level < item.level:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="\ud83d\udd12 You haven't unlocked this item yet!",
                    text=(
                        f"Our laboratory can't upgrade **{item.full_name}**, "
                        f"if you don't even have access to that item. "
                        "Sorry. \ud83d\ude15"
                    ),
                    footer=(
                        "This item is going to be unlocked at "
                        f"experience level {item.level}."
                    ),
                    ctx=ctx
                )
            )

        time1_mod, time2_mod, vol_mod = 0, 0, 0

        mods = await ctx.user_data.get_item_modification(ctx, item.id)
        if mods:
            time1_mod = mods['time1']
            time2_mod = mods['time2']
            vol_mod = mods['volume']

        embed = discord.Embed(
            title=(
                f"\ud83d\udd2c Genetic modifications: {item.full_name}"
            ),
            description=(
                "\ud83d\udc69\u200d\ud83d\udd2c These are all the "
                f"possible upgrades for your: **{item.full_name}**\n"
                "\ud83e\uddf9 The upgrade will be done instantly, "
                "but we are going to need some time to clean up the "
                "lab, before we can upgrade your next item.\n"
                "\u26a0\ufe0f Your currently growing items in farm "
                "won't be affected by this upgrade, so this upgrade is "
                "going to take effect upon your next planting!"
            ),
            color=discord.Color.from_rgb(146, 102, 204)
        )

        grow_time = time.seconds_to_time(
            modifications.get_growing_time(item, time1_mod)
        )
        collect_time = time.seconds_to_time(
            modifications.get_harvest_time(item, time2_mod)
        )
        base_volume = modifications.get_volume(item, vol_mod)

        if time1_mod < 10:
            next_grow_time = time.seconds_to_time(
                modifications.get_growing_time(
                    item, time1_mod + 1
                )
            )
            price = self.calculate_mod_cost(item, time1_mod + 1)

            cooldown = time.seconds_to_time(
                self.calculate_mod_cooldown(time1_mod + 1)
            )

            fmt = (
                f"\ud83c\udd95 Next level: **{next_grow_time}**\n\n"
                f"\u23f2\ufe0f Research cooldown:\n**{cooldown}**\n"
                "\ud83d\udcb0 Research costs:\n"
                f"**{price} {self.bot.gold_emoji}**\n\n"
                "\ud83d\uded2 Upgrade item: 1\ufe0f\u20e3"
            )
        else:
            fmt = "\ud83c\udf20 **Max. level**"

        embed.add_field(
            name="\ud83d\udd70\ufe0f Growing duration",
            value=(
                f"\ud83e\uddea Modifications: {time1_mod}/10\n"
                f"\ud83e\uddec Current: **{grow_time}**\n{fmt}"
            )
        )

        if time2_mod < 10:
            next_collect_time = time.seconds_to_time(
                modifications.get_harvest_time(
                    item, time2_mod + 1
                )
            )
            price = self.calculate_mod_cost(item, time2_mod + 1)

            cooldown = time.seconds_to_time(
                self.calculate_mod_cooldown(time2_mod + 1)
            )

            fmt = (
                f"\ud83c\udd95 Next level: **{next_collect_time}**\n\n"
                f"\u23f2\ufe0f Research cooldown:\n**{cooldown}**\n"
                "\ud83d\udcb0 Research costs:\n"
                f"**{price} {self.bot.gold_emoji}**\n\n"
                "\ud83d\uded2 Upgrade item: 2\ufe0f\u20e3"
            )
        else:
            fmt = "\ud83c\udf20 **Max. level**"

        embed.add_field(
            name="\ud83d\udd70\ufe0f Harvestable for",
            value=(
                f"\ud83e\uddea Modifications: {time2_mod}/10\n"
                f"\ud83e\uddec Current: **{collect_time}**\n{fmt}"
            )
        )

        if vol_mod < 10:
            next_base_volume = modifications.get_volume(
                item, vol_mod + 1
            )
            price = self.calculate_mod_cost(item, vol_mod + 1)

            cooldown = time.seconds_to_time(
                self.calculate_mod_cooldown(vol_mod + 1)
            )

            fmt = (
                f"\ud83c\udd95 Next level: **{next_base_volume} items**\n\n"
                f"\u23f2\ufe0f Research cooldown:\n**{cooldown}**\n"
                "\ud83d\udcb0 Research costs:\n"
                f"**{price} {self.bot.gold_emoji}**\n\n"
                "\ud83d\uded2 Upgrade item: 3\ufe0f\u20e3"
            )
        else:
            fmt = "\ud83c\udf20 **Max. level**"

        embed.add_field(
            name="\u2696\ufe0f Harvest volume",
            value=(
                f"\ud83e\uddea Modifications: {vol_mod}/10\n"
                f"\ud83e\uddec Current: **{base_volume} items**\n{fmt}"
            )
        )

        embed.set_footer(
            text=(
                "\ud83d\uded2 Press a button to purchase the "
                "selected modification"
            )
        )

        menu = pages.NumberSelection(embed=embed, count=3)
        result, msg = await menu.prompt(ctx)

        if not result:
            return

        mod_types_per_emoji_numbers = {
            1: "time1",
            2: "time2",
            3: "volume"
        }

        await self.perform_modification(
            ctx=ctx,
            msg=msg,
            item=item,
            mod_type=mod_types_per_emoji_numbers[result]
        )


def setup(bot):
    bot.add_cog(Lab(bot))

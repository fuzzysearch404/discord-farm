import discord
from datetime import datetime
from enum import Enum
from discord.ext import commands, menus

from .utils import pages
from .utils import time
from .utils import checks
from .utils import embeds
from .utils.converters import ItemAndAmount
from core import game_items


class PlantState(Enum):
    GROWING = 1
    COLLECTABLE = 2
    ROTTEN = 3


class PlantedFieldItem:

    __slots__ = (
        "item",
        "amount",
        "iterations",
        "fields_used",
        "ends",
        "dies",
        "robbed_fields",
        "cat_boost"
    )

    def __init__(
        self,
        item: game_items.PlantableItem,
        amount: int,
        iterations: int,
        fields_used: int,
        ends: datetime,
        dies: datetime,
        robbed_fields: int,
        cat_boost: bool
    ) -> None:
        self.item = item
        self.amount = amount
        self.iterations = iterations
        self.fields_used = fields_used
        self.ends = ends
        self.dies = dies
        self.robbed_fields = robbed_fields
        self.cat_boost = cat_boost

    @property
    def state(self) -> PlantState:
        now = datetime.now()

        if self.ends > now:
            return PlantState.GROWING
        elif self.dies > now:
            return PlantState.COLLECTABLE
        else:
            return PlantState.ROTTEN

    @property
    def is_harvestable(self) -> bool:
        state = self.state

        return state == PlantState.COLLECTABLE or \
            state == PlantState.ROTTEN and self.cat_boost

    @property
    def is_robbable(self) -> bool:
        return self.state == PlantState.COLLECTABLE and \
            self.robbed_fields < self.fields_used


class FarmFieldSource(menus.ListPageSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        used_slots: int,
        total_slots: int,
        has_slots_boost: bool,
        farm_guard: int,
        tile_emoji: str
    ):
        super().__init__(entries, per_page=12)
        self.target = target_user
        self.used_slots = used_slots
        self.total_slots = total_slots
        self.has_slots_boost = has_slots_boost
        self.farm_guard = farm_guard
        self.tile_emoji = tile_emoji

    async def format_page(self, menu, page):
        target = self.target

        embed = discord.Embed(
            title=f"\ud83c\udf31 {target.nick or target.name}'s farm field",
            color=discord.Color.green()
        )

        # NOTE: We have different ID prefixes for different item classes.
        # Also we have ordered the items by ID in our query for this.
        def get_item_class_name(item):
            return item.__class__.__name__ + "s"

        last_class = get_item_class_name(page[0].item)
        fmt = f"**{last_class}**\n"

        if not self.has_slots_boost:
            total_slots = self.total_slots
        else:
            total_slots = f"**{self.total_slots + 2}** \ud83d\udc39"

        header = (
            f"{self.tile_emoji} Farm's used space tiles: "
            f"{self.used_slots}/{total_slots}\n"
        )

        if self.farm_guard:
            remaining = time.seconds_to_time(self.farm_guard)
            header += (
                "\ud83d\udee1\ufe0f Because of Discord's or bot's errors, "
                "for a short period of time, farm's items can be harvested "
                "even if they are rotten, thanks to Farm Guard\u2122\ufe0f! "
                "\n\u23f2\ufe0f Farm Guard is going to be active for: "
                f"**{remaining}**\n\n"
            )

        for plant in page:
            item = plant.item

            current_item_class = get_item_class_name(item)
            if current_item_class != last_class:
                last_class = current_item_class

                fmt += f"\n**{last_class}**\n"

            if plant.state == PlantState.GROWING:
                delta_secs = (plant.ends - datetime.now()).total_seconds()
                state = f"Growing: {time.seconds_to_time(delta_secs)}"
            elif plant.state == PlantState.COLLECTABLE and not plant.cat_boost:
                delta_secs = (plant.dies - plant.ends).total_seconds()
                time_fmt = time.seconds_to_time(delta_secs)

                if isinstance(plant.item, game_items.ReplantableItem):
                    state = f"Collectable for: {time_fmt}"
                else:
                    state = f"Harvestable for: {time_fmt}"
            elif plant.cat_boost:
                if isinstance(plant.item, game_items.ReplantableItem):
                    state = "Collectable"
                else:
                    state = "Harvestable"
            else:
                state = "Rotten (not collected in time)"

            if isinstance(item, game_items.Crop):
                fmt += (
                    f"{item.emoji} **{item.name.capitalize()} "
                    f"x{plant.amount}** - {state}"
                )
            elif isinstance(item, game_items.Tree):
                fmt += (
                    f"{item.emoji} **{item.name.capitalize()} "
                    f"(x{plant.amount} {item.emoji})** "
                    f"- {state} (**{plant.iterations}.lvl**)"
                )
            else:
                fmt += (
                    f"{item.emoji_animal} **{item.name.capitalize()} "
                    f"(x{plant.amount} {item.emoji})** "
                    f"- {state} (**{plant.iterations}.lvl**)"
                )

            if plant.cat_boost:
                fmt += " \ud83d\udc31"

            fmt += "\n"

        embed.description = header + fmt
        embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )

        return embed


class Farm(commands.Cog):
    """
    Commands for crop, animal and tree growing.

    Each item has their growing time and time period while the item
    is harvestable (it's not rotten). Items can only be harvested when
    they are grown enough. Rotten items still take up your farm's space,
    but they are discarded automatically when you harvest your field.
    Trees, bushes and animals have multiple collection cycles,
    so you have to collect their items multiple times in a row.
    If they get rotten, just harvest the rotten items and the
    next growing cycle will start unaffected.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    def parse_db_rows_to_plant_data_classes(self, rows: dict) -> list:
        parsed = []

        for row in rows:
            item = self.bot.item_pool.find_item_by_id(row['item_id'])

            plant = PlantedFieldItem(
                item=item,
                amount=row['amount'],
                iterations=row['iterations'],
                fields_used=row['fields_used'],
                ends=row['ends'],
                dies=row['dies'],
                robbed_fields=row['robbed_fields'],
                cat_boost=row['cat_boost']
            )

            parsed.append(plant)

        return parsed

    @commands.command(aliases=["field", "f"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def farm(self, ctx, member: discord.Member = None):
        """
        \ud83c\udf3e Shows your or someone's farm field

        Useful to see what you or someone else is growing right now.
        Displays item quantities, growing statuses and grow timers.

        __Explanation__:
        If the item is **"Growing"** - that means that you have to wait the
        specified time until you can harvest the item.

        if the item is **"Harvestable" or "Collectable"** - that means that you
        can use the "{prefix}`harvest`" command, to collect these items.
        Be quick, because you can only collect those for the specified
        period of time, before they get rotten.

        If the item is **"Rotten"** - that means that you have missed the
        chance to collect this item and you won't be able to obtain these
        items. You have to use the "{prefix}`harvest`" command, to free up
        your farm space.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `farm` - view your farm
        {prefix} `farm @user` - view user's farm
        """
        if not member:
            user = ctx.user_data
        else:
            user = await checks.get_other_member(ctx, member)
        target_user = member or ctx.author

        field_data = await user.get_farm_field(ctx)

        if not field_data:
            if not member:
                error_title = "You have not planted anything on your field!"
            else:
                error_title = (
                    f"Nope, {member} has not planted anything on their field!"
                )

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=error_title,
                    text=(
                        "\ud83c\udf31 Plant items on the field with the "
                        f"**{ctx.prefix}plant** command"
                    ),
                    ctx=ctx
                )
            )

        field_parsed = self.parse_db_rows_to_plant_data_classes(field_data)

        field_guard = 0
        if self.bot.field_guard:
            delta_time = self.bot.guard_mode - datetime.now()
            field_guard = delta_time.total_seconds()

        has_slots_boost = await user.is_boost_active(ctx, "farm_slots")

        paginator = pages.MenuPages(
            source=FarmFieldSource(
                field_parsed,
                target_user,
                len(field_data),
                user.farm_slots,
                has_slots_boost,
                field_guard,
                self.bot.tile_emoji
            )
        )

        await paginator.start(ctx)

    @commands.command(aliases=["harv", "h"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def harvest(self, ctx):
        """
        \ud83d\udc68\u200d\ud83c\udf3e Harvests your farm field

        Collects the grown items and discards the rotten
        items from your farm field.
        If you collect tree, bush or animal items, then
        their next growing cycle begins.
        To check what you are currenly growing and if you can
        harvest anything, check out "{prefix}`farm`" command.
        """
        raise NotImplementedError()

    @commands.command(aliases=["p", "grow", "g"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def plant(self, ctx, *, item: ItemAndAmount, amount: int = 1):
        """
        \ud83c\udf31 Plants crops and trees, grows animals on your farm field

        __Arguments__:
        `item` - item to lookup for planting/growing (item's name or ID)
        __Optional arguments__:
        `amount` - specify how many items to plant/grow

        __Usage examples__:
        {prefix} `plant lettuce 2` - plant 2 lettuce items
        {prefix} `plant 1 2` - plant 2 lettuce items (by using item's ID)
        {prefix} `plant 1` - plant 1 lettuce item (no amount)
        """
        raise NotImplementedError()

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def clear(self, ctx):
        """
        \ud83e\uddf9 Clear your farm field

        Removes ALL of your planted items from your farm field for some gold.
        This command is useful if you planted something by accident and you
        want to get rid of those items, because they take up your farm field
        space. These items WILL NOT be moved to your inventory and WILL BE
        LOST without any compensation, so be careful with this feature.
        """
        raise NotImplementedError()

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def fish(self, ctx):
        """
        \ud83c\udfa3 [Unlocks from level 17] Go fishing!

        You can catch random amount of fish once per hour.
        Sometimes your luck can be bad, and you might not get any fish.
        """
        raise NotImplementedError()  # TODO: inner cooldown - 3600

    @commands.command(aliases=["rob", "loot"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def steal(self, ctx, user: discord.Member):
        """
        \ud83d\udd75\ufe0f Try to steal someone's farm field's items

        __Explanation__:
        You can try to get some items from other players farms.
        The target user's items must be harvestable at the moment of attempt.
        You can use command "{prefix}`farm @user`", to check user's farm field.
        You can't choose what items you will get, items are chosen randomly.
        Also, you only get partial volume of target's item volume.
        If the target user has dog boosters, your chances
        of successfully robbing the player are lowered.
        Otherwise, you get a bit from all target's goodies.
        After stealing attempt, this feature is on a temporary cooldown.
        Already robbed items can't be robbed again.

        __Arguments__:
        `member` - some user in your server (tagged user or user's ID)

        __Usage examples__:
        {prefix} `steal @user` - steal user's farm's items
        """
        raise NotImplementedError()  # TODO: inner cooldown


def setup(bot):
    bot.add_cog(Farm(bot))

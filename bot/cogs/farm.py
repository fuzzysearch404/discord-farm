import discord
import random
from datetime import datetime, timedelta
from contextlib import suppress
from enum import Enum
from discord.ext import commands, menus

from .utils import pages
from .utils import time
from .utils import checks
from .utils import embeds
from .utils.converters import ItemAndAmount
from core import game_items
from core import modifications


class PlantState(Enum):
    GROWING = 1
    COLLECTABLE = 2
    ROTTEN = 3


class PlantedFieldItem:

    __slots__ = (
        "id",
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
        id: int,
        item: game_items.PlantableItem,
        amount: int,
        iterations: int,
        fields_used: int,
        ends: datetime,
        dies: datetime,
        robbed_fields: int,
        cat_boost: bool
    ) -> None:
        self.id = id
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


class FarmFieldSource(menus.ListPageSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        used_slots: int,
        total_slots: int,
        has_slots_boost: bool,
        farm_guard: int
    ):
        super().__init__(entries, per_page=12)
        self.target = target_user
        self.used_slots = used_slots
        self.total_slots = total_slots
        self.has_slots_boost = has_slots_boost
        self.farm_guard = farm_guard

    async def format_page(self, menu, page):
        target = self.target

        embed = discord.Embed(
            title=f"\ud83c\udf31 {target.nick or target.name}'s farm field",
            color=discord.Color.from_rgb(119, 178, 85)
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
            f"{menu.bot.tile_emoji} Farm's used space tiles: "
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
                delta_secs = (plant.dies - datetime.now()).total_seconds()
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
                fmt += f"**{item.full_name} x{plant.amount}** - {state}"
            elif isinstance(item, game_items.Tree):
                fmt += (
                    f"**{item.full_name} x{plant.amount}** - {state} "
                    f"(**{plant.iterations}.lvl**)"
                )
            else:
                fmt += (
                    f"**{item.full_name} (x{plant.amount} {item.emoji})** "
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

    def parse_db_rows_to_plant_data_objects(self, rows: dict) -> list:
        parsed = []

        for row in rows:
            item = self.bot.item_pool.find_item_by_id(row['item_id'])

            plant = PlantedFieldItem(
                id=row['id'],
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
        can use the **{prefix}harvest** command, to collect these items.
        Be quick, because you can only collect those for the specified
        period of time, before they get rotten.

        If the item is **"Rotten"** - that means that you have missed the
        chance to collect this item and you won't be able to obtain these
        items. You have to use the **{prefix}harvest** command, to free up
        your farm space.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `farm` - view your farm
        {prefix} `farm @user` - view user's farm
        """
        if not member:
            user = ctx.user_data
            target_user = ctx.author
        else:
            user = await checks.get_other_member(ctx, member)
            target_user = member

        field_data = await user.get_farm_field(ctx)

        if not field_data:
            if not member:
                error_title = "You haven't planted anything on your field!"
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

        field_parsed = self.parse_db_rows_to_plant_data_objects(field_data)
        used_fields = sum(x.fields_used for x in field_parsed)

        field_guard = 0
        if self.bot.field_guard:
            delta_time = self.bot.guard_mode - datetime.now()
            field_guard = delta_time.total_seconds()

        has_slots_boost = await user.is_boost_active(ctx, "farm_slots")

        paginator = pages.MenuPages(
            source=FarmFieldSource(
                field_parsed,
                target_user,
                used_fields,
                user.farm_slots,
                has_slots_boost,
                field_guard
            )
        )

        await paginator.start(ctx)

    def group_plants(self, plants: list) -> dict:
        grouped = {}

        for plant in plants:
            try:
                grouped[plant.item] += plant.amount
            except KeyError:
                grouped[plant.item] = plant.amount

        return grouped

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
        harvest anything, check out the **{prefix}farm** command.
        """
        conn = await ctx.acquire()
        field_data = await ctx.user_data.get_farm_field(ctx, conn=conn)

        if not field_data:
            await ctx.release()

            return await ctx.reply(
                embed=embeds.error_embed(
                    title="You haven't planted anything on your field!",
                    text=(
                        "Hmmm... There is literally nothing to harvest, "
                        "because you did not even plant anything. \ud83e\udd14"
                        "\nPlant items on the field with the "
                        f"**{ctx.prefix}plant** command \ud83c\udf31"
                    ),
                    ctx=ctx
                )
            )

        field_parsed = self.parse_db_rows_to_plant_data_objects(field_data)

        to_harvest, to_update, to_discard = [], [], []

        for plant in field_parsed:
            if plant.iterations and plant.iterations > 1:
                if plant.is_harvestable or self.bot.field_guard \
                        and plant.state == PlantState.ROTTEN:
                    to_update.append(plant)
                elif plant.state == PlantState.ROTTEN:
                    to_discard.append(plant)
            else:
                if plant.is_harvestable or self.bot.field_guard \
                        and plant.state == PlantState.ROTTEN:
                    to_harvest.append(plant)
                elif plant.state == PlantState.ROTTEN:
                    to_discard.append(plant)

        if not (to_harvest or to_update or to_discard):
            await ctx.release()

            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Your items are still growing! \ud83c\udf31",
                    text=(
                        "Please be patient! Your items are growing! Soon we "
                        "will get that huge harvest! "
                        "\ud83d\udc68\u200d\ud83c\udf3e\nCheck out your "
                        "remaining item growing durations with "
                        f"the **{ctx.prefix}farm** command. \n"
                        "But don't get too relaxed, because you will have a "
                        "limited time to harvest your items. \u23f0"
                    ),
                    ctx=ctx
                )
            )

        to_reward, xp_gain = [], 0

        async with conn.transaction():
            if to_update:
                update_rows = []

                for plant in to_update:
                    item_mods = await modifications.get_item_mods(
                        ctx,
                        plant.item,
                        conn=conn
                    )
                    grow_time = item_mods[0]
                    collect_time = item_mods[1]
                    base_volume = item_mods[2]

                    ends = datetime.now() + timedelta(seconds=grow_time)
                    dies = ends + timedelta(seconds=collect_time)
                    amount = base_volume * plant.fields_used

                    update_rows.append((ends, dies, amount, plant.id))
                    to_reward.append((plant.item.id, plant.amount))
                    xp_gain += plant.item.xp * plant.amount

                query = """
                        UPDATE farm
                        SET ends = $1, dies = $2,
                        amount = $3, iterations = iterations - 1,
                        robbed_fields = 0
                        WHERE id = $4;
                        """

                await conn.executemany(query, update_rows)

            delete_rows = []

            for plant in to_harvest:
                delete_rows.append((plant.id, ))
                to_reward.append((plant.item.id, plant.amount))
                xp_gain += plant.item.xp * plant.amount
            for plant in to_discard:
                delete_rows.append((plant.id, ))

            if delete_rows:
                query = """
                        DELETE from farm
                        WHERE id = $1;
                        """
                await conn.executemany(query, delete_rows)

            if to_reward:
                await ctx.user_data.give_items(ctx, to_reward, conn=conn)

            await ctx.user_data.give_xp_and_level_up(ctx, xp_gain)
            await ctx.users.update_user(ctx.user_data, conn=conn)

        await ctx.release()

        to_harvest.extend(to_update)
        harvested = self.group_plants(to_harvest)
        updated = self.group_plants(to_update)
        discarded = self.group_plants(to_discard)

        if discarded and not(harvested or updated):
            fmt = ""
            for item, amount in discarded.items():
                fmt += f"{amount}x {item.full_name}, "

            await ctx.reply(
                embed=embeds.error_embed(
                    title="Oh no! Your items are gone!",
                    text=(
                        "You missed your chance to harvest your items "
                        f"on time, so your items: **{fmt[:-2]}** got rotten! "
                        "\ud83d\ude22\nPlease be more careful next time and "
                        f"follow the timers with **{ctx.prefix}farm** command."
                    ),
                    footer=(
                        "All rotten items have been removed from your "
                        "farm \u267b\ufe0f"
                    ),
                    ctx=ctx
                )
            )
        else:
            fmt = (
                "\ud83e\udd20 **You successfully harvested your farm field!**"
                "\n\ud83d\ude9c You harvested: **"
            )

            for item, amount in harvested.items():
                fmt += f"{item.full_name} x{amount}, "

            fmt = fmt[:-2] + "**"

            if updated:
                fmt += (
                    "\n\ud83d\udd01 Some items are now "
                    "growing their next cycle: "
                )

                for item, amount in updated.items():
                    fmt += f"{item.emoji}, "

                fmt = fmt[:-2]

            if discarded:
                fmt += (
                    "\n\n\u267b\ufe0f But some items got rotten and "
                    "had to be discarded: **"
                )

                for item, amount in discarded.items():
                    fmt += f"{item.full_name} x{amount}, "

                fmt = fmt[:-2] + "** \ud83d\ude10"

            fmt += (
                f"\n\nAnd you received: **+{xp_gain} XP** {self.bot.xp_emoji}"
            )

            embed = embeds.success_embed(
                title="You harvested your farm! Awesome!",
                text=fmt,
                footer="Harvested items are now moved to your inventory",
                ctx=ctx
            )

            await ctx.reply(embed=embed)

    @commands.command(aliases=["p", "grow", "g"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def plant(self, ctx, *, item: ItemAndAmount, tiles: int = 1):
        """
        \ud83c\udf31 Plants crops and trees, grows animals on your farm field

        __Arguments__:
        `item` - item to lookup for planting/growing (item's name or ID)
        __Optional arguments__:
        `tiles` - specify how many farm tiles to use for planting/growing

        __Usage examples__:
        {prefix} `plant lettuce 2` - plant 2 tiles of lettuce items
        {prefix} `plant 1 2` - plant 2 tiles of lettuce items (by using ID)
        {prefix} `plant 1` - plant lettuce (single tile)
        """
        item, tiles = item

        if not isinstance(item, game_items.PlantableItem):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=f"{item.name.capitalize()} is not a growable item!",
                    text=(
                        "Hey! HEY! YOU! STOP it right there! \ud83d\ude40 "
                        f"You can't just plant **{item.full_name}** "
                        "on your farm field! That's illegal! \ud83d\ude33 "
                        "It would be cool tho. \ud83e\udd14"
                    ),
                    footer="Check out shop to discover plantable items",
                    ctx=ctx
                )
            )

        if item.level > ctx.user_data.level:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="\ud83d\udd12 Insufficient experience level!",
                    text=(
                        f"**Sorry, you can't grow {item.full_name} just yet!**"
                        " I was told by shop cashier that they can't "
                        "let you purchase these, because you are not "
                        "experienced enough to handle these, you know? "
                        "Anyways, this item unlocks from level "
                        f"\ud83d\udd31 **{item.level}**."
                    ),
                    ctx=ctx
                )
            )

        item_mods = await modifications.get_item_mods(ctx, item)
        grow_time = item_mods[0]
        collect_time = item_mods[1]
        base_volume = item_mods[2]

        total_cost = tiles * item.gold_price
        total_items = tiles * base_volume

        embed = embeds.prompt_embed(
            title=(
                f"Are you really going to grow {tiles}x "
                f"tiles of {item.full_name}?"
            ),
            text=(
                "Check out these details and let me know if you approve"
            ),
            ctx=ctx
        )
        embed.add_field(
            name="\ud83e\uddfe Item",
            value=item.full_name
        )
        embed.add_field(
            name="\u2696\ufe0f Quantity",
            value=tiles
        )
        embed.add_field(
            name="\ud83d\udcb0 Total costs",
            value=f"{total_cost} {self.bot.gold_emoji}"
        )

        if isinstance(item, game_items.ReplantableItem):
            grow_info = (
                f"{total_items}x {item.full_name} ({item.iterations} times)"
            )
        else:
            grow_info = f"{total_items}x {item.full_name}"

        grow_time_str = time.seconds_to_time(grow_time)
        coll_time_str = time.seconds_to_time(collect_time)

        embed.add_field(
            name="\ud83c\udff7\ufe0f Will grow into",
            value=grow_info
        )
        embed.add_field(
            name="\ud83d\udd70\ufe0f Growing duration",
            value=grow_time_str
        )
        embed.add_field(
            name=(
                "\ud83d\udd70\ufe0f Maximum harvesting period before "
                "item gets rotten"
            ),
            value=coll_time_str
        )
        embed.set_footer(
            text=f"You have a total of {ctx.user_data.gold} gold coins"
        )

        menu = pages.ConfirmPrompt(pages.CONFIRM_COIN_BUTTTON, embed=embed)
        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        boosts = await ctx.user_data.get_all_boosts(ctx)
        slots_boost = "farm_slots" in [x.id for x in boosts]
        cat_boost = "cat" in [x.id for x in boosts]

        conn = await ctx.acquire()
        # Refetch user data, because user could have no money after prompt
        user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

        if total_cost > user_data.gold:
            await ctx.release()

            return await msg.edit(
                embed=embeds.no_money_embed(ctx, user_data, total_cost)
            )

        query = """
                SELECT sum(fields_used)
                FROM farm WHERE user_id = $1;
                """

        used_fields = await conn.fetchval(query, ctx.author.id) or 0

        total_slots = ctx.user_data.farm_slots
        if slots_boost:
            total_slots += 2
        available_slots = total_slots - used_fields

        if available_slots < tiles:
            await ctx.release()

            return await msg.edit(
                embed=embeds.error_embed(
                    title="Not enough farm space!",
                    text=(
                        f"**You are already currently using {used_fields} of "
                        f"your {total_slots} farm space tiles**!\n"
                        "I'm sorry to say, but there is no more space for "
                        f"**{tiles} tiles of {item.full_name}**.\n\n"
                        "What you can do about this:\na) Wait for your "
                        "currently planted items to grow and harvest them."
                        "\nb) Upgrade your farm size if you have gems "
                        f"with: **{ctx.prefix}upgrade farm**."
                    ),
                    ctx=ctx
                )
            )

        iterations = None
        if isinstance(item, game_items.ReplantableItem):
            iterations = item.iterations

        transaction = conn.transaction()
        await transaction.start()

        try:
            query = """
                    INSERT INTO farm
                    (user_id, item_id, amount, iterations, fields_used,
                    ends, dies, cat_boost)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
                    """

            ends = datetime.now() + timedelta(seconds=grow_time)
            await conn.execute(
                query,
                ctx.author.id,
                item.id,
                total_items,
                iterations,
                tiles,
                ends,
                ends + timedelta(seconds=collect_time),
                cat_boost
            )

            user_data.gold -= total_cost
            await ctx.users.update_user(user_data, conn=conn)
        except Exception:
            await transaction.rollback()
            raise
        else:
            await transaction.commit()

        await ctx.release()

        await msg.edit(
            embed=embeds.success_embed(
                title=(
                    f"Successfully started growing {item.full_name}!"
                ),
                text=(
                    f"Nicely done! **You are now growing {item.full_name}!** "
                    "\ud83e\udd20\nYou will be able to collect it in: "
                    f"**{grow_time_str}**. Just remember to harvest in time, "
                    "because you will only have limited time to do so... "
                    f"(**{coll_time_str}**) \u23f0"
                ),
                footer=(
                    "Track your item growing progress with the "
                    "\"farm\" command"
                ),
                ctx=ctx
            )
        )

    @commands.command(aliases=["clean"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def clear(self, ctx):
        """
        \ud83e\uddf9 Clear your farm field

        Removes ALL of your planted items from your farm field for some small
        gold price. This command is useful if you planted something by accident
        and you want to get rid of those items, because they take up your farm
        field space. These items WILL NOT be moved to your inventory and WILL
        BE LOST without any compensation, so be careful with this feature.
        """
        field_data = await ctx.user_data.get_farm_field(ctx)

        if not field_data:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="You are not growing anything!",
                    text=(
                        "Hmmm... This is weird. So you are telling me, that "
                        "you want to clear your farm field, but you are not "
                        "even growing anything? \ud83e\udd14"
                    ),
                    ctx=ctx
                )
            )

        total_cost, total_fields = 0, 0
        for data in field_data:
            item = ctx.items.find_item_by_id(data['item_id'])

            fields_used = data['fields_used']
            total_cost += item.gold_price * fields_used
            total_fields += fields_used

        # 5% of total
        total_cost = int(total_cost / 20) or 1

        embed = embeds.prompt_embed(
            title="Are you sure that you want to clear your field?",
            text=(
                f"\u26a0\ufe0f **You are about to lose ALL ({total_fields}) "
                "of your  currently growing items on farm field!**\nAnd they "
                "are NOT going to be refunded, neither moved to your "
                f"inventory. And this is going to cost extra **{total_cost}** "
                f"{self.bot.gold_emoji}! Let's do this? \ud83e\udd14"
            ),
            ctx=ctx
        )

        menu = pages.ConfirmPrompt(pages.CONFIRM_COIN_BUTTTON, embed=embed)
        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        async with ctx.acquire() as conn:
            # Refetch user data, because user could have no money after prompt
            user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

            if total_cost > user_data.gold:
                return await msg.edit(
                    embed=embeds.no_money_embed(ctx, user_data, total_cost)
                )

            query = """
                    DELETE FROM farm
                    WHERE user_id = $1;
                    """

            await conn.execute(query, ctx.author.id)

            user_data.gold -= total_cost
            await ctx.users.update_user(user_data, conn=conn)

        await msg.edit(
            embed=embeds.success_embed(
                title="Farm field cleared!",
                text=(
                    "Okey, I sent some or my workers to clear up "
                    "the farm for you! \ud83e\uddf9"
                ),
                footer="Your farm field items have been discarded",
                ctx=ctx
            )
        )

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def fish(self, ctx):
        """
        \ud83c\udfa3 [Unlocks from level 17] Go fishing!

        You can catch random amount of fish once per hour.
        Sometimes your luck can be bad, and you might not get any fish at all.
        """
        if ctx.user_data.level < 17:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "\ud83d\udd12 Fishing unlocks from experience "
                        "level 17!"
                    ),
                    text=(
                        "Sorry buddy, you don't have the "
                        "license for fishing yet! \ud83c\udfa3"
                    ),
                    ctx=ctx
                )
            )

        cooldown = await checks.get_user_cooldown(ctx, "recent_fishing")
        if cooldown:
            cd_timer = time.seconds_to_time(cooldown)

            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Searching for lures! \ud83e\udeb1",
                    text=(
                        "Emmm... I am digging for some worms for new lures. "
                        f"Could you please come again in: **{cd_timer}**? "
                        "\ud83e\ude9d"
                    ),
                    ctx=ctx
                )
            )

        await checks.set_user_cooldown(ctx, 3600, "recent_fishing")

        limits = [1, 5, 10, 20, 30, 40]
        weights = [8.0, 12.0, 10.0, 5.0, 2.0, 1.0]

        limit = random.choices(population=limits, weights=weights, k=1)
        win_amount = random.randint(0, limit[0])

        if win_amount == 0:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="\ud83e\ude9d Unlucky! No fish at all!",
                    text=(
                        f"You went to a {limit[0]} hour long fishing session "
                        "and could not catch a single fish... \ud83d\ude14\n"
                        "No worries! Hopefully you will have a "
                        "better luck next time! \ud83d\ude09"
                    ),
                    ctx=ctx
                )
            )

        # ID 600 - Fish item
        await ctx.user_data.give_item(ctx, 600, win_amount)

        await ctx.reply(
            embed=embeds.congratulations_embed(
                title="You successfully cought some fish! \ud83c\udfa3",
                text=(
                    "That's some nice catch! \ud83e\udd29 "
                    f"You cought: **{win_amount}x** \ud83d\udc1f"
                ),
                ctx=ctx
            )
        )

    @commands.command(aliases=["rob", "loot"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def steal(self, ctx, target: discord.Member):
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
        `target` - some user in your server (tagged user or user's ID)

        __Usage examples__:
        {prefix} `steal @user` - steal user's farm's items
        """
        if target == ctx.author:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="You can't steal from yourself!",
                    text="Silly you! Why would you ever do this? \ud83e\udd78",
                    ctx=ctx
                )
            )

        target_user = await checks.get_other_member(ctx, target)

        cooldown = await checks.get_user_cooldown(ctx, "recent_steal")
        if cooldown:
            cd_timer = time.seconds_to_time(cooldown)

            return await ctx.reply(
                embed=embeds.error_embed(
                    title="You are way too suspicious! \ud83e\udd2b",
                    text=(
                        "You recently already attempted something like this, "
                        f"so we have to wait for **{cd_timer}**, or they will "
                        "call the police just because of "
                        "seeing you there! \ud83d\ude94"
                    ),
                    ctx=ctx
                )
            )

        await checks.set_user_cooldown(ctx, 900, "recent_steal")

        async with ctx.acquire() as conn:
            target_data = await checks.get_other_member(ctx, target, conn=conn)

            query = """
                    SELECT * FROM farm
                    WHERE ends < $1 AND dies > $1
                    AND robbed_fields < fields_used
                    AND user_id = $2;
                    """
            target_field = await conn.fetch(query, datetime.now(), target.id)

        if not target_field:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        f"{target.nick or target.name} currently has "
                        "nothing to steal from!"
                    ),
                    text=(
                        "Oh no! They don't have any collectable harvest! "
                        "They most likely saw us walking in their farm, "
                        "so must hide behind this tree for a few minutes "
                        "\ud83d\udc49\ud83c\udf33. If they will ask "
                        "something - I don't know you. \ud83e\udd2b"
                    ),
                    footer=(
                        "The target user must have items ready to harvest "
                        "and they must not be already robbed from by "
                        "you or anyone else"
                    ),
                    ctx=ctx
                )
            )

        cought_chance, cought = 0, False
        target_boosts = await target_data.get_all_boosts(ctx)
        if target_boosts:
            boost_ids = [x.id for x in target_boosts]

            if "dog_3" in boost_ids:
                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="Harvest stealing attempt failed!",
                        text=(
                            "I went in there and I ran away as fast, as "
                            "I could, because they have a **HUGE** dog out "
                            "there! \ud83d\udc15 Better to be safe, than "
                            "sorry. \ud83d\ude13"
                        ),
                        ctx=ctx
                    )
                )
            elif "dog_2" in boost_ids and "dog_1" in boost_ids:
                cought_chance = 2
            elif "dog_2" in boost_ids:
                cought_chance = 4
            elif "dog_1" in boost_ids:
                cought_chance = 8

        field, rewards = [], {}

        for data in target_field:
            for _ in range(data['fields_used'] - data['robbed_fields']):
                field.append(data)

        while len(field) > 0:
            current = random.choice(field)
            field.remove(current)

            if cought_chance and random.randint(1, cought_chance) == 1:
                cought = True
                break

            try:
                rewards[current] += 1
            except KeyError:
                rewards[current] = 1

        won_items_and_amounts = {}
        if len(rewards) > 0:
            to_update, to_reward = [], []

            for data, field_count in rewards.items():
                item = ctx.items.find_item_by_id(data['item_id'])
                win_amount = int((item.amount * field_count) * 0.2) or 1

                # For response to user
                try:
                    won_items_and_amounts[item] += win_amount
                except KeyError:
                    won_items_and_amounts[item] = win_amount

                to_update.append((win_amount, field_count, data['id']))
                to_reward.append((data['item_id'], win_amount))

            async with ctx.acquire() as conn:
                async with conn.transaction():
                    query = """
                            UPDATE farm
                            SET amount = amount - $1,
                            robbed_fields = robbed_fields + $2
                            WHERE id = $3;
                            """

                    await conn.executemany(query, to_update)
                    await ctx.user_data.give_items(ctx, to_reward, conn=conn)

            fmt = ""
            for item, amount in won_items_and_amounts.items():
                fmt += f"{item.full_name} x{amount}, "

            fmt = fmt[:-2]
            if target_user.notifications:
                with suppress(discord.HTTPException):
                    await target.send(
                        embed=embeds.error_embed(
                            title=(
                                f"{ctx.author} managed to steal items from "
                                "your farm! \ud83d\udd75\ufe0f"
                            ),
                            text=(
                                "Hey boss! \ud83d\udc4b\nI am sorry to say, "
                                f"but someone named \"{ctx.author}\" managed "
                                f"to grab some items from your farm: **{fmt}**"
                                "!\n\ud83d\udca1Next time be a bit faster to "
                                "harvest your farm or buy a dog booster for "
                                "some protection!"
                            ),
                            private=True,
                            ctx=ctx
                        )
                    )

            if cought:
                return await ctx.reply(
                    embed=embeds.success_embed(
                        title="Nice attempt, but...",
                        text=(
                            f"Okey, so I went in and grabbed these: **{fmt}**!"
                            " But the dog saw me and I had to run, so I did "
                            "not get all the items! I'm glad that we got away "
                            "with atleast something. \ud83c\udfc3\ud83d\udc29"
                        ),
                        ctx=ctx
                    )
                )
            else:
                return await ctx.reply(
                    embed=embeds.congratulations_embed(
                        title="We did it! Jackpot!",
                        text=(
                            f"We managed to get a bit from all the harvest "
                            f"{target.nick or target.name} had: **{fmt}** "
                            "\ud83d\udd75\ufe0f\nNow you should better "
                            "watch out from them, because they won't be "
                            "happy about this! \ud83d\ude2c"
                        ),
                        ctx=ctx
                    )
                )

        await ctx.reply(
            embed=embeds.error_embed(
                title="We got cought! \ud83d\ude1e",
                text=(
                    f"Oh no! Oh no no no! {target.nick or target.name} had "
                    "a dog and I got cought! \ud83d\ude2b\n"
                    "Now my ass hurts real bad! But we can try again "
                    "some other time. It was fun! \ud83d\ude05"
                ),
                ctx=ctx
            )
        )


def setup(bot):
    bot.add_cog(Farm(bot))

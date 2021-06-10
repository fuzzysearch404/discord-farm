import discord
from datetime import datetime, timedelta
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
        item, amount = item
        item_name_capitalized = item.name.capitalize()

        if not isinstance(item, game_items.PlantableItem):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=f"{item_name_capitalized} is not a growable item!",
                    text=(
                        "Hey! HEY! YOU! STOP it right there! \ud83d\ude40 "
                        f"You can't just plant {item.emoji} **"
                        f"{item_name_capitalized}** on your farm field! "
                        "\ud83d\ude33 That's illegal! \ud83e\udd26 "
                        "Would be cool tho. \ud83e\udd14"
                    ),
                    footer="Check out shop to discover plantable items",
                    ctx=ctx
                )
            )

        if item.level > ctx.user_data.level:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Insufficient experience level!",
                    text=(
                        f"**Sorry, you can't grow {item.emoji} "
                        f"{item_name_capitalized} just yet!** "
                        "I was told by shop cashier that they can't "
                        "let you purchase these, because you are not "
                        "experienced enough to handle these, you know? "
                        "Anyways, this item unlocks from level "
                        f"\ud83d\udd31 **{item.level}**."
                    ),
                    ctx=ctx
                )
            )

        grow_time = item.grow_time
        collect_time = item.collect_time
        base_volume = item.amount

        mods = await ctx.user_data.get_item_modification(ctx, item.id)
        if mods:
            time1_mod = mods['time1']
            time2_mod = mods['time2']
            vol_mod = mods['volume']

            if time1_mod:
                grow_time = modifications.get_growing_time(item, time1_mod)
            if time2_mod:
                collect_time = modifications.get_harvest_time(item, time2_mod)
            if vol_mod:
                base_volume = modifications.get_volume(item, vol_mod)

        total_cost = amount * item.gold_price
        total_items = amount * base_volume

        embed = embeds.prompt_embed(
            title=(
                f"Are you really going to grow {amount}x "
                f"{item.emoji} {item_name_capitalized}?"
            ),
            text=(
                "Check out these details and let me know if you approve"
            ),
            ctx=ctx
        )
        embed.add_field(
            name="\ud83e\uddfe Item",
            value=f"{item.emoji} {item_name_capitalized}"
        )
        embed.add_field(
            name="\u2696\ufe0f Quantity",
            value=amount
        )
        embed.add_field(
            name="\ud83d\udcb0 Total costs",
            value=f"{total_cost} {self.bot.gold_emoji}"
        )

        if isinstance(item, game_items.ReplantableItem):
            grow_info = (
                f"{total_items}x {item.emoji} "
                f"{item_name_capitalized} ({item.iterations} times)"
            )
        else:
            grow_info = f"{total_items}x {item.emoji} {item_name_capitalized}"

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

        confirm, msg = await pages.ConfirmPrompt(embed=embed).prompt(ctx)

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
                embed=embeds.error_embed(
                    title="Insufficient gold coins!",
                    text=(
                        f"**You are missing {total_cost - user_data.gold} "
                        f"{self.bot.gold_emoji} for this purchase!** "
                        "I just smashed the piggy and there were no coins "
                        "left too! No, not the pig! \ud83d\udc37 "
                        "The piggy bank!\n "
                    ),
                    footer=f"You have a total of {user_data.gold} gold coins",
                    ctx=ctx
                )
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

        if available_slots < amount:
            await ctx.release()

            return await msg.edit(
                embed=embeds.error_embed(
                    title="Not enough farm space!",
                    text=(
                        f"**Currently you are already using {used_fields} of "
                        f"your {total_slots} farm space tiles**!\n"
                        "I'm sorry to say, but there is no more space for "
                        f"**{amount}x {item.emoji} {item_name_capitalized}**."
                        "\n\nWhat you can do about this:\na) Wait for "
                        "your currently planted items to grow and harvest them"
                        " \nb) Upgrade your farm size if you have gems "
                        f"with **{ctx.prefix}upgrade farm**"
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

            await conn.execute(
                query,
                ctx.author.id,
                item.id,
                total_items,
                iterations,
                amount,
                datetime.now() + timedelta(seconds=grow_time),
                datetime.now() + timedelta(seconds=collect_time),
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
                    f"Successfully started growing {item.emoji} "
                    f"{item_name_capitalized}!"
                ),
                text=(
                    f"Nicely done! **You are now growing {item.emoji} "
                    f"{item_name_capitalized}!** \ud83e\udd20\n"
                    f"You will be able to collect it in: **{grow_time_str}**. "
                    "Just remember to harvest in time, because you will only "
                    f"have limited time to do so... (**{coll_time_str}**)"
                ),
                footer="Check out your farm field with the \"farm\" command",
                ctx=ctx
            )
        )

    @commands.command()
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

        confirm, msg = await pages.ConfirmPrompt(embed=embed).prompt(ctx)

        if not confirm:
            return

        async with ctx.acquire() as conn:
            # Refetch user data, because user could have no money after prompt
            user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

            if total_cost > user_data.gold:
                return await msg.edit(
                    embed=embeds.error_embed(
                        title="Insufficient gold coins!",
                        text=(
                            f"**You are missing {total_cost - user_data.gold} "
                            f"{self.bot.gold_emoji} for this action!**\n "
                            "It looks like you will just need to harvest "
                            "those items, if you like it or not. \ud83d\ude44"
                        ),
                        footer=(
                            f"You have a total of {user_data.gold} gold coins"
                        ),
                        ctx=ctx
                    )
                )

            query = """
                    DELETE FROM farm
                    WHERE user_id = $1;
                    """

            await conn.execute(query, ctx.author.id)

            user_data.gold -= total_cost
            await ctx.users.update_user(user_data, conn=conn)

        await ctx.reply(
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

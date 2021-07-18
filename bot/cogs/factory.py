import discord
from enum import Enum
from datetime import datetime, timedelta
from discord.ext import commands

from .utils import time
from .utils import views
from .utils import embeds
from .utils import checks
from .utils.converters import ItemAndAmount
from core import game_items


class ProductState(Enum):
    QUEUED = 1
    PRODUCING = 2
    READY = 3


class FactoryItem:

    __slots__ = (
        "id",
        "user_id",
        "item",
        "starts",
        "ends"
    )

    def __init__(
        self,
        id: int,
        user_id: int,
        item: game_items.Product,
        starts: datetime,
        ends: datetime
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.item = item
        self.starts = starts
        self.ends = ends

    @property
    def state(self) -> ProductState:
        now = datetime.now()

        if self.starts > now:
            return ProductState.QUEUED
        elif self.ends > now:
            return ProductState.PRODUCING
        else:
            return ProductState.READY


class FactorySource(views.PaginatorSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        total_workers: int,
        total_slots: int,
        used_slots: int,
        has_slots_boost: bool
    ):
        super().__init__(entries, per_page=12)
        self.target_user = target_user
        self.total_workers = total_workers
        self.total_slots = total_slots
        self.used_slots = used_slots
        self.has_slots_boost = has_slots_boost

    async def format_page(self, page, view):
        target = self.target_user

        embed = discord.Embed(
            title=f"\ud83c\udfed {target.nick or target.name}'s factory",
            color=discord.Color.from_rgb(160, 4, 30)
        )

        if not self.has_slots_boost:
            capacity = self.total_slots
        else:
            capacity = f"**{self.total_slots + 2}** \ud83e\udd89"

        header = (
            "\ud83d\udce6 Used factory capacity: "
            f"{self.used_slots}/{capacity}\n"
            "\ud83d\udc68\u200d\ud83c\udf73 Factory workers: "
            f"{self.total_workers} ({self.total_workers *5}% "
            "faster manufacturing)\n\n"
        )

        fmt = ""
        for product in page:
            item = product.item

            if product.state == ProductState.PRODUCING:
                delta_secs = (product.ends - datetime.now()).total_seconds()
                state = f"Manufacturing: {time.seconds_to_time(delta_secs)}"
            elif product.state == ProductState.QUEUED:
                state = "Queued for manufacturing"
            else:
                state = "Ready to be collected"

            fmt += f"**{item.full_name}** - {state}\n"

        embed.description = header + fmt

        return embed


class Factory(commands.Cog):
    """
    In your factory you can turn your harvest into products.
    Manufacturing products gains you more XP and products have higher gold
    value than their raw materials total gold value.

    Unlike in farm, factory can produce only one item per time, but
    you can queue the next items to produce, depending on your
    factory capacity.
    Another benefit is that these items do not get rotten in the factory.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    def parse_db_rows_to_factory_data_objects(self, rows: dict) -> list:
        parsed = []

        for row in rows:
            item = self.bot.item_pool.find_item_by_id(row['item_id'])

            fact_item = FactoryItem(
                id=row['id'],
                user_id=row['user_id'],
                item=item,
                starts=row['starts'],
                ends=row['ends']
            )

            parsed.append(fact_item)

        return parsed

    @commands.command(aliases=["fa"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def factory(self, ctx, *, member: discord.Member = None):
        """
        \ud83c\udfed Shows your or someone's factory

        With this command you can check what are you currently manufacturing
        and what items are queued for manufacturing next.

        __Explanation__:
        If the product is **"Queued"** - that means that your product is
        scheduled for production, and it is going to be manufactured
        after the previous products will be ready.

        if the product is **"Manufacturing"** - that means that this product
        is currently being manufactured, and it is going to be collectable
        right after the specified duration.

        If the product is **"Ready"** - that means that the product is
        finally ready to be collected with the **{prefix}collect** command.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `factory` - view your factory
        {prefix} `factory @user` - view user's factory
        """
        if not member:
            user = ctx.user_data
            target_user = ctx.author
        else:
            user = await checks.get_other_member(ctx, member)
            target_user = member

        async with ctx.acquire() as conn:
            factory_data = await user.get_factory(ctx, conn=conn)

        if not factory_data:
            if not member:
                error_title = (
                    "You are not manufacturing anything in your factory!"
                )
            else:
                error_title = (
                    f"Nope, {member} is not manufacturing anything "
                    "in their factory"
                )

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=error_title,
                    text=(
                        "\ud83c\udfed Start manufacturing products with the "
                        f"**{ctx.prefix}make** command"
                    ),
                    ctx=ctx
                )
            )

        factory_parsed = self.parse_db_rows_to_factory_data_objects(
            factory_data
        )

        paginator = views.ButtonPaginatorView(
            source=FactorySource(
                factory_parsed,
                target_user,
                user.factory_level,
                user.factory_slots,
                len(factory_parsed),
                await user.is_boost_active(ctx, "factory_slots")
            )
        )

        await paginator.start(ctx)

    @commands.command(aliases=["craft", "produce"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def make(self, ctx, *, item: ItemAndAmount, amount: int = 1):
        """
        \ud83d\udce6 Adds a product to the manufacturing queue

        You can only queue products, if you have enough queue capacity.
        To upgrade your factory capacity, use the **{prefix}upgrade capacity**
        command.

        __Arguments__:
        `item` - product to produce (item's name or ID).
        __Optional arguments__:
        `amount` - specify how many products of this type to queue

        __Usage examples__:
        {prefix} `make green salad` - produce green salad
        {prefix} `make green salad 2` - produce 2 items of green salad
        {prefix} `make 701 2` - produce 2 items of green salad (by using ID)
        """
        item, amount = item

        if not isinstance(item, game_items.Product):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=f"{item.name.capitalize()} is not a product!",
                    text=(
                        f"Our factory can't manufacture **{item.full_name}**! "
                        "You will have to obtain these in some other way... "
                        "\ud83e\udd14"
                    ),
                    footer=(
                        "Check out the \"market factory\" command to discover "
                        "manufacturable items"
                    ),
                    ctx=ctx
                )
            )

        if item.level > ctx.user_data.level:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="\ud83d\udd12 You haven't unlocked this item yet!",
                    text=(
                        f"You can't produce **{item.full_name}**, "
                        f"because you have not unlocked this product yet. "
                        "One day we will be leading the world's market "
                        f"in {item.name} production. I promise! \ud83d\ude07"
                    ),
                    footer=(
                        "This item is going to be unlocked at "
                        f"experience level {item.level}."
                    ),
                    ctx=ctx
                )
            )

        has_slots_boost = await ctx.user_data.is_boost_active(
            ctx, "factory_slots"
        )

        factory_slots = ctx.user_data.factory_slots
        if has_slots_boost:
            factory_slots += 2

        async with ctx.acquire() as conn:
            query = """
                    SELECT COUNT(*) FROM factory
                    WHERE user_id = $1;
                    """

            used_slots = await conn.fetchval(query, ctx.author.id)

            if used_slots + amount > factory_slots:
                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="Not enough factory capacity!",
                        text=(
                            f"**You are already currently using {used_slots} "
                            f"of your {factory_slots} factory queue slots**!\n"
                            f"There is no more space for your **{amount}x "
                            f"{item.full_name}**.\n\nWhat you can do about "
                            "this:\na) Wait for your currently manufacturing "
                            "products to be produced and collect them.\nb) "
                            "Upgrade your factory capacity if you have gems "
                            f"with: **{ctx.prefix}upgrade capacity**."
                        ),
                        ctx=ctx
                    )
                )

            user_items = await ctx.user_data.get_all_items(ctx, conn=conn)

        missing_items = []

        if user_items:
            for iaa in item.made_from:
                req_item, req_amt = iaa.item, iaa.amount * amount

                try:
                    item_data = next(
                        x for x in user_items if x['item_id'] == req_item.id
                    )

                    if item_data['amount'] < req_amt:
                        missing_items.append(
                            (req_item, req_amt - item_data['amount'])
                        )
                except StopIteration:
                    missing_items.append((req_item, req_amt))
        else:
            for iaa in item.made_from:
                missing_items.append((iaa.item, iaa.amount * amount))

        if missing_items:
            fmt = ""
            for req_item, req_amt in missing_items:
                fmt += f"{req_item.full_name} x{req_amt}, "

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "You are missing raw materials for this product!"
                    ),
                    text=(
                        "The factory can't start manufacturing: "
                        f"**{amount}x {item.full_name}**, because you "
                        f"are missing these raw materials: **{fmt[:-2]}**\n"
                        "Gather these required items and try again! "
                        "\ud83e\uddee"
                    ),
                    ctx=ctx
                )
            )

        async with ctx.acquire() as conn:
            async with conn.transaction():
                for iaa in item.made_from:
                    await ctx.user_data.remove_item(
                        ctx, iaa.item.id, iaa.amount * amount, conn=conn
                    )

                query = """
                        SELECT ends FROM factory
                        WHERE user_id = $1
                        ORDER BY ends DESC
                        LIMIT 1;
                        """

                craft_seconds = item.craft_time_by_factory_level(
                    ctx.user_data.factory_level
                )
                oldest = await conn.fetchval(query, ctx.author.id)

                if not oldest or oldest < datetime.now():
                    oldest = datetime.now()

                to_insert = []

                for _ in range(amount):
                    ends = oldest + timedelta(seconds=craft_seconds)
                    to_insert.append((ctx.author.id, item.id, oldest, ends))

                    oldest = ends

                query = """
                        INSERT INTO factory
                        (user_id, item_id, starts, ends)
                        VALUES ($1, $2, $3, $4);
                        """

                await conn.executemany(query, to_insert)

        await ctx.reply(
            embed=embeds.success_embed(
                title="Products queued for manufacturing! \ud83d\ude9a",
                text=(
                    "Done! I've sent your resources to the factory "
                    f"to manufacture: **{amount}x {item.full_name}**!\n"
                    "Now we have to wait a bit while the factory "
                    "workers are doing their thing. \u23f3"
                ),
                footer=(
                    "Track the manufacturing progress with \"factory\" command"
                ),
                ctx=ctx
            )
        )

    @commands.command(aliases=["coll", "c"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def collect(self, ctx):
        """
        \ud83d\ude9a Collects the manufactured products from your factory

        Only items that are ready can be collected.
        Use command **{prefix}factory** to check which of your products
        are currently ready to be collected.
        """
        conn = await ctx.acquire()
        factory_data = await ctx.user_data.get_factory(ctx, conn=conn)

        if not factory_data:
            await ctx.release()

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "You are not manufacturing anything in "
                        "your factory!"
                    ),
                    text=(
                        "There is nothing to collect from the factory, "
                        "because you are not even manufacturing anything. "
                        "\ud83e\udd14\nProduce product items with the "
                        f"**{ctx.prefix}make** command \ud83d\udce6"
                    ),
                    ctx=ctx
                )
            )

        parsed_data = self.parse_db_rows_to_factory_data_objects(factory_data)

        to_collect, to_award, xp_gain = [], {}, 0

        for product in parsed_data:
            if product.state == ProductState.READY:
                to_collect.append((product.id, ))

                try:
                    to_award[product.item] += 1
                except KeyError:
                    to_award[product.item] = 1

                xp_gain += product.item.xp

        if not to_collect:
            await ctx.release()

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "Your items are still being manufactured! \ud83d\udce6"
                    ),
                    text=(
                        "Please be patient! Your products are being "
                        "manufactured by the hard working factory workers! "
                        "\ud83d\udc68\u200d\ud83c\udf73\n"
                        "Check out your remaining item production durations "
                        f"with the **{ctx.prefix}factory** command. \n"
                    ),
                    ctx=ctx
                )
            )

        to_award = list(to_award.items())

        async with conn.transaction():
            query = """
                    DELETE FROM factory
                    WHERE id = $1;
                    """

            await conn.executemany(query, to_collect)

            await ctx.user_data.give_items(ctx, to_award, conn=conn)

            ctx.user_data.xp += xp_gain
            await ctx.users.update_user(ctx.user_data, conn=conn)

        await ctx.release()

        fmt = ", ".join(f"{y}x {x.full_name}" for x, y in to_award)

        await ctx.reply(
            embed=embeds.success_embed(
                title="You collected products from the factory! \ud83d\ude9a",
                text=(
                    "Well done! I just arrived from the factory with freshly "
                    f"fragrant: **{fmt}**.\nYou also received "
                    f"**+{xp_gain} XP {self.bot.xp_emoji}**"
                ),
                footer="These products are now moved to your inventory",
                ctx=ctx
            )
        )


def setup(bot):
    bot.add_cog(Factory(bot))

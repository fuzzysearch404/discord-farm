import discord
import datetime
from enum import Enum
from typing import Optional

from core.game_items import Product
from .util import views
from .util import time as time_util
from .util import embeds as embed_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


class FactoryCollection(FarmCommandCollection):
    """
    Just a few miles away from the town, there is an old factory. Coincidentally, the factory is
    also a part of the farm you moved to, so you have full control over it. However, you might
    need to hire some workers to help you out and upgrading the warehouse for more productivity.
    <br><br>In your factory you can turn your harvest into products. Manufacturing products gains
    you more XP and products have higher gold value than the gold value of their raw materials
    combined.<br>
    Unlike in farm, factory can produce only one item per time, but you can queue the next items
    to produce, depending on the capacity of your factory.
    However, the benefit is that these items will never get rotten in the factory, so you don't
    have to hurry to collect your production.
    """
    help_emoji: str = "\N{FACTORY}"
    help_short_description: str = "Manufacture products from your harvest"

    def __init__(self, client):
        super().__init__(client, [FactoryCommand], name="Factory")


class ProductState(Enum):
    QUEUED = 1
    PRODUCING = 2
    READY = 3


class FactoryItem:

    __slots__ = ("id", "user_id", "item", "starts", "ends")

    def __init__(
        self,
        id: int,
        user_id: int,
        item: Product,
        starts: datetime.datetime,
        ends: datetime.datetime
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.item = item
        self.starts = starts
        self.ends = ends

    @property
    def state(self) -> ProductState:
        now = datetime.datetime.now()

        if self.starts > now:
            return ProductState.QUEUED
        elif self.ends > now:
            return ProductState.PRODUCING
        else:
            return ProductState.READY


def _parse_db_rows_to_factory_data_objects(client, rows: list) -> list:
    parsed = []

    for row in rows:
        item = client.item_pool.find_item_by_id(row['item_id'])
        parsed.append(FactoryItem(
            id=row['id'],
            user_id=row['user_id'],
            item=item,
            starts=row['starts'],
            ends=row['ends']
        ))

    return parsed


class FactorySource(views.AbstractPaginatorSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        total_workers: int,
        total_slots: int,
        used_slots: int,
        has_slots_boost: bool,
        last_item_timestamp: str
    ):
        super().__init__(entries, per_page=12)
        self.target_name = target_user.nick or target_user.name
        self.total_workers = total_workers
        self.total_slots = total_slots
        self.used_slots = used_slots
        self.has_slots_boost = has_slots_boost
        self.last_item_timestamp = last_item_timestamp

    def format_product_info(self, factory_item: FactoryItem) -> str:
        if factory_item.state == ProductState.PRODUCING:
            delta_secs = (factory_item.ends - datetime.datetime.now()).total_seconds()
            state = f"Manufacturing: {time_util.seconds_to_time(delta_secs)}"
        elif factory_item.state == ProductState.QUEUED:
            state = "Queued for manufacturing"
        else:
            state = "Ready to be collected"

        return f"**{factory_item.item.full_name}** - {state}"

    async def format_page(self, page, view):
        embed = discord.Embed(
            title=f"\N{FACTORY} {self.target_name}'s factory",
            color=discord.Color.from_rgb(160, 4, 30)
        )

        if not self.has_slots_boost:
            capacity = self.total_slots
        else:
            capacity = f"**{self.total_slots + 2}** \N{OWL}"

        header = (
            f"\N{PACKAGE} Used factory queue capacity: {self.used_slots}/{capacity}\n"
            "\N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING} Factory workers: "
            f"{self.total_workers} ({self.total_workers * 5}% faster manufacturing)"
        )

        if self.last_item_timestamp:
            header += (
                "\n\N{HOURGLASS WITH FLOWING SAND} All products are going to be finished: "
                f"{self.last_item_timestamp}"
            )

        embed.description = header + "\n\n" + "\n".join(
            self.format_product_info(product)
            for product in page
        )
        return embed


class FactoryCommand(FarmSlashCommand, name="factory"):
    _required_level: int = 3


class FactoryQueueCommand(
    FactoryCommand,
    name="queue",
    description="\N{FACTORY} Shows your or someone else's factory status",
    parent=FactoryCommand
):
    """
    With this command you can see what products you or someone else is currently producing in the
    factory. It displays the product queue, manufacturing statuses for items and timers.<br><br>
    __Manufacturing statuses__:<br>
    **"Queued"** - indicates that this product is scheduled for production, and it is going to be
    manufactured after the previous products in the list will be ready.<br>
    **"Manufacturing"** - indicates that this product is currently being manufactured, and it's
    going to be collectable after the specified duration.<br>
    **"Ready"** - indicates that this product is ready to be collected with the **/factory collect**
    command.<br><br>
    __Icon descriptions:__<br>
    \N{OWL} - indicates that the factory size booster "Alice" is activated.<br>
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose factory queue to view"
    )

    async def callback(self):
        async with self.acquire() as conn:
            if not self.player:
                user = self.user_data
                target_user = self.author
            else:
                user = await self.lookup_other_player(self.player, conn=conn)
                target_user = self.player

            factory_data = await user.get_factory(conn)

        if not factory_data:
            if not self.player:
                error_title = "You are not manufacturing anything in your factory!"
            else:
                name = target_user.nick or target_user.name
                error_title = f"{name} is not manufacturing anything in their factory"

            embed = embed_util.error_embed(
                title=error_title,
                text="\N{FACTORY} Start manufacturing products with the **/factory make** command",
                cmd=self
            )
            return await self.reply(embed=embed)

        factory_parsed = _parse_db_rows_to_factory_data_objects(self.client, factory_data)
        # Sorted by starting time
        last_product_in_queue = factory_parsed[-1]
        if last_product_in_queue.state != ProductState.READY:
            factory_fully_ready_in = time_util.maybe_timestamp(last_product_in_queue.ends)
        else:
            factory_fully_ready_in = None

        await views.ButtonPaginatorView(
            self,
            source=FactorySource(
                entries=factory_parsed,
                target_user=target_user,
                total_workers=user.factory_level,
                total_slots=user.factory_slots,
                used_slots=len(factory_parsed),
                has_slots_boost=await user.is_boost_active(self, "factory_slots"),
                last_item_timestamp=factory_fully_ready_in
            )
        ).start()


class FactoryMakeCommand(
    FactoryCommand,
    name="make",
    description="\N{PACKAGE} Queues a product for manufacturing",
    parent=FactoryCommand
):
    """
    You can only queue a limited amount of products at a time, based on your factory capacity.
    You can only manufacture a product if you have enough ingredients.<br>
    \N{ELECTRIC LIGHT BULB} You can check what and how many raw materials you need, to make a
    product, by using **/items inspect**.
    In the **/shop** you can buy more queue slots for your factory and upgrade your factory
    production speed, by buying the factory workers upgrade.
    """
    product: str = discord.app.Option(description="Product to manifacture", autocomplete=True)
    amount: Optional[int] = discord.app.Option(
        description="How many products of this type to manifacture",
        min=1,
        max=100,
        default=1
    )

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.products_autocomplete(options[focused]))

    async def callback(self):
        item = self.lookup_item(self.product)

        if not isinstance(item, Product):
            embed = embed_util.error_embed(
                title=f"{item.full_name} is not a factory product!",
                text=(
                    f"Sorry, but our factory can't manufacture **{item.full_name}**! "
                    "I guess you will have to obtain these in some other way... \N{THINKING FACE}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        if item.level > self.user_data.level:
            embed = embed_util.error_embed(
                title="\N{LOCK} You haven't unlocked this item yet!",
                text=(
                    f"You can't produce **{item.full_name}** yet, because you haven't unlocked "
                    "this product yet.\nOne day we will be leading the world's market in "
                    f"{item.name} production. I am sure - for sure! \N{MONEY-MOUTH FACE}"
                ),
                footer=f"This item is going to be unlocked at experience level {item.level}.",
                cmd=self
            )
            return await self.reply(embed=embed)

        has_slots_boost = await self.user_data.is_boost_active(self, "factory_slots")
        total_factory_slots = self.user_data.factory_slots
        if has_slots_boost:
            total_factory_slots += 2

        conn = await self.acquire()
        query = "SELECT COUNT(*) FROM factory WHERE user_id = $1;"
        used_slots = await conn.fetchval(query, self.author.id)

        if (used_slots + self.amount) > total_factory_slots:
            await self.release()
            embed = embed_util.error_embed(
                title="Not enough factory capacity to start the manifacturing!",
                text=(
                    f"**You are currently already using {used_slots} of your {total_factory_slots} "
                    f"factory queue slots**!\nThere is no more space for **{self.amount}x "
                    f"{item.full_name}**.\n\n\N{ELECTRIC LIGHT BULB} What you can do about this:\n"
                    "a) Wait for your currently manufacturing products to be produced and collect "
                    "them.\nb) Upgrade your factory capacity if you have gems with: "
                    "**/shop upgrades buy \"factory capacity\"**."
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        user_items = await self.user_data.get_all_items(conn)
        user_items_by_id = {item['item_id']: item for item in user_items}

        missing_items = []
        for item_and_amount in item.made_from:
            req_item, req_amt = item_and_amount[0], item_and_amount[1] * self.amount
            try:
                item_data = user_items_by_id[req_item.id]
                if item_data['amount'] < req_amt:
                    missing_items.append((req_item, req_amt - item_data['amount']))
            except KeyError:
                missing_items.append((req_item, req_amt))

        if missing_items:
            await self.release()
            fmt = ", ".join(f"{req_itm.full_name} x{req_amt}" for req_itm, req_amt in missing_items)
            embed = embed_util.error_embed(
                title="You are missing raw materials for this product!",
                text=(
                    f"The factory can't start manufacturing: **{self.amount}x {item.full_name}**, "
                    f"because you are missing these raw materials: **{fmt}**\n\n"
                    "Please gather these required items and try again! \N{ABACUS}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        async with conn.transaction():
            to_remove = [(iaa[0], iaa[1] * self.amount) for iaa in item.made_from]
            await self.user_data.remove_items(to_remove, conn)

            query = "SELECT ends FROM factory WHERE user_id = $1 ORDER BY ends DESC LIMIT 1;"
            last_ends_in_queue = await conn.fetchval(query, self.author.id)

            now = datetime.datetime.now()
            if not last_ends_in_queue or last_ends_in_queue < now:
                last_ends_in_queue = now

            to_insert = []
            craft_seconds = item.craft_time_by_factory_level(self.user_data.factory_level)
            for _ in range(self.amount):
                ends = last_ends_in_queue + datetime.timedelta(seconds=craft_seconds)
                to_insert.append((self.author.id, item.id, last_ends_in_queue, ends))
                last_ends_in_queue = ends

            query = "INSERT INTO factory (user_id, item_id, starts, ends) VALUES ($1, $2, $3, $4);"
            await conn.executemany(query, to_insert)

        await self.release()

        embed = embed_util.success_embed(
            title="Products have been queued for manufacturing! \N{DELIVERY TRUCK}",
            text=(
                "Done! I've sent your resources to the factory to manufacture: "
                f"**{self.amount}x {item.full_name}**!\nNow we have to wait a bit while the "
                "factory workers are doing their thing. \N{HOURGLASS WITH FLOWING SAND}"
            ),
            footer="Track the manufacturing progress with the \"/factory queue\" command",
            cmd=self
        )
        await self.reply(embed=embed)


class FactoryCollectCommand(
    FactoryCommand,
    name="collect",
    description="\N{DELIVERY TRUCK} Collects the manufactured products from your factory",
    parent=FactoryCommand
):
    """
    This command moves the production of your factory to the inventory.
    You can only collect items that are finished being manufactured.<br>
    \N{ELECTRIC LIGHT BULB} Use **/factory queue** to check which of your products are ready to be
    collected.
    """

    async def callback(self):
        conn = await self.acquire()
        factory_data = await self.user_data.get_factory(conn)

        if not factory_data:
            await self.release()
            embed = embed_util.error_embed(
                title="You are not manufacturing anything in your factory!",
                text=(
                    "There is nothing to collect from the factory, because you are not even "
                    "manufacturing anything. \N{THINKING FACE}\nProduce product items with the "
                    "**/factory make** command \N{PACKAGE}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        parsed_factory = _parse_db_rows_to_factory_data_objects(self.client, factory_data)

        to_delete, to_award, xp_gain = [], {}, 0
        for product in parsed_factory:
            if product.state == ProductState.READY:
                to_delete.append((product.id, ))

                try:
                    to_award[product.item] += 1
                except KeyError:
                    to_award[product.item] = 1

                xp_gain += product.item.xp

        if not to_delete:
            await self.release()
            embed = embed_util.error_embed(
                title="Your items are still being manufactured! \N{PACKAGE}",
                text=(
                    "Please be patient! Your products are being manufactured by the hard working "
                    "factory workers! \N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING}\nCheck out your "
                    "remaining item production durations with the **/factory queue** command. "
                    "\N{ALARM CLOCK}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        to_award = list(to_award.items())
        async with conn.transaction():
            query = "DELETE FROM factory WHERE id = $1;"
            await conn.executemany(query, to_delete)
            await self.user_data.give_items(to_award, conn)
            self.user_data.give_xp_and_level_up(self, xp_gain)
            await self.users.update_user(self.user_data, conn=conn)
        await self.release()

        fmt = ", ".join(f"{amount}x {item.full_name}" for item, amount in to_award)
        embed = embed_util.success_embed(
            title="You collected products from the factory! \N{DELIVERY TRUCK}",
            text=(
                f"Well done! I just arrived from the factory with freshly fragrant: **{fmt}**.\n"
                f"Also you received **+{xp_gain} XP {self.client.xp_emoji}**"
            ),
            footer="These products are now moved to your /inventory",
            cmd=self
        )
        await self.reply(embed=embed)


def setup(client) -> list:
    return [FactoryCollection(client)]

import discord
import datetime
from enum import Enum
from typing import Optional

from core import game_items
from .util import views
from .util import exceptions
from .util import time as time_util
from .util import embeds as embed_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


class FarmCollection(FarmCommandCollection):
    """
    Commands for crop, animal and tree growing.<br><br>
    This is your land, where you can plant whatever you want. However, the space here is not so big,
    as you may think, so you will have to think ahead what and how much to plant at a time.
    Also the timing is very important - make sure to plant only things that you think you will be
    able to harvest in time. Nobody in this town is buying rotten harvest...
    """
    help_emoji: str = "\N{SEEDLING}"
    help_short_description: str = "Plant, grow and harvest"

    def __init__(self, client):
        super().__init__(client, [FarmCommand], name="Farm")


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
        ends: datetime.datetime,
        dies: datetime.datetime,
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
        now = datetime.datetime.now()
        if self.ends > now:
            return PlantState.GROWING
        elif self.dies > now:
            return PlantState.COLLECTABLE
        else:
            return PlantState.ROTTEN

    @property
    def is_harvestable(self) -> bool:
        state = self.state
        return state == PlantState.COLLECTABLE or state == PlantState.ROTTEN and self.cat_boost

    @property
    def is_stealable(self) -> bool:
        state = self.state
        return state == PlantState.COLLECTABLE and self.robbed_fields < self.fields_used


def _parse_db_rows_to_plant_data_objects(client, rows: dict) -> list:
    parsed = []

    for row in rows:
        item = client.item_pool.find_item_by_id(row['item_id'])
        parsed.append(PlantedFieldItem(
            id=row['id'],
            item=item,
            amount=row['amount'],
            iterations=row['iterations'],
            fields_used=row['fields_used'],
            ends=row['ends'],
            dies=row['dies'],
            robbed_fields=row['robbed_fields'],
            cat_boost=row['cat_boost']
        ))

    return parsed


class FarmFieldSource(views.AbstractPaginatorSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        used_slots: int,
        total_slots: int,
        has_slots_boost: bool,
        has_stealable_fields: bool,
        farm_guard: int
    ):
        super().__init__(entries, per_page=12)
        self.target_name = target_user.nick or target_user.name
        self.used_slots = used_slots
        self.total_slots = total_slots
        self.has_slots_boost = has_slots_boost
        self.has_stealable_fields = has_stealable_fields
        self.farm_guard = farm_guard

    def group_by_class(self, page: list) -> dict:
        grouped = {}
        for entry in page:
            try:
                grouped[entry.item.__class__].append(entry)
            except KeyError:
                grouped[entry.item.__class__] = [entry]

        return grouped

    def format_plant_info(self, plant: PlantedFieldItem) -> str:
        item = plant.item

        if plant.state == PlantState.GROWING:
            delta_secs = (plant.ends - datetime.datetime.now()).total_seconds()
            state = f"Growing: {time_util.seconds_to_time(delta_secs)}"
        elif plant.state == PlantState.COLLECTABLE and not plant.cat_boost:
            delta_secs = (plant.dies - datetime.datetime.now()).total_seconds()
            time_fmt = time_util.seconds_to_time(delta_secs)

            if isinstance(item, game_items.ReplantableItem):
                state = f"Collectable for: {time_fmt}"
            else:
                state = f"Harvestable for: {time_fmt}"
        elif plant.cat_boost:
            if isinstance(item, game_items.ReplantableItem):
                state = "Collectable"
            else:
                state = "Harvestable"
        else:
            state = "Rotten (not collected in time)"

        em = "\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}"
        if isinstance(item, game_items.Crop):
            result = f"**{item.full_name} x{plant.amount}** - {state}"
        elif isinstance(item, game_items.Tree):
            result = f"**{item.full_name} x{plant.amount} | {em} {plant.iterations}** - {state}"
        else:
            result = (
                f"**{item.emoji_animal} {item.name.capitalize()} (x{plant.amount} {item.emoji}) "
                f"| {em} {plant.iterations}** - {state}"
            )

        if plant.cat_boost:
            result += " \N{CAT FACE}"

        return result

    async def format_page(self, page, view):
        embed = discord.Embed(
            title=f"\N{SEEDLING} {self.target_name}'s farm field",
            color=discord.Color.from_rgb(119, 178, 85)
        )

        if not self.has_slots_boost:
            total_slots = self.total_slots
        else:
            total_slots = f"**{self.total_slots + 2}** \N{HAMSTER FACE}"

        tile_emoji = view.command.client.tile_emoji
        header = f"{tile_emoji} Farm's used space tiles: {self.used_slots}/{total_slots}.\n\n"

        if self.farm_guard:
            remaining = time_util.seconds_to_time(self.farm_guard)
            header += (
                "\N{SHIELD} Because of Discord's or bot's downtime, for a short period of time, "
                "farm's items can be harvested even if they are rotten, thanks to Farm Guard"
                "\N{TRADE MARK SIGN}!\n\N{TIMER CLOCK} Farm Guard is going to be active for: "
                f"**{remaining}**\n\n"
            )

        fmt = ""
        for clazz, plants in self.group_by_class(page).items():
            fmt += f"**{clazz.inventory_name}:**\n"
            for plant_info in plants:
                fmt += self.format_plant_info(plant_info) + "\n"
            fmt += "\n"

        embed.description = header + fmt
        if self.has_stealable_fields:
            embed.set_footer(text="\N{SLEUTH OR SPY} This field has items that could be stolen")

        return embed


class FarmCommand(FarmSlashCommand, name="farm"):
    pass


class FarmFieldCommand(
    FarmSlashCommand,
    name="field",
    description="\N{EAR OF RICE} Shows your or someone else's farm field",
    parent=FarmCommand
):
    """
    With this command you can see what you or someone else is growing right this moment.
    It displays item quantities, growth and timers.<br><br>
    __Item growth__:<br>
    *"Growing"* - indicates that your items are still growing and you will have to wait the
    specified time period until you can harvest your items.<br>
    *"Harvestable"* or *"Collectable"* - indicates that your items are ready, and you can use the
    **/farm harvest** command, to collect those items. You can collect the items for the
    specified period of time, before items get rotten.<br>
    *"Rotten"* - indicates that you have missed the opportunity to collect your items in time,
    and you won't be able to get the items anymore. But you should still use the **/farm harvest**
    command, to free up your farm space for planting new items.
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose farm field to view"
    )

    async def callback(self) -> None:
        if not self.player:
            user = self.user_data
            target_user = self.author
        else:
            user = await self.lookup_other_player(self.player)
            target_user = self.player

        async with self.acquire() as conn:
            field_data = await user.get_farm_field(self, conn=conn)

        if not field_data:
            if not self.player:
                error_title = "You haven't planted anything yet"
            else:
                error_title = f"{target_user.nick or target_user.name} hasn't planted anything yet"

            embed = embed_util.error_embed(
                title=error_title,
                text="\N{SEEDLING} Plant items on your farm field with the **/farm plant** command",
                cmd=self
            )
            raise exceptions.FarmException(embed=embed)

        field_parsed = _parse_db_rows_to_plant_data_objects(self.client, field_data)
        field_guard_seconds = 0
        if self.client.field_guard:
            field_guard_seconds = (self.client.guard_mode - datetime.datetime.now()).total_seconds()

        await views.ButtonPaginatorView(
            self,
            source=FarmFieldSource(
                entries=field_parsed,
                target_user=target_user,
                used_slots=sum(x.fields_used for x in field_parsed),
                total_slots=user.farm_slots,
                has_slots_boost=await user.is_boost_active(self, "farm_slots"),
                has_stealable_fields=any(i.is_stealable for i in field_parsed),
                farm_guard=field_guard_seconds
            )
        ).start()


def setup(client) -> list:
    return [FarmCollection(client)]

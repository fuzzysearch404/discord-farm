import random
import discord
import datetime
from enum import Enum
from typing import Optional, Literal
from contextlib import suppress

from core import game_items
from core import ipc_classes
from core import modifications
from .clusters import get_cluster_collection
from .util import views
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
        super().__init__(client, [FarmCommand, FishCommand], name="Farm")


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
        return self.is_harvestable and self.robbed_fields < self.fields_used


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
            state = "Rotten \N{SKULL}"

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
        header = f"{tile_emoji} Used farm space tiles: {self.used_slots}/{total_slots}.\n\n"

        if self.farm_guard:
            remaining = time_util.seconds_to_time(self.farm_guard)
            header += (
                "\N{SHIELD} Because of the bot's or [Discord's downtime]"
                "(https://discordstatus.com/), for a short period of time, farm items can "
                "be harvested even if they are rotten, thanks to Farm Guard\N{TRADE MARK SIGN}!\n"
                f"\N{TIMER CLOCK} Farm Guard is going to be active for: **{remaining}**\n\n"
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
    and you won't be able to get the items anymore. \N{SKULL} But you should still use the
    **/farm harvest** command, to free up your farm space for planting new items.<br><br>
    __Icon descriptions:__<br>
    \N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} - indicates the number of
    remaining growth cycles for the item. (how many more times it's going to be harvestable).<br>
    \N{HAMSTER FACE} - indicates that the farm size booster "Susan" is activated.<br>
    \N{CAT FACE} - indicates that the item will never get rotten, thanks to the "Leo" booster.<br>
    \N{SHIELD} - indicates that all items can be harvested even if they are rotten, because of
    the safety mechanism that is activated by the bot's or
    [Discord's downtime](https://discordstatus.com/).
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose farm field to view"
    )

    async def callback(self):
        async with self.acquire() as conn:
            if not self.player:
                user = self.user_data
                target_user = self.author
            else:
                user = await self.lookup_other_player(self.player, conn=conn)
                target_user = self.player

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
            return await self.reply(embed=embed)

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


class FarmPlantCommand(
    FarmSlashCommand,
    name="plant",
    description="\N{SEEDLING} Plants crops and trees, grows animals on your farm field",
    parent=FarmCommand
):
    """
    Before planting items on your farm field, make sure that you have enough space for them.
    Every time you want to plant something, it will cost you some gold.
    Each item also has specific growing and harvest durations.<br>
    \N{ELECTRIC LIGHT BULB} To check how much it will cost, and how long it will take for the items
    to grow, use the **/item inspect** command. If you are unsure about what you can afford, you
    can also check the **/shop** command.<br>
    To check item growth status, use the **/farm field** command.
    """
    item: str = discord.app.Option(description="Item to plant on the field", autocomplete=True)
    tiles: int = discord.app.Option(description="How many space tiles to plant in", min=1, max=100)

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.plantables_autocomplete(options[focused]))

    async def send_reminder_to_ipc(self, item_id: int, item_amount: int, when: datetime.datetime):
        cluster_collection = get_cluster_collection(self.client)
        if not cluster_collection:
            return

        reminder = ipc_classes.Reminder(
            user_id=self.author.id,
            channel_id=self.channel.id,
            item_id=item_id,
            amount=item_amount,
            time=when
        )
        await cluster_collection.send_set_reminder_message(reminder)

    async def callback(self):
        item = self.lookup_item(self.item)

        if not isinstance(item, game_items.PlantableItem):
            embed = embed_util.error_embed(
                title=f"{item.name.capitalize()} is not a growable item!",
                text=(
                    "Hey! HEY! YOU! STOP it right there! \N{WEARY CAT FACE} You can't just plant "
                    f"**{item.full_name}** on your farm field! That's illegal! \N{FLUSHED FACE} "
                    "It would be cool though. \N{THINKING FACE}"
                ),
                footer="Check out the shop to discover plantable items",
                cmd=self
            )
            return await self.reply(embed=embed)

        if item.level > self.user_data.level:
            embed = embed_util.error_embed(
                title="\N{LOCK} Insufficient experience level!",
                text=(
                    f"**Sorry, you can't grow {item.full_name} just yet!** I was told by shop "
                    "cashier that they can't let you purchase these, because you are not yet "
                    "experienced enough to handle these, you know? Anyways, this item unlocks "
                    f"at level \N{TRIDENT EMBLEM} **{item.level}**."
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        item_mods = await modifications.get_item_mods_for_user(self, item)
        grow_time, collect_time, max_volume = item_mods[0], item_mods[1], item_mods[2]

        total_cost = self.tiles * item.gold_price
        total_items_min = self.tiles * item.amount  # Default
        total_items_max = self.tiles * max_volume  # With modification
        total_items = random.randint(total_items_min, total_items_max)

        # Don't show the actual amount of items that will be planted if modifications are applied
        if total_items_min != total_items_max:
            total_items_fmt = f"{total_items_min} - {total_items_max}"
        else:
            total_items_fmt = total_items_min

        embed = embed_util.prompt_embed(
            title=f"Are you really going to grow {self.tiles}x tiles of {item.full_name}?",
            text="Check out these purchase details and let me know if you approve",
            cmd=self
        )
        embed.add_field(name="\N{RECEIPT} Item", value=item.full_name)
        embed.add_field(name="\N{SCALES} Quantity", value=f"{self.tiles} farm tiles")
        embed.add_field(
            name="\N{MONEY BAG} Total cost",
            value=f"{total_cost} {self.client.gold_emoji}"
        )

        if isinstance(item, game_items.ReplantableItem):
            grow_info = f"{total_items_fmt}x {item.full_name} ({item.iterations} times)"
        else:
            grow_info = f"{total_items_fmt}x {item.full_name}"

        embed.add_field(name="\N{LABEL} Will grow into", value=grow_info)
        embed.add_field(
            name="\N{MANTELPIECE CLOCK} Growing duration",
            value=time_util.seconds_to_time(grow_time)
        )
        embed.add_field(
            name="\N{MANTELPIECE CLOCK} Maximum harvesting period before item gets rotten",
            value=time_util.seconds_to_time(collect_time)
        )
        embed.set_footer(text=f"You have a total of {self.user_data.gold} gold coins")

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            emoji=self.client.gold_emoji,
            label="Purchase and start growing"
        ).prompt()

        if not confirm:
            return

        boosts = await self.user_data.get_all_boosts(self)
        has_slots_boost = "farm_slots" in [x.id for x in boosts]
        has_cat_boost = "cat" in [x.id for x in boosts]

        conn = await self.acquire()
        # Refetch user data, because user could have no money after prompt
        self.user_data = await self.users.get_user(self.author.id, conn=conn)

        if total_cost > self.user_data.gold:
            await self.release()
            return await self.edit(embed=embed_util.no_money_embed(self, total_cost), view=None)

        query = "SELECT sum(fields_used) FROM farm WHERE user_id = $1;"
        used_fields = await conn.fetchval(query, self.author.id) or 0

        total_slots = self.user_data.farm_slots
        if has_slots_boost:
            total_slots += 2
        available_slots = total_slots - used_fields

        if available_slots < self.tiles:
            await self.release()
            embed = embed_util.error_embed(
                title="Not enough farm space!",
                text=(
                    f"**You are already currently using {used_fields} of your {total_slots} farm "
                    "space tiles**!\nI'm sorry to say, but there is no more space for "
                    f"**{self.tiles} tiles of {item.full_name}**.\n\n"
                    "What you can do about this:\na) Wait for your currently planted items to "
                    "grow and harvest them.\nb) Upgrade your farm size if you have gems "
                    "with: **/upgrade farm**."
                ),
                cmd=self
            )
            return await self.edit(embed=embed, view=None)

        iterations = None
        if isinstance(item, game_items.ReplantableItem):
            iterations = item.iterations
        now = datetime.datetime.now()
        ends = now + datetime.timedelta(seconds=grow_time)
        dies = ends + datetime.timedelta(seconds=collect_time)

        async with conn.transaction():
            query = """
                    INSERT INTO farm
                    (user_id, item_id, amount, iterations, fields_used, ends, dies, cat_boost)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
                    """
            await conn.execute(
                query,
                self.author.id,
                item.id,
                total_items,
                iterations,
                self.tiles,
                ends,
                dies,
                has_cat_boost
            )
            self.user_data.gold -= total_cost
            await self.users.update_user(self.user_data, conn=conn)
        await self.release()

        end_fmt = time_util.maybe_timestamp(ends, since=now)
        dies_fmt = discord.utils.format_dt(dies, style="f")

        embed = embed_util.success_embed(
            title=f"Successfully started growing {item.full_name}!",
            text=(
                f"Nicely done! You are now growing {item.full_name}! \N{FACE WITH COWBOY HAT}\n"
                f"You will be able to collect it: **{end_fmt}**. Just remember to harvest in time, "
                "because you will only have limited time to do so - **items are going to be rotten "
                f"at {dies_fmt}** \N{ALARM CLOCK}"
            ),
            footer="Track your item growth with the \"/farm field\" command",
            cmd=self
        )
        await self.edit(embed=embed, view=None)
        await self.send_reminder_to_ipc(item.id, total_items, ends)


class FarmHarvestCommand(
    FarmSlashCommand,
    name="harvest",
    description="\N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE} Harvests your farm field",
    parent=FarmCommand
):
    """
    Collects the fully grown items and discards the rotten ones from your farm field.
    If you collect tree, bush or animal items, then their next growing cycle begins (if
    the item has growth cycles remaining).<br>
    \N{ELECTRIC LIGHT BULB} To check what you are currently growing and if there are collectable
    items use the **/farm field** command.
    """

    async def send_reminder_to_ipc(self, item_id: int, item_amount: int, when: datetime.datetime):
        cluster_collection = get_cluster_collection(self.client)
        if not cluster_collection:
            return

        reminder = ipc_classes.Reminder(
            user_id=self.author.id,
            channel_id=self.channel.id,
            item_id=item_id,
            amount=item_amount,
            time=when
        )
        await cluster_collection.send_set_reminder_message(reminder)

    async def callback(self):
        conn = await self.acquire()
        field_data = await self.user_data.get_farm_field(self, conn=conn)

        if not field_data:
            await self.release()
            embed = embed_util.error_embed(
                title="You haven't planted anything on your field!",
                text=(
                    "Hmmm... There is literally nothing to harvest, because you did not even plant "
                    "anything. \N{THINKING FACE}\nPlant items on the field with the "
                    "**/farm plant** command \N{SEEDLING}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        field_parsed = _parse_db_rows_to_plant_data_objects(self.client, field_data)
        # Tuples for database queries and reminders
        to_remind, to_reward, update_rows, delete_rows = [], [], [], []
        # Plant objects for displaying in Discord
        harvested_plants, updated_plants, deleted_plants = [], [], []
        xp_gain = 0

        farm_guard_active = self.client.field_guard
        for plant in field_parsed:
            if plant.iterations and plant.iterations > 1:  # Trees, bushes, animals
                if plant.is_harvestable or (farm_guard_active and plant.state == PlantState.ROTTEN):
                    # Calculate the new growth cycle properties
                    item_mods = await modifications.get_item_mods_for_user(
                        self,
                        plant.item,
                        conn=conn
                    )
                    grow_time, collect_time, max_volume = item_mods[0], item_mods[1], item_mods[2]
                    ends = datetime.datetime.now() + datetime.timedelta(seconds=grow_time)
                    dies = ends + datetime.timedelta(seconds=collect_time)
                    amount = random.randint(
                        plant.item.amount * plant.fields_used,
                        max_volume * plant.fields_used
                    )

                    update_rows.append((ends, dies, amount, plant.id))
                    to_reward.append((plant.item.id, plant.amount))
                    to_remind.append((plant.item.id, amount, ends))
                    xp_gain += plant.item.xp * plant.amount
                    updated_plants.append(plant)
                elif plant.state == PlantState.ROTTEN:
                    delete_rows.append((plant.id, ))
                    deleted_plants.append(plant)
            else:  # One time harvest crops
                if plant.is_harvestable or (farm_guard_active and plant.state == PlantState.ROTTEN):
                    delete_rows.append((plant.id, ))
                    to_reward.append((plant.item.id, plant.amount))
                    xp_gain += plant.item.xp * plant.amount
                    harvested_plants.append(plant)
                elif plant.state == PlantState.ROTTEN:
                    delete_rows.append((plant.id, ))
                    deleted_plants.append(plant)

        if not (harvested_plants or updated_plants or deleted_plants):
            await self.release()
            embed = embed_util.error_embed(
                title="Your items are still growing! \N{SEEDLING}",
                text=(
                    "Please be patient! Your items are growing! Soon we will get that huge "
                    "harvest! \N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE}\nCheck out your "
                    "remaining item growing durations with the **/farm field** command.\n"
                    "But don't get too relaxed, because you will have a limited time to "
                    "harvest your items. \N{ALARM CLOCK}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        async with conn.transaction():
            if update_rows:
                query = """
                        UPDATE farm
                        SET ends = $1, dies = $2, amount = $3,
                        iterations = iterations - 1, robbed_fields = 0
                        WHERE id = $4;
                        """
                await conn.executemany(query, update_rows)

            if delete_rows:
                query = "DELETE from farm WHERE id = $1;"
                await conn.executemany(query, delete_rows)

            if to_reward:
                await self.user_data.give_items(self, to_reward, conn=conn)

            self.user_data.give_xp_and_level_up(self, xp_gain)
            await self.users.update_user(self.user_data, conn=conn)

        await self.release()

        def group_plants(plants: list) -> dict:
            grouped = {}
            for plant in plants:
                try:
                    grouped[plant.item] += plant.amount
                except KeyError:
                    grouped[plant.item] = plant.amount

            return grouped

        harvested_plants.extend(updated_plants)

        if deleted_plants and not harvested_plants:
            deleted_plants = group_plants(deleted_plants)
            fm = ", ".join(f"{amount}x {item.full_name}" for item, amount in deleted_plants.items())

            embed = embed_util.error_embed(
                title="Oh no! Your items are gone!",
                text=(
                    "You missed your chance to harvest your items on time, so your items: "
                    f"**{fm}** got rotten! \N{CRYING FACE}\nPlease be more careful next time and "
                    "follow the timers with the **/farm field** command."
                ),
                footer="All rotten items have been removed from your farm",
                cmd=self
            )
            return await self.reply(embed=embed)

        harvested_plants = group_plants(harvested_plants)
        fm = ", ".join(f"{item.full_name} x{amount}" for item, amount in harvested_plants.items())
        fmt = (
            "\N{FACE WITH COWBOY HAT} **You successfully harvested your farm field!**\n"
            f"\N{TRACTOR} You harvested: **{fm}**"
        )

        if updated_plants:
            updated_plants = group_plants(updated_plants)
            fm = ",".join(f"{item.emoji} " for item in updated_plants.keys())
            fmt += (
                "\n\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} Some items are now "
                f"growing their next cycle: {fm}"
            )
        if deleted_plants:
            deleted_plants = group_plants(deleted_plants)
            fm = ", ".join(f"{item.full_name} x{amount}" for item, amount in deleted_plants.items())
            fmt += (
                "\n\n\N{BLACK UNIVERSAL RECYCLING SYMBOL} But some items got rotten and "
                f"had to be discarded: **{fm}** \N{NEUTRAL FACE}"
            )

        fmt += f"\n\nAnd you received: **+{xp_gain} XP** {self.client.xp_emoji}"

        embed = embed_util.success_embed(
            title="You harvested your farm! Awesome!",
            text=fmt,
            footer="Harvested items are now moved to your inventory",
            cmd=self
        )
        await self.reply(embed=embed)

        for reminder_data in to_remind:
            await self.send_reminder_to_ipc(reminder_data[0], reminder_data[1], reminder_data[2])


class FarmClearCommand(
    FarmSlashCommand,
    name="clear",
    description="\N{BROOM} Clears your farm field",
    parent=FarmCommand
):
    """
    Removes all of your currently planted items from your farm field for some small gold price.
    This is a useful command if you planted something by accident and you want to get rid of it, to
    plant something new instead, because the previous items take up your farm space.
    However, these items won't be moved to your inventory and are going to be lost without any
    compensation.<br>
    \N{ELECTRIC LIGHT BULB} Before clearing your farm, make sure to double check what you are
    currently growing with **/farm field**.
    """

    async def send_delete_reminders_to_ipc(self):
        cluster_collection = get_cluster_collection(self.client)
        if not cluster_collection:
            return

        await cluster_collection.send_delete_reminders_message(self.author.id)

    async def callback(self) -> None:
        async with self.acquire() as conn:
            field_data = await self.user_data.get_farm_field(self, conn=conn)

        if not field_data:
            embed = embed_util.error_embed(
                title="You are not growing anything!",
                text=(
                    "Hmmm... This is weird. So you are telling me, that you want to clear your "
                    "farm field, but you are not even growing anything? \N{THINKING FACE}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        total_cost = total_fields = 0
        for data in field_data:
            item = self.items.find_item_by_id(data['item_id'])
            fields_used = data['fields_used']
            total_cost += item.gold_price * fields_used
            total_fields += fields_used
        # 5% of total
        total_cost = int(total_cost / 20) or 1

        embed = embed_util.prompt_embed(
            title="Are you sure that you want to clear your field?",
            text=(
                f"\N{WARNING SIGN} **You are about to lose ALL ({total_fields}) of your currently "
                "growing items on farm field!**\nAnd they are NOT going to be refunded, neither "
                f"moved to your inventory. And this is going to cost extra **{total_cost}** "
                f"{self.client.gold_emoji}! Let's do this? \N{THINKING FACE}"
            ),
            cmd=self
        )

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            style=discord.ButtonStyle.primary,
            emoji=self.client.gold_emoji,
            label="Sure, please clear my farm"
        ).prompt()

        if not confirm:
            return

        conn = await self.acquire()
        # Refetch user data, because user could have no money after prompt
        self.user_data = await self.users.get_user(self.author.id, conn=conn)

        if total_cost > self.user_data.gold:
            await self.release()
            return await self.edit(embed=embed_util.no_money_embed(self, total_cost), view=None)

        async with conn.transaction():
            query = "DELETE FROM farm WHERE user_id = $1;"
            await conn.execute(query, self.author.id)
            self.user_data.gold -= total_cost
            await self.users.update_user(self.user_data, conn=conn)
        await self.release()

        embed = embed_util.success_embed(
            title="Your farm field is cleared!",
            text="Okay, I sent some or my workers to clear up the farm for you! \N{BROOM}",
            footer="Your farm field items have been discarded",
            cmd=self
        )
        await self.edit(embed=embed, view=None)
        await self.send_delete_reminders_to_ipc()


class FarmStealCommand(
    FarmSlashCommand,
    name="steal",
    description="\N{SLEUTH OR SPY} Steals someone else's farm harvest",
    parent=FarmCommand
):
    """
    You can try out your luck and attempt stealing some harvest from other player farms.
    You can only steal items that are fully grown, not rotten and not already stolen from.
    You can't choose what items you will get, it is chosen randomly.
    If the targeted user has a dog booster, your chances of a successful robbery are lower.<br>
    \N{ELECTRIC LIGHT BULB} Use **/farm field @user** to check if some person has items that
    could be stolen. If there are items that could be stolen, it's going to be stated at the very
    bottom.
    """
    invoke_cooldown = 900  # type: int

    player: discord.Member = discord.app.Option(description="Other user, whose farm to rob")

    async def callback(self) -> None:
        if self.player == self.author:
            embed = embed_util.error_embed(
                title="You can't steal from yourself!",
                text="Silly you! Why and how would you ever do this? \N{DISGUISED FACE}",
                cmd=self
            )
            return await self.reply(embed=embed)

        async with self.acquire() as conn:
            target_data = await self.lookup_other_player(self.player, conn=conn)

            query = """
                    SELECT * FROM farm
                    WHERE ends < $1 AND dies > $1
                    AND robbed_fields < fields_used
                    AND user_id = $2;
                    """
            target_field = await conn.fetch(query, datetime.datetime.now(), self.player.id)

        if not target_field:
            target_name = self.player.nick or self.player.name
            embed = embed_util.error_embed(
                title=f"{target_name} currently has nothing to steal from!",
                text=(
                    "Oh no! They don't have any collectable harvest! They most likely saw us "
                    "walking in their farm, so we must hide behind this tree for a few minutes "
                    "\N{WHITE RIGHT POINTING BACKHAND INDEX}\N{DECIDUOUS TREE}. In case they ask "
                    "something - I don't know you. \N{FACE WITH FINGER COVERING CLOSED LIPS}"
                ),
                footer=(
                    "The target user must have items ready for harvest and the items must not be "
                    "already robbed from by you or anyone else"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        caught_chance, caught = 0, False
        target_boosts = await target_data.get_all_boosts(self)
        if target_boosts:
            boost_ids = [boost.id for boost in target_boosts]
            if "dog_3" in boost_ids:
                embed = embed_util.error_embed(
                    title="Harvest stealing attempt failed!",
                    text=(
                        "I went in there to scout out the area and I ran away as fast, as I could, "
                        "because they have a **HUGE** dog out there! \N{DOG} Better to be safe, "
                        "than sorry. \N{FACE WITH COLD SWEAT}"
                    ),
                    cmd=self
                )
                return await self.reply(embed=embed)
            elif "dog_2" in boost_ids and "dog_1" in boost_ids:
                caught_chance = 2
            elif "dog_2" in boost_ids:
                caught_chance = 4
            elif "dog_1" in boost_ids:
                caught_chance = 8

        field, rewards = [], {}
        for data in target_field:
            # If planted multiple same kind of items, split the chances equally
            for _ in range(data['fields_used'] - data['robbed_fields']):
                field.append(data)

        while len(field) > 0:
            current = random.choice(field)
            field.remove(current)

            if caught_chance and not random.randint(0, caught_chance):
                caught = True
                break

            try:
                rewards[current] += 1
            except KeyError:
                rewards[current] = 1

        if not rewards:
            embed = embed_util.error_embed(
                title="We got caught! \N{DISAPPOINTED FACE}",
                text=(
                    f"Oh no! Oh no no no! {self.player.nick or self.player.name} had a dog and I "
                    "got caught! \N{TIRED FACE}\nNow my body hurts badly! But we can try again "
                    "some other time. It was fun! \N{SMILING FACE WITH OPEN MOUTH AND COLD SWEAT}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        to_update, to_reward, won_items_and_amounts = [], [], {}
        for data, field_count in rewards.items():
            item = self.items.find_item_by_id(data['item_id'])
            win_amount = int((item.amount * field_count) * 0.2) or 1
            # For response to user
            try:
                won_items_and_amounts[item] += win_amount
            except KeyError:
                won_items_and_amounts[item] = win_amount
            # For database
            to_update.append((win_amount, field_count, data['id']))
            to_reward.append((data['item_id'], win_amount))

        async with self.acquire() as conn:
            async with conn.transaction():
                query = """
                        UPDATE farm
                        SET amount = amount - $1, robbed_fields = robbed_fields + $2
                        WHERE id = $3;
                        """

                await conn.executemany(query, to_update)
                await self.user_data.give_items(self, to_reward, conn=conn)

        fmt = ", ".join(f"{item.full_name} x{amt}" for item, amt in won_items_and_amounts.items())

        if caught:
            embed = embed_util.success_embed(
                title="Decent attempt, but we almost got caught...",
                text=(
                    f"Okay, so I went in and grabbed these: **{fmt}**! But the dog saw me and I "
                    "had to run, so I did not get all the items! I'm glad that we got away with "
                    "at least something. \N{RUNNER}\N{POODLE}"
                ),
                cmd=self
            )
            await self.reply(embed=embed)
        else:
            embed = embed_util.congratulations_embed(
                title="We did it! You got the jackpot!",
                text=(
                    "We managed to get a bit from all the harvest "
                    f"{self.player.nick or self.player.name} had: **{fmt}** \N{SLEUTH OR SPY}\n"
                    "Now you should better watch out from them, because they won't be happy about "
                    "this! \N{GRIMACING FACE}"
                ),
                cmd=self
            )
            await self.reply(embed=embed)

        if target_data.notifications:
            embed = embed_util.error_embed(
                title=f"{self.author} managed to steal items from your farm! \N{SLEUTH OR SPY}",
                text=(
                    "Hey boss! \N{WAVING HAND SIGN}\n\nI am sorry to say, but someone named "
                    f"\"{self.author.nick or self.author.name}\" managed to grab some items from "
                    f"your farm: **{fmt}**!\n\n\N{ELECTRIC LIGHT BULB}Next time be a bit faster to "
                    "harvest your farm or buy a dog booster for some protection!"
                ),
                private=True,
                cmd=self
            )
            # People could have direct messages closed
            with suppress(discord.HTTPException):
                await self.player.send(embed=embed)


class FishCommand(
    FarmSlashCommand,
    name="fish",
    description="\N{FISHING POLE AND FISH} Goes fishing!"
):
    """
    You can go fishing every hour and catch some random amount of fish!
    <br><br>__Fishing locations:__<br>
    **Pond** - Always has limited amount of fish that are easy to catch.<br>
    **Lake** and **River** - Usually have fish in medium quantities.<br>
    **Sea** - Has large amounts, but hard to catch fish.<br><br>
    __Icon descriptions:__<br>
    \N{BEAR FACE} - indicates that the reward was doubled, because of the "Archie" booster.
    """
    required_level = 17  # type: int
    invoke_cooldown = 3600  # type: int

    location: Literal["Pond", "Lake", "River", "Sea"] = discord.app.Option(
        description="Place where to go fishing to. Different places have different amounts of fish."
    )

    async def callback(self) -> None:
        if self.location == "Pond":
            base_min_amount, base_max_amount, fail_chance = 1, 4, 0
        elif self.location == "Lake":
            base_min_amount, base_max_amount, fail_chance = 2, 10, 1
        elif self.location == "River":
            base_min_amount, base_max_amount, fail_chance = 5, 25, 2
        elif self.location == "Sea":
            base_min_amount, base_max_amount, fail_chance = 12, 64, 4

        if random.randint(0, fail_chance) != 0:
            embed = embed_util.error_embed(
                title="\N{HOOK} Unlucky! No fish at all!",
                text=(
                    f"You went to a {base_min_amount} hour long fishing session to the "
                    f"{self.location.lower()} and could not catch a single fish... "
                    "No worries! Hopefully you will have a better luck next time! \N{WINKING FACE}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        win_amount = random.randint(base_min_amount, base_max_amount)
        has_luck_booster: bool = await self.user_data.is_boost_active(self, "fish_doubler")
        if has_luck_booster:
            win_amount *= 2

        # ID 600 - Fish item
        item = self.items.find_item_by_id(600)
        # Give XP based on the catch
        xp_gain = win_amount * item.xp
        self.user_data.give_xp_and_level_up(self, xp_gain)

        async with self.acquire() as conn:
            async with conn.transaction():
                await self.users.update_user(self.user_data, conn=conn)
                await self.user_data.give_item(self, item.id, win_amount, conn=conn)

        embed = embed_util.congratulations_embed(
            title="Nice catch! You successfully caught some fish! \N{FISHING POLE AND FISH}",
            text=(
                f"You went to the {self.location.lower()} and caught: **{win_amount}x** \N{FISH} "
                f"**+{xp_gain} XP** {self.client.xp_emoji}"
            ),
            cmd=self
        )
        if has_luck_booster:
            embed.description += " (x2 with \N{BEAR FACE})"

        await self.reply(embed=embed)


def setup(client) -> list:
    return [FarmCollection(client)]

import random
import discord
import datetime
from typing import Optional

from core import game_items
from core import modifications
from .util import views
from .util import exceptions
from .util import embeds as embed_util
from .util import time as time_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


class ProfileCollection(FarmCommandCollection):
    """Commands for general use, mostly related to player individual profiles."""
    help_emoji: str = "\N{HOUSE WITH GARDEN}"
    help_short_description: str = "Various game profile and item commands"

    def __init__(self, client) -> None:
        super().__init__(
            client,
            [
                ProfileCommand,
                BalanceCommand,
                InventoryCommand,
                BoostersCommand,
                ItemsCommand,
                ChestsCommand
            ],
            name="Profile"
        )


class InventorySource(views.AbstractPaginatorSource):

    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        inventory_category: str,
        inventory_emoji: str
    ):
        super().__init__(entries, per_page=30)
        self.target_name = target_user.nick or target_user.name
        self.inventory_category = inventory_category
        self.inventory_emoji = inventory_emoji

    async def format_page(self, page, view):
        embed = discord.Embed(
            title=f"{view.command.client.warehouse_emoji} {self.target_name}'s warehouse",
            color=discord.Color.from_rgb(234, 231, 231)
        )

        fmt, iteration = "", 0
        for item_and_amount in page:
            iteration += 1
            item, amount = item_and_amount[0], item_and_amount[1]

            # 3 items per line
            if iteration <= 3:
                fmt += f"{item.full_name} x{amount} "
            else:
                fmt += f"\n{item.full_name} x{amount} "
                iteration = 1

        view.select_source.placeholder = f"{self.inventory_emoji} {self.inventory_category}"
        embed.description = fmt
        return embed


class AllItemsSource(views.AbstractPaginatorSource):

    def __init__(self, entries: list):
        super().__init__(entries, per_page=15)

    async def format_page(self, page, view):
        head = "\N{LABEL} Item - \N{TRIDENT EMBLEM} Unlocked at level\n\n"
        fmt = "\n".join(f"**{i.full_name}** - Level {i.level}" for i in page)

        return discord.Embed(
            title="\N{OPEN LOCK} All items unlocked for your level:",
            color=discord.Color.from_rgb(255, 172, 51),
            description=head + fmt
        )


class ProfileCommand(
    FarmSlashCommand,
    name="profile",
    description="\N{HOUSE BUILDING} Shows your or someone else's profile"
):
    """
    This is the first command to use, when you want to see your overall game progress.<br>
    It provides a lot of information about your profile, including your current level, resources,
    timers on different features, and more.<br>
    Looking at other people's profiles is also possible, and it is a nice way to see how other
    people are doing.<br><br>
    __Icon descriptions:__<br>
    \N{HAMSTER FACE} - indicates that the farm size booster "Susan" is activated.<br>
    \N{OWL} - indicates that the factory size booster "Alice" is activated.
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose profile to view"
    )

    async def callback(self) -> None:
        async with self.acquire() as conn:
            if not self.player:
                user = self.user_data
                target_user = self.author
                mention = ""
            else:
                user = await self.lookup_other_player(self.player, conn=conn)
                target_user = self.player
                mention = target_user.mention

            # See schema.sql for this function
            query = "SELECT get_profile_stats($1, $2);"
            profile_stats = await conn.fetchrow(query, user.user_id, self.guild.id)
        # Function returns a nested record
        profile_stats = profile_stats[0]

        total_farm_slots = user.farm_slots
        has_boosters_unlocked: bool = user.level > 6
        if has_boosters_unlocked:
            all_boosts = await user.get_all_boosts(self)
            all_active_boost_ids = [b.id for b in all_boosts]

            if "farm_slots" in all_active_boost_ids:
                total_farm_slots += 2
                total_farm_slots_formatted = f"**{total_farm_slots}** \N{HAMSTER FACE}"
            else:
                total_farm_slots_formatted = total_farm_slots
            if "factory_slots" in all_active_boost_ids:
                factory_slots_formatted = f"**{user.factory_slots + 2}** \N{OWL}"
            else:
                factory_slots_formatted = user.factory_slots
        else:
            total_farm_slots_formatted = total_farm_slots
            factory_slots_formatted = user.factory_slots

        inventory_size = profile_stats.get("inventory_size") or 0
        farm_slots_used = profile_stats.get("farm_slots_used") or 0
        store_slots_used = profile_stats.get("store_slots_used") or 0

        free_farm_slots = total_farm_slots - farm_slots_used
        if free_farm_slots < 0:  # Expired +2 farm slots booster visual bug fix
            free_farm_slots = 0

        datetime_now = datetime.datetime.now()

        nearest_harvest = profile_stats.get("nearest_harvest")
        if nearest_harvest:
            if nearest_harvest > datetime_now:
                nearest_harvest = time_util.maybe_timestamp(nearest_harvest, since=datetime_now)
            else:
                nearest_harvest = self.client.check_emoji
        else:
            nearest_harvest = "-"

        nearest_factory = profile_stats.get("nearest_factory_production")
        if nearest_factory:
            if nearest_factory > datetime_now:
                nearest_factory = time_util.maybe_timestamp(nearest_factory, since=datetime_now)
            else:
                nearest_factory = self.client.check_emoji
        else:
            nearest_factory = "-"

        has_lab_unlocked: bool = user.level > 1
        if has_lab_unlocked:
            lab_info = f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/laboratory view** {mention}"
            lab_cd = await self.get_cooldown_ttl("recent_research", other_user_id=user.user_id)
            if lab_cd:
                lab_cd_ends = datetime_now + datetime.timedelta(seconds=lab_cd)
                lab_cd_ends = time_util.maybe_timestamp(lab_cd_ends)
                lab_info = f"\N{BROOM} Available again: {lab_cd_ends}\n" + lab_info

        embed = discord.Embed(
            title=f"\N{HOUSE WITH GARDEN} {target_user.nick or target_user.name}'s profile",
            color=discord.Color.from_rgb(196, 98, 12)
        )
        embed.add_field(
            name=f"\N{TRIDENT EMBLEM} {user.level}. level",
            value=f"{self.client.xp_emoji} {user.xp}/{user.next_level_xp}"
        )
        embed.add_field(name=f"{self.client.gold_emoji} Gold", value=user.gold)
        embed.add_field(name=f"{self.client.gem_emoji} Gems", value=user.gems)
        embed.add_field(
            name=f"{self.client.warehouse_emoji} Warehouse",
            value=(
                f"\N{LABEL} {inventory_size} inventory items\n"
                f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/inventory** {mention}"
            )
        )
        embed.add_field(
            name="\N{SEEDLING} Farm",
            value=(
                f"{self.client.tile_emoji} {free_farm_slots}/{total_farm_slots_formatted} "
                f"free tiles\n\N{ALARM CLOCK} Next harvest: {nearest_harvest}\n"
                f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/farm field** {mention}"
            )
        )

        if user.level > 2:
            embed.add_field(
                name="\N{FACTORY} Factory",
                value=(
                    f"\N{PACKAGE} Max. capacity: {factory_slots_formatted}\n"
                    f"\N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING} Workers: {user.factory_level}/10\n"
                    f"\N{ALARM CLOCK} Next production: {nearest_factory}\n"
                    f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/factory queue** {mention}"
                )
            )
        else:
            embed.add_field(name="\N{FACTORY} Factory", value="\N{LOCK} Unlocks at level 3")

        if user.level > 4:
            embed.add_field(
                name="\N{HANDSHAKE} Server trades",
                value=(
                    f"\N{MONEY BAG} Active trades: {store_slots_used}/{user.store_slots}\n"
                    "\N{RIGHT-POINTING MAGNIFYING GLASS} **/trades list**"
                )
            )
        else:
            embed.add_field(name="\N{HANDSHAKE} Server trades", value="\N{LOCK} Unlocks at level 5")

        if has_lab_unlocked:
            embed.add_field(name="\N{DNA DOUBLE HELIX} Laboratory", value=lab_info)
        else:
            embed.add_field(
                name="\N{DNA DOUBLE HELIX} Laboratory",
                value="\N{LOCK} Unlocks at level 2"
            )

        if has_boosters_unlocked:
            embed.add_field(
                name="\N{UPWARDS BLACK ARROW} Boosters",
                value=(
                    f"\N{CHART WITH UPWARDS TREND} {len(all_boosts)} boosters active\n"
                    f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/boosters** {mention}"
                )
            )
        else:
            embed.add_field(
                name="\N{UPWARDS BLACK ARROW} Boosters",
                value="\N{LOCK} Unlocks at level 7"
            )

        await self.reply(embed=embed)


class BalanceCommand(
    FarmSlashCommand,
    name="balance",
    description="\N{MONEY BAG} Shows your or someone else's funds"
):
    """With this command you can check how much money you or someone else has. That's about it."""
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose balance to check"
    )

    async def callback(self) -> None:
        if not self.player:
            await self.reply(
                f"{self.client.gold_emoji} **Gold:** {self.user_data.gold} "
                f"{self.client.gem_emoji} **Gems:** {self.user_data.gems}"
            )
        else:
            user = await self.lookup_other_player(self.player)
            await self.reply(
                f"{self.player.nick or self.player.name} has: "
                f"{self.client.gold_emoji} **Gold:** {user.gold} "
                f"{self.client.gem_emoji} **Gems:** {user.gems}"
            )


class InventoryCommand(
    FarmSlashCommand,
    name="inventory",
    description="\N{LOCK} Shows your or someone else's inventory"
):
    """
    Do you want to know what items you have? This command will show you!<br>
    You can even check what items someone else has! However, you can't
    access someone else's inventory - it's guarded very well.
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose inventory to view"
    )

    async def callback(self) -> None:
        async with self.acquire() as conn:
            if not self.player:
                user = self.user_data
                target_user = self.author
            else:
                user = await self.lookup_other_player(self.player, conn=conn)
                target_user = self.player

            all_items_data = await user.get_all_items(conn)

        items_and_amounts_by_class = {}
        for data in all_items_data:
            try:
                item = self.items.find_item_by_id(data['item_id'])
            except exceptions.ItemNotFoundException:
                # Could be a chest, we exclude those here
                continue

            item_and_amt = (item, data['amount'])

            # Group plantable items by base class
            if isinstance(item, game_items.PlantableItem):
                item_class = game_items.PlantableItem
            else:
                item_class = item.__class__

            try:
                items_and_amounts_by_class[item_class].append(item_and_amt)
            except KeyError:
                items_and_amounts_by_class[item_class] = [item_and_amt]

        if not items_and_amounts_by_class:
            await self.reply("\N{RAT} It's empty. There are only a few unfriendly rats in here...")
            return

        options_and_sources = {}
        for clazz, items in items_and_amounts_by_class.items():
            item_type = clazz.inventory_name
            item_emoji = clazz.inventory_emoji
            opt = discord.SelectOption(label=item_type, emoji=item_emoji)
            options_and_sources[opt] = InventorySource(items, target_user, item_type, item_emoji)

        await views.SelectButtonPaginatorView(self, options_and_sources).start()


class BoostersCommand(
    FarmSlashCommand,
    name="boosters",
    description="\N{UPWARDS BLACK ARROW} Lists your or someone else's boosters"
):
    """
    Boosters are very powerful special items that can help you in various ways.<br>
    They can make your farm more productive or facilitate different limits.
    However, they can also be very expensive, so you should buy them wisely.<br>
    \N{ELECTRIC LIGHT BULB} You can purchase boosters from the shop via **/shop boosters**
    after reaching level 7.
    """
    _required_level: int = 7

    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose boosters to view"
    )

    async def callback(self):
        if not self.player:
            user = self.user_data
            target_user = self.author
        else:
            user = await self.lookup_other_player(self.player)
            target_user = self.player

        all_boosts = await user.get_all_boosts(self)
        buy_tip = "\N{SHOPPING BAGS} Purchase boosters with the **/shop boosters** command."
        name = target_user.nick or target_user.name

        if not all_boosts:
            if not self.player:
                msg = "Nope, you don't have any active boosters! Why not buy some?"
            else:
                msg = f"Nope, {name} does not have any active boosters!"

            embed = embed_util.error_embed(
                title="No active boosters!",
                text=f"\N{SLEEPING SYMBOL} {msg}\n{buy_tip}",
                cmd=self
            )
            return await self.reply(embed=embed)

        embed = discord.Embed(
            title=f"\N{UPWARDS BLACK ARROW} {name}'s active boosters",
            color=discord.Color.from_rgb(39, 128, 184),
            description=buy_tip
        )

        for boost in all_boosts:
            boost_info = self.items.find_booster_by_id(boost.id)
            time_str = discord.utils.format_dt(boost.duration, style="f")

            embed.add_field(
                name=f"{boost_info.emoji} {boost_info.name}",
                value=f"Active for: {time_str}"
            )

        await self.reply(embed=embed)


class ItemsCommand(FarmSlashCommand, name="items"):
    pass


class ItemsUnlockedCommand(
    ItemsCommand,
    name="unlocked",
    description="\N{SPIRAL NOTE PAD} Lists all unlocked items for your level",
    parent=ItemsCommand
):
    """
    Do you ever wonder what items you have never used that you unlocked some long time ago?
    This command shows all items that you have previously unlocked.<br>
    \N{ELECTRIC LIGHT BULB} To view some item's unique properties, use the **/items inspect**
    command instead.
    """

    async def callback(self) -> None:
        all_items = self.items.find_all_items_by_level(self.user_data.level)
        await views.ButtonPaginatorView(self, source=AllItemsSource(all_items)).start()


class ItemsInspectCommand(
    ItemsCommand,
    name="inspect",
    description="\N{LEFT-POINTING MAGNIFYING GLASS} Shows detailed information about a game item",
    parent=ItemsCommand
):
    """
    *How long does it take to grow that one item? How big is the harvest?* If you want to know
    what item has what properties, then this is the right command for checking exactly that.<br>
    This command displays lots of useful information about almost any game item.<br><br>
    __Icon descriptions:__<br>
    \N{DNA DOUBLE HELIX} - indicates that the corresponding property of the item is upgraded
    in the laboratory.
    """
    item: str = discord.app.Option(description="Game item to inspect", autocomplete=True)

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.all_items_autocomplete(options[focused]))

    async def callback(self) -> None:
        item = self.lookup_item(self.item)

        embed = discord.Embed(
            title=item.full_name,
            description=f"\N{RIGHT-POINTING MAGNIFYING GLASS} **Item ID: {item.id}**",
            color=discord.Color.from_rgb(38, 202, 49)
        )
        embed.add_field(name="\N{TRIDENT EMBLEM} Required level", value=str(item.level))
        embed.add_field(
            name=f"{self.client.xp_emoji} Experience reward",
            value=f"{item.xp} xp / per unit"
        )

        if isinstance(item, game_items.PurchasableItem):
            embed.add_field(
                name="\N{MONEY BAG} Shop price (growing costs)",
                value=f"{item.gold_price} {self.client.gold_emoji}"
            )
        if isinstance(item, game_items.MarketItem):
            embed.add_field(
                name="\N{SHOPPING TROLLEY} Market price range",
                value=(
                    f"{item.min_market_price} - {item.max_market_price}"
                    f" {self.client.gold_emoji} / unit"
                )
            )
        if isinstance(item, game_items.SellableItem):
            embed.add_field(
                name="\N{CHART WITH UPWARDS TREND} Current market price",
                value=f"{item.gold_reward} {self.client.gold_emoji} / per unit"
            )

        if isinstance(item, game_items.ReplantableItem):
            embed.add_field(
                name="\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} Production cycles",
                value=f"Grows {item.iterations} times"
            )
        if isinstance(item, game_items.PlantableItem):
            async with self.acquire() as conn:
                mods = await self.user_data.get_item_modification(item.id, conn)

            growing_time = time_util.seconds_to_time(item.grow_time)
            harvest_time = time_util.seconds_to_time(item.collect_time)
            volume = item.amount

            if mods:
                time1_mod, time2_mod, vol_mod = mods['time1'], mods['time2'], mods['volume']
                if time1_mod:
                    fmt = time_util.seconds_to_time(modifications.get_growing_time(item, time1_mod))
                    growing_time = f"\N{DNA DOUBLE HELIX} {fmt}"
                if time2_mod:
                    fmt = time_util.seconds_to_time(modifications.get_harvest_time(item, time2_mod))
                    harvest_time = f"\N{DNA DOUBLE HELIX} {fmt}"
                if vol_mod:
                    new_vol = modifications.get_volume(item, vol_mod)
                    volume = f"\N{DNA DOUBLE HELIX} {volume} - {new_vol}"

                embed.set_footer(text=(
                    "The \N{DNA DOUBLE HELIX} emoji is indicating, that the "
                    "corresponding property is upgraded for this item"
                ))
            embed.add_field(name="\N{SCALES} Harvest volume", value=f"{volume} units")
            embed.add_field(name="\N{MANTELPIECE CLOCK} Growing duration", value=growing_time)
            embed.add_field(name="\N{MANTELPIECE CLOCK} Harvestable for", value=harvest_time)
            embed.add_field(name=f"{item.emoji} Grow", value=f"**/farm plant {item.name}**")

        if isinstance(item, game_items.Product):
            made_from = "\n".join(f"{i[0].full_name} x{i[1]}" for i in item.made_from)
            embed.add_field(name="\N{SCROLL} Required raw materials", value=made_from)
            embed.add_field(
                name="\N{MANTELPIECE CLOCK} Production duration",
                value=time_util.seconds_to_time(item.craft_time)
            )
            embed.add_field(name=f"{item.emoji} Produce", value=f"**/factory make {item.name}**")
            embed.color = discord.Color.from_rgb(168, 22, 56)

        if hasattr(item, "image_url"):
            embed.set_thumbnail(url=item.image_url)

        await self.reply(embed=embed)


class ChestsCommand(FarmSlashCommand, name="chests"):
    pass


class ChestsViewCommand(
    ChestsCommand,
    name="view",
    description="\N{TOOLBOX} Lists your owned chests",
    parent=ChestsCommand
):
    """
    This command shows what and how many chests you currently own.
    Chests are mysterious boxes that contain random goodies.
    Each different chest type has different possible rewards and odds of getting them.<br>
    You can obtain chests in various ways, while playing the game. One of those is by
    claiming daily and hourly bonuses.
    """

    async def callback(self) -> None:
        async with self.acquire() as conn:
            # When adding new chests, please increase this range
            query = """
                    SELECT * FROM inventory
                    WHERE user_id = $1
                    AND item_id BETWEEN 1000 AND 1005;
                    """
            chest_data = await conn.fetch(query, self.author.id)

        embed = discord.Embed(
            title="\N{TOOLBOX} Your chest inventory",
            color=discord.Color.from_rgb(196, 145, 16),
            description=(
                "\N{MAGIC WAND} These are your stashed chests. Open a chest with **/chests open**"
            )
        )

        chest_ids_and_amounts = {chest['item_id']: chest['amount'] for chest in chest_data}
        for chest in self.items.all_chests_by_id.values():
            try:
                amount = chest_ids_and_amounts[chest.id]
            except KeyError:
                amount = 0

            embed.add_field(
                name=f"{chest.emoji} {chest.name.capitalize()}",
                value=f"Available: **{amount}**"
            )

        await self.reply(embed=embed)


class ChestsOpenCommand(
    ChestsCommand,
    name="open",
    description="\N{CLOSED LOCK WITH KEY} Opens a chest",
    parent=ChestsCommand
):
    """
    This command opens a chest and gives you random rewards, based on the chest type you have chosen
    and other factors, for example, your current level.<br>
    \N{ELECTRIC LIGHT BULB} For more information about chests, see **/help chests view**.
    """
    chest: str = discord.app.Option(description="Chest to open", autocomplete=True)
    amount: Optional[int] = discord.app.Option(
        description="How many chests to open",
        min=1,
        max=100,
        default=1
    )

    def ladder_random(self, min: int, max: int, continue_chance: int) -> int:
        """Randint with a chance of summing up with another randint."""
        result = random.randint(min, max)

        while not random.randint(0, continue_chance):
            result += random.randint(min, max)

        return result

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.chests_autocomplete(options[focused]))

    async def callback(self):
        chest = self.lookup_chest(self.chest)

        async with self.acquire() as conn:
            chest_data = await self.user_data.get_item(chest.id, conn)

        if not chest_data or chest_data['amount'] < self.amount:
            embed = embed_util.error_embed(
                title=f"You don't have {self.amount}x {chest.name}!",
                text=(
                    "I just contacted our warehouse manager, and with a deep regret, I have to say "
                    f"that *inhales*, you don't have **{self.amount}x {chest.emoji} "
                    f"{chest.name.capitalize()}** in your inventory."
                ),
                footer="Check your chests with the \"/chests view\" command",
                cmd=self
            )
            return await self.reply(embed=embed)

        user_level, items_won = self.user_data.level, []
        gold_reward = gems_reward = 0
        base_growables_multiplier = int(self.user_data.level / 4) + 1

        if chest.id == 1000:  # Gold chest
            min_gold = user_level * 20
            max_gold = user_level * 45

            for _ in range(self.amount):
                gold_reward += self.ladder_random(min_gold, max_gold, 3)
        elif chest.id == 1001:  # Common chest
            min_gold = user_level * 2
            max_gold = user_level * 5
            multiplier = int(base_growables_multiplier / 2) or 1

            for _ in range(self.amount):
                if bool(random.getrandbits(1)):
                    items: dict = self.items.get_random_items(
                        user_level,
                        growables_multiplier=multiplier,
                        products=False
                    )
                    items_won.extend(items.items())
                else:
                    gold_reward += self.ladder_random(min_gold, max_gold, 10)
        elif chest.id == 1002:  # Uncommon chest
            min_gold = user_level * 3
            max_gold = user_level * 4

            for _ in range(self.amount):
                items: dict = self.items.get_random_items(
                    user_level,
                    extra_luck=0.055,
                    growables_multiplier=base_growables_multiplier,
                    products=False,
                    total_draws=self.ladder_random(1, 2, 14)
                )
                items_won.extend(items.items())

                if not random.randint(0, 6):
                    gold_reward += self.ladder_random(min_gold, max_gold, 8)
        elif chest.id == 1003:  # Rare chest
            min_gold = user_level * 4
            max_gold = user_level * 5

            for _ in range(self.amount):
                items: dict = self.items.get_random_items(
                    user_level,
                    extra_luck=0.1,
                    growables_multiplier=base_growables_multiplier + 2,
                    total_draws=self.ladder_random(1, 3, 12)
                )
                items_won.extend(items.items())

                if not random.randint(0, 4):
                    gold_reward += self.ladder_random(min_gold, max_gold, 6)
        elif chest.id == 1004:  # Epic chest
            min_gold = user_level * 15
            max_gold = user_level * 25

            for _ in range(self.amount):
                items: dict = self.items.get_random_items(
                    user_level,
                    extra_luck=0.35,
                    growables_multiplier=base_growables_multiplier + 6,
                    total_draws=self.ladder_random(3, 4, 9)
                )
                items_won.extend(items.items())

                gold_reward += self.ladder_random(min_gold, max_gold, 5)
        elif chest.id == 1005:  # Legendary chest
            min_gold = user_level * 20
            max_gold = user_level * 50

            for _ in range(self.amount):
                items: dict = self.items.get_random_items(
                    user_level,
                    extra_luck=0.85,
                    growables_multiplier=base_growables_multiplier + 12,
                    products_multiplier=2,
                    total_draws=self.ladder_random(4, 5, 6)
                )
                items_won.extend(items.items())

                gold_reward += self.ladder_random(min_gold, max_gold, 3)
                if not random.randint(0, 14):
                    gems_reward += 1

        self.user_data.gold += gold_reward
        self.user_data.gems += gems_reward

        async with self.acquire() as conn:
            async with conn.transaction():
                await self.user_data.remove_item(chest.id, self.amount, conn)

                if gold_reward or gems_reward:
                    await self.users.update_user(self.user_data, conn=conn)
                if items_won:
                    await self.user_data.give_items(items_won, conn)

        rewards, grouped = "", {}
        for item, amt in items_won:
            try:
                grouped[item] += amt
            except KeyError:
                grouped[item] = amt

        rewards += "".join(f"**{item.full_name}**: {amt} " for item, amt in grouped.items())
        if gold_reward:
            rewards += f"**{self.client.gold_emoji} {gold_reward} gold** "
        if gems_reward:
            rewards += f"**{self.client.gem_emoji} {gems_reward} gems** "

        embed = embed_util.congratulations_embed(
            title=f"{chest.name.capitalize()} opened!",
            text=(
                f"{self.author.mention} tried their luck, by opening their **{self.amount}x "
                f"{chest.emoji} {chest.name.capitalize()}**, and won these awesome rewards:\n\n"
                + rewards
            ),
            footer="These items are now moved to your inventory",
            cmd=self
        )
        await self.reply(embed=embed)


class ChestsDailyCommand(
    ChestsCommand,
    name="daily",
    description="\N{SLOT MACHINE} Gets a free random chest every day",
    parent=ChestsCommand
):
    """
    Do you want that cool, shiny chest? Well, you can get one for free every day with this command.
    <br>\N{ELECTRIC LIGHT BULB} For more information about chests, see **/help chests view**.
    """
    _invoke_cooldown: int = 82800

    async def callback(self) -> None:
        chests_and_rarities = {
            1000: 90.0,  # Gold
            1002: 125.0,  # Uncommon
            1003: 85.0,  # Rare
            1004: 45.5,  # Epic
            1005: 8.0  # Legendary
        }

        chest = random.choices(
            population=list(chests_and_rarities.keys()),
            weights=chests_and_rarities.values(),
            k=1
        )[0]

        async with self.acquire() as conn:
            await self.user_data.give_item(chest, 1, conn)

        chest_data = self.items.find_chest_by_id(chest)
        embed = embed_util.congratulations_embed(
            title="Daily bonus chest received!",
            text=(
                f"You won {chest_data.emoji} **{chest_data.name.capitalize()}** as your daily "
                "bonus! \N{FACE WITH COWBOY HAT}"
            ),
            footer=f"Use the \"/chests open {chest_data.name}\" command, to open",
            cmd=self
        )
        await self.reply(embed=embed)


class ChestsHourlyCommand(
    ChestsCommand,
    name="hourly",
    description="\N{CLOCK FACE TWELVE OCLOCK} Gets a free random chest every hour",
    parent=ChestsCommand
):
    """
    Do you want that cool, shiny chest? Well, you can get one for free every hour with this command.
    <br>\N{ELECTRIC LIGHT BULB} For more information about chests, see **/help chests view**.
    """
    _invoke_cooldown: int = 3600

    async def callback(self):
        chests_and_rarities = {
            1000: 80.5,  # Gold
            1001: 600.0,  # Common
            1002: 250.0,  # Uncommon
            1003: 70.0,  # Rare
            1004: 20.0,  # Epic
            1005: 2.5  # Legendary
        }
        chest_id = random.choices(
            population=list(chests_and_rarities.keys()),
            weights=chests_and_rarities.values(),
            k=1
        )[0]

        amount = 1
        # If common chest, give multiple
        if chest_id == 1001:
            min = int(self.user_data.level / 20) or 1
            max = int(self.user_data.level / 10) or 1
            amount = random.randint(min, max + 1)

        async with self.acquire() as conn:
            await self.user_data.give_item(chest_id, amount, conn)

        chest_data = self.items.find_chest_by_id(chest_id)
        embed = embed_util.congratulations_embed(
            title="Hourly bonus chest received!",
            text=(
                f"You won **{amount}x {chest_data.full_name} ** as your hourly bonus! "
                "\N{FACE WITH COWBOY HAT}"
            ),
            footer=f"Use the \"/chests open {chest_data.name}\" command, to open",
            cmd=self
        )
        await self.reply(embed=embed)


def setup(client) -> list:
    return [ProfileCollection(client)]

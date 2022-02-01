import json
import random
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from bot.commands.util.exceptions import ItemNotFoundException


# < 10 Minutes
VERY_SHORT_PERIOD = 599
# 30 Minutes
SHORT_PERIOD = 1800
# 3 Hours
MEDIUM_PERIOD = 10800
# 6 hours
LONG_PERIOD = 21600

# We lose 25% of item's value if we sell it at lowest price
MIN_MARKET_PRICE_LOSS = 0.25

PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 450
PLANTABLE_GOLD_GAIN_PER_HOUR_SHORT = 350
PLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 200
PLANTABLE_GOLD_GAIN_PER_HOUR_LONG = 100
PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 70

REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 650
REPLANTABLE_GOLD_GAIN_PER_HOUR_SHORT = 550
REPLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 300
REPLANTABLE_GOLD_GAIN_PER_HOUR_LONG = 225
REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 150

CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 1500
CRAFTABLE_GOLD_GAIN_PER_HOUR_SHORT = 950
CRAFTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 465
CRAFTABLE_GOLD_GAIN_PER_HOUR_LONG = 270
CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 155

GROWABLE_XP_GAIN_PER_HOUR_VERY_SHORT = 200
GROWABLE_XP_GAIN_PER_HOUR_SHORT = 180
GROWABLE_XP_GAIN_PER_HOUR_MEDIUM = 160
GROWABLE_XP_GAIN_PER_HOUR_LONG = 135
GROWABLE_XP_GAIN_PER_HOUR_VERY_LONG = 105

CRAFTABLE_XP_GAIN_PER_HOUR = 1000

# 10% discount
BOOST_THREE_DAYS_DISCOUNT = 0.10
# 25% discount
BOOST_SEVEN_DAYS_DISCOUNT = 0.25


@dataclass
class GameItem:
    """Base class for game items"""
    id: int
    level: int
    emoji: str
    name: str
    amount: int

    def __hash__(self) -> int:
        return self.id

    @property
    def full_name(self) -> str:
        return f"{self.emoji} {self.name.capitalize()}"


@dataclass
class PurchasableItem:
    """Marks an item as purchasable with the buy command."""
    gold_price: int


@dataclass
class SellableItem:
    """Marks an item as sellable with the sell command."""
    gold_reward: int


@dataclass
class MarketItem:
    """
    Marks an item that it is going to have a dynamic price.
    Also marks an item as tradeable.
    """
    min_market_price: int
    max_market_price: int


class PlantableItem(GameItem, PurchasableItem, SellableItem, MarketItem):
    """Represents an abstract game item, that can be planted on a farm field."""

    def __init__(
        self,
        id: int,
        level: int,
        emoji: str,
        name: str,
        amount: int,
        gold_price: int,
        grow_time: int,
        image_url: str
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        PurchasableItem.__init__(self, gold_price)
        SellableItem.__init__(self, 0)

        self.grow_time = grow_time
        self.image_url = image_url

        min_price = self._calculate_min_market_price()
        max_price = self._calculate_max_market_price()
        MarketItem.__init__(self, min_price, max_price)

        self.collect_time = int(grow_time * 1.5)
        self.xp = self._calculate_xp()

    def generate_new_price(self) -> None:
        """
        Generates a new price for the item.
        This should be called outside of the class.
        """
        self.gold_reward = random.randint(self.min_market_price, self.max_market_price)

    def _calculate_xp(self) -> int:
        if self.grow_time <= VERY_SHORT_PERIOD:
            gain = GROWABLE_XP_GAIN_PER_HOUR_VERY_SHORT
        elif self.grow_time <= SHORT_PERIOD:
            gain = GROWABLE_XP_GAIN_PER_HOUR_SHORT
        elif self.grow_time <= MEDIUM_PERIOD:
            gain = GROWABLE_XP_GAIN_PER_HOUR_MEDIUM
        elif self.grow_time <= LONG_PERIOD:
            gain = GROWABLE_XP_GAIN_PER_HOUR_LONG
        else:
            gain = GROWABLE_XP_GAIN_PER_HOUR_VERY_LONG

        return int((self.grow_time / 3600) * gain / self.amount) or 1

    def _calculate_min_market_price(self) -> int:
        total_new_value = self.gold_price - (self.gold_price * MIN_MARKET_PRICE_LOSS)
        return int(total_new_value / self.amount) or 1

    def _calculate_max_market_price(self) -> int:
        gold_per_item = self.gold_price / self.amount

        if self.grow_time <= VERY_SHORT_PERIOD:
            gain = PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT
        elif self.grow_time <= SHORT_PERIOD:
            gain = PLANTABLE_GOLD_GAIN_PER_HOUR_SHORT
        elif self.grow_time <= MEDIUM_PERIOD:
            gain = PLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM
        elif self.grow_time <= LONG_PERIOD:
            gain = PLANTABLE_GOLD_GAIN_PER_HOUR_LONG
        else:
            gain = PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG

        total_profit = (self.grow_time / 3600) * gain
        return int(gold_per_item + (total_profit / self.amount)) or 1


class ReplantableItem(PlantableItem):
    """Represents an abstract plantable item that has multiple harvests."""

    def __init__(self, iterations: int, *args, **kwargs):
        self.iterations = iterations
        super().__init__(*args, **kwargs)

    def _calculate_min_market_price(self) -> int:
        total_new_value = self.gold_price - (self.gold_price * MIN_MARKET_PRICE_LOSS)
        return int(total_new_value / (self.amount * self.iterations)) or 1

    def _calculate_max_market_price(self) -> int:
        gold_per_item = self.gold_price / (self.amount * self.iterations)

        if self.grow_time <= VERY_SHORT_PERIOD:
            gain = REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT
        elif self.grow_time <= SHORT_PERIOD:
            gain = REPLANTABLE_GOLD_GAIN_PER_HOUR_SHORT
        elif self.grow_time <= MEDIUM_PERIOD:
            gain = REPLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM
        elif self.grow_time <= LONG_PERIOD:
            gain = REPLANTABLE_GOLD_GAIN_PER_HOUR_LONG
        else:
            gain = REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG

        total_profit = (self.grow_time / 3600) * gain
        return int(gold_per_item + (total_profit / self.amount)) or 1


class Crop(PlantableItem):
    """Item class for crop items"""
    inventory_name = "Crops"
    inventory_emoji = "\N{EAR OF MAIZE}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Tree(ReplantableItem):
    """Item class for tree items"""
    inventory_name = "Trees and bushes"
    inventory_emoji = "\N{CHERRIES}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Animal(ReplantableItem):
    """Item class for animal items"""
    inventory_name = "Animal products"
    inventory_emoji = "\N{PIG NOSE}"

    def __init__(self, emoji_animal: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emoji_animal = emoji_animal


class Special(GameItem, SellableItem, MarketItem):
    """Represents an item in-game that has a special use case."""
    inventory_name = "Other items"
    inventory_emoji = "\N{PACKAGE}"

    def __init__(
        self,
        id: int,
        level: int,
        emoji: str,
        name: str,
        amount: int,
        xp: int,
        min_market_price: int,
        max_market_price: int,
        image_url: str
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        SellableItem.__init__(self, 0)

        self.xp = xp
        self.min_market_price = min_market_price
        self.max_market_price = max_market_price
        self.image_url = image_url

    def generate_new_price(self) -> None:
        """
        Generates a new price for the item.
        This should be called outside of the class.
        """
        self.gold_reward = random.randint(self.min_market_price, self.max_market_price)


class Chest(GameItem):
    """Represents a chest item."""

    def __init__(self, image_url: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_url = image_url


@dataclass
class ItemAndAmount:
    """A helper class to store item and amount info in Product objects"""

    __slots__ = ("item", "amount")

    item: GameItem
    amount: int


class Product(GameItem, SellableItem, MarketItem):
    """Represents an item that can be produced in a factory."""
    inventory_name = "Factory products"
    inventory_emoji = "\N{SOFT ICE CREAM}"

    def __init__(
        self,
        id: int,
        level: int,
        emoji: str,
        name: str,
        amount: int,
        made_from: list,
        craft_time: int,
        image_url: str
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        SellableItem.__init__(self, 0)

        self.made_from = made_from
        self.craft_time = craft_time
        self.image_url = image_url

        self.xp = self._calculate_xp()
        # WARNING: Must manually init min, max market prices
        # after the made_from list is parsed into list of ItemAndAmount objects
        self.min_market_price = 0
        self.max_market_price = 0

    def generate_new_price(self) -> None:
        """
        Generates a new price for the item.
        This should be called outside of the class.
        """
        self.gold_reward = random.randint(self.min_market_price, self.max_market_price)

    def _calculate_total_value(self) -> int:
        # Just to check if we have items at all and if there are ItemAndAmount instances, not dicts.
        assert isinstance(self.made_from[0], ItemAndAmount), "Product made_from not initialized"

        total_value = 0
        for item_and_amount in self.made_from:
            if isinstance(item_and_amount.item, Product):
                total_value += item_and_amount.item._calculate_total_value() \
                    * item_and_amount.amount
            else:
                total_value += item_and_amount.item.max_market_price * item_and_amount.amount

        return total_value

    def _calculate_min_market_price(self) -> int:
        total_value = self._calculate_total_value()
        total_new_value = total_value - (total_value * MIN_MARKET_PRICE_LOSS)

        return int(total_new_value) or 1

    def _calculate_max_market_price(self) -> int:
        total_value = self._calculate_total_value()

        if self.craft_time <= VERY_SHORT_PERIOD:
            gain = CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT
        elif self.craft_time <= SHORT_PERIOD:
            gain = CRAFTABLE_GOLD_GAIN_PER_HOUR_SHORT
        elif self.craft_time <= MEDIUM_PERIOD:
            gain = CRAFTABLE_GOLD_GAIN_PER_HOUR_MEDIUM
        elif self.craft_time <= LONG_PERIOD:
            gain = CRAFTABLE_GOLD_GAIN_PER_HOUR_LONG
        else:
            gain = CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG

        total_profit = (self.craft_time / 3600) * gain
        return int(total_value + total_profit) or 1

    def _calculate_xp(self) -> int:
        return int((self.craft_time / 3600) * CRAFTABLE_XP_GAIN_PER_HOUR)

    def craft_time_by_factory_level(self, level: int) -> int:
        return self.craft_time - int((self.craft_time / 100) * (level * 5))


class BoostDuration(Enum):
    """Defines available boost durations in seconds."""
    ONE_DAY = 86400
    THREE_DAYS = 259200
    SEVEN_DAYS = 604800


class Boost:
    """A special class to represent booster items."""

    __slots__ = (
        "id",
        "name",
        "info",
        "emoji",
        "base_price",
        "price_increase_per_farm_slots",
        "price_increase_per_factory_slots",
        "price_increase_per_user_level"
    )

    def __init__(
        self,
        id: str,
        name: str,
        info: str,
        emoji: str,
        base_price: int,
        price_increase_per_farm_slots: int,
        price_increase_per_factory_slots: int,
        price_increase_per_user_level: int
    ) -> None:
        self.id = id
        self.name = name
        self.info = info
        self.emoji = emoji
        self.base_price = base_price
        self.price_increase_per_farm_slots = price_increase_per_farm_slots
        self.price_increase_per_factory_slots = price_increase_per_factory_slots
        self.price_increase_per_user_level = price_increase_per_user_level

    def get_boost_price(self, duration: BoostDuration, user) -> int:
        price_per_day = self.base_price

        price_per_day += self.price_increase_per_farm_slots * user.farm_slots
        price_per_day += self.price_increase_per_factory_slots * user.factory_slots
        price_per_day += self.price_increase_per_user_level * user.level

        if duration == BoostDuration.ONE_DAY:
            # No discount
            return price_per_day
        elif duration == BoostDuration.THREE_DAYS:
            total = price_per_day * 3
            return int(total - total * BOOST_THREE_DAYS_DISCOUNT)
        else:
            total = price_per_day * 7
            return int(total - total * BOOST_SEVEN_DAYS_DISCOUNT)


class PartialBoost:
    """Boost class for storing boosts in Redis."""

    __slots__ = ("id", "duration")

    def __init__(self, id: str, duration: datetime) -> None:
        self.id = id
        self.duration = duration


class ItemPool:
    """Utility class for easy access to items and utility methods."""

    __slots__ = (
        "all_items",
        "all_items_by_id",
        "all_item_ids_by_name",
        "all_boosts_by_id",
        "all_boost_ids_by_name",
        "all_chests_by_id",
        "all_chest_ids_by_name",
        "all_plantable_ids_by_name",
        "all_product_ids_by_name"
    )

    def __init__(self, all_items: list, all_boosts: list, all_chests: list) -> None:
        self.all_items = all_items
        self.all_items_by_id = {str(i.id): i for i in all_items}
        self.all_item_ids_by_name = {i.name: i.id for i in all_items}
        self.all_boosts_by_id = {b.id: b for b in all_boosts}
        self.all_boost_ids_by_name = {b.name: b.id for b in all_boosts}
        self.all_chests_by_id = {str(c.id): c for c in all_chests}
        self.all_chest_ids_by_name = {c.name: c.id for c in all_chests}
        self.all_plantable_ids_by_name = self._sort_names_by_ids_per_class(PlantableItem)
        self.all_product_ids_by_name = self._sort_names_by_ids_per_class(Product)

    def _sort_names_by_ids_per_class(self, item_class) -> dict:
        return {x.name: x.id for x in self.all_items if isinstance(x, item_class)}

    def find_items_by_level(self, item_level: int) -> list:
        """Finds all items unique to a certain level."""
        return [x for x in self.all_items if x.level == item_level]

    def find_all_items_by_level(self, user_level: int) -> list:
        """Finds all unlocked items for specified user level."""
        return [x for x in self.all_items if x.level <= user_level]

    def find_item_by_id(self, item_id: int) -> GameItem:
        try:
            return self.all_items_by_id[str(item_id)]
        except KeyError:
            raise ItemNotFoundException(f"Item {item_id} not found!")

    def find_booster_by_id(self, boost_id: str) -> Boost:
        try:
            return self.all_boosts_by_id[boost_id]
        except KeyError:
            raise ItemNotFoundException(f"Boost {boost_id} not found!")

    def find_chest_by_id(self, chest_id: int) -> Chest:
        try:
            return self.all_chests_by_id[str(chest_id)]
        except KeyError:
            raise ItemNotFoundException(f"Chest {chest_id} not found!")

    def update_market_prices(self) -> None:
        for item in self.all_items:
            if isinstance(item, MarketItem):
                item.generate_new_price()

    def get_random_items(
        self,
        user_level: int,
        extra_luck: float = 0,  # 0 - 1.0
        total_draws: int = 1,
        growables_multiplier: int = 1,
        products_multiplier: int = 1,
        growables: bool = True,
        products: bool = True,
        specials: bool = False
    ) -> list:
        items = self.find_all_items_by_level(user_level)

        population, weights = [], []
        max_weight = 0
        for item in items:
            if not growables and isinstance(item, PlantableItem):
                continue

            if not products and isinstance(item, Product):
                continue

            if not specials and isinstance(item, Special):
                continue

            if item.gold_reward > max_weight:
                max_weight = item.gold_reward

            population.append(item)
            weights.append(item.gold_reward)

        weights_size = len(weights)
        new_weights = [0] * weights_size

        for i in range(weights_size):
            current = weights[i]
            # If extra luck is 1 (max), then all items have equal weights
            with_luck = current - (current * extra_luck)
            new_weights[i] = (max_weight + 1) - with_luck

        items = random.choices(population, weights=new_weights, k=total_draws)

        rewards = []
        for item in items:
            # Generate amounts
            # Hardcore to make it balanced by my liking
            if isinstance(item, PlantableItem):
                gold_reward = item.gold_reward
                if gold_reward <= 10:
                    min, max = 5, 14
                elif gold_reward <= 30:
                    min, max = 3, 8
                elif gold_reward <= 50:
                    min, max = 2, 6
                else:
                    min, max = 1, 3

                min *= growables_multiplier
                max *= growables_multiplier

                amount = random.randint(min, max)
            else:
                # Default product amount is 1.
                # If multiplier, lower the chance to get more items
                population = []
                for i in range(products_multiplier):
                    population.extend([i + 1] * (products_multiplier - i) * 2)

                amount = random.choice(population)

            try:
                # Try to just change the existing amount if same item
                existing = next(x for x in rewards if item == x[0])
                rewards.remove(existing)
                rewards.append((item, existing[1] + amount))
            except StopIteration:
                rewards.append((item, amount))

        return rewards


def _load_crops() -> list:
    all_items = []

    with open("data/items/crops.json", "r") as file:
        data = json.load(file)

        for item_data in data['crops']:
            item = Crop(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                gold_price=item_data['gold_price'],
                grow_time=item_data['grow_time'],
                image_url=item_data['image_url']
            )
            all_items.append(item)

    return all_items


def _load_trees() -> list:
    all_items = []

    with open("data/items/trees.json", "r") as file:
        data = json.load(file)

        for item_data in data['trees']:
            item = Tree(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                gold_price=item_data['gold_price'],
                grow_time=item_data['grow_time'],
                image_url=item_data['image_url'],
                iterations=item_data['iterations']
            )
            all_items.append(item)

    return all_items


def _load_animals() -> list:
    all_items = []

    with open("data/items/animals.json", "r") as file:
        data = json.load(file)

        for item_data in data['animals']:
            item = Animal(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                gold_price=item_data['gold_price'],
                grow_time=item_data['grow_time'],
                image_url=item_data['image_url'],
                iterations=item_data['iterations'],
                emoji_animal=item_data['emoji_animal']
            )
            all_items.append(item)

    return all_items


def _load_special_items() -> list:
    all_items = []

    with open("data/items/special_items.json", "r") as file:
        data = json.load(file)

        for item_data in data['special']:
            item = Special(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                xp=item_data['xp'],
                min_market_price=item_data['min_market_price'],
                max_market_price=item_data['max_market_price'],
                image_url=item_data['image_url']
            )
            all_items.append(item)

    return all_items


def _load_craftables(all_loaded_items: list) -> None:
    all_craftables = []

    with open("data/items/craftables.json", "r") as file:
        data = json.load(file)

        for item_data in data['craftables']:
            item = Product(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                made_from=item_data['made_from'],
                craft_time=item_data['craft_time'],
                image_url=item_data['image_url']
            )
            all_craftables.append(item)

    # Add craftables to all items list
    all_loaded_items.extend(all_craftables)

    # Initialize relations to other items
    for craftable in all_craftables:
        made_from_list = craftable.made_from

        made_from_new_list = []
        for requirement in made_from_list:
            for item, amount in requirement.items():
                item_obj = next(obj for obj in all_loaded_items if obj.id == int(item))
                made_from_new_list.append(ItemAndAmount(item_obj, amount))

        craftable.made_from = made_from_new_list

    # Only now we can calculate the prices of these items
    for craftable in all_craftables:
        craftable.min_market_price = craftable._calculate_min_market_price()
        craftable.max_market_price = craftable._calculate_max_market_price()


def _load_boosts() -> list:
    all_boosts = []

    with open("data/items/boosts.json", "r") as file:
        data = json.load(file)

        for boost_data in data['boosts']:
            increase_farm_slots = boost_data['price_increase_per_farm_slots']
            increase_factory_slots = boost_data['price_increase_per_factory_slots']
            increase_user_level = boost_data['price_increase_per_user_level']

            boost = Boost(
                id=boost_data['id'],
                name=boost_data['name'],
                info=boost_data['info'],
                emoji=boost_data['emoji'],
                base_price=boost_data['base_price'],
                price_increase_per_farm_slots=increase_farm_slots,
                price_increase_per_factory_slots=increase_factory_slots,
                price_increase_per_user_level=increase_user_level
            )
            all_boosts.append(boost)

    return all_boosts


def _load_chests() -> list:
    all_chests = []

    with open("data/items/chests.json", "r") as file:
        data = json.load(file)

        for chest_data in data['chests']:
            chest = Chest(
                id=chest_data['id'],
                level=chest_data['level'],
                emoji=chest_data['emoji'],
                name=chest_data['name'],
                amount=chest_data['amount'],
                image_url=chest_data['image_url']
            )
            all_chests.append(chest)

    return all_chests


def load_all_items() -> ItemPool:
    all_items = []

    all_items.extend(_load_crops())
    all_items.extend(_load_trees())
    all_items.extend(_load_animals())
    all_items.extend(_load_special_items())

    # This has to be loaded last, to attach made_from subobject references
    _load_craftables(all_items)

    all_boosts = _load_boosts()
    all_chests = _load_chests()

    item_pool = ItemPool(all_items, all_boosts, all_chests)
    # Items have no market prices, so we generate them
    item_pool.update_market_prices()
    return item_pool

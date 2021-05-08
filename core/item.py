import json
import random
from enum import Enum
from dataclasses import dataclass
from difflib import get_close_matches

from core.user import User
from core.exceptions import ItemNotFoundException


# 10 Minutes
VERY_SHORT_PERIOD = 600
# 1 Hour
SHORT_PERIOD = 3600
# 6 Hours
MEDIUM_PERIOD = 21600
# 12 hours
LONG_PERIOD = 43200

# We lose 25% of item's value if we sell it at lowest price
MIN_MARKET_PRICE_LOSS = 0.25

PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 500
PLANTABLE_GOLD_GAIN_PER_HOUR_SHORT = 250
PLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 180
PLANTABLE_GOLD_GAIN_PER_HOUR_LONG = 125
PLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 85

REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 700
REPLANTABLE_GOLD_GAIN_PER_HOUR_SHORT = 375
REPLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 245
REPLANTABLE_GOLD_GAIN_PER_HOUR_LONG = 150
REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 95

CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 250
CRAFTABLE_GOLD_GAIN_PER_HOUR_SHORT = 200
CRAFTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 150
CRAFTABLE_GOLD_GAIN_PER_HOUR_LONG = 100
CRAFTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 50

GROWABLE_XP_GAIN_PER_HOUR = 200
CRAFTABLE_XP_GAIN_PER_HOUR = 400

# 10% discount
BOOST_THREE_DAYS_DISCOUNT = 0.10
# 25% discount
BOOST_SEVEN_DAYS_DISCOUNT = 0.25


@dataclass
class GameItem:

    __slots__ = (
        'id',
        'level',
        'emoji',
        'name',
        'amount'
    )

    id: int
    level: int
    emoji: str
    name: str
    amount: int


@dataclass
class PurchasableItem:
    gold_price: int
    gems_price: int


@dataclass
class SellableItem:
    gold_reward: int
    gems_reward: int


class MarketItem:
    pass


class PlantableItem(GameItem, PurchasableItem, SellableItem, MarketItem):

    __slots__ = (
        'grow_time',
        'image_url',
        'collect_time',
        'xp',
        'min_market_price',
        'max_market_price',
        'gold_price',
        'gems_price',
        'gold_reward',
        'gems_reward',
    )

    def __init__(
        self,
        id: int,
        level: int,
        emoji: str,
        name: str,
        amount: int,
        gold_price: int,
        grow_time: int,
        image_url: str,
        gems_price: int = -1,
        gems_reward: int = -1,
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        PurchasableItem.__init__(self, gold_price, gems_price)
        SellableItem.__init__(self, 0, gems_reward)

        self.grow_time = grow_time
        self.image_url = image_url

        self.collect_time = int(grow_time * 1.5)
        self.xp = self._calculate_xp()

        self.min_market_price = self._calculate_min_market_price()
        self.max_market_price = self._calculate_max_market_price()

    def generate_new_price(self) -> None:
        self.gold_reward = random.randint(
            self.min_market_price, self.max_market_price
        )

    def _calculate_xp(self) -> int:
        return int(
            (self.grow_time / 3600) * GROWABLE_XP_GAIN_PER_HOUR / self.amount
        ) or 1

    def _calculate_min_market_price(self) -> int:
        total_new_value = \
            self.gold_price - (self.gold_price * MIN_MARKET_PRICE_LOSS)

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

    __slots__ = ('iterations')

    def __init__(self, iterations: int, *args, **kwargs):
        self.iterations = iterations
        super().__init__(*args, **kwargs)

    def _calculate_min_market_price(self) -> int:
        total_new_value = \
            self.gold_price - (self.gold_price * MIN_MARKET_PRICE_LOSS)

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

        return int(
            gold_per_item + (total_profit / (self.amount * self.iterations))
        ) or 1


class Crop(PlantableItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Tree(ReplantableItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Animal(ReplantableItem):
    def __init__(self, emoji_animal: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emoji_animal = emoji_animal


class SpecialUnpurchasableItem(GameItem, SellableItem, MarketItem):

    __slots__ = (
        'xp',
        'min_market_price',
        'max_market_price',
        'image_url',
        'gold_reward',
        'gems_reward'
    )

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
        image_url: str,
        gems_reward: int = -1
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        SellableItem.__init__(self, 0, gems_reward)

        self.xp = xp
        self.min_market_price = min_market_price
        self.max_market_price = max_market_price
        self.image_url = image_url

    def generate_new_price(self) -> None:
        self.gold_reward = random.randint(
            self.min_market_price, self.max_market_price
        )


@dataclass
class ItemAndAmount:

    __slots__ = ('item', 'amount')

    item: GameItem
    amount: int


class CraftableItem(GameItem, SellableItem, MarketItem):

    __slots__ = (
        'made_from',
        'craft_time',
        'image_url',
        'xp'
        'min_market_price',
        'max_market_price',
        'gold_reward',
        'gems_reward'
    )

    def __init__(
        self,
        id: int,
        level: int,
        emoji: str,
        name: str,
        amount: int,
        made_from: list,
        craft_time: int,
        image_url: str,
        gems_reward: int = -1
    ) -> None:
        GameItem.__init__(self, id, level, emoji, name, amount)
        SellableItem.__init__(self, 0, gems_reward)

        self.made_from = made_from
        self.craft_time = craft_time
        self.image_url = image_url

        self.xp = self._calculate_xp()

        # WARNING: Must manually init min, max market prices
        # after the made_from list is parsed into list of ItemAndAmount objects
        self.min_market_price = 0
        self.max_market_price = 0

    def generate_new_price(self) -> None:
        self.gold_reward = random.randint(
            self.min_market_price, self.max_market_price
        )

    def _calculate_total_value(self) -> int:
        # Just to check if we have items at all,
        # and if there are ItemAndAmount instances, not dicts.
        if not isinstance(self.made_from[0], ItemAndAmount):
            raise Exception(
                f"CraftedItem ID: {self.id} made_from not initialized"
            )

        value = 0

        for item_and_amount in self.made_from:
            if isinstance(item_and_amount.item, CraftableItem):
                value += item_and_amount.item._calculate_total_value()
            else:
                value += \
                    item_and_amount.item.max_market_price \
                    * item_and_amount.amount

        return value

    def _calculate_min_market_price(self) -> int:
        total_value = self._calculate_total_value()
        total_new_value = \
            total_value - (total_value * MIN_MARKET_PRICE_LOSS)

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


class BoostDuration(Enum):
    ONE_DAY = 86400
    THREE_DAYS = 259200
    SEVEN_DAYS = 604800


class Boost:

    __slots__ = (
        'id',
        'name',
        'emoji',
        'base_price',
        'price_increase_per_farm_slots',
        'price_increase_per_factory_slots',
        'price_increase_per_user_level'
    )

    def __init__(
        self,
        id: str,
        name: str,
        emoji: str,
        base_price: int,
        price_increase_per_farm_slots: int,
        price_increase_per_factory_slots: int,
        price_increase_per_user_level: int
    ) -> None:
        self.id = id
        self.name = name
        self.emoji = emoji
        self.base_price = base_price
        self.price_increase_per_farm_slots = price_increase_per_farm_slots
        self.price_increase_per_factory_slots = \
            price_increase_per_factory_slots
        self.price_increase_per_user_level = price_increase_per_user_level

    def get_boost_price(self, duration: BoostDuration, user: User) -> int:
        price_per_day = self.base_price

        price_per_day += self.price_increase_per_farm_slots * user.farm_slots
        price_per_day += \
            self.price_increase_per_factory_slots * user.factory_slots
        price_per_day += self.price_increase_per_user_level * user.level

        if duration.ONE_DAY:
            # No discount
            return price_per_day
        elif duration.THREE_DAYS:
            total = price_per_day * 3

            return int(total - total * BOOST_THREE_DAYS_DISCOUNT)
        else:
            total = price_per_day * 7

            return int(total - total * BOOST_SEVEN_DAYS_DISCOUNT)


class ItemPool:

    __slots__ = (
        'all_items',
        'all_boosts',
        'items_per_name',
        'all_item_names'
    )

    def __init__(self, all_items: list, all_boosts: list) -> None:
        self.all_items = all_items
        self.all_boosts = all_boosts
        self.items_per_name = self._group_items_per_name()
        self.all_item_names = self.items_per_name.keys()

    def find_item_by_id(self, item_id: int) -> GameItem:
        try:
            item = next(x for x in self.all_items if x.id == item_id)
        except StopIteration:
            raise ItemNotFoundException(f"Item {item_id} not found!")

        return item

    def find_item_by_name(self, item_name: str) -> GameItem:
        matches = get_close_matches(
            item_name,
            self.all_item_names,
            cutoff=0.72
        )

        if not matches:
            raise ItemNotFoundException(f"Item \"{item_name}\" not found!")

        return self.items_per_name[matches[0]]

    def find_boost_by_id(self, boost_id: str) -> Boost:
        boost = next(x for x in self.all_boosts if x.id == boost_id)

        return boost

    def update_market_prices(self) -> None:
        for item in self.all_items:
            if isinstance(item, MarketItem):
                item.generate_new_price()

    def _group_items_per_name(self) -> dict:
        items_per_name = {}

        for item in self.all_items:
            items_per_name[item.name] = item

        return items_per_name


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


def _load_special_unpurchasables() -> list:
    all_items = []

    with open("data/items/special_unpurchasable_items.json", "r") as file:
        data = json.load(file)

        for item_data in data['special_unpurchasables']:
            item = SpecialUnpurchasableItem(
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
    all_items = []

    with open("data/items/craftables.json", "r") as file:
        data = json.load(file)

        for item_data in data['craftables']:
            item = CraftableItem(
                id=item_data['id'],
                level=item_data['level'],
                emoji=item_data['emoji'],
                name=item_data['name'],
                amount=item_data['amount'],
                made_from=item_data['made_from'],
                craft_time=item_data['craft_time'],
                image_url=item_data['image_url']
            )

            all_items.append(item)

    all_loaded_items.extend(all_items)

    # Update relations
    for craftable in all_items:
        made_from_list = craftable.made_from

        made_from_new_list = []
        for requirement in made_from_list:
            for item, amount in requirement.items():
                item_obj = next(
                    obj for obj in all_loaded_items if obj.id == int(item)
                )

                item_and_amount = ItemAndAmount(item_obj, amount)
                made_from_new_list.append(item_and_amount)

        craftable.made_from = made_from_new_list

    # Fully init craftables
    for craftable in all_items:
        craftable.min_market_price = craftable._calculate_min_market_price()
        craftable.max_market_price = craftable._calculate_max_market_price()


def _load_boosts() -> list:
    all_boosts = []

    with open("data/items/boosts.json", "r") as file:
        data = json.load(file)

        for boost_data in data['boosts']:
            increase_farm_slots = boost_data['price_increase_per_farm_slots']
            increase_factory_slots = \
                boost_data['price_increase_per_factory_slots']
            increase_user_level = boost_data['price_increase_per_user_level']

            boost = Boost(
                id=boost_data['id'],
                name=boost_data['name'],
                emoji=boost_data['emoji'],
                base_price=boost_data['base_price'],
                price_increase_per_farm_slots=increase_farm_slots,
                price_increase_per_factory_slots=increase_factory_slots,
                price_increase_per_user_level=increase_user_level
            )

            all_boosts.append(boost)

    return all_boosts


def load_all_items() -> ItemPool:
    all_items = []

    all_items.extend(_load_crops())
    all_items.extend(_load_trees())
    all_items.extend(_load_animals())
    all_items.extend(_load_special_unpurchasables())

    # This has to be loaded last, to attach made_from subobject references
    _load_craftables(all_items)

    for item in all_items:
        if isinstance(item, MarketItem):
            item.generate_new_price()

    all_boosts = _load_boosts()

    return ItemPool(all_items, all_boosts)

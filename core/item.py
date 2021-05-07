import json
import random
from dataclasses import dataclass

# 10 Minutes
VERY_SHORT_PERIOD = 600
# 1 Hour
SHORT_PERIOD = 3600
# 6 Hours
MEDIUM_PERIOD = 21600
# 12 hours
LONG_PERIOD = 43200

GOLD_GAIN_PER_HOUR_VERY_SHORT = 500
GOLD_GAIN_PER_HOUR_SHORT = 250
GOLD_GAIN_PER_HOUR_MEDIUM = 180
GOLD_GAIN_PER_HOUR_LONG = 125
GOLD_GAIN_PER_HOUR_VERY_LONG = 85

REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_SHORT = 700
REPLANTABLE_GOLD_GAIN_PER_HOUR_SHORT = 375
REPLANTABLE_GOLD_GAIN_PER_HOUR_MEDIUM = 245
REPLANTABLE_GOLD_GAIN_PER_HOUR_LONG = 150
REPLANTABLE_GOLD_GAIN_PER_HOUR_VERY_LONG = 95

GROWABLE_XP_GAIN_PER_HOUR = 200
CRAFTABLE_XP_GAIN_PER_HOUR = 400


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

        self.generate_new_price()

    def generate_new_price(self) -> None:
        self.gold_reward = random.randint(
            self.min_market_price, self.max_market_price
        )

    def _calculate_xp(self) -> int:
        return int(
            (self.grow_time / 3600) * GROWABLE_XP_GAIN_PER_HOUR / self.amount
        ) or 1

    def _calculate_min_market_price(self) -> int:
        total_new_value = self.gold_price - (self.gold_price * 0.25)

        return int(total_new_value / self.amount) or 1

    def _calculate_max_market_price(self) -> int:
        gold_per_item = self.gold_price / self.amount

        if self.grow_time <= VERY_SHORT_PERIOD:
            gain = GOLD_GAIN_PER_HOUR_VERY_SHORT
        elif self.grow_time <= SHORT_PERIOD:
            gain = GOLD_GAIN_PER_HOUR_SHORT
        elif self.grow_time <= MEDIUM_PERIOD:
            gain = GOLD_GAIN_PER_HOUR_MEDIUM
        elif self.grow_time <= LONG_PERIOD:
            gain = GOLD_GAIN_PER_HOUR_LONG
        else:
            gain = GOLD_GAIN_PER_HOUR_VERY_LONG

        total_profit = (self.grow_time / 3600) * gain

        return int(gold_per_item + (total_profit / self.amount)) or 1


class ReplantableItem(PlantableItem):

    __slots__ = ('iterations')

    def __init__(self, iterations: int, *args, **kwargs):
        self.iterations = iterations
        super().__init__(*args, **kwargs)

    def _calculate_min_market_price(self) -> int:
        total_new_value = self.gold_price - (self.gold_price * 0.25)

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


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
        #gold_reward: int,
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

        #self.min_market_price = min_market_price
        #self.max_market_price = max_market_price

        self.generate_new_price()

    def generate_new_price(self) -> None:
        self.gold_reward = random.randint(
            self.min_market_price, self.max_market_price
        )

    def _calculate_xp(self) -> int:
        return int((self.time / 3600) * CRAFTABLE_XP_GAIN_PER_HOUR)


@dataclass
class Boost():
    pass


def load_all_items() -> list:
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


all_items = load_all_items()
for item in all_items:
    print(f"{item.emoji}{item.name}: min: {item.min_market_price}, max: {item.max_market_price}, xp: {item.xp}")

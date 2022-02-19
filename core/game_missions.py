import json
import random

from . import game_items


with open("data/mission_names.json", "r") as file:
    MISSION_NAMES = json.load(file)


class BusinessMission:

    __slots__ = ("requests", "gold_reward", "xp_reward", "name", "chest")

    def __init__(
        self,
        requests: list,  # Either tuples of (item_id, amount) or (item object, amount)
        gold_reward: int,
        xp_reward: int,
        name: str,
        chest: int = 0
    ) -> None:
        self.requests = requests
        self.gold_reward = gold_reward
        self.xp_reward = xp_reward
        self.name = name
        self.chest = chest

    @classmethod
    def generate(
        cls,
        cmd,
        growables_multiplier: float = 1.0,
        reward_multiplier: float = 1.0,
        add_chest: bool = True
    ):
        user_level = cmd.user_data.level
        if user_level < 3:
            max_requests, max_products_requests = 1, 1
        elif user_level < 5:
            max_requests, max_products_requests = 2, 1
        elif user_level < 10:
            max_requests, max_products_requests = 2, 1
        elif user_level < 15:
            max_requests, max_products_requests = 3, 1
        elif user_level < 20:
            max_requests, max_products_requests = 3, 1
        elif user_level < 25:
            max_requests, max_products_requests = 3, 2
        else:
            max_requests, max_products_requests = 4, 2

        request_items = []
        # Increase growables_multiplier for extra complexity
        multiplier = int(growables_multiplier * user_level)
        total_request_amount = random.randint(1, max_requests)

        # 1/3 chance to require products
        if user_level >= 3 and random.randint(1, 3) == 1:
            # If multiplier, lower the chance to get more product requests
            product_amount_population = []
            for i in range(max_products_requests):
                product_amount_population.extend([i + 1] * (max_products_requests - i) * 3)

            product_request_amount = random.choice(product_amount_population)
            total_request_amount = total_request_amount - product_request_amount

            products: dict = cmd.items.get_random_items(
                user_level=user_level,
                extra_luck=0.82,
                total_draws=product_request_amount,
                products_multiplier=int(user_level / 12) or 1,
                growables=False,
                products=True
            )
            request_items.extend(products.items())

        # If we still have requests to add
        if total_request_amount > 0:
            growables: dict = cmd.items.get_random_items(
                user_level=user_level,
                extra_luck=0.62,
                total_draws=total_request_amount,
                growables_multiplier=multiplier,
                growables=True,
                products=False
            )
            request_items.extend(growables.items())

        total_worth, requests = 0, []
        for item, amount in request_items:
            requests.append((item.id, amount))

            extra_worth = random.randint(70, 115) / 100  # 0.7 - 1.15
            total_worth += int(item.max_market_price * amount * extra_worth)

        total_worth = int(total_worth * reward_multiplier)
        xp_reward = random.randint(int(total_worth / 17), int(total_worth / 16))
        gold_reward = total_worth - xp_reward

        # Add chest in every 8th mission
        chest_id = 0
        if add_chest and random.randint(1, 8) == 1:
            chests_and_rarities = {
                1000: 750.0,  # Gold
                1001: 2000.0,  # Common
                1002: 950.0,  # Uncommon
                1003: 420.0,  # Rare
                1004: 150.0,  # Epic
                1005: 25.0  # Legendary
            }

            chest_id = random.choices(
                population=list(chests_and_rarities.keys()),
                weights=chests_and_rarities.values(),
                k=1
            )[0]

        return cls(
            requests=requests,
            gold_reward=gold_reward,
            xp_reward=xp_reward,
            name=random.choice(MISSION_NAMES['businesses']),
            chest=chest_id
        )

    def initialize_from_partial_data(self, cmd) -> None:
        self.requests = [
            (cmd.items.find_item_by_id(request[0]), request[1])
            for request in self.requests
        ]

        if self.chest:
            self.chest = cmd.items.find_chest_by_id(self.chest)

    def format_for_embed(self, cmd) -> str:
        fmt = f"\N{BOOKMARK TABS} {self.name}\nRequest:\n"

        for req in self.requests:
            item, amount = req[0], req[1]
            fmt += f"**{item.full_name} x{amount}**\n"

        fmt += "\n\N{MONEY BAG} Rewards:\n**"
        if self.gold_reward:
            fmt += f"{self.gold_reward} {cmd.client.gold_emoji} "
        if self.xp_reward:
            fmt += f"{self.xp_reward} {cmd.client.xp_emoji}"
        if self.chest:
            fmt += f"\n\N{WRAPPED PRESENT} Bonus: 1x {self.chest.emoji} "

        return fmt + "**"


class ExportMission:

    __slots__ = (
        "item",
        "amount",
        "base_gold",
        "base_xp",
        "shipments",
        "port_name"
    )

    def __init__(
        self,
        item: game_items.MarketItem,
        amount: int,
        base_gold: int,
        base_xp: int,
        shipments: int,
        port_name: str
    ) -> None:
        self.item = item
        self.amount = amount
        self.base_gold = base_gold
        self.base_xp = base_xp
        self.shipments = shipments
        self.port_name = port_name

    @classmethod
    def generate(cls, cmd):
        # Small chance to randomize with products
        # Because we have more products than other items
        randomize_products: bool = random.randint(1, 3) == 1

        item, amount = cmd.items.get_random_items(
            user_level=cmd.user_data.level,
            extra_luck=0.75,
            total_draws=1,
            growables_multiplier=cmd.user_data.level,
            products_multiplier=int(cmd.user_data.level / 15) or 1,
            growables=True,
            products=randomize_products
        ).items()[0]

        return cls(
            item=item,
            amount=amount,
            base_gold=int(item.max_market_price / 5.11 * amount) or 1,
            base_xp=int(item.xp * amount / 12) or 1,
            shipments=0,
            port_name=random.choice(MISSION_NAMES['ports'])
        )

    def rewards_for_shipment(self, shipment: int = 0) -> tuple:
        shipment = shipment or self.shipments + 1

        chests_per_shipments = {3: 1001, 7: 1003, 10: 1004}

        try:
            chest_id = chests_per_shipments[shipment]
        except KeyError:
            chest_id = None

        gold = self.base_gold * shipment
        xp = self.base_xp + self.base_xp * (shipment * 0.4)
        return (int(gold), int(xp), chest_id)

import json
import random
from dataclasses import dataclass


with open("data/mission_names.json", "r") as file:
    MISSION_NAMES = json.load(file)


@dataclass
class MissionRequest:
    """
    Used to store less data in DB.
    We could just jsonpickle it, but why should we store all
    item data? Also item properties might change any time.
    """

    __slots__ = ("item_id", "amount")

    item_id: int
    amount: int


class BusinessMission:

    __slots__ = ("requests", "gold_reward", "xp_reward", "name", "chest")

    def __init__(
        self,
        requests: list,
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
        ctx,
        growables_multiplier: float = 1.0,
        reward_multiplier: float = 1.0,
        add_chest: bool = True
    ):
        user_level = ctx.user_data.level
        if user_level < 3:
            max_requests = 1
        elif user_level < 5:
            max_requests, max_products_req = 2, 1
        elif user_level < 10:
            max_requests, max_products_req = 2, 1
        elif user_level < 15:
            max_requests, max_products_req = 3, 1
        elif user_level < 20:
            max_requests, max_products_req = 3, 2
        elif user_level < 25:
            max_requests, max_products_req = 3, 2
        else:
            max_requests, max_products_req = 4, 2

        # Increase growables_multiplier for extra complexity
        multiplier = int(growables_multiplier * user_level)

        request_items = []
        request_amount = random.randint(1, max_requests)

        # 1/3 chance to require products
        if user_level >= 3 and random.randint(1, 3) == 1:
            # Default max product request amount is 1.
            # If multiplier, lower the chance to get more requests
            population = []
            for i in range(max_products_req):
                population.extend([i + 1] * (max_products_req - i) * 3)

            product_req_amount = random.choice(population)
            request_amount = request_amount - product_req_amount

            products = ctx.items.get_random_items(
                user_level=user_level,
                extra_luck=0.82,
                total_draws=product_req_amount,
                products_multiplier=int(user_level / 10) or 1,
                growables=False,
                products=True,
                specials=False
            )
            request_items.extend(products)

        # If we still have requests to add
        if request_amount > 0:
            growables = ctx.items.get_random_items(
                user_level=user_level,
                extra_luck=0.82,
                total_draws=request_amount,
                growables_multiplier=multiplier,
                growables=True,
                products=False,
                specials=False
            )
            request_items.extend(growables)

        total_worth, requests = 0, []
        for item, amount in request_items:
            requests.append(MissionRequest(item.id, amount))
            total_worth += int(item.max_market_price * amount * 1.08)

        total_worth = int(total_worth * reward_multiplier)
        xp_reward = random.randint(
            int(total_worth / 20), int(total_worth / 18)
        )
        gold_reward = total_worth - xp_reward

        # Add chest in every 8th mission
        chest_id = 0
        if add_chest and random.randint(1, 8) == 1:
            chests_and_rarities = {
                1000: 450.0,  # Gold
                1001: 1700.0,  # Common
                1002: 950.0,  # Uncommon
                1003: 350.0,  # Rare
                1004: 100.0,  # Epic
                1005: 1.8  # Legendary
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

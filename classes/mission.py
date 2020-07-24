import json
from random import randint, choice
from datetime import datetime, timedelta

from classes.item import base_amount_for_growables

BUISNESS_NAMES = (
    "Toby's Greenhouse", "FishTastic Restaurants", "Mark's Store",
    "Robert's and John's Factory", "Elon's Masks", "Bill's gates and fences",
    "Pink Elephants Store", 'Kindergarden "Nuts"', "Laura's Cafe",
    'Restaurant "Yuri mum"', "Seapickle Cafe", "Local Highschool",
    "Katie's Grandma", "BurgerStation Cafe", 'Kindergarden "Chill"',
    "Supermarket 24/7", "Bob's restraurant", "Soup Cafe",
    "Lazloo's Kitchen", "Horror pancake's celler", "Andy's Cow Resort",
    "Donkey's bakery", "Bob's dairy", "Stella's aunt",
    "Greg's waterpark", "Cafe El-pesto", "Kebab dinner"
)

PORT_NAMES = (
    "\ud83c\uddf1\ud83c\uddfbVentspils", "\ud83c\uddf8\ud83c\uddeaHelsinki", "\ud83c\udde9\ud83c\uddeaBremerhaven",
    "\ud83c\udde8\ud83c\uddf3Shanghai", "\ud83c\uddf0\ud83c\uddf7Busan", "\ud83c\uddf3\ud83c\uddf1Rotterdam",
    "\ud83c\udde7\ud83c\uddeaAntwerp", "\ud83c\uddec\ud83c\udde7Dubai", "\ud83c\uddf2\ud83c\uddfePort Klang",
    "\ud83c\uddf9\ud83c\uddfcKaohsiung", "\ud83c\uddfa\ud83c\uddf8Los Angeles", "\ud83c\uddea\ud83c\uddf8Valencia",
    "\ud83c\uddee\ud83c\uddf3Mumbai", "\ud83c\uddec\ud83c\uddf7Piraeus", "\ud83c\uddef\ud83c\uddf5Tokyo",
    "\ud83c\udde7\ud83c\uddf7Santos", "\ud83c\udde8\ud83c\udde6Vancouver", "\ud83c\uddf2\ud83c\udde6Tanger-Med",
    "\ud83c\uddee\ud83c\uddf9Trieste", "\ud83c\uddf7\ud83c\uddfaPrimorsk", "\ud83c\uddf9\ud83c\uddf7Izmit"
)

EXPORT_DURATION = 22500 # 6 hours 15 minutes

class Mission:
    __slots__ = ('buisness', 'moneyaward', 'xpaward', 'requests')

    def __init__(self, buisness, moneyaward, xpaward, requests):
        self.buisness = buisness
        self.moneyaward = moneyaward
        self.xpaward = xpaward
        self.requests = requests

    @classmethod
    def generate(cls, useracc, boosted=False):
        requests, alreadyused = [], []

        suitableitems = useracc.find_all_unlocked_tradeble_items(special=False)
        user_level = useracc.level
        requestsamount = randint(1, cls.items_for_level(user_level))

        # WARNING: if user doesnt have unlocked
        # enough items, then loop would never end.
        # Check items_for_level().
        for i in range(requestsamount):
            newitem = None
            
            while not newitem or newitem in alreadyused:
                newitem = choice(suitableitems)
            
            amount = cls.calc_amount(user_level, newitem)
            req = (newitem, amount)
            
            requests.append(req)
            alreadyused.append(newitem)

        xp, money = cls.calc_reward(requests, boosted)
        buisness = cls.get_buisness_name()
        
        return cls(buisness, money, xp, requests)

    @staticmethod
    def items_for_level(level):
        if level < 3: return 1
        elif level < 5: return 2
        elif level < 15: return 3
        elif level < 25: return 4
        else: return 5

    @staticmethod
    def calc_amount(level, item):
        if level < 3: 
            if not hasattr(item, "craftedfrom"):
                return base_amount_for_growables(item)
            else: return 1
        elif level < 10:
            if not hasattr(item, "craftedfrom"):
                return base_amount_for_growables(item) * 3
            else: return 1
        elif level < 20:
            if not hasattr(item, "craftedfrom"):
                return base_amount_for_growables(item) * 5
            elif item.rarity == 2: return randint(1, 2)
            else: return 1
        elif level < 30:
            if not hasattr(item, "craftedfrom"):
                return base_amount_for_growables(item) * 8
            elif item.rarity == 2: return randint(1, 2)
            else: return 1
        else:
            if not hasattr(item, "craftedfrom"):
                return base_amount_for_growables(item) * 10
            elif item.rarity == 2: return randint(1, 3)
            else: return randint(1, 2)

    @staticmethod
    def calc_reward(items, boosted):
        sum = 0

        for item in items:
            sum += int(item[0].maxprice * 1.37 * item[1])

        if boosted:
            sum = int(sum * 1.5)

        xp = randint(int(sum / 20), sum)
        money = sum - xp
        
        return xp, money

    def export_as_string(self):
        string = ''
        for req in self.requests:
            string += f"{req[0].id}/{req[1]}="
        
        return string[:-1]

    @classmethod
    def import_as_string(cls, client, buisness, moneyaward, xpaward, string):
        increquests = string.split('=')
        requests = []

        try:
            for req in increquests:
                temp = req.split('/')
                reqv = (client.allitems[int(temp[0])], int(temp[1]))
                requests.append(reqv)
        except KeyError:
            raise Exception(f"Critical: Cannot find item. (importstring)")

        return cls(buisness, moneyaward, xpaward, requests)

    @staticmethod
    def get_buisness_name():
        return choice(BUISNESS_NAMES)

def missions_per_level(level):
    if level < 10: return 3
    elif level < 20: return 4
    elif level < 30: return 5
    else: return 6


class ExportMission:
    __slots__ = ('item', 'port', 'amount', 'base_gold', 'base_xp', 'shipped', 'ends')
    
    def __init__(self, item, port, amount, base_gold, base_xp, shipped, ends=None):
        self.item = item
        self.port = port
        self.amount = amount
        self.base_gold = base_gold
        self.base_xp = base_xp
        
        # When this export missions ends
        if ends:
            self.ends = ends
        else:
            ends = datetime.now().replace(microsecond=0) + timedelta(seconds=EXPORT_DURATION)
            self.ends = ends
        
        # How many times completed
        self.shipped = shipped

    @classmethod
    def generate(cls, useracc):
        suitableitems = useracc.find_all_unlocked_crop_items()
        user_level = useracc.level
        
        item = choice(suitableitems)
        amount = cls.calc_amount(useracc.client, user_level, item)

        base_xp, base_gold = cls.calc_base_reward(item, amount)
        port_name = cls.get_port_name()

        return cls(item, port_name, amount, base_gold, base_xp, 0)

    @staticmethod
    def calc_base_reward(item, amount):
        money_per_item = item.minprice
        money = money_per_item * amount

        xp_per_item = int(item.xp / 3.5) or 1
        xp = xp_per_item * amount
        
        return xp, money

    @staticmethod
    def calc_amount(client, level, item):
        return base_amount_for_growables(item) * (int(level / 2.4) or 1)

    def calc_reward_for_shipment(self, shipment=0):
        times_shipped = shipment or self.shipped

        gold = self.base_gold + self.base_gold * (times_shipped * 0.3)
        xp = self.base_xp + self.base_xp * (times_shipped * 0.3)
        
        return int(gold) or 1, int(xp) or 1

    def export_as_json(self):
        data = {}

        data["item"] = self.item.id
        data["port"] = self.port
        data["amount"] = self.amount
        data["gold"] = self.base_gold
        data["xp"] = self.base_xp
        data["ends"] = self.ends.isoformat()
        data["shipped"] = self.shipped

        return json.dumps(data)

    @classmethod
    def import_from_json(cls, client, json_str):
        data_dict = json.loads(json_str)
        
        return cls(
            item=client.allitems[data_dict["item"]],
            port=data_dict["port"],
            amount=data_dict["amount"],
            base_gold=data_dict["gold"],
            base_xp=data_dict["xp"],
            ends=datetime.fromisoformat(data_dict["ends"]),
            shipped=data_dict["shipped"]
        )

    @staticmethod
    def get_port_name():
        return choice(PORT_NAMES)
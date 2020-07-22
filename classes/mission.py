from random import randint, choice

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

        suitableitems = useracc.find_all_unlocked_tradeble_items()
        user_level = useracc.level
        requestsamount = randint(1, cls.itemsforlevel(user_level))

        # WARNING: if user doesnt have unlocked
        # enough items, then loop would never end.
        # Check itemsforlevel().
        for i in range(requestsamount):
            newitem = None
            
            while not newitem or newitem in alreadyused:
                newitem = choice(suitableitems)
            
            amount = cls.calcamount(user_level, newitem)
            req = (newitem, amount)
            
            requests.append(req)
            alreadyused.append(newitem)

        xp, money = cls.calcreward(requests, boosted)
        buisness = cls.buisness_name()
        
        return cls(buisness, money, xp, requests)

    @staticmethod
    def itemsforlevel(level):
        if level < 3: return 1
        elif level < 5: return 2
        elif level < 15: return 3
        elif level < 25: return 4
        else: return 5

    @staticmethod
    def calcamount(level, item):
        if level < 3: 
            if item.rarity == 1: return randint(6, 20)
            else: return 1
        elif level < 10:
            if item.rarity == 1: return randint(10, 50)
            elif item.rarity == 2: return randint(1, 2)
            else: return 1
        elif level < 20:
            if item.rarity == 1: return randint(15, 80)
            elif item.rarity == 2: return randint(1, 2)
            else: return 1
        elif level < 30:
            if item.rarity == 1: return randint(20, 140)
            elif item.rarity == 2: return randint(1, 3)
            else: return randint(1, 2)
        else:
            if item.rarity == 1: return randint(25, 200)
            elif item.rarity == 2: return randint(1, 4)
            else: return randint(1, 2)

    @staticmethod
    def calcreward(items, boosted):
        sum = 0

        for item in items:
            sum += int(item[0].maxprice * 1.37 * item[1])

        if boosted:
            sum = int(sum * 1.5)

        xp = randint(int(sum / 20), sum)
        money = sum - xp
        
        return xp, money

    def exportstring(self):
        string = ''
        for req in self.requests:
            string += f"{req[0].id}/{req[1]}="
        
        return string[:-1]

    @classmethod
    def importstring(cls, client, buisness, moneyaward, xpaward, string):
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
    def buisness_name():
        return choice(BUISNESS_NAMES)

def missions_per_level(level):
    if level < 10: return 3
    elif level < 20: return 4
    elif level < 30: return 5
    else: return 6
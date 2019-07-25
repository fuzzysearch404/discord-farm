from random import randint, choice


class Mission:
    def __init__(self, moneyaward, xpaward, requests):
        self.moneyaward = moneyaward
        self.xpaward = xpaward
        self.requests = requests

    @classmethod
    def generate(cls, client, level):
        suitableitems = []
        requests = []
        alreadyused = []

        for item in client.crops.values():
            if item.level <= level:
                suitableitems.append(item)

        requestsamount = randint(1, cls.itemsforlevel(level))

        for i in range(requestsamount):
            newitem = None
            while not newitem or newitem in alreadyused:
                newitem = choice(suitableitems)
            amount = cls.calcamount(level, newitem)
            req = (newitem, amount)
            requests.append(req)
            alreadyused.append(newitem)

        xp, money = cls.calcreward(requests)
        return cls(money, xp, requests)

    @staticmethod
    def itemsforlevel(level):
        if level < 3:
            return 1
        elif level < 5:
            return 2
        else:
            return 3

    @staticmethod
    def calcamount(level, item):
        if level < 3:
            return randint(8, 20)
        elif level < 10:
            if item.rarity == 1:
                return randint(10, 50)
            else:
                return randint(1, 5)
        elif level < 20:
            if item.rarity == 1:
                return randint(30, 100)
            else:
                return randint(1, 6)
        else:
            if item.rarity == 1:
                return randint(1, 150)
            else:
                return randint(1, 8)

    @staticmethod
    def calcreward(items):
        sum = 0

        for item in items:
            sum += item[0].xp * item[1]
            sum += int(item[0].maxprice * 1.3 * item[1])

        xp = randint(int(sum / 4), sum)
        money = sum - xp
        return xp, money

    def exportstring(self):
        string = ''
        for req in self.requests:
            string += f"{req[0].id}/{req[1]}="
        return string[:-1]

    @classmethod
    def importstring(cls, client, moneyaward, xpaward, string):
        increquests = string.split('=')
        requests = []

        try:
            for req in increquests:
                temp = req.split('/')
                reqv = (client.allitems[int(temp[0])], int(temp[1]))
                requests.append(reqv)
        except KeyError:
            raise Exception(f"Critical: Cannot find item. (importstring)")

        return cls(moneyaward, xpaward, requests)

import json
from random import randint
from difflib import get_close_matches


class Item:
    def __init__(
        self, id, emoji, name, rarity, amount,
        cost, scost, level, xp, img
    ):
        self.id = id
        self.emoji = emoji
        self.name = name
        self.rarity = rarity
        self.amount = amount
        self.cost = cost
        self.scost = scost
        self.level = level
        self.xp = xp
        self.img = img
        self.type = None


class Crop(Item):
    def __init__(self, name2, minprice, maxprice, grows, dies, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.minprice = minprice
        self.maxprice = maxprice
        self.grows = grows
        self.dies = dies
        self.type = 'crop'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)


def croploader():
    rcrops = {}

    with open("files/crops.json", "r", encoding="UTF8") as file:
        crops = json.load(file)

    for c, v in crops.items():
        crop = Crop(
            v['name2'], v['minprice'], v['maxprice'], v['grows'], v['dies'],
            v['id'], v['emoji'], v['name'], v['rarity'], v['amount'],
            v['cost'], v['scost'], v['level'], v['xp'], v['img']
        )
        rcrops[int(c)] = crop

    return rcrops


def finditembyname(client, name):
    itemslist = list(client.allitems.values())

    tempitems = {}
    tempwords = []
    for item in itemslist:
        tempitems[item.name] = item
        tempwords.append(item.name)
        if item.name2:
            tempitems[item.name2] = item
            tempwords.append(item.name2)

    matches = get_close_matches(name, tempwords)
    if not matches:
        return False
    return tempitems[matches[0]]

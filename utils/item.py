import json
import utils.embeds as emb
from random import randint
from difflib import get_close_matches


class Item:
    def __init__(
        self, id, emoji, name, rarity, amount,
        cost, scost
    ):
        self.id = id
        self.emoji = emoji
        self.name = name
        self.rarity = rarity
        self.amount = amount
        self.cost = cost
        self.scost = scost
        self.type = None


class CropSeed(Item):
    def __init__(self, name2, level, grows, dies, expandsto, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.level = level
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.type = 'cropseed'

    def getchild(self, client):
        return client.crops[self.expandsto]


class Crop(Item):
    def __init__(self, name2, level, xp, img, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.level = level
        self.xp = xp
        self.img = img
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.type = 'crop'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)

    def getparent(self, client):
        return client.allitems[self.madefrom]


class Animal(Item):
    def __init__(self, name2, level, xp, grows, dies, expandsto, img, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.level = level
        self.xp = xp
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.img = img
        self.type = 'animal'

    def getchild(self, client):
        return client.items[self.expandsto]


class Tree(Item):
    def __init__(self, name2, level, xp, grows, dies, expandsto, img, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.level = level
        self.xp = xp
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.img = img
        self.type = 'tree'

    def getchild(self, client):
        return client.crops[self.expandsto]


class CraftedItem(Item):
    def __init__(self, name2, level, xp, img, minprice, maxprice, madefrom, time, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.level = level
        self.xp = xp
        self.img = img
        self.minprice = minprice
        self.maxprice = maxprice
        self.unpackmadefrom(madefrom)
        self.time = time
        self.type = 'crafteditem'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)

    def unpackmadefrom(self, madefrom):
        temp = {}
        real = {}

        for pack in madefrom:
            temp.update(pack)

        for key, value in temp.items():
            real[int(key)] = value

        self.madefrom = real


class SellableItem(Item):
    def __init__(self, name2, xp, minprice, maxprice, level, img, *args, **kw):
        super().__init__(*args, **kw)
        self.name2 = name2
        self.xp = xp
        self.minprice = minprice
        self.maxprice = maxprice
        self.level = level
        self.img = img
        self.type = 'item'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)


def cropseedloader():
    rseeds = {}

    with open("files/cropseed.json", "r", encoding="UTF8") as file:
        seeds = json.load(file)

    for c, v in seeds.items():
        crop = CropSeed(
            v['name2'], v['level'], v['grows'], v['dies'], v['expandsto'], v['id'],
            v['emoji'], v['name'], v['rarity'], v['amount'], v['cost'],
            v['scost']
        )
        rseeds[int(c)] = crop

    return rseeds


def croploader():
    rcrops = {}

    with open("files/crop.json", "r", encoding="UTF8") as file:
        crops = json.load(file)

    for c, v in crops.items():
        crop = Crop(
            v['name2'], v['level'], v['xp'], v['img'], v['minprice'], v['maxprice'],
            v['madefrom'], v['id'], v['emoji'], v['name'], v['rarity'],
            v['amount'], v['cost'], v['scost']
        )
        rcrops[int(c)] = crop

    return rcrops


def crafteditemloader():
    ritems = {}

    with open("files/citems.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = CraftedItem(
            v['name2'], v['level'], v['xp'], v['img'], v['minprice'], v['maxprice'],
            v['madefrom'], v['time'], v['id'], v['emoji'], v['name'], v['rarity'],
            v['amount'], v['cost'], v['scost']
        )
        ritems[int(c)] = item

    return ritems


def animalloader():
    ritems = {}

    with open("files/animals.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = Animal(
            v['name2'], v['level'], v['xp'], v['grows'], v['dies'], v['expandsto'],
            v['img'], v['id'], v['emoji'], v['name'], v['rarity'],
            v['amount'], v['cost'], v['scost']
        )
        ritems[int(c)] = item

    return ritems


def treeloader():
    ritems = {}

    with open("files/trees.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = Tree(
            v['name2'], v['level'], v['xp'], v['grows'], v['dies'], v['expandsto'],
            v['img'], v['id'], v['emoji'], v['name'], v['rarity'],
            v['amount'], v['cost'], v['scost']
        )
        ritems[int(c)] = item

    return ritems


def itemloader():
    ritems = {}

    with open("files/items.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = SellableItem(
            v['name2'], v['xp'], v['minprice'], v['maxprice'], v['level'],
            v['img'], v['id'], v['emoji'], v['name'], v['rarity'],
            v['amount'], v['cost'], v['scost']
        )
        ritems[int(c)] = item

    return ritems


def finditembyname(client, name):
    itemslist = list(client.allitems.values())

    tempitems = {}
    tempwords = []
    for item in itemslist:
        tempitems[item.name] = item
        tempwords.append(item.name)
        if item.name2 and item.type != 'cropseed':
            tempitems[item.name2] = item
            tempwords.append(item.name2)

    matches = get_close_matches(name, tempwords)
    if not matches:
        return False
    return tempitems[matches[0]]


async def finditem(client, ctx, possibleitem):
    try:
        possibleitem = int(possibleitem)
    except ValueError:
        pass

    if isinstance(possibleitem, int):
        try:
            item = client.allitems[possibleitem]
        except KeyError:
            embed = emb.errorembed("Neatradu tādu lietu\ud83e\udd14", ctx)
            await ctx.send(embed=embed)
            return None
    elif isinstance(possibleitem, str):
        item = finditembyname(client, possibleitem)
        if not item:
            embed = emb.errorembed("Neatradu tādu lietu\ud83e\udd14", ctx)
            await ctx.send(embed=embed)
            return None

    return item


def convertmadefrom(client, madefrom):
    temp = {}
    for id, amount in madefrom.items():
        item = client.allitems[id]
        temp[item] = amount

    return temp


def madefromtostring(client, madefrom):
    string = ''
    xitems = convertmadefrom(client, madefrom)
    for item, value in xitems.items():
        string += f"{item.emoji}{item.name.capitalize()} x{value}, "

    return string[:-2]

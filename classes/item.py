import json
import utils.embeds as emb
from random import randint
from difflib import get_close_matches


class Item:
    def __init__(
        self, id, level, emoji, name, rarity, amount
    ):
        self.id = id
        self.level = level
        self.emoji = emoji
        self.name = name
        self.rarity = rarity
        self.amount = amount
        self.type = None


class CropSeed(Item):
    def __init__(self, grows, dies, expandsto, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.gold_cost = gold_cost
        self.type = 'cropseed'

    def getchild(self, client):
        return client.crops[self.expandsto]


class Crop(Item):
    def __init__(self, xp, img, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
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
        return client.cropseeds[self.madefrom]


class Animal(Item):
    def __init__(self, grows, dies, expandsto, img, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.img = img
        self.gold_cost = gold_cost
        self.type = 'animal'

    def getchild(self, client):
        return client.animalproducts[self.expandsto]


class AnimalProduct(Item):
    def __init__(self, xp, minprice, maxprice, madefrom, img, *args, **kw):
        super().__init__(*args, **kw)
        self.xp = xp
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.img = img
        self.type = 'animalproduct'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)

    def getparent(self, client):
        return client.animals[self.madefrom]


class Tree(Item):
    def __init__(self, grows, dies, expandsto, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = dies
        self.expandsto = expandsto
        self.gold_cost = gold_cost
        self.type = 'tree'

    def getchild(self, client):
        return client.treeproducts[self.expandsto]


class TreeProduct(Item):
    def __init__(self, xp, img, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
        self.xp = xp
        self.img = img
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.type = 'treeproduct'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)

    def getparent(self, client):
        return client.trees[self.madefrom]


class CraftedItem(Item):
    def __init__(self, xp, img, minprice, maxprice, madefrom, time, *args, **kw):
        super().__init__(*args, **kw)
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

class SpecialItem(Item):
    def __init__(self, xp, minprice, maxprice, img, *args, **kw):
        super().__init__(*args, **kw)
        self.xp = xp
        self.minprice = minprice
        self.maxprice = maxprice
        self.img = img
        self.type = 'special'
        self.getmarketprice()

    def getmarketprice(self):
        self.marketprice = randint(self.minprice, self.maxprice)


def cropseedloader():
    rseeds = {}

    with open("files/cropseed.json", "r", encoding="UTF8") as file:
        seeds = json.load(file)

    for c, v in seeds.items():
        crop = CropSeed(
            level=v['level'],
            grows=v['grows'],
            dies=v['dies'],
            expandsto=v['expandsto'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=1,
            gold_cost=v['gold_cost']
        )
        rseeds[int(c)] = crop

    return rseeds


def croploader():
    rcrops = {}

    with open("files/crop.json", "r", encoding="UTF8") as file:
        crops = json.load(file)

    for c, v in crops.items():
        crop = Crop(
            id=v['id'],
            level=v['level'],
            xp=v['xp'],
            img=v['img'],
            minprice=v['minprice'], 
            maxprice=v['maxprice'],
            madefrom=v['madefrom'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount']
        )
        rcrops[int(c)] = crop

    return rcrops


def treeloader():
    ritems = {}

    with open("files/trees.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = Tree(
            level=v['level'],
            grows=v['grows'],
            dies=v['dies'],
            expandsto=v['expandsto'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount'],
            gold_cost=v['gold_cost']
        )
        ritems[int(c)] = item

    return ritems


def treeproductloader():
    rprods = {}

    with open("files/treeproducts.json", "r", encoding="UTF8") as file:
        prods = json.load(file)

    for c, v in prods.items():
        prod = TreeProduct(
            id=v['id'],
            level=v['level'],
            xp=v['xp'],
            img=v['img'],
            minprice=v['minprice'], 
            maxprice=v['maxprice'],
            madefrom=v['madefrom'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount']
        )
        rprods[int(c)] = prod

    return rprods


def animalloader():
    ritems = {}

    with open("files/animals.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = Animal(
            level=v['level'],
            grows=v['grows'],
            dies=v['dies'],
            expandsto=v['expandsto'],
            img=v['img'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount'],
            gold_cost=v['gold_cost']
        )
        ritems[int(c)] = item

    return ritems


def animalproductloader():
    ritems = {}

    with open("files/animalproducts.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = AnimalProduct(
            xp=v['xp'],
            minprice=v['minprice'],
            maxprice=v['maxprice'],
            level=v['level'],
            img=v['img'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount'],
            madefrom=v['madefrom']
        )
        ritems[int(c)] = item

    return ritems


def crafteditemloader():
    ritems = {}

    with open("files/craftables.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = CraftedItem(
            level=v['level'],
            xp=v['xp'],
            img=v['img'],
            minprice=v['minprice'], 
            maxprice=v['maxprice'],
            madefrom=v['madefrom'],
            time=v['time'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount']
        )
        ritems[int(c)] = item

    return ritems

def specialitemloader():
    sitems = {}

    with open("files/specialitems.json", "r", encoding="UTF8") as file:
        litems = json.load(file)

    for c, v in litems.items():
        item = SpecialItem(
            level=v['level'],
            xp=v['xp'],
            img=v['img'],
            minprice=v['minprice'], 
            maxprice=v['maxprice'],
            id=v['id'],
            emoji=v['emoji'],
            name=v['name'],
            rarity=v['rarity'],
            amount=v['amount']
        )
        sitems[int(c)] = item

    return sitems


def finditembyname(client, name):
    itemslist = list(client.allitems.values())

    tempitems = {}
    tempwords = []
    for item in itemslist:
        tempitems[item.name] = item
        tempwords.append(item.name)

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
            embed = emb.errorembed("I didn't find any items by this ID \ud83e\udd14", ctx)
            await ctx.send(embed=embed)
            return None
    else:
        item = finditembyname(client, possibleitem)
        if not item:
            embed = emb.errorembed("I didn't find any items named like that \ud83e\udd14", ctx)
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
        string += f"{item.emoji}{item.name.capitalize()} x{value},\n"

    return string[:-2]

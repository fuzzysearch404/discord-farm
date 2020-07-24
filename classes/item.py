import json
from random import randint
from difflib import get_close_matches

import utils.embeds as emb


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
    def __init__(self, grows, expandsto, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = int(grows * 1.5)
        self.expandsto = expandsto
        self.gold_cost = gold_cost
        self.type = 'cropseed'


class Crop(Item):
    def __init__(self, img, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
        self.img = img
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.type = 'crop'

    @property
    def xp(self):
        xp = int((self.madefrom.grows / 3600) * 200 / self.amount)
        
        return xp or 1


class Animal(Item):
    def __init__(self, grows, expandsto, img, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = int(grows * 1.5)
        self.expandsto = expandsto
        self.img = img
        self.gold_cost = gold_cost
        self.type = 'animal'


class AnimalProduct(Item):
    def __init__(self, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.type = 'animalproduct'

    @property
    def xp(self):
        xp = int((self.madefrom.grows / 3600) * 200 / self.amount)
        
        return xp or 1


class Tree(Item):
    def __init__(self, grows, expandsto, gold_cost, *args, **kw):
        super().__init__(*args, **kw)
        self.grows = grows
        self.dies = int(grows * 1.5)
        self.expandsto = expandsto
        self.gold_cost = gold_cost
        self.type = 'tree'


class TreeProduct(Item):
    def __init__(self, img, minprice, maxprice, madefrom, *args, **kw):
        super().__init__(*args, **kw)
        self.img = img
        self.minprice = minprice
        self.maxprice = maxprice
        self.madefrom = madefrom
        self.type = 'treeproduct'

    @property
    def xp(self):
        xp = int((self.madefrom.grows / 3600) * 200 / self.amount)
        
        return xp or 1


class CraftedItem(Item):
    def __init__(self, img, craftedfrom, time, *args, **kw):
        super().__init__(*args, **kw)
        self.img = img
        self.unpackmadefrom(craftedfrom)
        self.time = time
        self.type = 'crafteditem'

    @property
    def minprice(self):
        price = 0
        for item, amount in self.craftedfrom.items():
            price += item.maxprice * amount

        return int(price - (price / 8))

    @property
    def maxprice(self):
        price = 0
        for item, amount in self.craftedfrom.items():
            price += item.maxprice * amount

        return int(price + (price / 10) + (self.time / 2000))

    @property
    def xp(self):
        return int((self.time / 3600) * 240)

    def unpackmadefrom(self, craftedfrom):
        temp = {}
        real = {}

        for pack in craftedfrom:
            temp.update(pack)

        for key, value in temp.items():
            real[int(key)] = value

        self.craftedfrom = real

class SpecialItem(Item):
    def __init__(self, xp, minprice, maxprice, img, *args, **kw):
        super().__init__(*args, **kw)
        self.xp = xp
        self.minprice = minprice
        self.maxprice = maxprice
        self.img = img
        self.type = 'special'


def cropseedloader():
    rseeds = {}

    with open("files/cropseed.json", "r", encoding="UTF8") as file:
        seeds = json.load(file)

    for c, v in seeds.items():
        crop = CropSeed(
            level=v['level'],
            grows=v['grows'],
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
            minprice=v['minprice'],
            maxprice=v['maxprice'],
            level=v['level'],
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
            img=v['img'],
            craftedfrom=v['craftedfrom'],
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


def update_market_prices(client):
    
    def update_price(item):
        item.marketprice = randint(item.minprice, item.maxprice)

    for item in client.crops.values():
        update_price(item)
    for item in client.treeproducts.values():
        update_price(item)
    for item in client.animalproducts.values():
        update_price(item)
    for item in client.crafteditems.values():
        update_price(item)
    for item in client.specialitems.values():
        update_price(item)

def update_item_relations(client):
    for item in client.allitems.values():
        if hasattr(item, 'expandsto'):
            item.expandsto = client.allitems[item.expandsto]
        elif hasattr(item, 'madefrom'):
            item.madefrom = client.allitems[item.madefrom]
        elif hasattr(item, 'craftedfrom'):
            dct = {}
            for product, amount in item.craftedfrom.items():
                product = client.allitems[product]
                dct[product] = amount

            item.craftedfrom = dct


def find_item_by_name(client, name):
    itemslist = list(client.allitems.values())

    tempitems = {}
    tempwords = []
    for item in itemslist:
        tempitems[item.name] = item
        tempwords.append(item.name)

    matches = get_close_matches(name, tempwords, cutoff=0.72)
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
        item = find_item_by_name(client, possibleitem)
        if not item:
            embed = emb.errorembed("I didn't find any items named like that \ud83e\udd14", ctx)
            await ctx.send(embed=embed)
            return None

    return item


def crafted_from_to_string(item):
    string = ''
    for product, value in item.craftedfrom.items():
        string += f"{product.emoji}{product.name.capitalize()} x{value},\n"

    return string[:-2]

def base_amount_for_growables(item):
    grow_time = item.madefrom.grows
    items_per_hour = int(item.amount / (grow_time / 3600))
    amount = randint(items_per_hour, int(items_per_hour * 1.5))
        
    if grow_time > 3600:
        return amount
    elif grow_time > 1800:
        return int(amount / 2)
    else:
        return int(amount / 4)

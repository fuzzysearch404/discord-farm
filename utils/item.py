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
        return client.cropseeds[self.madefrom]


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

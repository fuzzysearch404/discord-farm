import json
from difflib import get_close_matches


class Crop:
    def __init__(
        self, id, emoji, name, name2, rarity, grows, dies, amount,
        cost, scost, minprice, maxprice, level, xp, img
    ):
        self.id = id
        self.emoji = emoji
        self.name = name
        self.name2 = name2
        self.rarity = rarity
        self.grows = grows
        self.dies = dies
        self.amount = amount
        self.cost = cost
        self.scost = scost
        self.minprice = minprice
        self.maxprice = maxprice
        self.level = level
        self.xp = xp
        self.img = img


def croploader():
    rcrops = {}

    with open("files/crops.json", "r", encoding="UTF8") as file:
        crops = json.load(file)

    for c, v in crops.items():
        crop = Crop(
            v['id'], v['emoji'], v['name'], v['name2'], v['rarity'], v['grows'],
            v['dies'], v['amount'], v['cost'], v['scost'], v['minprice'],
            v['maxprice'], v['level'], v['xp'], v['img']
        )
        rcrops[int(c)] = crop

    return rcrops


def findcropbyname(client, name):
    cropslist = list(client.crops.values())

    tempcrops = {}
    tempwords = []
    for crop in cropslist:
        tempcrops[crop.name] = crop
        tempwords.append(crop.name)

    matches = get_close_matches(name, tempwords)
    if not matches:
        return False
    return tempcrops[matches[0]]

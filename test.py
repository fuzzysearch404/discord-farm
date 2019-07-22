import json

with open("files/crops.json", "r", encoding="UTF8") as file:
    crops = json.load(file)


class Crop:
    def __init__(
        self, name, name2, rarity, grows, dies, amount, cost,
        scost, minprice, maxprice, level, xp
    ):
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


for c, v in crops.items():
    crop = Crop(
        v['name'], v['name2'], v['rarity'], v['grows'], v['dies'], v['amount'],
        v['cost'], v['scost'], v['minprice'], v['maxprice'], v['level'], v['xp']
    )
    print(crop)

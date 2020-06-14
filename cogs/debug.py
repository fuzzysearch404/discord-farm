from discord.ext import commands
from discord import Embed
from utils import checks
from classes.item import finditem


class Debug(commands.Cog, name="Debugging tools", command_attrs={'hidden': True}):
    """Admin-only commands for debugging."""
    def __init__(self, client):
        self.client = client

    @commands.command()
    @checks.is_owner()
    async def ditem(self, ctx, *, search):
        """
        \ud83c\udf3d Shows some calculations about an item.

        Parameters:
        `search` - item to lookup. (item's name or ID)
        """
        try:
            possibleamount = search.rsplit(' ', 1)[1]
            tiles = int(possibleamount)
            search = search.rsplit(' ', 1)[0]
        except Exception:
            tiles = 1
        
        item = await finditem(self.client, ctx, search)
        if not item: return

        embed = Embed(title=item.name)
        embed.add_field(name="Rarity", value=item.rarity)
        embed.add_field(name="Level", value=item.rarity)
        
        if item.type == "cropseed":
            item = item.madefrom
            self.add_fields_crop(embed, item, tiles)
        elif item.type == "crop": self.add_fields_crop(embed, item, tiles)
        elif item.type == "animal" or item.type == "tree":
            item = item.expandsto
            self.add_fields_animal_tree(embed, item, tiles) 
        elif item.type == "animalproduct" or item.type == "treeproduct":
            self.add_fields_animal_tree(embed, item, tiles)
        elif item.type == "crafteditem":
            self.add_fields_crafted(embed, item)

        await ctx.send(embed=embed)

    def add_fields_crop(self, embed, item, tiles):
        seed = item.madefrom
        avgmarket = (item.minprice + item.maxprice) / 2
        xph = (item.xp * item.amount) / (seed.grows / 60) * 60
        avgprofit = (item.amount * avgmarket) - seed.gold_cost
        maxprofit = (item.amount * item.maxprice) - seed.gold_cost
        minprofit = (item.amount * item.minprice) - seed.gold_cost
        avggoldh = avgprofit / (seed.grows / 60) * 60
        maxgoldh = maxprofit / (seed.grows / 60) * 60

        embed.add_field(name="XP/H.", value=xph * tiles)
        embed.add_field(name="Min. profit (market)", value=minprofit * tiles)
        embed.add_field(name="Avg. profit (market)", value=avgprofit * tiles)
        embed.add_field(name="Max. profit (market)", value=maxprofit * tiles)
        embed.add_field(name="Avg. marketprice", value=avgmarket * tiles)
        embed.add_field(name="Avg. Gold/H.", value=avggoldh * tiles)
        embed.add_field(name="Max. Gold/H.", value=maxgoldh * tiles)

    def add_fields_animal_tree(self, embed, item, tiles):
        parent = item.madefrom
        avgmarket = (item.minprice + item.maxprice) / 2
        xph = (item.xp * item.amount) / (parent.grows / 60) * 60
        avgprofit = (item.amount * parent.amount * avgmarket) - parent.gold_cost
        maxprofit = (item.amount * parent.amount * item.maxprice) - parent.gold_cost
        minprofit = (item.amount * parent.amount * item.minprice) - parent.gold_cost
        avggoldh = avgprofit / (parent.grows * parent.amount / 60) * 60
        maxgoldh = maxprofit / (parent.grows * parent.amount / 60) * 60

        embed.add_field(name="XP/H.", value=xph * tiles)
        embed.add_field(name="Min. profit (market)", value=minprofit * tiles)
        embed.add_field(name="Avg. profit (market)", value=avgprofit * tiles)
        embed.add_field(name="Max. profit (market)", value=maxprofit * tiles)
        embed.add_field(name="Avg. marketprice", value=avgmarket * tiles)
        embed.add_field(name="Avg. Gold/H.", value=avggoldh * tiles)
        embed.add_field(name="Max. Gold/H.", value=maxgoldh * tiles)

    def add_fields_crafted(self, embed, item):
        made_from = {}
        for i, a in item.craftedfrom.items():
            _item = self.client.allitems[i]
            made_from[_item] = a
        
        costmin, costmax, = 0, 0
        for i, a in made_from.items():
            costmax += i.maxprice * a
            costmin += i.minprice * a

        xph = item.xp / (item.time / 60) * 60

        embed.add_field(name="XP/H.", value=xph)
        embed.add_field(name="Min. req. cost", value=costmin)
        embed.add_field(name="Avg. req. cost", value=(costmin + costmax) / 2)
        embed.add_field(name="Max. req. cost", value=costmax)
        embed.add_field(name="Min. profit Max. req. cost", value=item.minprice - costmax)
        embed.add_field(
            name="Avg. profit Max. cost", 
            value=(item.minprice + item.maxprice) / 2 - costmax
        )
        embed.add_field(name="Max. profit Max. req. cost", value=item.maxprice - costmax)
        embed.add_field(
            name="Avg. Gold/H Max. req. cost",
            value=((item.minprice + item.maxprice) / 2 - costmax) / (item.time / 60) * 60
        )
        embed.add_field(
            name="Max. Gold/H Max. req. cost",
            value=(item.maxprice - costmax) / (item.time / 60) * 60
        )


def setup(client):
    client.add_cog(Debug(client))
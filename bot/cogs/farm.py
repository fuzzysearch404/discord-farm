import discord
from discord.ext import commands

from .utils import checks
from .utils.converters import ItemAndAmount


class Farm(commands.Cog):
    """
    Commands for crop, animal and tree growing.

    Each item has their growing time and time period while the item
    is harvestable (it's not rotten). Items can only be harvested when
    they are grown enough. Rotten items still take up your farm's space,
    but they are discarded automatically when you harvest your field.
    Trees, bushes and animals have multiple collection cycles,
    so you have to collect their items multiple times in a row.
    If they get rotten, just harvest the rotten items and the
    next growing cycle will start unaffected.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command(aliases=["field", "f"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def farm(self, ctx, member: discord.Member = None):
        """
        \ud83c\udf3e Shows your or someone's farm field

        Useful to see what you or someone else is growing right now.
        Displays item quantities, growing statuses and grow timers.

        __Explanation__:
        If the item is **"Growing"** - that means that you have to wait the
        specified time until you can harvest the item.

        if the item is **"Harvestable" or "Collectable"** - that means that you
        can use the "{prefix}`harvest`" command, to collect these items.
        Be quick, because you can only collect those for the specified
        period of time, before they get rotten.

        If the item is **"Rotten"** - that means that you have missed the
        chance to collect this item and you won't be able to obtain these
        items. You have to use the "{prefix}`harvest`" command, to free up
        your farm space.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `farm` - view your farm
        {prefix} `farm @user` - view user's farm
        """
        raise NotImplementedError()

    @commands.command(aliases=["harv", "h"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def harvest(self, ctx):
        """
        \ud83d\udc68\u200d\ud83c\udf3e Harvests your farm field

        Collects the grown items and discards the rotten
        items from your farm field.
        If you collect tree, bush or animal items, then
        their next growing cycle begins.
        To check what you are currenly growing and if you can
        harvest anything, check out "{prefix}`farm`" command.
        """
        raise NotImplementedError()

    @commands.command(aliases=["p", "grow", "g"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def plant(self, ctx, *, item: ItemAndAmount, amount: int = 1):
        """
        \ud83c\udf31 Plants crops and trees, grows animals on your farm field

        __Arguments__:
        `item` - item to lookup for planting/growing (item's name or ID)
        __Optional arguments__:
        `amount` - specify how many items to plant/grow

        __Usage examples__:
        {prefix} `plant lettuce 2` - plant 2 lettuce items
        {prefix} `plant 1 2` - plant 2 lettuce items (by using item's ID)
        {prefix} `plant 1` - plant 1 lettuce item (no amount)
        """
        raise NotImplementedError()

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def clear(self, ctx):
        """
        \ud83e\uddf9 Clear your farm field

        Removes ALL of your planted items from your farm field for some gold.
        This command is useful if you planted something by accident and you
        want to get rid of those items, because they take up your farm field
        space. These items WILL NOT be moved to your inventory and WILL BE
        LOST without any compensation, so be careful with this feature.
        """
        raise NotImplementedError()

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def fish(self, ctx):
        """
        \ud83c\udfa3 [Unlocks from level 17] Go fishing!

        You can catch random amount of fish once per hour.
        Sometimes your luck can be bad, and you might not get any fish.
        """
        raise NotImplementedError()  # TODO: inner cooldown - 3600


def setup(bot):
    bot.add_cog(Farm(bot))

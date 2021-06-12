from datetime import datetime, timedelta
from discord.ext import commands

from core import game_items
from .utils import checks


class Beta(commands.Cog, command_attrs={"hidden": True}):
    """
    Temp. commands while bot is in developement.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command()
    @checks.has_account()
    async def boost_test(self, ctx):
        b = game_items.ObtainedBoost("farm_slots", datetime.now() + timedelta(seconds=60))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("factory_slots", datetime.now() + timedelta(seconds=160))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("cat", datetime.now() + timedelta(seconds=86900))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("cat", datetime.now() + timedelta(seconds=10))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("dog_3", datetime.now() + timedelta(seconds=30))
        await ctx.user_data.give_boost(ctx, b)

    @commands.command()
    @checks.has_account()
    async def setgold(self, ctx, money: int = 0):
        ctx.user_data.gold = money
        await ctx.users.update_user(ctx.user_data)

    @commands.command()
    @checks.has_account()
    async def setgems(self, ctx, gems: int = 0):
        ctx.user_data.gems = gems
        await ctx.users.update_user(ctx.user_data)

    @commands.command()
    @checks.has_account()
    async def setxp(self, ctx, xp: int = 0):
        ctx.user_data.xp = xp
        await ctx.users.update_user(ctx.user_data)


def setup(bot):
    bot.add_cog(Beta(bot))

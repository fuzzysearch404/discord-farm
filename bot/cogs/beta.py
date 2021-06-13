from discord.ext import commands

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
        ctx.user_data.level, ctx.user_data.next_level_xp = \
            ctx.user_data._calculate_user_level()
        await ctx.users.update_user(ctx.user_data)

    @commands.command()
    @checks.has_account()
    async def setfarm(self, ctx, x: int = 0):
        ctx.user_data.farm_slots = x
        await ctx.users.update_user(ctx.user_data)

    @commands.command()
    @checks.has_account()
    async def setfact(self, ctx, x: int = 0):
        ctx.user_data.factory_slots = x
        await ctx.users.update_user(ctx.user_data)


def setup(bot):
    bot.add_cog(Beta(bot))

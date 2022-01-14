from discord.ext import commands

from core import exceptions
from core import static
from .utils import converters
from .utils import checks


class Beta(commands.Cog):
    """
    Beta version only commands for testing purposes.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True

        raise exceptions.FarmException("Sorry, this is a bot owner-only command.")

    @property
    def hide_in_help_command(self) -> bool:
        return True

    @commands.group(
        name="set",
        invoke_without_command=False,
        slash_command_guilds=static.DEVELOPMENT_GUILD_IDS
    )
    async def set_group(self, ctx):
        """\ud83d\udd27 [Beta only] Utility commands for quick account modifications"""
        pass

    @set_group.group(name="units", invoke_without_command=False)
    async def set_units_group(self, ctx):
        """\ud83d\udd27 [Beta only] Utility commands for quick account modifications"""
        pass

    @set_units_group.command(name="gold")
    @checks.has_account()
    async def set_gold(self, ctx, gold: int):
        """\ud83d\udd27 [Beta only] Set the gold amount"""
        ctx.user_data.gold = gold

        await ctx.users.update_user(ctx.user_data)
        await ctx.reply(f"Gold set to {ctx.user_data.gold}")

    @set_units_group.command(name="gems")
    @checks.has_account()
    async def set_gems(self, ctx, gems: int):
        """\ud83d\udd27 [Beta only] Set the gems amount"""
        ctx.user_data.gems = gems

        await ctx.users.update_user(ctx.user_data)
        await ctx.reply(f"Gems set to {ctx.user_data.gems}")

    @set_units_group.command(name="xp")
    @checks.has_account()
    async def set_xp(self, ctx, xp: int):
        """\ud83d\udd27 [Beta only] Set the XP amount"""
        ctx.user_data.xp = xp
        ctx.user_data.level, ctx.user_data.next_level_xp = \
            ctx.user_data._calculate_user_level()

        await ctx.users.update_user(ctx.user_data)
        await ctx.reply(f"XP set to {ctx.user_data.xp} (level {ctx.user_data.level})")

    @set_units_group.command()
    @checks.has_account()
    async def farmsize(self, ctx, size: int):
        """\ud83d\udd27 [Beta only] Set the farm size"""
        ctx.user_data.farm_slots = size

        await ctx.users.update_user(ctx.user_data)
        await ctx.reply(f"Farm size set to {ctx.user_data.gold}")

    @set_units_group.command()
    @checks.has_account()
    async def factorysize(self, ctx, size: int):
        """\ud83d\udd27 [Beta only] Set the factory size"""
        ctx.user_data.factory_slots = size

        await ctx.users.update_user(ctx.user_data)
        await ctx.reply(f"Factory size set to {ctx.user_data.gold}")

    @set_group.group(name="items", invoke_without_command=False)
    async def set_items_group(self, ctx):
        """\ud83d\udd27 [Beta only] Utility commands for quick account modifications"""
        pass

    @set_items_group.command()
    @checks.has_account()
    async def getitem(self, ctx, item: converters.Item, amount: int):
        """\ud83d\udd27 [Beta only] Get game items"""
        await ctx.user_data.give_item(ctx, item.id, amount)
        await ctx.reply(f"Obtained {amount}x {item.full_name}")

    @set_items_group.command()
    @checks.has_account()
    async def getchest(self, ctx, item: converters.Chest, amount: int):
        """\ud83d\udd27 [Beta only] Get chests"""
        await ctx.user_data.give_item(ctx, item.id, amount)
        await ctx.reply(f"Obtained {amount}x {item.full_name} chests")


def setup(bot) -> None:
    bot.add_cog(Beta(bot))

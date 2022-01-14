import io
import time
import traceback
import discord
from contextlib import suppress
from discord.ext import commands

from core import exceptions
from core import static


class Admin(commands.Cog):
    """
    Developer only commands for testing purposes.
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
        name="run",
        invoke_without_command=False,
        slash_command_guilds=static.DEVELOPMENT_GUILD_IDS
    )
    async def run_group(self, ctx):
        """\ud83d\udd27 [Developer only] Developer only commands for remote controls"""
        pass

    @run_group.command(name="eval")
    async def _eval(self, ctx, *, body: str):
        """\ud83d\udd27 [Developer only] Evaluates Python code"""
        results = await self.bot.eval_code(body, ctx=ctx)

        if not results:
            with suppress(discord.HTTPException):
                return await ctx.message.add_reaction(self.bot.check_emoji)

        await ctx.reply(f"```py\n{results}\n```")

    @run_group.command()
    async def sql(self, ctx, *, query: str):
        """\ud83d\udd27 [Developer only] Execute a SQL query"""
        query = self.bot.cleanup_code(query)

        is_multi = query.count(';') > 1
        if is_multi:
            strategy = ctx.db.execute
        else:
            strategy = ctx.db.fetch

        async with ctx.db.acquire():
            try:
                start = time.perf_counter()
                results = await strategy(query)
                dt = (time.perf_counter() - start) * 1000.0
            except Exception:
                return await ctx.reply(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multi or rows == 0:
            return await ctx.reply(f'`{dt:.3f}ms: {results}`')

        fmt = "```"
        for num, res in enumerate(results):
            fmt += f"{num + 1}: {res}\n"

        fmt += f"```\n*Returned {rows} rows in {dt:.3f}ms*"

        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode("utf-8"))
            await ctx.reply("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await ctx.reply(fmt)

    @run_group.command()
    async def redis(self, ctx, *, query: str):
        """\ud83d\udd27 [Developer only] Execute a Redis command"""
        try:
            results = await ctx.redis.execute_command(query)
        except Exception as e:
            return await ctx.reply(str(e))

        if not results:
            with suppress(discord.HTTPException):
                return await ctx.message.add_reaction(self.bot.check_emoji)

        result_str = str(results)

        if len(result_str) > 2000:
            fp = io.BytesIO(result_str.encode("utf-8"))
            await ctx.reply("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await ctx.reply(result_str)


def setup(bot) -> None:
    bot.add_cog(Admin(bot))

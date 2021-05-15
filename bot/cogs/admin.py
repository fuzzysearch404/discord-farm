import io
import time
import traceback
import discord
from contextlib import suppress
from discord.ext import commands


class Admin(commands.Cog, command_attrs={"hidden": True}):

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def cog_check(self, ctx) -> None:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="eval")
    async def _eval(self, ctx, *, body: str):
        """Evaluates Python code"""
        results = await self.bot.eval_code(body, ctx=ctx)

        if not results:
            with suppress(discord.HTTPException):
                return await ctx.message.add_reaction("\u2705")

        await ctx.send(f"```py\n{results}\n```")

    @commands.command()
    async def sql(self, ctx, *, query: str):
        """Execute SQL"""
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
                return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multi or rows == 0:
            return await ctx.send(f'`{dt:.3f}ms: {results}`')

        fmt = "```"
        for num, res in enumerate(results):
            fmt += f"{num + 1}: {res}\n"

        fmt += f"```\n*Returned {rows} rows in {dt:.3f}ms*"

        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode("utf-8"))
            await ctx.send(
                "Output too long...", file=discord.File(fp, "data.txt")
            )
        else:
            await ctx.send(fmt)

    @commands.command()
    async def redis(self, ctx, *, query: str):
        """Execute Redis command"""
        try:
            results = await ctx.redis.execute_command(query)
        except Exception as e:
            return await ctx.send(str(e))

        if not results:
            with suppress(discord.HTTPException):
                return await ctx.message.add_reaction("\u2705")

        result_str = str(results)

        if len(result_str) > 2000:
            fp = io.BytesIO(result_str.encode("utf-8"))
            await ctx.send(
                "Output too long...", file=discord.File(fp, "data.txt")
            )
        else:
            await ctx.send(result_str)

    @commands.command()
    async def uptime(self, ctx):
        """Get instance uptime"""
        await ctx.send(self.bot.uptime)


def setup(bot) -> None:
    bot.add_cog(Admin(bot))

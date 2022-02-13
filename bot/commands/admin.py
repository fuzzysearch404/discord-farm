import time
import discord

from core import static
from .util import exceptions
from .util.commands import FarmSlashCommand, FarmCommandCollection


class AdminCollection(FarmCommandCollection):
    """Developer only commands for testing purposes."""
    hidden_in_help_command: bool = True

    def __init__(self, client):
        super().__init__(client, [RunCommand], name="Admin")

    async def collection_check(self, command) -> None:
        # I am aware that this is a double check when using "_owner_only" = True
        if not await self.client.is_owner(command.author):
            raise exceptions.CommandOwnerOnlyException()


class RunCommand(FarmSlashCommand, name="run", guilds=static.DEVELOPMENT_GUILD_IDS):
    pass


class RunEvalCommand(
    FarmSlashCommand,
    name="eval",
    description="\N{WRENCH} [Developer only] Evaluates Python code",
    parent=RunCommand
):
    _avoid_maintenance: bool = False
    _requires_account: bool = False
    _owner_only: bool = True
    # TODO: Use multi line text input, when possible
    body: str = discord.app.Option(description="Python code to execute")

    async def callback(self):
        results = await self.client.eval_code(self.body, cmd=self)

        if not results:
            return await self.reply(f"{self.client.check_emoji} Executed with no output.")

        if len(results) > 2000:
            # TODO: Send as a file, when it's going to be possible
            await self.reply("Output too long...")
            #  fp = io.BytesIO(results.encode("utf-8"))
            #  await self.reply("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await self.reply(f"```py\n{results}\n```")


class RunSQLCommand(
    FarmSlashCommand,
    name="sql",
    description="\N{WRENCH} [Developer only] Executes a SQL query",
    parent=RunCommand
):
    _avoid_maintenance: bool = False
    _requires_account: bool = False
    _owner_only: bool = True

    query: str = discord.app.Option(description="SQL query to execute")

    async def callback(self):
        query = self.client.cleanup_code(self.query)

        is_multi = query.count(';') > 1
        if is_multi:
            strategy = self.db.execute
        else:
            strategy = self.db.fetch

        async with self.acquire():
            try:
                start = time.perf_counter()
                results = await strategy(query)
                dt = (time.perf_counter() - start) * 1000.0
            except Exception as ex:
                return await self.reply(str(ex))

        rows = len(results)
        if is_multi or rows == 0:
            return await self.reply(f'`{dt:.3f}ms: {results}`')

        fmt = "```"
        for num, res in enumerate(results):
            fmt += f"{num + 1}: {res}\n"
        fmt += f"```\n*Returned {rows} rows in {dt:.3f}ms*"

        if len(fmt) > 2000:
            # TODO: Send as a file, when it's going to be possible
            await self.reply("Output too long...")
            #  fp = io.BytesIO(results.encode("utf-8"))
            #  await self.reply("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await self.reply(fmt)


class RunRedisCommand(
    FarmSlashCommand,
    name="redis",
    description="\N{WRENCH} [Developer only] Executes a Redis command",
    parent=RunCommand
):
    _avoid_maintenance: bool = False
    _requires_account: bool = False
    _owner_only: bool = True

    command: str = discord.app.Option(description="Redis command to execute")

    async def callback(self):
        try:
            results = await self.redis.execute_command(self.command)
        except Exception as ex:
            return await self.reply(str(ex))

        if not results:
            return await self.reply(f"{self.client.check_emoji} Executed with no output.")

        results = str(results)

        if len(results) > 2000:
            # TODO: Send as a file, when it's going to be possible
            await self.reply("Output too long...")
            #  fp = io.BytesIO(results.encode("utf-8"))
            #  await self.reply("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await self.reply(f"```py\n{results}\n```")


def setup(client) -> list:
    return [AdminCollection(client)]

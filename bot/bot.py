import io
import json
import datetime
import asyncio
import textwrap
import traceback
import contextlib
import logging
import aiohttp
import aioredis
import asyncpg
import discord
from logging.handlers import RotatingFileHandler
from discord.ext import commands

from .cogs.utils.context import Context
from .cogs.utils.time import seconds_to_time
from core.game_user import UserManager
from core import exceptions


class BotClient(commands.AutoShardedBot):
    def __init__(self, **kwargs) -> None:
        self.pipe = kwargs.pop("pipe")
        self.cluster_name = kwargs.pop("cluster_name")

        # We need new loop, because the launcher is using one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        config = self._load_config()
        self.config = config

        self._log_webhook = config['bot']['logs-webhook']
        self.maintenance_mode = config['bot']['start-in-maintenance']
        self.is_beta = config['bot']['beta']

        self.ipc_ping = 0

        # Common emojis
        emojis = config['emoji']
        self.check_emoji = emojis['check']
        self.gold_emoji = emojis['gold']
        self.gem_emoji = emojis['gem']
        self.tile_emoji = emojis['farm_tile']
        self.xp_emoji = emojis['xp']
        self.warehouse_emoji = emojis['warehouse']

        self._init_logger()
        self.log.info(f"Shards: {kwargs['shard_ids']}, shard count: {kwargs['shard_count']}")

        self.enable_field_guard(config['bot']['startup-farm-guard-duration'])

        try:
            loop.run_until_complete(self._connect_db())
        except Exception:
            self.log.exception("Could not connect to Postgres")

        self._connect_redis()

        # TODO: For removal in May 2022
        self.custom_prefixes = {}

        self.user_cache = UserManager(self.redis, self.db_pool)

        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True

        super().__init__(
            intents=intents,
            slash_commands=True,
            chunk_guilds_at_startup=False,
            command_prefix=self.get_custom_prefix,  # TODO: For removal in May 2022
            **kwargs,
            loop=loop
        )

        self.add_check(self.temp_beta_check().predicate)

        for extension in self.config['bot']['initial-cogs']:
            try:
                self.log.debug(f"Loading extension: {extension}")
                self.load_extension(extension)
            except Exception:
                self.log.exception(f"Failed to load extension: {extension}")

        if self.is_beta:
            self.log.warning("Loading the beta debug extension")
            self.load_extension("bot.cogs.beta")

        self.run()

    # TODO: remove after proper slash permissions impl. by Discord
    def temp_beta_check(self) -> commands.check:
        async def pred(ctx) -> bool:
            if ctx.author.id in (234622520739758080, 665906176264896533):
                return True

            raise exceptions.FarmException("No, I don't think so, buddy...")

        return commands.check(pred)

    # TODO: For removal in May 2022
    async def fetch_custom_prefixes(self):
        all_guild_ids = [x.id for x in self.guilds]

        query = "SELECT * FROM guilds;"

        guild_data = await self.db_pool.fetch(query)
        for row in guild_data:
            try:
                if row['guild_id'] in all_guild_ids:
                    self.custom_prefixes[row['guild_id']] = row['prefix']
            except KeyError:
                pass

        self.log.info(f"Fetched {len(self.custom_prefixes)} custom prefixes")

    # TODO: For removal in May 2022
    async def get_custom_prefix(self, bot, message):
        if message.guild:
            try:
                return commands.when_mentioned_or(
                    self.custom_prefixes[message.guild.id]
                )(self, message)
            except KeyError:
                return commands.when_mentioned_or(
                    "%"
                )(self, message)
        else:
            return "%"

    @property
    def uptime(self) -> datetime.datetime:
        return datetime.datetime.now() - self.launch_time

    @property
    def field_guard(self) -> datetime.datetime:
        return self.guard_mode > datetime.datetime.now()

    def enable_field_guard(self, seconds: int) -> datetime.datetime:
        self.guard_mode = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self.log.info(f"Enabled field guard until: {self.guard_mode}")
        return self.guard_mode

    def _load_config(self) -> dict:
        with open("config.json", "r") as file:
            return json.load(file)

    def _init_logger(self) -> None:
        log = logging.getLogger(f"Cluster#{self.cluster_name}")

        if self.is_beta:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)

        log_formatter = logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s")
        file_handler = RotatingFileHandler(
            f"cluster-{self.cluster_name}.log",
            encoding="utf-8",
            mode="a",
            maxBytes=2 * 1024
        )
        file_handler.setFormatter(log_formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        log.handlers = [file_handler, stream_handler]
        self.log = log

    async def _connect_db(self) -> None:
        connect_args = {
            "user": self.config['postgres']['user'],
            "password": self.config['postgres']['password'],
            "database": self.config['postgres']['database'],
            "host": self.config['postgres']['host']
        }

        self.db_pool = await asyncpg.create_pool(
            **connect_args,
            min_size=10,
            max_size=15,
            command_timeout=60.0
        )

    def _connect_redis(self) -> None:
        pool = aioredis.ConnectionPool.from_url(
            self.config['redis']['host'],
            password=self.config['redis']['password'],
            db=self.config['redis']['db-index']
        )
        self.redis = aioredis.Redis(connection_pool=pool)

    async def log_to_discord(self, content: str, embed: discord.Embed = None) -> None:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(self._log_webhook, session=session)

            await webhook.send(
                f"**[{self.cluster_name}]** " + content,
                embed=embed,
                username=self.user.name
            )

    async def on_shard_ready(self, shard_id) -> None:
        self.log.info(f"Shard {shard_id} ready")

    async def on_ready(self) -> None:
        self.log.info("Cluster ready called")

        try:
            self.pipe.send(1)
            self.pipe.close()
        except OSError:
            pass

        if not hasattr(self, "launch_time"):
            self.launch_time = datetime.datetime.now()

        # Check if the Redis is connected
        try:
            await self.redis.time()
        except Exception:
            await self.log_to_discord("\u274c Redis not connected!")

        # Check if Postgres is connected
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchrow("SELECT NOW();")
        except Exception:
            await self.log_to_discord("\u274c Postgres not connected!")

        # TODO: For removal in May 2022
        await self.fetch_custom_prefixes()

        await self.log_to_discord(
            f"\ud83d\udfe2 Ready! Maintenance mode: `{self.maintenance_mode}` "
            f"Shards: `{self.shard_ids}` Total guilds: `{len(self.guilds)}`"
        )

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "\u274c Sorry, you can only interact with this bot in Discord servers!"
            )
            return

        await self.process_slash_commands(interaction)

    async def on_command_error(self, ctx, error) -> None:
        if isinstance(error, commands.errors.CommandNotFound):
            pass
        elif isinstance(error, exceptions.FarmException):
            await ctx.reply(f"\u274c {str(error)}", ephemeral=True)
        elif isinstance(error, commands.errors.CommandOnCooldown):
            return await ctx.reply(
                "\u23f0 This command is on cooldown for:  "
                f"**{seconds_to_time(error.retry_after)}**",
                ephemeral=True
            )
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            return await ctx.reply(
                "\u274c This command requires additional argument: "
                f"`{error.param.name}`. For this command's usage information "
                f"please see **/help {ctx.invoked_with}**.",
                ephemeral=True
            )
        elif isinstance(error, commands.errors.BadArgument):
            return await ctx.reply(
                "\u274c Invalid command argument provided. "
                "For this command's usage information please see "
                f"**/help {ctx.invoked_with}**.",
                ephemeral=True
            )
        elif isinstance(error, commands.errors.BotMissingPermissions):
            # Keeping this one not ephemeral to inform the server staff faster
            return await ctx.reply(
                f"\u274c {str(error)} Please ask a server admin to enable those. "
                "Otherwise, I can't function as intended \ud83d\ude2b"
            )
        elif isinstance(error, commands.errors.MissingPermissions):
            return await ctx.reply(f"\u274c {str(error)}", ephemeral=True)
        elif isinstance(error, commands.errors.MaxConcurrencyReached):
            return await ctx.reply(f"\u274c {str(error)}", ephemeral=True)
        elif isinstance(error, commands.errors.DisabledCommand):
            return await ctx.reply(
                "\u274c Sorry, this command currently has been "
                "disabled and it cannot be used right now.",
                ephemeral=True
            )
        elif isinstance(error, commands.errors.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                exc_info = (type(original), original, original.__traceback__)
                self.log.error(f"In {ctx.command.qualified_name}:", exc_info=exc_info)
        elif isinstance(error, commands.errors.ArgumentParsingError):
            return await ctx.reply(error, ephemeral=True)
        elif isinstance(error, commands.errors.CheckFailure):
            return await ctx.reply("\u274c Sorry, you can't use this command", ephemeral=True)
        else:
            exc_info = (type(error), error, error.__traceback__)
            self.log.error(f"In {ctx.command.qualified_name}:", exc_info=exc_info)

    async def on_guild_join(self, guild) -> None:
        message = (
            "Hello! \ud83d\udc4b Thanks for adding me here!\n"
            "Access the command list with: **/help**\n"
            "Start the game with **/register**\n"
            "Happy farming! \ud83d\udc68\u200d\ud83c\udf3e"
        )

        txt_chans = guild.text_channels
        channels = list(filter(lambda x: x.permissions_for(guild.me).send_messages, txt_chans))

        if channels:
            await channels[0].send(message)

        await self.log_to_discord(
            f"\ud83d\udce5 Joined guild: {guild.name} "
            f"(`{guild.id}`) Large:`{guild.large}` "
            f"Total guilds: `{len(self.guilds)}`"
        )
        self.log.info(f"Joined guild: {guild.id}")

    async def on_guild_remove(self, guild) -> None:
        async with self.db_pool.acquire() as conn:
            query = "DELETE FROM store WHERE guild_id = $1;"
            await conn.execute(query, guild.id)

        await self.log_to_discord(
            f"\ud83d\udce4 Left guild: {guild.name} "
            f"(`{guild.id}`) Large:`{guild.large}`"
            f"Total guilds: `{len(self.guilds)}`"
        )
        self.log.info(f"Left guild: {guild.id}")

    # TODO: For removal in May 2022
    async def on_message(self, message) -> None:
        author = message.author

        if author == self.user or author.bot:
            return

        try:
            await self.process_commands(message)
        except Exception as e:
            self.log.exception(f"Error occured while executing commands: {e}")

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def invoke(self, ctx: Context) -> None:
        if ctx.author.bot:  # Just in case, right???
            return

        if ctx.command is not None:
            self.dispatch("command", ctx)
            try:
                if await self.can_run(ctx, call_once=True):
                    await ctx.command.invoke(ctx)
                else:
                    raise commands.errors.CheckFailure("The global check once functions failed.")
            except commands.errors.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch("command_completion", ctx)
            # The main reason why to override this method is to drop the db connetion
            await ctx.release()
        elif ctx.invoked_with:
            exc = commands.errors.CommandNotFound(f'Command "{ctx.invoked_with}" is not found')
            self.dispatch("command_error", ctx, exc)

    # TODO: For removal in May 2022
    async def process_commands(self, message) -> None:
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is None:
            return

        if not message.channel.permissions_for(message.guild.me).send_messages:
            return

        await ctx.reply(
            "This bot is now using slash commands, as they are required "
            "by Discord for all bots from May 2022.\n"
            "You can now see my commands, by starting to type the **/** symbol in chat.\n"
            "For example, the command you just wanted to use, is now accessible with "
            f"**/{ctx.command.name}**\nIf you don't see any commands, please reinvite the bot "
            "to your server with the \"Add to server\" button in "
            "my profile. Sorry, there is no way we can keep the old command system."
        )

        # await self.invoke(ctx)

    def cleanup_code(self, content: str) -> str:
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        return content.strip("` \n")

    async def eval_code(self, code: str, ctx=None) -> str:
        env = {"bot": self, "ctx": ctx}
        env.update(globals())

        body = self.cleanup_code(code)
        stdout = io.StringIO()
        to_compile = f"async def func():\n{textwrap.indent(body, '  ')}"

        try:
            exec(to_compile, env)
        except Exception as e:
            return f"{e.__class__.__name__}: {e}"

        func = env['func']

        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()

            return f"{value}{traceback.format_exc()}"
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    return str(value)
                else:
                    return "None"
            else:
                return f"{value}{ret}"

    async def close(self) -> None:
        self.log.info("Shutting down")
        await self.log_to_discord("Shutting down")

        await super().close()
        await self.db_pool.close()
        await self.redis.connection_pool.disconnect()

    def run(self) -> None:
        super().run(self.config['bot']['discord-token'], reconnect=True)

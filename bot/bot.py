import io
import sys
import psutil
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
from logging.handlers import TimedRotatingFileHandler
from discord.ext.modules import AutoShardedModularCommandClient

from core.game_user import UserManager


if sys.platform == "linux":
    import uvloop
    uvloop.install()


class BotClient(AutoShardedModularCommandClient):
    def __init__(self, **kwargs) -> None:
        self.pipe = kwargs.pop("pipe")
        self.cluster_name = kwargs.pop("cluster_name")
        config = kwargs.pop("config")
        self.config = config
        self._log_webhook = config['bot']['logs-webhook']
        self.maintenance_mode = config['bot']['start-in-maintenance']
        self.is_beta = config['bot']['beta']
        self.ipc_ping = 0
        self.custom_prefixes = {}  # TODO: For removal in May 2022
        self.owner_ids = set()
        self.process_info = psutil.Process()

        emojis = config['emoji']
        self.check_emoji = emojis['check']
        self.gold_emoji = emojis['gold']
        self.gem_emoji = emojis['gem']
        self.tile_emoji = emojis['farm_tile']
        self.xp_emoji = emojis['xp']
        self.warehouse_emoji = emojis['warehouse']

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        log = logging.getLogger(f"Cluster#{self.cluster_name}")
        if self.is_beta:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
        log_formatter = logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s")
        file_handler = TimedRotatingFileHandler(
            f"./logs/cluster-{self.cluster_name}.log",
            encoding="utf-8",
            when="W0",
            interval=2
        )
        file_handler.setFormatter(log_formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        log.handlers = [file_handler, stream_handler]
        self.log = log
        self.log.info(f"Shards: {kwargs['shard_ids']}, shard count: {kwargs['shard_count']}")

        loop.run_until_complete(self._connect_postgres())
        loop.run_until_complete(self._connect_redis())
        self.user_cache = UserManager(self.redis, self.db_pool)

        # TODO: guild_messages for removal in May 2022
        super().__init__(
            intents=discord.Intents(guilds=True, guild_messages=True),
            chunk_guilds_at_startup=False,
            **kwargs,
            loop=loop
        )

        for extension in self.config['bot']['initial-extensions']:
            try:
                self.log.debug(f"Loading extension: {extension}")
                self.load_extension(extension)
            except Exception:
                self.log.exception(f"Failed to load extension: {extension}")

        if self.is_beta:
            self.log.warning("Loading the beta debug extension")
            self.load_extension("bot.commands.beta")

        self.enable_field_guard(config['bot']['startup-farm-guard-duration'])
        self.run()

    @property
    def uptime(self) -> datetime.datetime:
        return datetime.datetime.now() - self.launch_time

    @property
    def field_guard(self) -> datetime.datetime:
        return self.guard_mode > datetime.datetime.now()

    async def setup(self):
        # Upload commands only once (if this client has shard zero)
        if 0 in self.shard_ids:
            await self.upload_global_application_commands()
            await self.upload_guild_application_commands()

    async def _connect_postgres(self) -> None:
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
            command_timeout=60.0,
            max_inactive_connection_lifetime=30.0
        )

        # Check if Postgres is connected
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchrow("SELECT NOW();")
        except Exception as ex:
            self.log.exception("Failed to connect to Postgres")
            raise ex

    async def _connect_redis(self) -> None:
        pool = aioredis.ConnectionPool.from_url(
            self.config['redis']['host'],
            password=self.config['redis']['password'],
            db=self.config['redis']['db-index']
        )
        self.redis = aioredis.Redis(connection_pool=pool)

        # Check if the Redis is connected
        try:
            await self.redis.time()
        except Exception as ex:
            self.log.exception("Failed to connect to Redis")
            raise ex

    async def is_owner(self, user: discord.User):
        if not self.owner_ids:
            app = await self.application_info()
            if app.team:
                self.owner_ids = {member.id for member in app.team.members}
            else:
                self.owner_ids = {app.owner.id}

        return user.id in self.owner_ids

    def find_loaded_command_by_name(self, command_name: str):
        """Finds a loaded command by it's full name"""
        for collection in self.command_collections.values():
            for command in collection.commands:
                # In collections we store only top level commands
                if command._name_ == command_name:
                    return command

                if command_name.startswith(command._name_):
                    for child in command.find_all_lowest_children(command):
                        if child.get_full_name(child) == command_name:
                            return child
                    # Dead search
                    return None

        return None

    def cleanup_code(self, content: str) -> str:
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])
        return content.strip("` \n")

    async def eval_code(self, code: str, cmd=None) -> str:
        env = {"bot": self, "cmd": cmd}
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
                return str(value) if value else "None"
            else:
                return f"{value}{ret}"

    def enable_field_guard(self, seconds: int) -> datetime.datetime:
        self.guard_mode = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self.log.info(f"Enabled field guard until: {self.guard_mode}")
        return self.guard_mode

    async def log_to_discord(self, content: str, embed: discord.Embed = None) -> None:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(self._log_webhook, session=session)

            await webhook.send(
                f"**[{self.cluster_name}]** " + content,
                embed=embed,
                username=self.user.name
            )

    # TODO: For removal in May 2022
    async def fetch_custom_prefixes(self):
        all_guild_ids = [x.id for x in self.guilds]

        guild_data = await self.db_pool.fetch("SELECT * FROM guilds;")
        for row in guild_data:
            try:
                if row['guild_id'] in all_guild_ids:
                    self.custom_prefixes[row['guild_id']] = row['prefix']
            except KeyError:
                pass

        self.log.info(f"Fetched {len(self.custom_prefixes)} custom prefixes")

    # TODO: For removal in May 2022
    def get_custom_prefix(self, bot, message):
        try:
            return self.custom_prefixes[message.guild.id]
        except KeyError:
            return "%"

    # TODO: For removal in May 2022
    async def on_message(self, message) -> None:
        author = message.author

        if author == self.user or author.bot:
            return

        if not message.channel.permissions_for(message.guild.me).send_messages:
            return

        prefix = self.get_custom_prefix(self, message)
        if not message.content.startswith(prefix):
            return

        # Dirty nested for loop, but as this is only temporary, it's fine
        all_commands = []
        for collection in self.command_collections.values():
            for command in collection.commands:
                all_commands.append(command._name_)
        # Include common aliases
        aliases = {
            "prof": "profile",
            "inv": "inventory",
            "p": "plant",
            "i": "item",
            "h": "harvest",
            "mi": "missions",
            "f": "farm",
            "fa": "factory"
        }

        cmd = message.content[len(prefix):].strip().split(" ")[0].lower()
        if cmd in aliases:
            cmd = aliases[cmd]
        elif cmd not in all_commands:
            return

        await message.reply(
            "This bot is now using slash commands, as they are required "
            "by Discord for all bots from May 2022.\n"
            "You can now see my commands, by starting to type the **/** symbol in chat.\n"
            "For example, the command you just wanted to use, is now accessible with "
            f"**/{cmd}**\n\n**If you don't see any slash commands, please reinvite the bot "
            "to your server with the \"Add to server\" button in "
            "my profile.**\nSorry, there is no way we can keep the old command system."
        )

    async def on_shard_ready(self, shard_id: int) -> None:
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

        # TODO: For removal in May 2022
        await self.fetch_custom_prefixes()

        await self.log_to_discord(
            f"\N{LARGE GREEN CIRCLE} Ready! Maintenance mode: `{self.maintenance_mode}` "
            f"Shards: `{self.shard_ids}` Total guilds: `{len(self.guilds)}`"
        )

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            if interaction.guild_id is None:
                await interaction.response.send_message(
                    "\N{CROSS MARK} Sorry, you can only interact with this bot in Discord servers!"
                )
                return

        await super().on_interaction(interaction)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        message = (
            "Hello! \N{WAVING HAND SIGN} Thanks for adding me here!\n"
            "Access my command list with: **/help**. "
            "Start the game with **/account create**.\n"
            "Have fun! \N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE}"
        )

        txt_chans = guild.text_channels
        channels = list(filter(lambda x: x.permissions_for(guild.me).send_messages, txt_chans))

        if channels:
            await channels[0].send(message)

        await self.log_to_discord(
            f"\N{INBOX TRAY} Joined guild: {guild.name} "
            f"(`{guild.id}`) Large:`{guild.large}` "
            f"Total guilds: `{len(self.guilds)}`"
        )
        self.log.info(f"Joined guild: {guild.id}")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        async with self.db_pool.acquire() as conn:
            query = "DELETE FROM store WHERE guild_id = $1;"
            await conn.execute(query, guild.id)

        await self.log_to_discord(
            f"\N{OUTBOX TRAY} Left guild: {guild.name} "
            f"(`{guild.id}`) Large:`{guild.large}`"
            f"Total guilds: `{len(self.guilds)}`"
        )
        self.log.info(f"Left guild: {guild.id}")

    async def close(self) -> None:
        self.log.info("Shutting down")
        await self.log_to_discord("Shutting down")

        await super().close()
        await self.db_pool.close()
        await self.redis.connection_pool.disconnect()

    def run(self) -> None:
        super().run(self.config['bot']['discord-token'], reconnect=True)

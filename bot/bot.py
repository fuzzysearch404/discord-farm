import json
import aiohttp
import aioredis
import asyncpg
import logging
import asyncio
import discord
from logging.handlers import RotatingFileHandler
from discord.ext import commands


class BotClient(commands.AutoShardedBot):
    def __init__(self, **kwargs) -> None:
        self.pipe = kwargs.pop("pipe")
        self.cluster_name = kwargs.pop("cluster_name")

        # We need new loop, because the launcher is using one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.config = self._load_config()
        self._log_webhook = self.config['bot']['logs-webhook']

        self._init_logger()
        self.log.info(
            f"Shards: {kwargs['shard_ids']}"
            f", shard count: {kwargs['shard_count']}"
        )

        try:
            loop.run_until_complete(self._connect_db())
        except Exception:
            self.log.exception("Could not connect to Postgres")

        self._connect_redis()

        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True

        super().__init__(
            intents=intents,
            chunk_guilds_at_startup=False,
            guild_subscriptions=False,
            max_messages=7500,
            command_prefix=commands.when_mentioned_or(
                self.config['bot']['prefix']
            ),
            **kwargs,
            loop=loop
        )

        for extension in self.config['bot']['initial-cogs']:
            try:
                self.load_extension(extension)
            except Exception:
                self.log.exception(f"Failed to load extension: {extension}")

        self.run()

    def _load_config(self) -> dict:
        with open("config.json", "r") as file:
            return json.load(file)

    def _init_logger(self) -> None:
        log = logging.getLogger(f"Cluster#{self.cluster_name}")
        log.setLevel(logging.DEBUG)
        log_formatter = logging.Formatter(
            "[%(asctime)s %(name)s/%(levelname)s] %(message)s"
        )
        file_handler = RotatingFileHandler(
            f"cluster-{self.cluster_name}.log",
            encoding="utf-8",
            mode="a",
            maxBytes=2 * 1024 * 1024
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

        self.db = await asyncpg.create_pool(
            **connect_args,
            min_size=20,
            max_size=20,
            command_timeout=60.0
        )

    def _connect_redis(self) -> None:
        pool = aioredis.ConnectionPool.from_url(
            self.config['redis']['host'],
            password=self.config['redis']['password']
        )

        self.redis = aioredis.Redis(connection_pool=pool)
        self.redis_pubsub = self.redis.pubsub()

    async def log_to_discord(
        self,
        content: str,
        embed: discord.Embed = None
    ) -> None:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(
                self._log_webhook,
                adapter=discord.AsyncWebhookAdapter(session)
            )

            await webhook.send(
                f"**[{self.cluster_name}]** " + content,
                embed=embed,
                username=self.user.name
            )

    async def on_shard_ready(self, shard_id) -> None:
        self.log.info(f"Shard {shard_id} ready")

    async def on_ready(self) -> None:
        self.log.info("Cluster ready called")

        self.pipe.send(1)
        self.pipe.close()

        # Check if the Redis is connected
        try:
            await self.redis.time()
        except Exception:
            await self.log_to_discord("\u274c Redis not connected!")

        # Check if Postgres is connected
        try:
            async with self.db.acquire() as con:
                await con.fetchrow("SELECT NOW();")
        except Exception:
            await self.log_to_discord("\u274c Postgres not connected!")

    async def close(self):
        await self.log_to_discord("Shutting down")

        await super().close()
        await self.db.close()
        await self.redis.connection_pool.disconnect()

    def run(self) -> None:
        super().run(self.config['bot']['discord-token'], reconnect=True)

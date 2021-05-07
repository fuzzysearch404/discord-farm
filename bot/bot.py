import json
import logging
import asyncio
import discord
from logging.handlers import RotatingFileHandler
from discord.ext import commands


class BotClient(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.pipe = kwargs.pop("pipe")
        self.cluster_name = kwargs.pop("cluster_name")

        # We need new loop, because the launcher is using one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.config = self._load_config()

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

        log.info(
            f"Shards: {kwargs['shard_ids']}"
            f", shard count: {kwargs['shard_count']}"
        )
        self.log = log

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

        self.run()

    def _load_config(self):
        with open("config.json", "r") as file:
            return json.load(file)

    async def on_shard_ready(self, shard_id):
        self.log.info(f"Shard {shard_id} ready")

    async def on_ready(self):
        self.log.info("Cluster ready called")

        self.pipe.send(1)
        self.pipe.close()

    def run(self):
        super().run(self.config['bot']['discord-token'], reconnect=True)

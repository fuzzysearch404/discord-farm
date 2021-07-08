import sys
import json
import logging
import asyncio
import aiohttp
import aioredis
import jsonpickle
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

from core.ipc_classes import IPCMessage
from core.game_items import load_all_items


class IPC:
    def __init__(self) -> None:
        self._loop = asyncio.get_event_loop()

        self._config = self._load_config()
        self.game_news = self._load_game_news()
        self.eval_responses = {}

        log = logging.getLogger("IPC")
        log.setLevel(logging.DEBUG)
        log_formatter = logging.Formatter(
            "[%(asctime)s %(name)s/%(levelname)s] %(message)s"
        )
        file_handler = RotatingFileHandler(
            "ipc.log",
            encoding="utf-8",
            mode="a",
            maxBytes=2 * 1024 * 1024
        )
        file_handler.setFormatter(log_formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        log.handlers = [file_handler, stream_handler]
        self.log = log

        log.debug("Launching...")

        self.game_news = self._load_game_news()

        ipc_config = self._config['ipc']
        self.bot_id = ipc_config['bot-id']
        self.ipc_name = ipc_config['ipc-author']
        self.is_beta = ipc_config['beta']
        self.db_backup_delay = ipc_config['db-backups-delay']
        self.cluster_inactive_timeout = ipc_config['cluster-inactive-timeout']
        self.cluster_check_delay = ipc_config['cluster-check-delay']
        self.post_stats_delay = ipc_config['post-bot-stats-delay']
        self.incident_check_delay = ipc_config['incident-check-delay']
        self.critical_incident_guard = ipc_config['critical-incident-guard']
        self.major_incident_guard = ipc_config['major-incident-guard']

        redis_config = self._config['redis']
        self.global_channel = redis_config['global-channel-name']
        self.cluster_channel_prefix = redis_config['cluster-channel-prefix']

        self.ignore_actions = (
            "maintenance",
            "enable_guard",
            "eval",
            "result",
            "reload",
            "load",
            "unload",
            "shutdown"
        )

        self.active_clusters = []
        self.total_guild_count = 0
        self.total_shard_count = 0

        try:
            self._connect_redis()
        except Exception:
            log.exception("Could not connect to Redis")

        log.debug("Loading game items")

        self.item_pool = load_all_items()

        log.debug("Ready")

    def start(self) -> None:
        self.log.info("Starting: Registering tasks")

        self._loop.create_task(self._register_tasks())

        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            self._loop.run_until_complete(self.stop())

    async def stop(self) -> None:
        await self._unregister_redis_channels()

        self.log.info("Exiting")

        self._loop.stop()

    def _load_config(self) -> dict:
        with open("config.json", "r") as file:
            return json.load(file)

    def _load_game_news(self) -> str:
        with open("data/news.txt", "r") as file:
            return file.read()

    def _connect_redis(self) -> None:
        self.log.debug("Connecting Redis")

        self.redis = aioredis.from_url(
            self._config['redis']['host'],
            password=self._config['redis']['password'],
            db=self._config['redis']['db-index']
        )
        self.redis_pubsub = self.redis.pubsub()

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.psubscribe(self.cluster_channel_prefix + "*")

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.punsubscribe(self.cluster_channel_prefix + "*")

    async def _register_tasks(self) -> None:
        await self._register_redis_channels()

        # Incoming messages handler
        self._loop.create_task(self._redis_event_handler())
        # Local tasks
        self._loop.create_task(self._cluster_check_task())
        # Global message publish tasks
        self._loop.create_task(self._global_task_update_items())

        if not self.is_beta:
            self._loop.create_task(self._global_task_send_stats())
            self._loop.create_task(self._global_task_do_backups())

        self._loop.create_task(self._global_task_check_discord_incidents())

    def _resolve_reply_channel(self, message: IPCMessage) -> str:
        if message.reply_global:
            return self.global_channel
        else:
            return message.author

    async def _redis_event_handler(self) -> None:
        async for message in self.redis_pubsub.listen():
            if message['type'] != 'message' and message['type'] != 'pmessage':
                continue

            try:
                ipc_message = jsonpickle.decode(message['data'])
            except Exception:
                continue

            if ipc_message.author == self.ipc_name:
                continue

            self.log.info(
                f"Received message from: {ipc_message.author} "
                f"Action: {ipc_message.action} "
                f"Reply global: {ipc_message.reply_global}"
            )

            reply_channel = self._resolve_reply_channel(ipc_message)

            if ipc_message.action == "ping":
                await self._update_cluster_status(ipc_message, reply_channel)
            elif ipc_message.action == "get_items":
                await self._send_update_items_message(reply_channel)
            elif ipc_message.action == "get_game_news":
                await self._send_update_game_news_message(reply_channel)
            elif ipc_message.action == "set_items":
                await self._handle_set_items()
            elif ipc_message.action == "set_game_news":
                await self._handle_set_news(ipc_message)
            elif ipc_message.action in self.ignore_actions:
                continue
            else:
                self.log.error(f"Unknown action: {ipc_message.action}")

    async def _update_cluster_status(
        self,
        message: IPCMessage,
        reply_channel: str
    ) -> None:
        cluster = jsonpickle.decode(message.data)

        try:
            to_remove = next(
                x for x in self.active_clusters if x.name == cluster.name
            )
            self.active_clusters.remove(to_remove)
        except StopIteration:
            pass

        self.active_clusters.append(cluster)

        await self._send_ping_message(reply_channel)

    async def _cluster_check_task(self) -> None:
        while not self._loop.is_closed():
            await asyncio.sleep(self.cluster_check_delay)

            guild_count, shard_count = 0, 0
            for cluster in self.active_clusters:
                delta_time = datetime.now() - cluster.last_ping

                if delta_time.total_seconds() >= self.cluster_inactive_timeout:
                    self.active_clusters.remove(cluster)

                    continue

                guild_count += cluster.guild_count
                shard_count += len(cluster.latencies)

            self.total_guild_count = guild_count
            self.total_shard_count = shard_count

    async def _handle_set_news(self, message: IPCMessage) -> None:
        self.game_news = message.data

        with open("data/news.txt", "w") as file:
            file.write(self.game_news)

        await self._send_update_game_news_message(self.global_channel)

    async def _handle_set_items(self) -> None:
        self.item_pool = load_all_items()

        self.item_pool.update_market_prices()

        await self._send_update_items_message(self.global_channel)

    async def _send_ping_message(self, channel: str) -> None:
        message = IPCMessage(
            author=self.ipc_name,
            action="ping",
            reply_global=False,
            data=jsonpickle.encode(self.active_clusters)
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_update_game_news_message(self, channel: str) -> None:
        message = IPCMessage(
            author=self.ipc_name,
            action="get_game_news",
            reply_global=False,
            data=self.game_news
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_set_game_guard_message(
        self,
        channel: str,
        duration: int
    ) -> None:
        message = IPCMessage(
            author=self.ipc_name,
            action="enable_guard",
            reply_global=False,
            data=duration
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_update_items_message(self, channel: str) -> None:
        message = IPCMessage(
            author=self.ipc_name,
            action="get_items",
            reply_global=False,
            data=jsonpickle.encode(self.item_pool)
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _global_task_update_items(self) -> None:
        while not self._loop.is_closed():
            self.item_pool.update_market_prices()

            await self._send_update_items_message(self.global_channel)

            self.log.info("Published global update items message")

            # Update every hour, exactly at minute 0
            next_refresh = datetime.now().replace(
                microsecond=0,
                second=0,
                minute=0
            ) + timedelta(hours=1)

            time_until = next_refresh - datetime.now()

            await asyncio.sleep(time_until.total_seconds())

    async def _global_task_send_stats(self) -> None:
        while not self._loop.is_closed():
            await asyncio.sleep(self.post_stats_delay)

            if not self.total_shard_count or not self.total_guild_count:
                continue

            url = f"https://top.gg/api/bots/{self.bot_id}/stats"
            headers = {
                "Authorization": self._config['topgg']['auth_token']
            }
            body = {
                "server_count": self.total_guild_count,
                "shard_count": self.total_shard_count
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=body) as r:
                    if r.status != 200:
                        self.log.error(
                            "Could not post stats to top.gg. "
                            f"Response: {r.status}"
                        )
                    else:
                        self.log.info(
                            "Published stats to top.gg: "
                            f"Guild count: {self.total_guild_count} "
                            f"Shard count: {self.total_shard_count}"
                        )

    async def _global_task_do_backups(self) -> None:
        postgres_config = self._config['postgres']

        while not self._loop.is_closed():
            await asyncio.sleep(self.db_backup_delay)

            self.log.info("Starting the database backup script")

            cmd = (
                "sh scripts/backup.sh "
                f"{postgres_config['host']} "
                f"{postgres_config['database']} "
                f"{postgres_config['user']} "
                f"{postgres_config['password']}"
            )

            process = await asyncio.create_subprocess_shell(
                cmd, stdout=sys.stdout, stderr=sys.stderr
            )

            await process.wait()

            self.log.info(
                "Backup script exited with code: "
                f"{process.returncode}"
            )

    async def _global_task_check_discord_incidents(self) -> None:
        while not self._loop.is_closed():
            await asyncio.sleep(self.incident_check_delay)

            url = "https://discordstatus.com/api/v2/incidents/unresolved.json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    if r.status != 200:
                        self.log.error(
                            "Could not get Discord status page. "
                            f"Response: {r.status}"
                        )

                        continue
                    else:
                        js = await r.json()

            try:
                all_impacts = [x['impact'] for x in js['incidents']]
            except KeyError as e:
                self.log.error(
                    "Error while parsing Discord status JSON:",
                    exc_info=(type(e), e, e.__traceback__)
                )

            if "critical" in all_impacts:
                self.log.info(
                    "Activating farm guard because of a "
                    "critical Discord incident"
                )
                await self._send_set_game_guard_message(
                    self.global_channel, self.critical_incident_guard
                )
            elif "major" in all_impacts:
                self.log.info(
                    "Activating farm guard because of "
                    "a major Discord incident"
                )
                await self._send_set_game_guard_message(
                    self.global_channel, self.major_incident_guard
                )


if __name__ == "__main__":
    ipc = IPC()
    ipc.start()

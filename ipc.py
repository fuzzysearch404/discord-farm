import sys
import json
import random
import logging
import asyncio
import aiohttp
import asyncpg
import aioredis
import jsonpickle
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta

from core import ipc_classes
from core.game_items import load_all_items


if sys.platform == "linux":
    import uvloop
    uvloop.install()


class IPC:
    def __init__(self) -> None:
        self.loop = asyncio.get_event_loop()

        with open("config.json", "r") as file:
            self.config = json.load(file)
        with open("data/news.txt", "r") as file:
            self.game_news = file.read()

        log = logging.getLogger("IPC")
        if self.config['ipc']['beta']:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)

        log_formatter = logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s")
        file_handler = TimedRotatingFileHandler("./logs/ipc.log", encoding="utf-8", when="W0")
        file_handler.setFormatter(log_formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        log.handlers = [file_handler, stream_handler]
        self.log = log

        ipc_config = self.config['ipc']
        self.bot_id = ipc_config['bot-id']
        self.is_beta = ipc_config['beta']
        self.db_backup_delay = ipc_config['db-backups-delay']
        self.cluster_inactive_timeout = ipc_config['cluster-inactive-timeout']
        self.cluster_check_delay = ipc_config['cluster-check-delay']
        self.post_stats_delay = ipc_config['post-bot-stats-delay']
        self.incident_check_delay = ipc_config['incident-check-delay']
        self.critical_incident_guard = ipc_config['critical-incident-guard']
        self.major_incident_guard = ipc_config['major-incident-guard']

        self.ipc_name = "IPC"
        self.global_channel = "global"
        self.cluster_channel_prefix = "cluster-"

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

        self.reminder_queue = asyncio.PriorityQueue()
        self.reminder_ignore_ids = set()
        self.reminder_deleted_keys = set()
        self.next_reminder = None
        self.next_reminder_key = None
        self.reminder_scheduler = None
        self.reminder_scheduler_sleeping = False

        self.active_clusters = []
        self.total_guild_count = 0
        self.total_shard_count = 0
        self.eval_responses = {}

        log.debug("Connecting to Redis")
        self.redis = aioredis.from_url(
            self.config['redis']['host'],
            password=self.config['redis']['password'],
            db=self.config['redis']['db-index']
        )
        self.redis_pubsub = self.redis.pubsub()

        log.debug("Fetching reminders")
        self.loop.run_until_complete(self.fetch_reminder_ignore_ids())
        self.loop.run_until_complete(self.get_current_reminders())

        log.debug("Loading game items")
        self.item_pool = load_all_items()

    def start(self) -> None:
        self.log.info("Starting: Registering tasks")
        self.loop.create_task(self._register_tasks())

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.stop())

    async def stop(self) -> None:
        self.log.info("Exiting")
        await self._unregister_redis_channels()
        self.loop.stop()

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.psubscribe(self.cluster_channel_prefix + "*")

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.punsubscribe(self.cluster_channel_prefix + "*")

    async def _register_tasks(self) -> None:
        await self._register_redis_channels()

        # Incoming messages handler
        self.loop.create_task(self._redis_event_handler())
        # Local tasks
        self.loop.create_task(self._cluster_check_task())
        # Global message publish tasks
        self.loop.create_task(self._global_task_update_items())
        # Global reminders task
        self.reminder_scheduler = self.loop.create_task(self._global_task_dispatch_reminders())
        # Discord incidents check task for Farm Guard
        self.loop.create_task(self._global_task_check_discord_incidents())

        if not self.is_beta:
            self.loop.create_task(self._global_task_send_stats())
            self.loop.create_task(self._global_task_do_backups())

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

            if ipc_message.reply_global:
                reply_channel = self.global_channel
            else:
                reply_channel = ipc_message.author

            if ipc_message.action == "ping":
                await self._update_cluster_status(ipc_message.data, reply_channel)
            elif ipc_message.action == "add_reminder":
                await self._handle_add_reminder(ipc_message.data)
            elif ipc_message.action == "get_items":
                await self._send_update_items_message(reply_channel)
            elif ipc_message.action == "get_game_news":
                await self._send_update_game_news_message(reply_channel)
            elif ipc_message.action == "set_items":
                await self._handle_set_items()
            elif ipc_message.action == "set_game_news":
                await self._handle_set_news(ipc_message)
            elif ipc_message.action == "stop_reminders":
                self._handle_disable_reminders(ipc_message.data)
            elif ipc_message.action == "start_reminders":
                self._handle_enable_reminders(ipc_message.data)
            elif ipc_message.action == "del_reminders":
                await self._handle_delete_reminders(ipc_message.data)
            elif ipc_message.action in self.ignore_actions:
                continue
            else:
                self.log.error(f"Unknown action: {ipc_message.action}")

    async def _update_cluster_status(
        self,
        cluster: ipc_classes.Cluster,
        reply_channel: str
    ) -> None:
        try:
            to_remove = next(x for x in self.active_clusters if x.name == cluster.name)
            self.active_clusters.remove(to_remove)
        except StopIteration:
            pass

        self.active_clusters.append(cluster)
        await self._send_ping_message(reply_channel)

    async def _cluster_check_task(self) -> None:
        while not self.loop.is_closed():
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

    async def fetch_reminder_ignore_ids(self) -> None:
        connect_args = {
            "user": self.config['postgres']['user'],
            "password": self.config['postgres']['password'],
            "database": self.config['postgres']['database'],
            "host": self.config['postgres']['host']
        }

        conn = await asyncpg.connect(**connect_args)
        ignore_ids = await conn.fetch("SELECT user_id FROM profile WHERE notifications = false;")

        for id in ignore_ids:
            self.reminder_ignore_ids.add(id['user_id'])

        await conn.close()

    async def fetch_reminder_keys(self, user_id: int = 0) -> list:
        match = "reminder:*:*" if not user_id else f"reminder:{user_id}:*"
        results = []

        cur = b"0"
        while cur:
            cur, keys = await self.redis.scan(cur, match=match)
            results.extend([x.decode("utf-8") for x in keys])

        return results

    async def get_current_reminders(self) -> None:
        all_keys = await self.fetch_reminder_keys()

        for key in all_keys:
            # reminder:user_id:reminder_id
            ends_milis = int(key.split(":")[-1])
            await self.reminder_queue.put((ends_milis, key))

    async def _handle_add_reminder(self, reminder: ipc_classes.Reminder) -> None:
        milis = int(reminder.time.timestamp() * 1000)
        rem_secs = int((reminder.time - datetime.now()).total_seconds())
        # Set expiry to 30 seconds more, to avoid expiring it on Redis side
        # before we are even able to fetch it
        await self.redis.execute_command(
            "SET", f"reminder:{reminder.user_id}:{milis}",
            jsonpickle.encode(reminder), "EX", rem_secs + 30
        )

        if not self.next_reminder or self.next_reminder.time < reminder.time:
            # New reminder is later than than the current one
            await self.reminder_queue.put((milis, f"reminder:{reminder.user_id}:{milis}"))
            return

        # Swap the current reminder to the new one
        # Add the new reminder to the queue
        await self.reminder_queue.put((milis, f"reminder:{reminder.user_id}:{milis}"))

        # If waiting, restart the task, otherwise let it finish the current job
        if self.reminder_scheduler_sleeping:
            # Readd the old reminder back to the queue
            old_milis = int(self.next_reminder.time.timestamp() * 1000)
            await self.reminder_queue.put((old_milis, self.next_reminder_key))

            self.reminder_scheduler.cancel()
            self.next_reminder = None
            self.reminder_scheduler = self.loop.create_task(
                self._global_task_dispatch_reminders()
            )

    def _handle_disable_reminders(self, user_id: int) -> None:
        self.reminder_ignore_ids.add(user_id)

    def _handle_enable_reminders(self, user_id: int) -> None:
        try:
            self.reminder_ignore_ids.remove(user_id)
        except KeyError:
            pass

    async def _handle_delete_reminders(self, user_id: int) -> None:
        reminders = await self.fetch_reminder_keys(user_id)

        for rem in reminders:
            await self.redis.execute_command("DEL", rem)
            self.reminder_deleted_keys.add(rem)

    async def _handle_set_news(self, message: ipc_classes.IPCMessage) -> None:
        self.game_news = message.data

        with open("data/news.txt", "w") as file:
            file.write(self.game_news)

        await self._send_update_game_news_message(self.global_channel)

    async def _handle_set_items(self) -> None:
        self.item_pool = load_all_items()
        self.item_pool.update_market_prices()

        await self._send_update_items_message(self.global_channel)

    async def _send_ping_message(self, channel: str) -> None:
        message = ipc_classes.IPCMessage(
            author=self.ipc_name,
            action="ping",
            reply_global=False,
            data=self.active_clusters
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_update_game_news_message(self, channel: str) -> None:
        message = ipc_classes.IPCMessage(
            author=self.ipc_name,
            action="get_game_news",
            reply_global=False,
            data=self.game_news
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_set_game_guard_message(self, channel: str, duration: int) -> None:
        message = ipc_classes.IPCMessage(
            author=self.ipc_name,
            action="enable_guard",
            reply_global=False,
            data=duration
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _send_update_items_message(self, channel: str) -> None:
        message = ipc_classes.IPCMessage(
            author=self.ipc_name,
            action="get_items",
            reply_global=False,
            data=self.item_pool
        )

        await self.redis.publish(channel, jsonpickle.encode(message))

    async def _post_reminder_message(self, reminder: ipc_classes.Reminder) -> None:
        random_names = ("Thomas", "Sophia", "Liam", "Emma")
        random_messages = (
            "Hey, are you here? Are you awake? \N{WAVING HAND SIGN}",
            "It's harvest time! \N{ADULT}\N{ZERO WIDTH JOINER}\N{EAR OF RICE}",
            "Guess who's harvest is ready? \N{THINKING FACE}",
            "Hey, it's harvest time! \N{PERSON RAISING BOTH HANDS IN CELEBRATION}",
            "I have some good news for you! \N{FACE WITH COWBOY HAT}",
            "Hi. Just letting you know that you harvest is ready. \N{TRACTOR}",
            "No time for chatting, it's harvest time! \N{FACE WITH FINGER COVERING CLOSED LIPS}",
            "Get yourself ready for some work, it's harvest time! \N{FACE SCREAMING IN FEAR}",
            "Come, I have something to show you! \N{FACE WITH OPEN MOUTH}"
        )
        msg = random.choice(random_messages)
        name = random.choice(random_names)

        item = self.item_pool.find_item_by_id(reminder.item_id)

        url = f"https://discord.com/api/v9/channels/{reminder.channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self.config['bot']['discord-token']}",
            "User-Agent": (
                f"Discord Farm Bot {self.config['bot']['version']} "
                "(https://github.com/fuzzysearch404/discord-farm/)"
            )
        }
        body = {
            "content": f"<@{reminder.user_id}> \N{BIRD} {name}, the mail bird: *\"{msg}\"*",
            "embeds": [
                {
                    "color": 12697268,
                    "title": "\N{ALARM CLOCK} Your harvest is ready!",
                    "description": (
                        f"\N{SEEDLING} Your **{reminder.amount}x {item.full_name}** "
                        "have been fully grown and are now ready to be harvested!\n"
                        "\N{TRACTOR} Use **/harvest** to collect your items!"
                    ),
                    "footer": {
                        "text": (
                            "\N{ELECTRIC LIGHT BULB} You can disable these game notifications with "
                            "the /notifications command."
                        )
                    }
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as r:
                    if r.status == 200:
                        self.log.info(
                            f"Published reminder message to channel: {reminder.channel_id}"
                        )
                        return

                    try:
                        r.raise_for_status()
                    except aiohttp.ClientResponseError as e:
                        # Don't want to get banned
                        if e.status == 429:
                            retry_after = e.headers.get("X-RateLimit-Reset-After") or 0
                            retry_after = int(float(retry_after)) + 1

                            self.log.error(f"Reminders: Got ratelimited for {retry_after} seconds!")
                            await asyncio.sleep(retry_after)
                        elif e.status >= 400 and e.status < 500:
                            self.log.error(f"Failed to post reminder message: {e.status}")
                            self.reminder_ignore_ids.add(reminder.channel_id)
                            self.log.error(f"Temp. ignoring channel: {reminder.channel_id}")
                        else:
                            self.log.exception(f"Failed to post reminder message: {e.status}")
        except Exception:
            self.log.exception("Failed to post reminder message")

    async def _global_task_dispatch_reminders(self) -> None:
        async def wait(seconds: int = 30) -> None:
            # 30 seconds is for idle waiting
            self.reminder_scheduler_sleeping = True
            await asyncio.sleep(seconds)
            self.reminder_scheduler_sleeping = False

        while not self.loop.is_closed():
            if not self.next_reminder and self.reminder_queue.empty():
                await wait()
                continue

            if not self.next_reminder:
                _, self.next_reminder_key = await self.reminder_queue.get()
                next_reminder = await self.redis.execute_command("GET", self.next_reminder_key)

                if not next_reminder:
                    # Already expired on Redis side or deleted
                    continue

                self.next_reminder = jsonpickle.decode(next_reminder)
                self.log.debug(f"Found a new reminder to wait for: {self.next_reminder_key}")

            remaining_seconds = (self.next_reminder.time - datetime.now()).total_seconds()
            if remaining_seconds > 40:
                # Wait for a while until the next reminder is closer
                await wait()
                continue

            # The actual waiting for the reminder
            if remaining_seconds > 0:
                await wait(remaining_seconds)

            if self.next_reminder.user_id in self.reminder_ignore_ids:
                self.next_reminder = None
                continue

            # The reminder got deleted
            if self.next_reminder_key in self.reminder_deleted_keys:
                self.reminder_deleted_keys.remove(self.next_reminder_key)
                self.next_reminder = None
                continue

            if self.next_reminder.channel_id not in self.reminder_ignore_ids:
                self.log.info(f"Reminder {self.next_reminder_key} done, posting...")
                await self._post_reminder_message(self.next_reminder)

            self.next_reminder = None

    async def _global_task_update_items(self) -> None:
        while not self.loop.is_closed():
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
        while not self.loop.is_closed():
            await asyncio.sleep(self.post_stats_delay)

            if not self.total_shard_count or not self.total_guild_count:
                # Avoid posting when data is not gathered yet
                continue

            url = f"https://top.gg/api/bots/{self.bot_id}/stats"
            headers = {
                "Authorization": self.config['topgg']['auth_token']
            }
            body = {
                "server_count": self.total_guild_count,
                "shard_count": self.total_shard_count
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=body) as resp:
                        if resp.status == 200:
                            self.log.info(
                                "Published stats to top.gg: "
                                f"Guild count: {self.total_guild_count} "
                                f"Shard count: {self.total_shard_count}"
                            )
                            continue

                        try:
                            resp.raise_for_status()
                        except aiohttp.ClientResponseError as e:
                            self.log.exception(f"Failed to post top.gg stats: {e.status}")
            except Exception:
                self.log.exception("Failed to post top.gg stats")

    async def _global_task_do_backups(self) -> None:
        postgres_config = self.config['postgres']

        while not self.loop.is_closed():
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
            self.log.info(f"Backup script exited with code: {process.returncode}")

    async def _global_task_check_discord_incidents(self) -> None:
        while not self.loop.is_closed():
            await asyncio.sleep(self.incident_check_delay)

            url = "https://discordstatus.com/api/v2/incidents/unresolved.json"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as r:
                        if r.status == 200:
                            js = await r.json()

                        try:
                            r.raise_for_status()
                        except aiohttp.ClientResponseError as e:
                            self.log.exception(f"Failed to fetch discord incidents: {e.status}")
                            continue
            except Exception:
                self.log.exception("Failed to fetch discord incidents")
                continue

            try:
                all_impacts = [x['impact'] for x in js['incidents']]
            except KeyError as e:
                self.log.error(
                    "Error while parsing Discord status JSON:",
                    exc_info=(type(e), e, e.__traceback__)
                )

            if "critical" in all_impacts:
                self.log.info("Activating farm guard because of a critical Discord incident")
                await self._send_set_game_guard_message(
                    self.global_channel, self.critical_incident_guard
                )
            elif "major" in all_impacts:
                self.log.info("Activating farm guard because of a major Discord incident")
                await self._send_set_game_guard_message(
                    self.global_channel, self.major_incident_guard
                )


if __name__ == "__main__":
    IPC().start()

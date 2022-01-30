import asyncio
import jsonpickle
import datetime

from core.ipc_classes import Cluster, IPCMessage, Reminder
from .util import exceptions
from .util.commands import FarmCommandCollection


class ClustersCollection(FarmCommandCollection):
    """Developer only commands for bot management purposes."""
    hidden_in_help_command = True

    def __init__(self, client) -> None:
        super().__init__(client, [], name="Clusters")
        self.redis_pubsub = client.redis.pubsub()

        self.global_channel = "global"
        self.self_name = "cluster-" + client.cluster_name

        self.cluster_update_delay = client.config['ipc']['cluster-update-delay']
        self.last_ping = None

        # We will execute these too (don't ignore as self author)
        self.self_execute_actions = (
            "maintenance",
            "enable_guard",
            "eval",
            "result",
            "reload",
            "load",
            "unload",
            "shutdown"
        )

        self.responses = {}
        self.response_lock = asyncio.Lock()

        self.client.loop.create_task(self._register_tasks_and_channels())
        self.client.loop.create_task(self._request_all_required_data())
        # Block the bot from firing ready until
        # ensuring that we have the mandatory data
        self.client.loop.run_until_complete(self._ensure_all_required_data())

    async def collection_check(self, command) -> bool:
        # I am aware that this is a double check when using "owner_only" = True
        if not await self.client.is_owner(command.author):
            raise exceptions.CommandOwnerOnlyException()

    def on_unload(self) -> None:
        self.client.loop.create_task(self._unregister_tasks_and_channels())

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.subscribe(self.self_name)

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.unsubscribe(self.self_name)

    async def _register_tasks_and_channels(self) -> None:
        await self._register_redis_channels()
        self._handler_task = self.client.loop.create_task(self._redis_event_handler())
        self._ping_task = self.client.loop.create_task(self._cluster_ping_task())

    async def _unregister_tasks_and_channels(self) -> None:
        self._handler_task.cancel()
        self._ping_task.cancel()
        await self._unregister_redis_channels()

    async def _redis_event_handler(self) -> None:
        async for message in self.redis_pubsub.listen():
            if message['type'] != "message":
                continue

            try:
                ipc_message = jsonpickle.decode(message['data'])
            except TypeError:
                continue

            if ipc_message.author == self.self_name \
                    and ipc_message.action not in self.self_execute_actions:
                continue

            self.client.log.debug(
                f"Received message from: {ipc_message.author} "
                f"Action: {ipc_message.action} "
                f"Reply global: {ipc_message.reply_global}"
            )

            if ipc_message.action == "ping":
                self._handle_update_cluster_data(ipc_message)
            elif ipc_message.action == "get_items":
                self._handle_update_items(ipc_message)
            elif ipc_message.action == "get_game_news":
                self._handle_update_game_news(ipc_message)
            elif ipc_message.action == "maintenance":
                await self._handle_maintenance(ipc_message)
            elif ipc_message.action == "enable_guard":
                await self._handle_farm_guard(ipc_message)
            elif ipc_message.action == "reload":
                await self._handle_reload_extension(ipc_message)
            elif ipc_message.action == "load":
                await self._handle_load_extension(ipc_message)
            elif ipc_message.action == "unload":
                await self._handle_unload_extension(ipc_message)
            elif ipc_message.action == "eval":
                await self._handle_eval_command(ipc_message)
            elif ipc_message.action == "result":
                self.responses[ipc_message.author] = ipc_message.data
            elif ipc_message.action == "shutdown":
                self._handle_shutdown()
            else:
                self.log.error(f"Unknown action: {ipc_message.action}")

    async def _request_all_required_data(self) -> None:
        if not hasattr(self.client, "item_pool"):
            await self._send_get_items_message()

        if not hasattr(self.client, "cluster_data"):
            await self._send_ping_message()

        if not hasattr(self.client, "game_news"):
            await self._send_get_game_news_message()

    async def _ensure_all_required_data(self) -> None:
        retry_in = 0
        # Well, we can't get the responses instantly
        await asyncio.sleep(0.1)

        while not self.client.is_closed():
            missing = False

            if not hasattr(self.client, "item_pool"):
                missing = True

            if not hasattr(self.client, "cluster_data"):
                missing = True

            if not hasattr(self.client, "game_news"):
                missing = True

            if not missing:
                return

            self.client.log.critical(
                f"Missing required data from IPC. Retrying in: {retry_in} seconds"
            )

            await asyncio.sleep(retry_in)
            if retry_in < 60:
                retry_in += 3

            await self._request_all_required_data()

    async def _cluster_ping_task(self) -> None:
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            await self._send_ping_message()
            await asyncio.sleep(self.cluster_update_delay)

    def _handle_update_items(self, message: IPCMessage) -> None:
        self.client.item_pool = message.data

    async def _handle_maintenance(self, message: IPCMessage) -> None:
        self.client.maintenance_mode = message.data
        await self._send_results(f"\N{WHITE HEAVY CHECK MARK} {self.client.maintenance_mode}")

    async def _handle_farm_guard(self, message: IPCMessage) -> None:
        self.client.enable_field_guard(message.data)
        await self._send_results(self.client.guard_mode)

    def _handle_update_cluster_data(self, message: IPCMessage) -> None:
        self.client.cluster_data = message.data

        time_delta = datetime.datetime.now() - self.last_ping
        self.client.ipc_ping = time_delta.total_seconds() * 1000  # ms

    def _handle_update_game_news(self, message: IPCMessage) -> None:
        self.client.game_news = message.data

    async def _handle_eval_command(self, message: IPCMessage) -> None:
        result = await self.client.eval_code(message.data)
        await self._send_results(result)

    async def _handle_reload_extension(self, message: IPCMessage) -> None:
        try:
            self.client.reload_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\N{WHITE HEAVY CHECK MARK}")

    async def _handle_load_extension(self, message: IPCMessage) -> None:
        try:
            self.client.load_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\N{WHITE HEAVY CHECK MARK}")

    async def _handle_unload_extension(self, message: IPCMessage) -> None:
        try:
            self.client.unload_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\N{WHITE HEAVY CHECK MARK}")

    def _handle_shutdown(self) -> None:
        self.client.loop.create_task(self.client.close())

    async def send_ipc_message(
        self,
        action: str,
        reply_global: bool,
        data=None,
        global_channel: bool = False
    ) -> None:
        message = IPCMessage(
            author=self.self_name,
            action=action,
            reply_global=reply_global,
            data=data
        )
        channel = self.self_name if not global_channel else self.global_channel
        await self.client.redis.publish(channel, jsonpickle.encode(message))

    async def _send_ping_message(self) -> None:
        self.last_ping = datetime.datetime.now()

        if hasattr(self.client, "launch_time"):
            uptime = self.client.uptime
        else:
            uptime = datetime.timedelta(seconds=0)

        cluster = Cluster(
            name=self.client.cluster_name,
            latencies=self.client.latencies,
            ipc_latency=self.client.ipc_ping,
            guild_count=len(self.client.guilds),
            last_ping=self.last_ping,
            uptime=uptime
        )

        await self.send_ipc_message("ping", False, cluster)

    async def send_set_reminder_message(self, reminder: Reminder) -> None:
        await self.send_ipc_message("add_reminder", False, reminder)

    async def send_disable_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("stop_reminders", False, user_id)

    async def send_enable_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("start_reminders", False, user_id)

    async def send_delete_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("del_reminders", False, user_id)

    async def _send_get_items_message(self, reply_global: bool = False) -> None:
        await self.send_ipc_message("get_items", reply_global, None)

    async def _send_set_items_message(self) -> None:
        await self.send_ipc_message("set_items", True, None)

    async def _send_get_game_news_message(self, reply_global: bool = False) -> None:
        await self.send_ipc_message("get_game_news", reply_global, None)

    async def _send_set_game_news_message(self, game_news: str) -> None:
        await self.send_ipc_message("set_game_news", True, game_news)

    async def _send_set_field_guard_message(self, duration: int) -> None:
        await self.send_ipc_message("enable_guard", True, duration, global_channel=True)

    async def _send_set_maintenance_message(self, enabled: bool) -> None:
        await self.send_ipc_message("maintenance", True, enabled, global_channel=True)

    async def _send_eval_message(self, eval_code: str) -> None:
        await self.send_ipc_message("eval", True, eval_code, global_channel=True)

    async def _send_results(self, result: str) -> None:
        await self.send_ipc_message("result", True, result, global_channel=True)

    async def _send_reload_message(self, extension: str) -> None:
        await self.send_ipc_message("reload", True, extension, global_channel=True)

    async def _send_load_message(self, extension: str) -> None:
        await self.send_ipc_message("load", True, extension, global_channel=True)

    async def _send_unload_message(self, extension: str) -> None:
        await self.send_ipc_message("unload", True, extension, global_channel=True)

    async def _send_shutdown_message(self) -> None:
        await self.send_ipc_message("shutdown", True, None, global_channel=True)

    async def _wait_and_publish_responses(self, cmd) -> None:
        # Wait for responses
        await cmd.defer()
        await asyncio.sleep(3)

        fmt = ""
        for cluster_name, result in self.responses.items():
            fmt += f"{cluster_name}: {result}\n"

        if len(fmt) > 1994:  # 2000 - 6 for code block
            # TODO: Send as a file, when it's going to be possible
            await cmd.edit("Output too long...")
            #  fp = io.BytesIO(fmt.encode("utf-8"))
            #  await cmd.edit(content="Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await cmd.edit(content=f"```{fmt}```")


def setup(client) -> list:
    return [ClustersCollection(client)]

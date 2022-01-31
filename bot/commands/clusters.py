import asyncio
import datetime
import discord
import jsonpickle
from typing import Optional

from core import ipc_classes
from core import static
from .util import exceptions
from .util import time as time_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


class ClustersCollection(FarmCommandCollection):
    """Developer only commands for bot management purposes."""
    hidden_in_help_command = True

    def __init__(self, client) -> None:
        super().__init__(client, [ClustersCommand], name="Clusters")
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
        await self.redis_pubsub.close()

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
            await self.send_get_items_message()

        if not hasattr(self.client, "cluster_data"):
            await self.send_ping_message()

        if not hasattr(self.client, "game_news"):
            await self.send_get_game_news_message()

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
            await self.send_ping_message()
            await asyncio.sleep(self.cluster_update_delay)

    def _handle_update_items(self, message: ipc_classes.IPCMessage) -> None:
        self.client.item_pool = message.data

    async def _handle_maintenance(self, message: ipc_classes.IPCMessage) -> None:
        self.client.maintenance_mode = message.data
        await self.send_results(f"\N{WHITE HEAVY CHECK MARK} {self.client.maintenance_mode}")

    async def _handle_farm_guard(self, message: ipc_classes.IPCMessage) -> None:
        self.client.enable_field_guard(message.data)
        await self.send_results(self.client.guard_mode)

    def _handle_update_cluster_data(self, message: ipc_classes.IPCMessage) -> None:
        self.client.cluster_data = message.data

        time_delta = datetime.datetime.now() - self.last_ping
        self.client.ipc_ping = time_delta.total_seconds() * 1000  # ms

    def _handle_update_game_news(self, message: ipc_classes.IPCMessage) -> None:
        self.client.game_news = message.data

    async def _handle_eval_command(self, message: ipc_classes.IPCMessage) -> None:
        result = await self.client.eval_code(message.data)
        await self.send_results(result)

    async def _handle_reload_extension(self, message: ipc_classes.IPCMessage) -> None:
        try:
            self.client.reload_extension(message.data)
        except Exception as e:
            await self.send_results(str(e))
            return

        await self.send_results("\N{WHITE HEAVY CHECK MARK}")

    async def _handle_load_extension(self, message: ipc_classes.IPCMessage) -> None:
        try:
            self.client.load_extension(message.data)
        except Exception as e:
            await self.send_results(str(e))
            return

        await self.send_results("\N{WHITE HEAVY CHECK MARK}")

    async def _handle_unload_extension(self, message: ipc_classes.IPCMessage) -> None:
        try:
            self.client.unload_extension(message.data)
        except Exception as e:
            await self.send_results(str(e))
            return

        await self.send_results("\N{WHITE HEAVY CHECK MARK}")

    def _handle_shutdown(self) -> None:
        self.client.loop.create_task(self.client.close())

    async def send_ipc_message(
        self,
        action: str,
        reply_global: bool,
        data=None,
        global_channel: bool = False
    ) -> None:
        message = ipc_classes.IPCMessage(
            author=self.self_name,
            action=action,
            reply_global=reply_global,
            data=data
        )
        channel = self.self_name if not global_channel else self.global_channel
        await self.client.redis.publish(channel, jsonpickle.encode(message))

    async def send_ping_message(self) -> None:
        self.last_ping = datetime.datetime.now()

        if hasattr(self.client, "launch_time"):
            uptime = self.client.uptime
        else:
            uptime = datetime.timedelta(seconds=0)

        cluster = ipc_classes.Cluster(
            name=self.client.cluster_name,
            latencies=self.client.latencies,
            ipc_latency=self.client.ipc_ping,
            guild_count=len(self.client.guilds),
            last_ping=self.last_ping,
            uptime=uptime
        )

        await self.send_ipc_message("ping", False, cluster)

    async def send_set_reminder_message(self, reminder: ipc_classes.Reminder) -> None:
        await self.send_ipc_message("add_reminder", False, reminder)

    async def send_disable_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("stop_reminders", False, user_id)

    async def send_enable_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("start_reminders", False, user_id)

    async def send_delete_reminders_message(self, user_id: int) -> None:
        await self.send_ipc_message("del_reminders", False, user_id)

    async def send_get_items_message(self) -> None:
        await self.send_ipc_message("get_items", False, None)

    async def send_set_items_message(self) -> None:
        await self.send_ipc_message("set_items", True, None)

    async def send_get_game_news_message(self) -> None:
        await self.send_ipc_message("get_game_news", False, None)

    async def send_set_game_news_message(self, game_news: str) -> None:
        await self.send_ipc_message("set_game_news", True, game_news)

    async def send_set_farm_guard_message(self, duration: int) -> None:
        await self.send_ipc_message("enable_guard", True, duration, global_channel=True)

    async def send_set_maintenance_message(self, enabled: bool) -> None:
        await self.send_ipc_message("maintenance", True, enabled, global_channel=True)

    async def send_eval_message(self, eval_code: str) -> None:
        await self.send_ipc_message("eval", True, eval_code, global_channel=True)

    async def send_results(self, result: str) -> None:
        await self.send_ipc_message("result", True, result, global_channel=True)

    async def send_reload_message(self, extension: str) -> None:
        await self.send_ipc_message("reload", True, extension, global_channel=True)

    async def send_load_message(self, extension: str) -> None:
        await self.send_ipc_message("load", True, extension, global_channel=True)

    async def send_unload_message(self, extension: str) -> None:
        await self.send_ipc_message("unload", True, extension, global_channel=True)

    async def send_shutdown_message(self) -> None:
        await self.send_ipc_message("shutdown", True, None, global_channel=True)

    async def wait_and_publish_responses(self, cmd) -> None:
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


def get_cluster_collection(client) -> ClustersCollection:
    try:
        return client.get_command_collection("Clusters")
    except KeyError:
        client.log.critical("Cluster collection not loaded!")
        return None


class ClustersCommand(FarmSlashCommand, name="clusters", guilds=static.DEVELOPMENT_GUILD_IDS):
    pass


class ClustersEvalCommand(
    FarmSlashCommand,
    name="eval",
    description="\N{SATELLITE} [Developer only] Runs Python code on all clusters",
    parent=ClustersCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool
    # TODO: Use multi line text input, when possible
    body: str = discord.app.Option(description="Python code to execute")

    async def callback(self) -> None:
        clusters_collection = get_cluster_collection(self.client)
        async with clusters_collection.response_lock:
            clusters_collection.responses = {}
            await clusters_collection.send_eval_message(self.body)
            await clusters_collection.wait_and_publish_responses(self)


class ClustersStatusCommand(
    FarmSlashCommand,
    name="status",
    description="\N{SATELLITE} [Developer only] Shows bot's all cluster statuses",
    parent=ClustersCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    async def callback(self) -> None:
        embed = discord.Embed()
        embed.set_footer(text=f"Local IPC ping: {'%.0f' % self.client.ipc_ping}ms")

        for cluster in self.client.cluster_data:
            fmt = ""
            for id, ping in cluster.latencies:
                fmt += f"> **#{id} - {'%.0f' % (ping * 1000)}ms**\n"

            fmt += f"\n**Uptime: {time_util.seconds_to_time(cluster.uptime.total_seconds())} **"
            embed.add_field(name=f"**{cluster.name} ({cluster.guild_count} guilds)**", value=fmt)

        await self.reply(embed=embed)


class ClustersLogoutCommand(
    FarmSlashCommand,
    name="logout",
    description="\N{SATELLITE} [Developer only] Logs off this or all bot instances",
    parent=ClustersCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    run_locally: Optional[bool] = discord.app.Option(
        description="Set to True to logout only the current instance",
        default=False
    )

    async def callback(self) -> None:
        if self.run_locally:
            await self.reply("\N{WHITE HEAVY CHECK MARK} Logging off this instance...")
            self.client.loop.create_task(self.client.close())
        else:
            await self.reply("\N{WHITE HEAVY CHECK MARK} Logging off all instances...")
            await get_cluster_collection(self.client).send_shutdown_message()


class ClustersCommandsCommand(FarmSlashCommand, name="commands", parent=ClustersCommand):
    pass


class ClustersCommandsSyncCommand(
    FarmSlashCommand,
    name="sync",
    description="\N{SATELLITE} [Developer only] Synchronizes commands based on this instance",
    parent=ClustersCommandsCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    global_commands: Optional[bool] = discord.app.Option(
        description="If set to True, global application commands are going to be synced",
        default=True
    )
    guild_commands: Optional[bool] = discord.app.Option(
        description="If set to True, guild application commands are going to be synced",
        default=True
    )

    async def callback(self) -> None:
        await self.defer()

        if self.global_commands:
            await self.client.upload_global_application_commands()
        if self.guild_commands:
            await self.client.upload_guild_application_commands()

        await self.edit(content="\N{WHITE HEAVY CHECK MARK} Sync request sent to Discord!")


class ClustersCommandsLoadModuleCommand(
    FarmSlashCommand,
    name="load_module",
    description="\N{SATELLITE} [Developer only] Loads an extension",
    parent=ClustersCommandsCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    extension: str = discord.app.Option(description="Extension name")

    async def callback(self) -> None:
        if not self.extension.startswith("bot.commands."):
            self.extension = "bot.commands." + self.extension

        clusters_collection = get_cluster_collection(self.client)
        async with clusters_collection.response_lock:
            clusters_collection.responses = {}
            await clusters_collection.send_load_message(self.extension)
            await clusters_collection.wait_and_publish_responses(self)


class ClustersCommandsUnloadModuleCommand(
    FarmSlashCommand,
    name="unload_module",
    description="\N{SATELLITE} [Developer only] Unloads an extension",
    parent=ClustersCommandsCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    extension: str = discord.app.Option(description="Extension name")

    async def callback(self) -> None:
        if not self.extension.startswith("bot.commands."):
            self.extension = "bot.commands." + self.extension

        clusters_collection = get_cluster_collection(self.client)
        async with clusters_collection.response_lock:
            clusters_collection.responses = {}
            await clusters_collection.send_unload_message(self.extension)
            await clusters_collection.wait_and_publish_responses(self)


class ClustersCommandsReloadModuleCommand(
    FarmSlashCommand,
    name="reload_module",
    description="\N{SATELLITE} [Developer only] Reloads an extension",
    parent=ClustersCommandsCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    extension: str = discord.app.Option(description="Extension name")

    async def callback(self) -> None:
        if not self.extension.startswith("bot.commands."):
            self.extension = "bot.commands." + self.extension

        clusters_collection = get_cluster_collection(self.client)
        async with clusters_collection.response_lock:
            clusters_collection.responses = {}
            await clusters_collection.send_reload_message(self.extension)
            await clusters_collection.wait_and_publish_responses(self)


class ClustersGameMasterCommand(FarmSlashCommand, name="game_master", parent=ClustersCommand):
    pass


class ClustersGameMasterReloadItemsCommand(
    FarmSlashCommand,
    name="reload_items",
    description="\N{SATELLITE} [Developer only] Reloads game items data on all clusters",
    parent=ClustersGameMasterCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    async def callback(self) -> None:
        await get_cluster_collection(self.client).send_set_items_message()
        await self.reply("\N{WHITE HEAVY CHECK MARK} Sent reload items request to IPC")


class ClustersGameMasterEditNewsCommand(
    FarmSlashCommand,
    name="edit_news",
    description="\N{SATELLITE} [Developer only] Edits the game news",
    parent=ClustersGameMasterCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool
    # TODO: Use multi line text input, when possible
    news: str = discord.app.Option(description="The news text to set")

    async def callback(self) -> None:
        await get_cluster_collection(self.client).send_set_game_news_message(self.news)
        # Wait for the news to arrive to self
        await self.defer()
        await asyncio.sleep(2)
        await self.edit(content=self.client.game_news)


class ClustersGameMasterEditMaintenanceCommand(
    FarmSlashCommand,
    name="edit_maintenance",
    description="\N{SATELLITE} [Developer only] Edits the bot's maintenance status",
    parent=ClustersGameMasterCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    enabled: bool = discord.app.Option(description="Set to True to enable maintenance")

    async def callback(self) -> None:
        cluster_collection = get_cluster_collection(self.client)
        async with cluster_collection.response_lock:
            cluster_collection.responses = {}
            await cluster_collection.send_set_maintenance_message(self.enabled)
            await cluster_collection.wait_and_publish_responses(self)


class ClustersGameMasterFarmGuardCommand(
    FarmSlashCommand,
    name="farm_guard",
    description="\N{SATELLITE} [Developer only] Enables the farm guard feature",
    parent=ClustersGameMasterCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    duration: int = discord.app.Option(description="Duration in seconds", min=0)

    async def callback(self) -> None:
        cluster_collection = get_cluster_collection(self.client)
        async with cluster_collection.response_lock:
            cluster_collection.responses = {}
            await cluster_collection.send_set_farm_guard_message(self.duration)
            await cluster_collection.wait_and_publish_responses(self)


def setup(client) -> list:
    return [ClustersCollection(client)]

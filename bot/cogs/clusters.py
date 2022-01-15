import io
import asyncio
import discord
import jsonpickle
import datetime
from discord.ext import commands

from core import exceptions
from core.ipc_classes import Cluster, IPCMessage, Reminder
from core import static
from .utils import time as time_util


class Clusters(commands.Cog):
    """
    Developer only commands for bot management purposes.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        self.redis_pubsub = bot.redis.pubsub()

        redis_config = bot.config['redis']
        self.global_channel = redis_config['global-channel-name']
        cluster_channel_prefix = redis_config['cluster-channel-prefix']
        self.self_name = cluster_channel_prefix + bot.cluster_name

        self.cluster_update_delay = bot.config['ipc']['cluster-update-delay']
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

        self.bot.loop.create_task(self._register_tasks())
        self.bot.loop.create_task(self._request_all_required_data())
        # Block the bot from firing ready until
        # ensuring that we have the mandatory data
        self.bot.loop.run_until_complete(self._ensure_all_required_data())

    async def cog_check(self, ctx) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True

        raise exceptions.FarmException("Sorry, this is a bot owner-only command.")

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self._unregister_tasks())

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.subscribe(self.self_name)

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.unsubscribe(self.self_name)

    async def _register_tasks(self) -> None:
        await self._register_redis_channels()

        self._handler_task = self.bot.loop.create_task(self._redis_event_handler())
        self._ping_task = self.bot.loop.create_task(self._cluster_ping_task())

    async def _unregister_tasks(self) -> None:
        self._handler_task.cancel()
        self._ping_task.cancel()

        await self._unregister_redis_channels()

    async def _redis_event_handler(self) -> None:
        async for message in self.redis_pubsub.listen():
            if message['type'] != 'message':
                continue

            try:
                ipc_message = jsonpickle.decode(message['data'])
            except TypeError:
                continue

            if ipc_message.author == self.self_name \
                    and ipc_message.action not in self.self_execute_actions:
                continue

            self.bot.log.debug(
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
        if not hasattr(self.bot, "item_pool"):
            await self._send_get_items_message()

        if not hasattr(self.bot, "cluster_data"):
            await self._send_ping_message()

        if not hasattr(self.bot, "game_news"):
            await self._send_get_game_news_message()

    async def _ensure_all_required_data(self) -> None:
        retry_in = 0

        # Well, we can't get the responses instantly
        await asyncio.sleep(0.1)

        while not self.bot.is_closed():
            missing = False

            if not hasattr(self.bot, "item_pool"):
                missing = True

            if not hasattr(self.bot, "cluster_data"):
                missing = True

            if not hasattr(self.bot, "game_news"):
                missing = True

            if not missing:
                return
            else:
                self.bot.log.critical(
                    "Missing required data from IPC. "
                    f"Retrying in: {retry_in} seconds"
                )

                await asyncio.sleep(retry_in)
                if retry_in < 60:
                    retry_in += 3

                await self._request_all_required_data()

    async def _cluster_ping_task(self) -> None:
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            await self._send_ping_message()

            await asyncio.sleep(self.cluster_update_delay)

    def _handle_update_items(self, message: IPCMessage) -> None:
        item_pool = jsonpickle.decode(message.data)

        self.bot.item_pool = item_pool

    async def _handle_maintenance(self, message: IPCMessage) -> None:
        self.bot.maintenance_mode = message.data

        await self._send_results(f"\u2705 {self.bot.maintenance_mode}")

    async def _handle_farm_guard(self, message: IPCMessage) -> None:
        self.bot.enable_field_guard(message.data)

        await self._send_results(self.bot.guard_mode)

    def _handle_update_cluster_data(self, message: IPCMessage) -> None:
        cluster_data = jsonpickle.decode(message.data)

        time_delta = datetime.datetime.now() - self.last_ping
        self.bot.ipc_ping = time_delta.total_seconds() * 1000  # ms

        self.bot.cluster_data = cluster_data

    def _handle_update_game_news(self, message: IPCMessage) -> None:
        self.bot.game_news = message.data

    async def _handle_eval_command(self, message: IPCMessage) -> None:
        result = await self.bot.eval_code(message.data)

        await self._send_results(result)

    async def _handle_reload_extension(self, message: IPCMessage) -> None:
        try:
            self.bot.reload_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\u2705")

    async def _handle_load_extension(self, message: IPCMessage) -> None:
        try:
            self.bot.load_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\u2705")

    async def _handle_unload_extension(self, message: IPCMessage) -> None:
        try:
            self.bot.unload_extension(message.data)
        except Exception as e:
            await self._send_results(str(e))
            return

        await self._send_results("\u2705")

    def _handle_shutdown(self) -> None:
        self.bot.loop.create_task(self.bot.close())

    async def _send_ping_message(self) -> None:
        self.last_ping = datetime.datetime.now()

        if hasattr(self.bot, "launch_time"):
            uptime = self.bot.uptime
        else:
            uptime = datetime.timedelta(seconds=0)

        cluster = Cluster(
            self.bot.cluster_name,
            self.bot.latencies,
            self.bot.ipc_ping,
            len(self.bot.guilds),
            self.last_ping,
            uptime
        )

        message = IPCMessage(
            author=self.self_name,
            action="ping",
            reply_global=False,
            data=jsonpickle.encode(cluster)
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def send_set_reminder_message(self, reminder: Reminder) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="add_reminder",
            reply_global=False,
            data=reminder
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def send_disable_reminders_message(self, user_id: int) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="stop_reminders",
            reply_global=False,
            data=user_id
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def send_enable_reminders_message(self, user_id: int) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="start_reminders",
            reply_global=False,
            data=user_id
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def send_delete_reminders_message(self, user_id: int) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="del_reminders",
            reply_global=False,
            data=user_id
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def _send_get_items_message(self, reply_global: bool = False) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="get_items",
            reply_global=reply_global,
            data=None
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def _send_set_items_message(self) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="set_items",
            reply_global=True,
            data=None
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def _send_get_game_news_message(self, reply_global: bool = False) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="get_game_news",
            reply_global=reply_global,
            data=None
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def _send_set_game_news_message(self, game_news: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="set_game_news",
            reply_global=False,
            data=game_news
        )

        await self.bot.redis.publish(self.self_name, jsonpickle.encode(message))

    async def _send_set_field_guard_message(self, duration: int) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="enable_guard",
            reply_global=True,
            data=duration
        )

        await self.bot.redis.publish(
            self.global_channel, jsonpickle.encode(message)
        )

    async def _send_set_maintenance_message(self, enabled: bool) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="maintenance",
            reply_global=True,
            data=enabled
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_eval_message(self, eval_code: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="eval",
            reply_global=True,
            data=eval_code
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_results(self, result: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="result",
            reply_global=True,
            data=result
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_reload_message(self, extension: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="reload",
            reply_global=True,
            data=extension
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_load_message(self, extension: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="load",
            reply_global=True,
            data=extension
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_unload_message(self, extenstion: str) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="unload",
            reply_global=True,
            data=extenstion
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _send_shutdown_message(self) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="shutdown",
            reply_global=True,
            data=None
        )

        await self.bot.redis.publish(self.global_channel, jsonpickle.encode(message))

    async def _wait_and_publish_responses(self, ctx) -> None:
        # Wait for responses
        await ctx.defer()
        await asyncio.sleep(3)

        fmt = ""
        for cluster_name, result in self.responses.items():
            fmt += f"{cluster_name}: {result}\n"

        fmt = f"```{fmt}```"

        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode("utf-8"))
            await ctx.send("Output too long...", file=discord.File(fp, "data.txt"))
        else:
            await ctx.reply(fmt)

    @commands.group(
        name="clusters",
        invoke_without_command=False,
        slash_command_guilds=static.DEVELOPMENT_GUILD_IDS
    )
    async def clusters_group(self, ctx):
        """\ud83d\udd27 [Developer only] Commands for managing all bot instances"""
        pass

    @clusters_group.command(name="status")
    async def clusters_status(self, ctx):
        """\ud83d\udd27 [Developer only] View bot's all cluster statuses"""
        embed = discord.Embed(title="Clusters information", color=discord.Color.random())

        for cluster in self.bot.cluster_data:
            fmt = ""

            for id, ping in cluster.latencies:
                ping = ping * 1000
                fmt += (
                    f"> **#{id} - {'%.0f' % ping}ms** "
                    f"IPC: {'%.0f' % self.bot.ipc_ping}ms\n"
                )

            uptime = time_util.seconds_to_time(cluster.uptime.total_seconds())
            fmt += f"\n**Uptime: {uptime} **"

            embed.add_field(
                name=f"**{cluster.name} ({cluster.guild_count} guilds)**",
                value=fmt
            )

        await ctx.reply(embed=embed)

    @clusters_group.command()
    async def logout(self, ctx, run_locally: bool = False):
        """
        \ud83d\udd27 [Developer only] Logout instance or all clusters

        __Optional arguments__:
        `run_locally` - Shut down only this cluster.
        """
        if run_locally:
            self.bot.loop.create_task(self.bot.close())
        else:
            await self._send_shutdown_message()

    @clusters_group.group(name="cogs", invoke_without_command=False)
    async def clusters_cogs_group(self, ctx):
        """\ud83d\udd27 [Developer only] Commands for managing the bot extensions"""
        pass

    @clusters_cogs_group.command()
    async def load(self, ctx, extension: str, run_locally: bool = False):
        """
        \ud83d\udd27 [Developer only] Loads an extension on this intsance or all clusters
        Defaults on all clusters.

        __Optional arguments__:
        `run_locally` - Load extension only only on this cluster.
        """
        if not extension.startswith("bot.cogs."):
            extension = "bot.cogs." + extension

        if run_locally:
            try:
                self.bot.load_extension(extension)
                await ctx.reply(f"{self.bot.check_emoji} {extension}")
            except Exception as e:
                self.bot.log.exception(f"Failed to load: {extension}")
                await ctx.reply(f"{e.__class__.__name__}: {e}")
            finally:
                return

        async with self.response_lock:
            self.responses = {}

            await self._send_load_message(extension)
            await self._wait_and_publish_responses(ctx)

    @clusters_cogs_group.command()
    async def unload(self, ctx, extension: str, run_locally: bool = False):
        """
        \ud83d\udd27 [Developer only] Unloads an extension on this instance or all clusters
        Defaults on all clusters.

        __Optional arguments__:
        `run_locally` - Unload extension only only on this cluster.
        """
        if not extension.startswith("bot.cogs."):
            extension = "bot.cogs." + extension

        if run_locally:
            try:
                self.bot.unload_extension(extension)
                await ctx.reply(f"{self.bot.check_emoji} {extension}")
            except Exception as e:
                self.bot.log.exception(f"Failed to unload: {extension}")
                await ctx.reply(f"{e.__class__.__name__}: {e}")
            finally:
                return
        async with self.response_lock:
            self.responses = {}

            await self._send_unload_message(extension)
            await self._wait_and_publish_responses(ctx)

    @clusters_cogs_group.command()
    async def reload(self, ctx, extension: str, run_locally: bool = False):
        """
        \ud83d\udd27 [Developer only] Reloads an extension on this instance or all clusters
        Defaults on all clusters.

        __Optional arguments__:
        `run_locally` - Reload extension only only on this cluster.
        """
        if not extension.startswith("bot.cogs."):
            extension = "bot.cogs." + extension

        if run_locally:
            try:
                self.bot.reload_extension(extension)
                await ctx.reply(f"{self.bot.check_emoji} {extension}")
            except Exception as e:
                self.bot.log.exception(f"Failed to reload: {extension}")
                await ctx.reply(f"{e.__class__.__name__}: {e}")
            finally:
                return
        async with self.response_lock:
            self.responses = {}

            await self._send_reload_message(extension)
            await self._wait_and_publish_responses(ctx)

    @clusters_group.group(name="gamemaster", invoke_without_command=False)
    async def clusters_gamemaster_group(self, ctx):
        """\ud83d\udd27 [Developer only] Commands for managing the game"""
        pass

    @clusters_gamemaster_group.command()
    async def reloaditems(self, ctx):
        """\ud83d\udd27 [Developer only] Reloads game item data on all clusters"""
        await self._send_set_items_message()

        await ctx.reply("\u2705 Sent reload items request to IPC")

    @clusters_gamemaster_group.command()
    async def editnews(self, ctx, *, news: str):
        """\ud83d\udd27 [Developer only] Edits game news"""
        await self._send_set_game_news_message(news)
        await ctx.defer()
        await asyncio.sleep(2)
        await ctx.reply(self.bot.game_news)

    @clusters_gamemaster_group.command()
    async def maintenance(self, ctx, enabled: bool):
        """\ud83d\udd27 [Developer only] Edits game maintenance status"""
        async with self.response_lock:
            self.responses = {}

            await self._send_set_maintenance_message(enabled)
            await self._wait_and_publish_responses(ctx)

    @clusters_gamemaster_group.command()
    async def enableguard(self, ctx, seconds: int):
        """\ud83d\udd27 [Developer only] Enables farm guard"""
        async with self.response_lock:
            self.responses = {}

            await self._send_set_field_guard_message(seconds)
            await self._wait_and_publish_responses(ctx)

    @clusters_group.command()
    async def evall(self, ctx, *, body: str):
        """\ud83d\udd27 [Developer only] Runs code on all clusters"""
        async with self.response_lock:
            self.responses = {}

            await self._send_eval_message(body)
            await self._wait_and_publish_responses(ctx)


def setup(bot) -> None:
    bot.add_cog(Clusters(bot))

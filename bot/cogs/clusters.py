import asyncio
import discord
import jsonpickle
import datetime
from contextlib import suppress
from discord.ext import commands

from core.ipc_classes import Cluster, IPCMessage


class Clusters(commands.Cog):

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        self.redis_pubsub = bot.redis.pubsub()

        redis_config = bot.config['redis']
        self.global_channel = redis_config['global-channel-name']
        cluster_channel_prefix = redis_config['cluster-channel-prefix']
        self.self_name = cluster_channel_prefix + bot.cluster_name

        self.bot.loop.run_until_complete(self._register_tasks())
        self.bot.loop.run_until_complete(self._request_all_required_data())
        self.bot.loop.run_until_complete(self._ensure_all_required_data())

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self._unregister_tasks)

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.subscribe(self.self_name)

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.unsubscribe(self.self_name)

    async def _register_tasks(self) -> None:
        await self._register_redis_channels()

        self._handler_task = self.bot.loop.create_task(
            self._redis_event_handler()
        )

    async def _unregister_tasks(self) -> None:
        self._handler_task.cancel()

        await self._unregister_redis_channels()

    def _resolve_reply_channel(self, message: IPCMessage) -> str:
        if message.reply_global:
            return self.global_channel
        else:
            return self.self_name

    async def _redis_event_handler(self) -> None:
        async for message in self.redis_pubsub.listen():
            if message['type'] != 'message':
                continue

            try:
                ipc_message = jsonpickle.decode(message['data'])
            except TypeError:
                continue

            if ipc_message.author == self.self_name:
                continue

            self.bot.log.info(
                f"Received message from: {ipc_message.author} "
                f"Action: {ipc_message.action} "
                f"Global: {ipc_message.reply_global}"
            )

            reply_channel = self._resolve_reply_channel(ipc_message)

            if ipc_message.action == "ping":
                self._handle_update_cluster_data(ipc_message)
            elif ipc_message.action == "set_items":
                self._handle_update_items(ipc_message)
            elif ipc_message.action == "set_game_news":
                self._handle_update_game_news(ipc_message)
            elif ipc_message.action == "eval":
                pass
            elif ipc_message.action == "eval_result":
                pass
            elif ipc_message.action == "shutdown":
                await self._handle_shutdown()
            else:
                self.log.error(f"Unknown action: {ipc_message.action}")

    async def _request_all_required_data(self) -> None:
        if not hasattr(self.bot, 'item_pool'):
            await self._send_get_items_message()

        if not hasattr(self.bot, "cluster_data"):
            await self._send_ping_message()

        if not hasattr(self.bot, "game_news"):
            await self._send_get_game_news_message()

    async def _ensure_all_required_data(self) -> None:
        retry_in = 0

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
                retry_in += 10

                await self._request_all_required_data()

    async def _cluster_ping_task(self) -> None:
        pass

    def _handle_update_items(self, message: IPCMessage) -> None:
        item_pool = jsonpickle.decode(message.data)

        self.bot.item_pool = item_pool

    def _handle_update_cluster_data(self, message: IPCMessage) -> None:
        cluster_data = jsonpickle.decode(message.data)

        self.bot.cluster_data = cluster_data

    def _handle_update_game_news(self, message: IPCMessage) -> None:
        self.bot.game_news = message.data

    async def _handle_shutdown(self) -> None:
        await self.bot.close()

    async def _send_ping_message(self) -> None:
        cluster = Cluster(
            self.bot.cluster_name,
            self.bot.latencies,
            len(self.bot.guilds),
            datetime.datetime.now()
        )

        message = IPCMessage(
            author=self.self_name,
            action="ping",
            reply_global=False,
            data=jsonpickle.encode(cluster)
        )

        await self.bot.redis.publish(
            self.self_name, jsonpickle.encode(message)
        )

    async def _send_get_items_message(
        self, reply_global: bool = False
    ) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="get_items",
            reply_global=reply_global,
            data=None
        )

        await self.bot.redis.publish(
            self.self_name, jsonpickle.encode(message)
        )

    async def _send_get_game_news_message(
        self, reply_global: bool = False
    ) -> None:
        message = IPCMessage(
            author=self.self_name,
            action="get_game_news",
            reply_global=reply_global,
            data=None
        )

        await self.bot.redis.publish(
            self.self_name, jsonpickle.encode(message)
        )

    @commands.is_owner()
    @commands.command(hidden=True)
    async def logout(self, ctx, run_global: str = None) -> None:
        """
        Logout instance or all clusters

        Optional arguments:
        `run_global` - "on" - Shut down all clusters.
        """
        if run_global == "on":
            pass
            # TODO: run global

        await self.bot.close()

    @commands.is_owner()
    @commands.command(hidden=True)
    async def load(self, ctx, extension: str, run_local: str = None) -> None:
        """
        Loads an extension on this insance or all clusters.
        Defaults on all clusters.

        Parameters:
        `run_local` - "on" - Load extension only locally.
        """
        if run_local == "on":
            try:
                self.bot.load_extension(extension)

                with suppress(discord.HTTPException):
                    await ctx.message.add_reaction("\u2705")
            except Exception as e:
                self.bot.log.exception(f"Failed to load: {extension}")

                await ctx.send(f"{e.__class__.__name__}: {e}")
            finally:
                return

        # TODO: run global

    @commands.is_owner()
    @commands.command(hidden=True)
    async def unload(self, ctx, extension: str, run_local: str = None) -> None:
        """
        Unloads an extension on this insance or all clusters.
        Defaults on all clusters.

        Parameters:
        `run_local` - "on" - Unload extension only locally.
        """
        if run_local == "on":
            try:
                self.bot.unload_extension(extension)

                with suppress(discord.HTTPException):
                    await ctx.message.add_reaction("\u2705")
            except Exception as e:
                self.bot.log.exception(f"Failed to unload: {extension}")

                await ctx.send(f"{e.__class__.__name__}: {e}")
            finally:
                return

        # TODO: run global

    @commands.is_owner()
    @commands.command(hidden=True)
    async def reload(self, ctx, extension: str, run_local: str = None) -> None:
        """
        Reloads an extension on this insance or all clusters.
        Defaults on all clusters.

        Parameters:
        `run_local` - "on" - Reload extension only locally.
        """
        if run_local == "on":
            try:
                self.bot.reload_extension(extension)

                with suppress(discord.HTTPException):
                    await ctx.message.add_reaction("\u2705")
            except Exception as e:
                self.bot.log.exception(f"Failed to reload: {extension}")

                await ctx.send(f"{e.__class__.__name__}: {e}")
            finally:
                return

        # TODO: run global

    @commands.is_owner()
    @commands.command(hidden=True)
    async def reloaditems(self, ctx) -> None:
        """Reloads game item data on all clusters."""
        pass

    @commands.is_owner()
    @commands.command(hidden=True)
    async def editnews(self, ctx) -> None:
        """Edits game news"""
        pass

    @commands.is_owner()
    @commands.command(hidden=True)
    async def maintenance(self, ctx) -> None:
        """Edits game maintenance status"""
        pass

    @commands.is_owner()
    @commands.command(hidden=True)
    async def enableguard(self, ctx) -> None:
        """Enables farm guard"""
        pass

    @commands.is_owner()
    @commands.command(hidden=True)
    async def evall(self, ctx) -> None:
        """Runs code on all clusters"""
        pass


def setup(bot):
    bot.add_cog(Clusters(bot))

import discord
import asyncio
import logging
import traceback
import websockets
import aioredis
import io
import json
import textwrap
from aiohttp import ClientSession
from collections import Counter
from contextlib import redirect_stdout
from asyncpg import create_pool
from discord.ext import commands
from datetime import datetime, timedelta, timezone

import botsettings
import classes.item as utilitems
from utils import checks
from utils.time import secstotime

TEMP_BAN_DURATION = 604800 # 7 days


class BotClient(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.pipe = kwargs.pop('pipe')
        self.cluster_name = kwargs.pop('cluster_name')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        super().__init__(
            chunk_guilds_at_startup=False,
            guild_subscriptions=False,
            max_messages=5000,
            command_prefix=commands.when_mentioned_or('%'), 
            **kwargs, loop=loop
        )
        self.websocket = None
        self._last_result = None
        self.ws_task = None
        self.responses = asyncio.Queue()
        self.eval_wait = False
        log = logging.getLogger(f"Cluster#{self.cluster_name}")
        log.setLevel(logging.DEBUG)
        log.handlers = [logging.FileHandler(f'cluster-{self.cluster_name}.log', encoding='utf-8', mode='a')]

        log.info(f'[Cluster#{self.cluster_name}] {kwargs["shard_ids"]}, {kwargs["shard_count"]}')
        self.log = log
        self.loop.create_task(self.ensure_ipc())
        
        self.allitems = {}
        
        self.config = botsettings
        self.owner_ids = botsettings.owner_ids
        self.maintenance_mode = botsettings.maintenance_mode
        
        self.initemojis()
        self.loaditems()
        self.load_news()
        self.loop.create_task(self._connectdb())

        self.global_cooldown = commands.CooldownMapping.from_cooldown(3, 8.0, commands.BucketType.user)
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 12.0, commands.BucketType.user)
        self._auto_spam_count = Counter()
        self.add_check(self.check_global_cooldown, call_once=True)

        for ext in self.config.initial_extensions:
            try:
                self.load_extension(ext)
            except Exception as e:
                log.error(f'Failed to load extension {ext}.')
                log.error(traceback.format_exc())

        self.run()

    async def _connectdb(self):
        self.db = await create_pool(
            **self.config.database_credentials, min_size=10, max_size=20, command_timeout=60.0
        )
        try:
            self.redis = await aioredis.create_pool(
                "redis://localhost", minsize=10, maxsize=20
            )
        except aioredis.RedisError as e:
            self.log.error(traceback.format_exc())

    def loaditems(self):
        self.cropseeds = utilitems.cropseedloader()
        self.crops = utilitems.croploader()
        self.crafteditems = utilitems.crafteditemloader()
        self.animalproducts = utilitems.animalproductloader()
        self.animals = utilitems.animalloader()
        self.trees = utilitems.treeloader()
        self.treeproducts = utilitems.treeproductloader()
        self.specialitems = utilitems.specialitemloader()

        self.allitems.update(self.cropseeds)
        self.allitems.update(self.crops)
        self.allitems.update(self.trees)
        self.allitems.update(self.treeproducts)
        self.allitems.update(self.animals)
        self.allitems.update(self.animalproducts)
        self.allitems.update(self.specialitems)
        self.allitems.update(self.crafteditems)

        utilitems.update_item_relations(self)
        utilitems.update_market_prices(self)

    def initemojis(self):
        self.gold = self.config.gold_emoji
        self.xp = self.config.xp_emoji
        self.gem = self.config.gem_emoji
        self.tile = self.config.tile_emoji

    def load_news(self):
        with open('files/news.txt', "r", encoding='utf-8') as f:
            self.news = f.read()

    @property
    def uptime(self):
        return datetime.now() - self.launchtime

    @property
    def field_guard(self):
        if not hasattr(self, 'guard_mode'): return False
        
        return self.guard_mode > datetime.now()

    def enable_field_guard(self, seconds):
        self.guard_mode = datetime.now() + timedelta(seconds=seconds)

        return self.guard_mode

    async def send_log(self, content, embed=None):
        """Sends message to support server's log channel."""
        async with ClientSession() as session:
            webhook = discord.Webhook.from_url(
                self.config.bot_log_webhook,
                adapter=discord.AsyncWebhookAdapter(session)
            )
            await webhook.send(
                f"**[{self.cluster_name}]** " + content,
                embed=embed,
                username=self.user.name
            )

    async def on_ready(self):
        self.log.info(f'[Cluster#{self.cluster_name}] Ready called.')
        if self.pipe:
            self.pipe.send(1)
            #self.pipe.close()

        if not hasattr(self, 'launchtime'):
            self.launchtime = datetime.now()

        await self.send_log(
            f'\ud83d\udfe2 Ready! Maintenance mode: `{self.maintenance_mode}` '
            f'DB: `{self.db != None}` Redis: `{self.redis != None}` '
            f'Shards: `{self.shard_ids}` Total guilds: `{len(self.guilds)}`'
        )

    async def on_shard_ready(self, shard_id):
        self.log.info(f'[Cluster#{self.cluster_name}] Shard {shard_id} ready')

    async def log_spammer(self, message, banned=False):
        if not banned:
            await self.send_log(
                f"\ud83d\udfe7 {message.author} (`{message.author.id}`) Mass spam: {message.clean_content[:200]}"
            )
        else:
            await self.send_log(
                f"\ud83d\udfe5 {message.author} (`{message.author.id}`) Mass spam ban: {message.clean_content[:200]}"
            )

    async def check_global_cooldown(self, ctx):
        current = ctx.message.created_at.replace(tzinfo=timezone.utc).timestamp()
        bucket = self.global_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit(current)
        
        if retry_after and ctx.author.id not in self.owner_ids:
            raise checks.GlobalCooldown(ctx, retry_after)
        
        return True

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=commands.Context)

        if ctx.command is None:
            return

        author_id = message.author.id

        # Check if user is banned
        banned = await ctx.bot.redis.execute("GET", f"ban:{author_id}")
        if banned:
            return

        # Check mass commands spam
        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()
        bucket = self.spam_control.get_bucket(message)
        retry_after = bucket.update_rate_limit(current)
        if retry_after and author_id not in self.owner_ids:
            self._auto_spam_count[author_id] += 1
            if self._auto_spam_count[author_id] >= 3:
                await ctx.bot.redis.execute("SET", f"ban:{author_id}", 1, "EX", TEMP_BAN_DURATION)
                del self._auto_spam_count[author_id]
                await self.log_spammer(message, banned=True)
            else:
                await self.log_spammer(message)
            return
        else:
            self._auto_spam_count.pop(author_id, None)
        
        if not message.guild:
            return await message.author.send("\u274c Sorry, this bot only accepts commands in servers...")

        if not message.channel.permissions_for(message.guild.me).send_messages:
            return

        await self.invoke(ctx)

    async def on_message(self, message):
        author = message.author
        if author == self.user or author.bot:
            return

        try:
            await self.process_commands(message)
        except Exception as e:
            self.log.critical(f'Error occured while executing commands: {e}')
            self.log.critical(traceback.format_exc())

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            return
        elif isinstance(error, commands.errors.CheckFailure):
            if isinstance(error, checks.GameIsInMaintenance):
                return await ctx.send("\u26a0\ufe0f Game's commands are disabled for bot's maintenance "
                    "or update.\n"
                    "\ud83d\udd50 Please try again after a while... :)\n"
                    "\ud83d\udcf0 For more information use command - `%news`.")
            elif isinstance(error, checks.MissingEmbedPermissions):
                return await ctx.send("\u274c Please enable **Embed Links** permission for "
                "me in this channel's settings, to use this command!")
            elif isinstance(error, checks.MissingAddReactionPermissions):
                return await ctx.send("\u274c Please enable **Add Reactions** permission for "
                "me in this channel's settings, to use this command!")
            elif isinstance(error, checks.MissingReadMessageHistoryPermissions):
                return await ctx.send("\u274c Please enable **Read Message History** permission for "
                "me in this channel's settings, to use this command!")
        elif isinstance(error, checks.GlobalCooldown):
            return await ctx.send(
                f"\u23f2\ufe0f You are typing commands way too fast! Slow down for: **{secstotime(error.retry_after)}**"
            )
        elif isinstance(error, commands.errors.CommandOnCooldown):
            return await ctx.send(f"\u23f0 This command is on cooldown for:  **{secstotime(error.retry_after)}**")
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            return await ctx.send("\u274c This command requires additional parameters.")
        elif isinstance(error, commands.errors.BadArgument):
            return await ctx.send("\u274c Invalid command parameters provided.")
        elif isinstance(error, commands.NoPrivateMessage):
            return await ctx.author.send("\u274c This command is disabled for Direct Messages.")
        elif isinstance(error, commands.DisabledCommand):
            return await ctx.author.send("\u274c This command currently has been disabled and it cannot be used.")
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                self.log.critical(f'In {ctx.command.qualified_name}:')
                self.log.critical(str(original))
                self.log.critical(traceback.format_tb(original.__traceback__))
        elif isinstance(error, commands.ArgumentParsingError):
            return await ctx.send(error)
        else:
            self.log.critical(''.join(traceback.format_exception(type(error), error, error.__traceback__)))

    def on_error(self, event_method, *args, **kwargs):
        self.log.critical(traceback.format_exc())

    async def on_guild_join(self, guild):
        message = ("Hello! \ud83d\udc4b\nThanks for adding me here! Access the command list with: `%help`.\n"
        "Happy farming! \ud83d\udc68\u200d\ud83c\udf3e")

        channels = list(
            filter(
                lambda x: x.permissions_for(guild.me).send_messages, guild.text_channels
            )
        )
        if channels:
            await channels[0].send(message)

        await self.send_log(
            f'\ud83d\udce5 Joined guild: {guild.name} (`{guild.id}`) Large:`{guild.large}` '
            f'Total guilds: `{len(self.guilds)}`'
        )

    async def on_guild_remove(self, guild):
        async with self.db.acquire() as connection:
            async with connection.transaction():
                query = """DELETE FROM store WHERE guildid = $1;"""
                await self.db.execute(query, guild.id)

        await self.send_log(
            f'\ud83d\udce4 Left guild: {guild.name} (`{guild.id}`) Large:`{guild.large}`'
            f'Total guilds: `{len(self.guilds)}`'
        )

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def close(self, *args, **kwargs):
        self.log.info(f"Shutting down...")
        await self.websocket.close()
        await super().close()

    async def exec_eval(self, code):
        env = {
            'client': self,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(code)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return f'{e.__class__.__name__}: {e}'

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            f'{value}{traceback.format_exc()}'
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    return str(value)
                else:
                    return 'None'
            else:
                self._last_result = ret
                return f'{value}{ret}'

    async def websocket_loop(self):
        while True:
            try:
                msg = await self.websocket.recv()
            except websockets.ConnectionClosed as exc:
                if exc.code == 1000:
                    return
                raise
            data = json.loads(msg, encoding='utf-8')
            if self.eval_wait and data.get('response'):
                await self.responses.put(data)
            cmd = data.get('command')
            if not cmd:
                continue
            if cmd == 'ping':
                ret = {'response': 'pong'}
                self.log.info("received command [ping]")
            elif cmd == 'eval':
                self.log.info(f"received command [eval] ({data['content']})")
                content = data['content']
                data = await self.exec_eval(content)
                ret = {'response': str(data)}
            elif cmd == 'maintenance':
                content = data['content']
                self.log.info(f"received command [maintenance] ({content})")
                if content.lower() == 'on':
                    self.maintenance_mode = True
                    ret = {'response': '\u2705'}
                elif content.lower() == 'off':
                    self.maintenance_mode = False
                    ret = {'response': '\u2705'}

                await self.send_log(f"\u2699\ufe0f Maintenance mode: `{self.maintenance_mode}`")
            elif cmd == 'guard':
                self.log.info(f"received command [guard] ({data['content']})")
                data = self.enable_field_guard(int(data['content']))
                ret = {'response': str(data)}

                await self.send_log(f"\ud83d\udee1\ufe0f Guard mode enabled: `{data}`")
            elif cmd == 'reloaditems':
                self.log.info(f"received command [reloaditems]")
                self.loaditems()
                ret = {'response': '\u2705'}

                await self.send_log(f"\ud83d\udd04 Items reloaded")
            elif cmd == 'reload':
                self.log.info(f"received command [reload] ({data['content']})")
                try:
                    self.reload_extension(data['content'])
                    ret = {'response': "\u2705"}
                except Exception as e:
                    ret = {'response': e.__class__.__name__}
            elif cmd == 'unload':
                self.log.info(f"received command [unload] ({data['content']})")
                try:
                    self.unload_extension(data['content'])
                    ret = {'response': "\u2705"}
                except Exception as e:
                    ret = {'response': e.__class__.__name__}
            elif cmd == 'load':
                self.log.info(f"received command [load] ({data['content']})")
                try:
                    self.load_extension(data['content'])
                    ret = {'response': "\u2705"}
                except Exception as e:
                    ret = {'response': e.__class__.__name__}
            elif cmd == 'logout':
                self.log.info(f"received command [logout]")
                await self.close()
            elif cmd == 'readnews':
                self.load_news()
                ret = {'response': "\u2705"}
            else:
                ret = {'response': 'unknown command'}
            ret['author'] = self.cluster_name
            self.log.info(f"responding: {ret}")
            try:
                await self.websocket.send(json.dumps(ret).encode('utf-8'))
            except websockets.ConnectionClosed as exc:
                if exc.code == 1000:
                    return
                raise

    async def ensure_ipc(self):
        self.websocket = w = await websockets.connect('ws://localhost:42069')
        await w.send(self.cluster_name.encode('utf-8'))
        try:
            await w.recv()
            self.ws_task = self.loop.create_task(self.websocket_loop())
            self.log.info("ws connection succeeded")
        except websockets.ConnectionClosed as exc:
            self.log.warning(f"! couldnt connect to ws: {exc.code} {exc.reason}")
            self.websocket = None
            raise

    def run(self):
        super().run(self.config.bot_auth_token, reconnect=True)

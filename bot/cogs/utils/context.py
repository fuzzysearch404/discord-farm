from discord.ext import commands


class _DBContextAcquire:

    __slots__ = ('ctx', 'timeout')

    def __init__(self, ctx, timeout):
        self.ctx = ctx
        self.timeout = timeout

    def __await__(self):
        return self.ctx._acquire(self.timeout).__await__()

    async def __aenter__(self):
        await self.ctx._acquire(self.timeout)

        return self.ctx.db

    async def __aexit__(self, *args):
        await self.ctx.release()


class Context(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool = self.bot.db_pool
        self.redis = self.bot.redis
        self.users = self.bot.user_cache
        self._db = None

    @property
    def db(self):
        return self._db if self._db else self.pool

    async def _acquire(self, timeout):
        if self._db is None:
            self._db = await self.pool.acquire(timeout=timeout)

        return self._db

    def acquire(self, *, timeout=300):
        return _DBContextAcquire(self, timeout)

    async def release(self):
        if self._db is not None:
            await self.bot.pool.release(self._db)
            self._db = None

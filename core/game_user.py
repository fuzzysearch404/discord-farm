import asyncpg
import datetime
import jsonpickle

from bot.commands.util import exceptions
from core.game_items import GameItem


class UserNotifications:
    FARM_HARVEST_READY: int = 1 << 0
    FARM_ROBBED: int = 1 << 1
    TRADE_ACCEPTED: int = 1 << 2

    __slots__ = ("value", )

    def __init__(self, value: int):
        self.value = value

    @classmethod
    def all_enabled(cls):
        return cls(0b111)

    def is_enabled(self, notification: int) -> bool:
        """Checks if notifications integer bit is set to one"""
        return self.value & notification == notification


class User:

    __slots__ = (
        "user_id",
        "xp",
        "gold",
        "gems",
        "farm_slots",
        "factory_slots",
        "factory_level",
        "store_slots",
        "notifications",
        "registration_date",
        "level",
        "next_level_xp"
    )

    def __init__(
        self,
        user_id: int,
        xp: int,
        gold: int,
        gems: int,
        farm_slots: int,
        factory_slots: int,
        factory_level: int,
        store_slots: int,
        notifications: int,
        registration_date: datetime.date
    ) -> None:
        self.user_id = user_id
        self.xp = xp
        self.gold = gold
        self.gems = gems
        self.farm_slots = farm_slots
        self.factory_slots = factory_slots
        self.factory_level = factory_level
        self.store_slots = store_slots
        self.notifications = UserNotifications(notifications)
        self.registration_date = registration_date
        self.level, self.next_level_xp = self._calculate_user_level()

    def _calculate_user_level(self) -> tuple:
        """Calculates current player level and xp to the next level."""
        if self.xp < 11_500_000:
            # Levels 1 - 15
            if self.xp < 200000:
                limits = (
                    0, 20, 250, 750, 2000, 4500, 8000, 15000, 24000, 34000,
                    49000, 69420, 100000, 140000, 200000
                )
                level = 0
            # Levels 15 - 30
            else:
                limits = (
                    280000, 380000, 500000, 650000, 900000,
                    1_200_000, 1_600_000, 2_100_000, 2_850_000, 3_850_000,
                    5_000_000, 6_500_000, 8_000_000, 9_500_000, 11_500_000
                )
                level = 15

            for points in limits:
                if self.xp >= points:
                    level += 1
                else:
                    return level, points

        # User has reached high levels with a constant XP growth,
        # that is 2.5 million XP per level.
        remaining = self.xp - 11_500_000
        lev = int(remaining / 2_500_000)
        return 30 + lev, 11_500_000 + ((lev + 1) * 2_500_000)

    def give_xp_and_level_up(self, cmd, xp: int) -> None:
        old_level = self.level
        self.xp += xp
        self.level, self.next_level_xp = self._calculate_user_level()

        if old_level == self.level:
            return

        # If we somehow level up multiple levels at a time, give all gems
        self.gems += self.level - old_level
        # This is going to inject level up embed in the next response
        cmd._level_up = True

    async def get_all_boosts(self, cmd) -> list:
        boosts = await cmd.redis.execute_command("GET", f"user_boosts:{self.user_id}")

        if not boosts:
            return []

        boosts = jsonpickle.decode(boosts)
        # Removes expired boosts
        return [b for b in boosts if b.duration > datetime.datetime.now()]

    async def is_boost_active(self, cmd, boost_id: str) -> bool:
        all_boosts = await self.get_all_boosts(cmd)
        return boost_id in [b.id for b in all_boosts]

    async def give_boost(self, cmd, partial_boost) -> list:
        existing_boosts = await self.get_all_boosts(cmd)

        try:
            # Extend duration if already currently active
            existing = next(x for x in existing_boosts if x.id == partial_boost.id)
            existing.duration += (partial_boost.duration - datetime.datetime.now())
        except StopIteration:
            existing_boosts.append(partial_boost)

        # Find the new longest boost
        longest = max(existing_boosts, key=lambda b: b.duration)
        seconds_until = (longest.duration - datetime.datetime.now()).total_seconds()

        await cmd.redis.execute_command(
            "SET", f"user_boosts:{self.user_id}",
            jsonpickle.encode(existing_boosts),
            "EX", round(seconds_until)
        )

        return existing_boosts

    async def get_all_items(self, conn) -> list:
        """Fetches all items currently in inventory"""
        query = "SELECT * FROM inventory WHERE user_id = $1 ORDER BY item_id;"
        return await conn.fetch(query, self.user_id)

    async def get_item(self, item_id: int, conn) -> asyncpg.Record:
        """Fetches a single item currently in inventory"""
        query = "SELECT * FROM inventory WHERE user_id = $1 AND item_id = $2;"
        return await conn.fetchrow(query, self.user_id, item_id)

    async def give_item(self, item_id: int, amount: int, conn) -> None:
        """Adds a single type of items to inventory"""
        query = """
                INSERT INTO inventory(user_id, item_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, item_id)
                DO UPDATE
                SET amount = inventory.amount + $3;
                """
        await conn.execute(query, self.user_id, item_id, amount)

    async def give_items(self, items_and_amounts: list, conn) -> None:
        """Adds items to user. Accepts a list of tuples with items IDs and amounts"""
        items_with_user_id = []
        for item, amount in items_and_amounts:
            if isinstance(item, GameItem):
                item = item.id
            items_with_user_id.append((self.user_id, item, amount))

        query = """
                INSERT INTO inventory(user_id, item_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, item_id)
                DO UPDATE
                SET amount = inventory.amount + $3;
                """
        await conn.executemany(query, items_with_user_id)

    async def remove_item(self, item_id: int, amount: int, conn) -> None:
        """Removes a single type of items from inventory"""
        # See schema.sql for the procedure
        query = "CALL remove_item($1, $2, $3);"
        await conn.execute(query, self.user_id, item_id, amount)

    async def remove_items(self, items_and_amounts: list, conn) -> None:
        """Removes multiple type of items from inventory"""
        items_with_user_id = []
        for item, amount in items_and_amounts:
            if isinstance(item, GameItem):
                item = item.id
            items_with_user_id.append((self.user_id, item, amount))

        # See schema.sql for the procedure
        query = "CALL remove_item($1, $2, $3);"
        await conn.executemany(query, items_with_user_id)

    async def get_item_modification(self, item_id: int, conn) -> asyncpg.Record:
        """Fetches item modifications data for a single item"""
        query = "SELECT * FROM modifications WHERE user_id = $1 AND item_id = $2;"
        return await conn.fetchrow(query, self.user_id, item_id)

    async def get_farm_field(self, conn) -> list:
        """Fetches all items currently in farm"""
        query = "SELECT * FROM farm WHERE user_id = $1 ORDER BY item_id;"
        return await conn.fetch(query, self.user_id)

    async def get_factory(self, conn) -> list:
        """Fetches all items currently in factory"""
        query = "SELECT * from factory WHERE user_id = $1 ORDER by starts;"
        return await conn.fetch(query, self.user_id)


class UserManager:

    __slots__ = ("redis", "db_pool")

    def __init__(self, redis, db_pool) -> None:
        self.redis = redis
        self.db_pool = db_pool

    async def get_user(self, user_id: int, conn=None) -> User:
        user_data = await self.redis.execute_command("GET", f"user_profile:{user_id}")

        if user_data:
            return jsonpickle.decode(user_data)

        if not conn:
            release_required = True
            conn = await self.db_pool.acquire()
        else:
            release_required = False

        query = "SELECT * FROM profile WHERE user_id = $1;"
        user_data = await conn.fetchrow(query, user_id)

        if release_required:
            await self.db_pool.release(conn)

        if not user_data:
            raise exceptions.UserNotFoundException("You don't have a game account")

        user = User(
            user_id=user_data['user_id'],
            xp=user_data['xp'],
            gold=user_data['gold'],
            gems=user_data['gems'],
            farm_slots=user_data['farm_slots'],
            factory_slots=user_data['factory_slots'],
            factory_level=user_data['factory_level'],
            store_slots=user_data['store_slots'],
            notifications=user_data['notifications'],
            registration_date=user_data['registration_date']
        )

        # Keep in Redis for 10 minutes, then refetch
        await self.redis.execute_command(
            "SET", f"user_profile:{user_id}",
            jsonpickle.encode(user),
            "EX", 600
        )

        return user

    async def create_user(self, user_id: int, conn=None) -> User:
        if not conn:
            release_required = True
            conn = await self.db_pool.acquire()
        else:
            release_required = False

        query = "INSERT INTO profile (user_id, notifications) VALUES ($1, $2);"
        await conn.execute(query, user_id, UserNotifications.all_enabled().value)

        if release_required:
            await self.db_pool.release(conn)

        return await self.get_user(user_id)

    async def update_user(self, user: User, conn=None) -> None:
        if not conn:
            release_required = True
            conn = await self.db_pool.acquire()
        else:
            release_required = False

        query = """
                UPDATE profile SET
                xp = $1,
                gold = $2,
                gems = $3,
                farm_slots = $4,
                factory_slots = $5,
                factory_level = $6,
                store_slots = $7,
                notifications = $8
                WHERE user_id = $9
                """
        await conn.execute(
            query,
            user.xp,
            user.gold,
            user.gems,
            user.farm_slots,
            user.factory_slots,
            user.factory_level,
            user.store_slots,
            user.notifications.value,
            user.user_id
        )

        if release_required:
            await self.db_pool.release(conn)

        await self.redis.execute_command(
            "SET", f"user_profile:{user.user_id}",
            jsonpickle.encode(user),
            "EX", 600
        )

    async def delete_user(self, user_id: int, conn=None) -> None:
        if not conn:
            release_required = True
            conn = await self.db_pool.acquire()
        else:
            release_required = False

        query = "DELETE FROM profile WHERE user_id = $1;"
        await conn.execute(query, user_id)

        if release_required:
            await self.db_pool.release(conn)

        await self.redis.execute_command("DEL", f"user_profile:{user_id}")
        # Delete boosts and export mission
        await self.redis.execute_command("DEL", f"user_boosts:{user_id}")
        await self.redis.execute_command("DEL", f"export:{user_id}")

import asyncpg
import jsonpickle
from datetime import datetime

from bot.commands.util import exceptions
from core.game_items import GameItem


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
        notifications: bool
    ) -> None:
        self.user_id = user_id
        self.xp = xp
        self.gold = gold
        self.gems = gems
        self.farm_slots = farm_slots
        self.factory_slots = factory_slots
        self.factory_level = factory_level
        self.store_slots = store_slots
        self.notifications = notifications
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
        cmd._level_up = True

    async def get_all_boosts(self, cmd) -> list:
        boosts = await cmd.redis.execute_command("GET", f"user_boosts:{self.user_id}")

        if not boosts:
            return []

        boosts = jsonpickle.decode(boosts)
        # Removes expired boosts
        return [x for x in boosts if x.duration > datetime.now()]

    async def is_boost_active(self, cmd, boost_id: str) -> bool:
        all_boosts = await self.get_all_boosts(cmd)
        return boost_id in [x.id for x in all_boosts]

    async def give_boost(self, cmd, boost) -> list:
        existing_boosts = await self.get_all_boosts(cmd)

        try:
            # Extend duration if already currently active
            existing = next(x for x in existing_boosts if x.id == boost.id)
            existing.duration += (boost.duration - datetime.now())
        except StopIteration:
            existing_boosts.append(boost)

        # Find the new longest boost
        longest = max(existing_boosts, key=lambda b: b.duration)
        seconds_until = (longest.duration - datetime.now()).total_seconds()

        await cmd.redis.execute_command(
            "SET", f"user_boosts:{self.user_id}",
            jsonpickle.encode(existing_boosts),
            "EX", round(seconds_until)
        )

        return existing_boosts

    async def get_all_items(self, cmd, conn=None) -> list:
        """Fetches all items currently in inventory"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT * FROM inventory
                WHERE user_id = $1
                ORDER BY item_id;
                """
        items = await conn.fetch(query, self.user_id)

        if release_required:
            await cmd.release()

        return items

    async def get_item(self, cmd, item_id: int, conn=None) -> asyncpg.Record:
        """Fetches a single item currently in inventory"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT * FROM inventory
                WHERE user_id = $1
                AND item_id = $2;
                """
        item = await conn.fetchrow(query, self.user_id, item_id)

        if release_required:
            await cmd.release()

        return item

    async def give_item(self, cmd, item_id: int, amount: int, conn=None) -> None:
        """Adds a single type of items to inventory"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                INSERT INTO inventory(user_id, item_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, item_id)
                DO UPDATE
                SET amount = inventory.amount + $3;
                """
        await conn.execute(query, self.user_id, item_id, amount)

        if release_required:
            await cmd.release()

    async def give_items(self, cmd, items: list, conn=None) -> None:
        """Adds items to user. Accepts a list of tuples with items IDs and amounts"""
        items_with_user_id = []
        for item, amount in items:
            if isinstance(item, GameItem):
                item = item.id

            items_with_user_id.append((self.user_id, item, amount))

        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                INSERT INTO inventory(user_id, item_id, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, item_id)
                DO UPDATE
                SET amount = inventory.amount + $3;
                """
        await conn.executemany(query, items_with_user_id)

        if release_required:
            await cmd.release()

    async def remove_item(self, cmd, item_id: int, amount: int, conn=None) -> None:
        """Removes a single type of items from inventory"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT id, amount FROM inventory
                WHERE user_id = $1
                AND item_id = $2;
                """
        current_data = await conn.fetchrow(query, self.user_id, item_id)

        if current_data:
            if current_data['amount'] - amount > 0:
                query = """
                        UPDATE inventory
                        SET amount = inventory.amount - $2
                        WHERE id = $1;
                        """
                await conn.execute(query, current_data['id'], amount)
            else:
                query = """
                        DELETE FROM inventory
                        WHERE id = $1;
                        """
                await conn.execute(query, current_data['id'])

        if release_required:
            await cmd.release()

    async def get_item_modification(self, cmd, item_id: int, conn=None) -> asyncpg.Record:
        """Fetches item modifications data for a single item"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT * FROM modifications
                WHERE user_id = $1
                AND item_id = $2;
                """
        data = await conn.fetchrow(query, self.user_id, item_id)

        if release_required:
            await cmd.release()

        return data

    async def get_farm_field(self, cmd, conn=None) -> list:
        """Fetches all items currently in farm"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT * FROM farm
                WHERE user_id = $1
                ORDER BY item_id;
                """
        data = await conn.fetch(query, self.user_id)

        if release_required:
            await cmd.release()

        return data

    async def get_factory(self, cmd, conn=None) -> list:
        """Fetches all items currently in factory"""
        if not conn:
            release_required = True
            conn = await cmd.acquire()
        else:
            release_required = False

        query = """
                SELECT * from factory
                WHERE user_id = $1
                ORDER by starts;
                """
        data = await conn.fetch(query, self.user_id)

        if release_required:
            await cmd.release()

        return data


class UserManager:

    __slots__ = ('redis', 'db_pool')

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
            notifications=user_data['notifications']
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

        query = "INSERT INTO profile (user_id) VALUES ($1);"
        await conn.execute(query, user_id)

        if release_required:
            await self.db_pool.release(conn)

        user = await self.get_user(user_id)
        return user

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
            user.notifications,
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

from core.exceptions import UserNotFoundException
import discord


class User:

    __slots__ = (
        'bot',
        'user_id',
        'xp',
        'gold',
        'gems',
        'farm_slots',
        'factory_slots',
        'factory_level',
        'store_slots',
        'notifications',
        'registration_date',
        'level',
        'next_level_xp'
    )

    def __init__(
        self,
        bot: discord.Client,
        user_id: int,
        xp: int,
        gold: int,
        gems: int,
        farm_slots: int,
        factory_slots: int,
        store_slots: int,
        notifications: bool,

    ) -> None:
        self.bot = bot
        self.user_id = user_id,
        self.xp = xp,
        self.gold = gold,
        self.gems = gems,
        self.farm_slots = farm_slots,
        self.factory_slots = factory_slots,
        self.store_slots = store_slots,
        notifications = notifications

        self.level, self.next_level_xp = self._calculate_user_level()

    @classmethod
    async def get_user_from_db_data(cls, bot: discord.Client, user_id: int):
        """Converts database object to User object."""
        query = "SELECT * FROM profile WHERE user_id = $1;"

        data = await bot.db.fetchrow(query, user_id)

        if not data:
            raise UserNotFoundException(f"User ID: {user_id} not found!")

        return cls(
            bot=bot,
            user_id=data['user_id'],
            xp=data['xp'],
            gold=data['gold'],
            gems=data['gems'],
            farm_slots=data['farm_slots'],
            factory_slots=data['factory_slots'],
            store_slots=data['store_slots'],
            notifications=data['notifications']
        )

    def _calculate_user_level(self) -> tuple:
        """Calculates current player level and xp to the next level."""
        limit = (
            0, 20, 250, 750, 2000, 4500, 8000, 16000, 24000, 34000,  # 1 - 10
            49000, 69420, 100000, 140000, 200000,  # 11 - 15
            280000, 380000, 500000, 650000, 900000,  # 16 - 20
            1_200_000, 1_600_000, 2_100_000, 2_850_000, 3_850_000,  # 21 - 25
            5_000_000, 6_500_000, 8_000_000, 9_500_000, 11_000_000  # 26 - 30
        )
        level = 0

        for points in limit:
            if self.xp >= points:
                level += 1
            else:
                return level, points

        # We reached high levels with constant XP growth
        remaining = self.xp - points
        lev, _ = divmod(remaining, 2_000_000)

        return level + lev, points + ((lev + 1) * 2_000_000)

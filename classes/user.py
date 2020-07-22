from datetime import datetime, timedelta
from utils.embeds import congratzembed


class User:
    __slots__ = ('client', 'userid', 'xp', 'money', 'gems', 'tiles',
    'factoryslots', 'factorylevel', 'storeslots', 'faction', 'notifications', 'level',
    'nextlevelxp')

    def __init__(
        self, client, userid, xp, money, gems, tiles,
        factoryslots, factorylevel, storeslots, faction, notifications
    ):
        self.client = client
        self.userid = userid
        self.xp = xp
        self.money = money
        self.gems = gems
        self.tiles = tiles
        self.factoryslots = factoryslots
        self.factorylevel = factorylevel
        self.storeslots = storeslots
        self.faction = faction
        self.notifications = notifications
        self.level, self.nextlevelxp = self.get_level()
    
    @classmethod
    def get_user(cls, data, client):
        """Converts database object to User object."""
        return cls(
            client, data['userid'], data['xp'], data['money'],
            data['gems'], data['tiles'], data['factoryslots'], data['factorylevel'],
            data['storeslots'], data['faction'], data['notifications']
        )

    def get_level(self):
        """Calculates current player level and xp to
        the next level."""
        limit = (
            0, 20, 250, 750, 2000, 4500, 8000, 16000, 24000, 34000, # 1 - 10
            49000, 69420, 100000, 140000, 200000, # 11 - 15
            280000, 380000, 500000, 650000, 900000, # 16 - 20
            1_200_000, 1_600_000, 2_100_000, 2_850_000, 3_850_000, # 21 - 25
            5_000_000, 6_500_000, 8_000_000, 9_500_000, 11_000_000, # 26 - 30
            13_000_000, 15_000_000, 17_000_000, 19_000_000, 21_000_000 # 31 - 35
        )
        level = 0

        for points in limit:
            if self.xp >= points:
                level += 1
            else:
                break

        return level, points

    def get_store_upgrade_cost(self):
        return self.storeslots * 5000

    async def get_inventory(self):
        """Fetches all inventory items from database. [{item:amount}...]"""
        query = """SELECT * FROM inventory WHERE userid = $1;"""
        inventory = await self.client.db.fetch(query, self.userid)

        found = {}
        for item in inventory:
            try:
                found[self.client.allitems[item['itemid']]] = item['amount']
            except KeyError:
                raise Exception(f"Could not find item {item['itemid']}")
        
        return found

    async def get_field(self):
        """Fetches all field data from database."""
        query = """SELECT * FROM planted WHERE userid = $1;"""
        data = await self.client.db.fetch(query, self.userid)
        
        return data

    async def get_used_field_count(self):
        """Fetches the count of used tiles on the field"""
        query = """SELECT SUM(fieldsused) FROM planted WHERE userid = $1;"""
        data = await self.client.db.fetchrow(query, self.userid)
        
        return data['sum'] or 0

    async def get_used_store_slot_count(self, guild):
        """Fetches the count of used store slots (trades)"""
        query = """SELECT count(id) FROM store WHERE userid = $1
        AND guildid = $2;"""
        slots = await self.client.db.fetchrow(query, self.userid, guild.id)
        if not slots: return 0
        
        return slots[0]

    async def get_factory(self):
        """Fetches factory data from database"""
        query = """SELECT * FROM factory WHERE userid = $1;"""
        data = await self.client.db.fetch(query, self.userid)
        
        return data

    async def check_used_factory_slots(self):
        """Fetches used factory slots count from database"""
        query = """SELECT count(id) FROM factory WHERE userid = $1;"""
        slots = await self.client.db.fetchrow(query, self.userid)

        if not slots:
            return 0
        else:
            return slots[0]

    async def get_oldest_factory_item(self):
        """Fetches firstly added factory item from database"""
        query = """SELECT * FROM factory WHERE userid = $1
        ORDER BY ends DESC LIMIT 1;"""
        data = await self.client.db.fetchrow(query, self.userid)
        
        return data

    async def get_boosts(self):
        """Fetches boost data from database"""
        query = """SELECT * FROM boosts WHERE userid = $1;"""
        data = await self.client.db.fetchrow(query, self.userid)
        
        return data

    async def get_missions(self):
        """Fetches mission data from database"""
        query = """SELECT * FROM missions WHERE userid = $1;"""
        missions = await self.client.db.fetch(query, self.userid)
        
        return missions

    async def get_user_store(self, guild):
        query = """SELECT * FROM store WHERE userid = $1
        AND guildid = $2;"""
        data = await self.client.db.fetch(query, self.userid, guild.id)
        
        return data

    async def get_guild_store(self, guild):
        query = """SELECT * FROM store WHERE guildid = $1
            ORDER BY userid;"""
        data = await self.client.db.fetch(query, guild.id)
        
        return data

    async def check_inventory_item(self, item):
        """Checks if user has item in inventory"""
        query = """SELECT * FROM inventory WHERE userid = $1
        AND itemid = $2;"""
        item = await self.client.db.fetchrow(query, self.userid, item.id)
        
        return item

    async def give_gems(self, gems):
        """Adds gems to user's balance"""
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET gems = gems + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, gems, self.userid)

        self.gems += gems


    async def give_money(self, money):
        """Adds money to user's balance."""
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET money = money + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, money, self.userid)

        self.money += money

    async def give_xp_and_level_up(self, xp, ctx):
        """Adds xp ands levels up the user."""
        oldlevel = self.level

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET xp = xp + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, xp, self.userid)
                self.xp += xp

        self.level, self.nextlevelxp = self.get_level()
        if oldlevel < self.level:
            await self.give_gems(1)
            unlocked = self.find_new_unlocked_items()
            lvlmsg = f"You reached level {self.level} and you got a {self.client.gem}!"
            if len(unlocked) > 0:
                itemstr = ""
                for item in unlocked:
                    if item.emoji not in itemstr: itemstr += item.emoji + " "
                lvlmsg += f"\n\ud83d\udd13You've unlocked new items: {itemstr}!"
            embed = congratzembed(lvlmsg, ctx)
            await ctx.send(embed=embed)

    def find_new_unlocked_items(self):
        return list(
            filter(
                lambda x: x.level == self.level, self.client.allitems.values()
            )
        )

    async def add_item_to_inventory(self, item, amount):
        olditem = await self.check_inventory_item(item)
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                if not olditem:
                    query = """INSERT INTO inventory(itemid, userid, amount)
                    VALUES($1, $2, $3);"""
                else:
                    query = """UPDATE inventory SET amount = $1
                    WHERE userid = $2 AND itemid = $3;"""

                if not olditem:
                    await self.client.db.execute(
                        query, item.id, self.userid, amount
                    )
                else:
                    await self.client.db.execute(
                        query, olditem['amount'] + amount, self.userid, item.id
                    )

    async def remove_item_from_inventory(self, item, amount):
        query = """SELECT * FROM inventory
        WHERE userid = $1 AND itemid = $2;"""
        data = await self.client.db.fetchrow(query, self.userid, item.id)
        if not data:
            raise Exception("Critical error: User does not have this item.")
        oldamount = data['amount']

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                if oldamount <= 1 or oldamount <= amount:
                    query = """DELETE FROM inventory
                    WHERE userid = $1 AND itemid = $2;"""
                    await self.client.db.execute(query, self.userid, item.id)
                else:
                    query = """UPDATE inventory SET amount = amount - $1
                    WHERE userid = $2 AND itemid = $3;"""
                    await self.client.db.execute(query, amount, self.userid, item.id)

    async def add_fields(self, amount):
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET tiles = tiles + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, amount, self.userid)

    async def add_factory_slots(self, amount):
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET factoryslots = factoryslots + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, amount, self.userid)

    async def add_factory_level(self, amount):
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET factorylevel = factorylevel + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, amount, self.userid)

    async def add_store_slots(self, amount):
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET storeslots = storeslots + $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, amount, self.userid)

    async def add_boost(self, boost, duration):
        now = datetime.now()
        period = now + timedelta(seconds=duration)
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = f"""INSERT INTO boosts(userid, {boost.id})
                VALUES($1, $2) ON CONFLICT(userid) DO UPDATE
                SET {boost.id} = CASE
                WHEN boosts.{boost.id} IS NULL THEN EXCLUDED.{boost.id}
                WHEN boosts.{boost.id} < $3 THEN EXCLUDED.{boost.id}
                ELSE boosts.{boost.id} + $4 * INTERVAL '1 SECONDS'
                END;"""
                await self.client.db.execute(query, self.userid, period, now, duration)

    async def toggle_notifications(self, notif):
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """UPDATE profile SET notifications = $1
                WHERE userid = $2;"""
                await self.client.db.execute(query, notif, self.userid)

    def find_all_items_unlocked(self):
        """Lists all items unlocked for user by
        specific level"""
        suitableitems = []

        for item in self.client.allitems.values():
            if item.level <= self.level:
                suitableitems.append(item)

        return suitableitems

    def find_all_unlocked_tradeble_items(self):
        """Filters unlocked tradable items.
        Basically items that have marketprice atribute."""
        unlocked_items = self.find_all_items_unlocked()

        tradables = []
        for item in unlocked_items:
            if hasattr(item, "marketprice"):
                tradables.append(item)

        return tradables
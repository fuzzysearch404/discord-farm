from utils.usertools import generategameuserid
from datetime import datetime, timedelta

DEFAULT_DOG_1_GOLD_PRICE = 50
DEFAULT_DOG_2_GOLD_PRICE = 95
DEFAULT_DOG_3_GOLD_PRICE = 200
DEFAULT_CAT_GOLD_PRICE = 200

durations = {
    1: 86400,
    3: 259200,
    7: 604800
}


def getboostgoldprices(tiles, boost):
    prices = {}

    if tiles < 5:  # Increase prices even more with tiles amount
        tiles *= 2
    elif tiles < 8:
        tiles = int(tiles * 2.5)
    elif tiles < 12:
        tiles = int(tiles * 3)
    else:
        tiles = int(tiles * 3.5)

    if boost == 1:
        for duration, time in durations.items():
            prices[duration] = genboostgoldprice(duration, DEFAULT_DOG_1_GOLD_PRICE * tiles)
    elif boost == 2:
        for duration, time in durations.items():
            prices[duration] = genboostgoldprice(duration, DEFAULT_DOG_2_GOLD_PRICE * tiles)
    elif boost == 3:
        for duration, time in durations.items():
            prices[duration] = genboostgoldprice(duration, DEFAULT_DOG_3_GOLD_PRICE * tiles)
    elif boost == 4:
        for duration, time in durations.items():
            prices[duration] = genboostgoldprice(duration, DEFAULT_CAT_GOLD_PRICE * tiles)

    return prices


def genboostgoldprice(duration, price):
    if duration == 1:
        return price
    elif duration == 3:
        price = price * duration
        return price - int(price * 0.18)
    else:
        price = price * duration
        return price - int(price * 0.28)


async def addboost(client, member, boost, duration):
    userid = generategameuserid(member)
    data = await preparedb(client, userid)
    now = datetime.now().replace(microsecond=0)

    if boost == 1:
        query = """UPDATE boosts SET dog1 = $1 WHERE userid = $2;"""
        if not data['dog1'] or data['dog1'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog1'] + timedelta(seconds=durations[duration])
    elif boost == 2:
        query = """UPDATE boosts SET dog2 = $1 WHERE userid = $2;"""
        if not data['dog2'] or data['dog2'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog2'] + timedelta(seconds=durations[duration])
    elif boost == 3:
        query = """UPDATE boosts SET dog3 = $1 WHERE userid = $2;"""
        if not data['dog3'] or data['dog3'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog3'] + timedelta(seconds=durations[duration])
    elif boost == 4:
        query = """UPDATE boosts SET cat = $1 WHERE userid = $2;"""
        if not data['cat'] or data['cat'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['cat'] + timedelta(seconds=durations[duration])
    await appenddb(client, userid, query, timestamp)


async def preparedb(client, userid):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """INSERT INTO boosts(userid)
        VALUES($1)
        ON CONFLICT DO NOTHING;"""
        await client.db.execute(query, userid)

        query = """SELECT * FROM boosts
        WHERE userid = $1;"""
        data = await client.db.fetchrow(query, userid)
    await client.db.release(connection)
    return data


async def appenddb(client, userid, query, timestamp):
    connection = await client.db.acquire()
    async with connection.transaction():
        await client.db.execute(query, timestamp, userid)
    await client.db.release(connection)


async def removeboosts(client, userid):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """DELETE FROM boosts WHERE userid = $1;"""
        await client.db.execute(query, userid)
    await client.db.release(connection)


def boostvalid(date):
    if not date:
        return False
    return date > datetime.now()

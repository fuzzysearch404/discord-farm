from utils.usertools import generategameuserid
from datetime import datetime, timedelta

DEFAULT_DOG_1_GOLD_PRICE = 15
DEFAULT_DOG_1_GEM_PRICE = 0.2
DEFAULT_DOG_2_GOLD_PRICE = 25
DEFAULT_DOG_2_GEM_PRICE = 0.4
DEFAULT_DOG_3_GOLD_PRICE = 60
DEFAULT_DOG_3_GEM_PRICE = 0.6

durations = {
    1: 86400,
    3: 259200,
    7: 604800
}


def getdoggoldprices(tiles, dog):
    prices = {}

    if dog == 1:
        for duration, time in durations.items():
            prices[duration] = gendoggoldprice(duration, DEFAULT_DOG_1_GOLD_PRICE * tiles)
    elif dog == 2:
        for duration, time in durations.items():
            prices[duration] = gendoggoldprice(duration, DEFAULT_DOG_2_GOLD_PRICE * tiles)
    elif dog == 3:
        for duration, time in durations.items():
            prices[duration] = gendoggoldprice(duration, DEFAULT_DOG_3_GOLD_PRICE * tiles)

    return prices


def getdoggemprices(tiles, dog):
    prices = {}

    if dog == 1:
        for duration, time in durations.items():
            prices[duration] = gendoggemprice(duration, DEFAULT_DOG_1_GEM_PRICE * tiles)
    elif dog == 2:
        for duration, time in durations.items():
            prices[duration] = gendoggemprice(duration, DEFAULT_DOG_2_GEM_PRICE * tiles)
    elif dog == 3:
        for duration, time in durations.items():
            prices[duration] = gendoggemprice(duration, DEFAULT_DOG_3_GEM_PRICE * tiles)

    return prices


def gendoggoldprice(duration, price):
    if duration == 1:
        return price
    elif duration == 3:
        price = price * duration
        return price - int(price * 0.18)
    else:
        price = price * duration
        return price - int(price * 0.28)


def gendoggemprice(duration, price):
    if duration == 1:
        return int(price)
    elif duration == 3:
        price = price * duration
        return int(price - 1)
    else:
        price = price * duration
        return int(price - 3)


async def adddog(client, member, dog, duration):
    userid = generategameuserid(member)
    data = await preparedb(client, userid)
    now = datetime.now().replace(microsecond=0)

    if dog == 1:
        query = """UPDATE boosts SET dog1 = $1 WHERE userid = $2;"""
        if not data['dog1'] or data['dog1'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog1'] + timedelta(seconds=durations[duration])
    elif dog == 2:
        query = """UPDATE boosts SET dog2 = $1 WHERE userid = $2;"""
        if not data['dog2'] or data['dog2'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog2'] + timedelta(seconds=durations[duration])
    elif dog == 3:
        query = """UPDATE boosts SET dog3 = $1 WHERE userid = $2;"""
        if not data['dog3'] or data['dog3'] < datetime.now():
            timestamp = now + timedelta(seconds=durations[duration])
        else:
            timestamp = data['dog3'] + timedelta(seconds=durations[duration])
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

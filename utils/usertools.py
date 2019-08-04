from utils.embeds import congratzembed
from decimal import Decimal


def generategameuserid(member):
    string = str(member.guild.id) + str(member.id)
    return int(string)


def splitgameuserid(longid, ctx):
    string = str(longid)
    string = string.replace(str(ctx.guild.id), "")
    return int(string)


async def getprofile(client, member):
    query = """SELECT * FROM users WHERE id = $1;"""
    userprofile = await client.db.fetchrow(query, generategameuserid(member))
    return userprofile


async def deleteacc(client, member):
    queries = (
        "DELETE FROM planted WHERE userid = $1;",
        "DELETE FROM inventory WHERE userid = $1;",
        "DELETE FROM missions WHERE userid = $1;",
        "DELETE FROM factory WHERE userid = $1;",
        "DELETE FROM store WHERE userid = $1;"
        "DELETE FROM users WHERE id = $1;"
    )

    userid = generategameuserid(member)

    connection = await client.db.acquire()
    async with connection.transaction():
        for query in queries:
            await client.db.execute(query, userid)
    await client.db.release(connection)


async def getinventory(client, member):
    query = """SELECT * FROM inventory WHERE userid = $1;"""
    inventory = await client.db.fetch(query, generategameuserid(member))
    return geninventory(client, inventory)


def geninventory(client, invlist):
    found = {}
    for object in invlist:
        try:
            found[client.allitems[object['itemid']]] = object['amount']
        except KeyError:
            raise Exception(f"Could not find item {object['itemid']}")
    return found


async def checkinventoryitem(client, member, item):
    query = """SELECT * FROM inventory WHERE userid = $1
    AND itemid = $2;"""
    item = await client.db.fetchrow(query, generategameuserid(member), item.id)
    return item


async def getuserfield(client, member):
    query = """SELECT * FROM planted WHERE userid = $1;"""
    data = await client.db.fetch(query, generategameuserid(member))
    return data


async def givexpandlevelup(client, ctx, xp):
    member = ctx.author
    oldxp = await getprofile(client, member)
    oldxp = oldxp['xp']
    oldlevel = getlevel(oldxp)[0]

    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET xp = $1
        WHERE id = $2;"""
        newxp = oldxp + xp
        await client.db.execute(query, newxp, generategameuserid(member))
    await client.db.release(connection)

    newlevel = getlevel(newxp)[0]
    if oldlevel < newlevel:
        gems = gemsforlevel(newlevel)
        await givegems(client, member, gems)
        embed = congratzembed(
            f"Tu sasniedzi {newlevel}.līmeni un ieguvi {gems}{client.gem}!\n"
            "Noskaidro ko esi atbloķējis ar `%allitems`",
            ctx
        )
        await ctx.send(embed=embed)


async def givegems(client, member, gems):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET gems = gems + $1
        WHERE id = $2;"""
        await client.db.execute(query, gems, generategameuserid(member))
    await client.db.release(connection)


async def givemoney(client, member, money):
    if not isinstance(member, Decimal):
        member = generategameuserid(member)

    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET money = money + $1
        WHERE id = $2;"""
        await client.db.execute(query, money, member)
    await client.db.release(connection)


async def additemtoinventory(client, member, item, amount):
    olditem = await checkinventoryitem(client, member, item)
    if not olditem:
        query = """INSERT INTO inventory(itemid, userid, amount)
        VALUES($1, $2, $3);"""
    else:
        query = """UPDATE inventory SET amount = $1
        WHERE userid = $2 AND itemid = $3;"""

    connection = await client.db.acquire()
    async with connection.transaction():
        if olditem:
            await client.db.execute(
                query, olditem['amount'] + amount, generategameuserid(member), item.id
                )
        else:
            await client.db.execute(
                query, item.id, generategameuserid(member), amount
            )

    await client.db.release(connection)


async def removeitemfrominventory(client, member, item, amount):
    query = """SELECT * FROM inventory
    WHERE userid = $1 AND itemid = $2;"""
    data = await client.db.fetchrow(query, generategameuserid(member), item.id)
    if not data:
        raise Exception("Critical error: User does not have this item.")
    oldamount = data['amount']

    connection = await client.db.acquire()
    async with connection.transaction():
        if oldamount <= 1 or oldamount <= amount:
            query = """DELETE FROM inventory
            WHERE userid = $1 AND itemid = $2;"""
            await client.db.execute(query, generategameuserid(member), item.id)
        else:
            query = """UPDATE inventory SET amount = amount - $1
            WHERE userid = $2 AND itemid = $3;"""
            await client.db.execute(query, amount, generategameuserid(member), item.id)
    await client.db.release(connection)


async def addfields(client, member, amount):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET tiles = tiles + $1
        WHERE id = $2;"""
        await client.db.execute(query, amount, generategameuserid(member))
    await client.db.release(connection)


async def addusedfields(client, member, amount):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET usedtiles = usedtiles + $1
        WHERE id = $2;"""
        await client.db.execute(query, amount, generategameuserid(member))
    await client.db.release(connection)


async def getmissions(client, member):
    query = """SELECT * FROM missions WHERE userid = $1;"""
    missions = await client.db.fetch(query, generategameuserid(member))
    return missions


async def checkfactoryslots(client, member):
    profile = await getprofile(client, member)

    query = """SELECT count(id) FROM factory WHERE userid = $1;"""
    slots = await client.db.fetchrow(query, generategameuserid(member))

    if not slots:
        return profile['factoryslots']

    avaiable = profile['factoryslots'] - slots[0]

    if avaiable > 0:
        return avaiable
    else:
        return 0


async def getuserfactory(client, member):
    query = """SELECT * FROM factory WHERE userid = $1;"""
    data = await client.db.fetch(query, generategameuserid(member))
    return data


async def getoldestfactoryitem(client, member):
    query = """SELECT * FROM factory WHERE userid = $1
    ORDER BY ends DESC LIMIT 1;"""
    data = await client.db.fetchrow(query, generategameuserid(member))
    return data


async def addfactoryslots(client, member, amount):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET factoryslots = factoryslots + $1
        WHERE id = $2;"""
        await client.db.execute(query, amount, generategameuserid(member))
    await client.db.release(connection)


async def addstoreslots(client, member, amount):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET storeslots = storeslots + $1
        WHERE id = $2;"""
        await client.db.execute(query, amount, generategameuserid(member))
    await client.db.release(connection)


async def getuserstore(client, member):
    query = """SELECT * FROM store WHERE userid = $1;"""
    data = await client.db.fetch(query, generategameuserid(member))
    return data


async def getguildstore(client, guild):
    query = """SELECT * FROM store WHERE guildid = $1
            ORDER BY userid;"""
    data = await client.db.fetch(query, guild.id)
    return data


async def gettrade(client, id):
    query = """SELECT * FROM store WHERE id = $1;"""
    data = await client.db.fetchrow(query, id)
    return data


async def deletetrade(client, id):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """DELETE FROM store WHERE id = $1;"""
        await client.db.execute(query, id)
    await client.db.release(connection)


async def getstoreslotcount(client, member):
    query = """SELECT count(id) FROM store WHERE userid = $1;"""
    slots = await client.db.fetchrow(query, generategameuserid(member))
    if not slots:
        return False
    return slots[0]


def upgradecost(ownedtiles):
    if ownedtiles < 5:
        return 4
    elif ownedtiles < 8:
        return 7
    elif ownedtiles < 11:
        return 11
    else:
        return 14


def storeupgcost(ownedslots):
    return ownedslots * 1000


def gemsforlevel(level):
    if level < 9:
        return 3
    elif level < 14:
        return 4
    elif level < 19:
        return 5
    else:
        return 6


def getlevel(xp):
    limit = (
        0, 20, 240, 750, 1950, 3300, 5100, 7950, 12000, 16800,
        23100, 31500, 42000, 57000, 80100
    )
    level = 0

    for points in limit:
        if xp >= points:
            level += 1
        else:
            break

    return level, points

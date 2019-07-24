from utils.embeds import congratzembed


def generategameuserid(member):
    string = str(member.guild.id) + str(member.id)
    return int(string)


async def getprofile(client, member):
    query = """SELECT * FROM users WHERE id = $1;"""
    userprofile = await client.db.fetchrow(query, generategameuserid(member))
    return userprofile


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
        embed = congratzembed(f"Tu sasniedzi {newlevel}.līmeni un ieguvi {gems}{client.gem}!")
        await ctx.send(embed=embed)


async def givegems(client, member, gems):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET gems = gems + $1
        WHERE id = $2;"""
        await client.db.execute(query, gems, generategameuserid(member))
    await client.db.release(connection)


async def givemoney(client, member, money):
    connection = await client.db.acquire()
    async with connection.transaction():
        query = """UPDATE users SET money = money + $1
        WHERE id = $2;"""
        await client.db.execute(query, money, generategameuserid(member))
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
        if oldamount <= 1 or oldamount < amount:
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


def gemsforlevel(level):
    if level < 9:
        return 3
    elif level < 14:
        return 4
    else:
        return 5


def getlevel(xp):
    limit = [0, 10, 30, 100, 150, 220, 310, 400, 500, 620]
    level = 0

    for points in limit:
        if xp >= points:
            level += 1
        else:
            break

    return level, points

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


def getlevel(xp):
    limit = [0, 10, 30, 100, 150, 220, 310, 400, 500, 620]
    level = 0

    for points in limit:
        if xp >= points:
            level += 1
        else:
            break

    return level, points

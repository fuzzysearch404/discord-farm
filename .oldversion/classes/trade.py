async def get_trade(client, id, guild):
    query = """SELECT * FROM store WHERE id = $1
    AND guildid = $2;"""
    data = await client.db.fetchrow(query, id, guild.id)
    
    return data

async def delete_trade(client, id):
    async with client.db.acquire() as connection:
            async with connection.transaction():
                query = """DELETE FROM store WHERE id = $1;"""
                await client.db.execute(query, id)
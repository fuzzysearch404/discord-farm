from discord.ext import commands
from utils import checks
from utils import usertools
from utils import embeds as emb
from utils.convertors import MemberID


class Usercontrol(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    @checks.is_owner()
    async def deluser(self, ctx, member: MemberID):
        client = self.client
        queries = (
            "DELETE FROM planted WHERE userid = $1;",
            "DELETE FROM inventory WHERE userid = $1;",
            "DELETE FROM users WHERE id = $1;"
        )

        userid = usertools.generategameuserid(member)

        connection = await client.db.acquire()
        async with connection.transaction():
            for query in queries:
                await client.db.execute(query, userid)
        await client.db.release(connection)
        embed = emb.confirmembed(f'Deleted: {member}')
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Usercontrol(client))

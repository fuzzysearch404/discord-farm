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
        await usertools.deleteacc(self.client, member)
        embed = emb.confirmembed(f'Deleted: {member}')
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Usercontrol(client))

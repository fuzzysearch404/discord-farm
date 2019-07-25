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
    async def editnews(self, ctx):
        content = ctx.message.clean_content.replace("%editnews ", "")
        with open('files/news.txt', "w", encoding='utf-8') as f:
            f.write(content)
        embed = emb.confirmembed(content)
        await ctx.send(embed=embed)

    @commands.command()
    @checks.is_owner()
    async def deluser(self, ctx, member: MemberID):
        await usertools.deleteacc(self.client, member)
        embed = emb.confirmembed(f'Deleted: {member}')
        await ctx.send(embed=embed)

    @commands.command()
    @checks.is_owner()
    async def disablegame(self, ctx):
        if self.client.disabledcommands:
            self.client.disabledcommands = False
        else:
            self.client.disabledcommands = True
        embed = emb.confirmembed(f'Game disabled: {self.client.disabledcommands}')
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Usercontrol(client))

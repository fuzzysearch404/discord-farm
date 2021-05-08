from discord.ext import commands


class Admin(commands.Cog):

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command()
    async def test(self, ctx, a:int =2):
        await ctx.send("1")


def setup(bot) -> None:
    bot.add_cog(Admin(bot))

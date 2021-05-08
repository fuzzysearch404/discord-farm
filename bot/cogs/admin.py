from discord.ext import commands


class Admin(commands.Cog):

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot


def setup(bot) -> None:
    Admin(bot)

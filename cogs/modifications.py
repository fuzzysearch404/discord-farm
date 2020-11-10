from discord.ext import commands


class Modifications(commands.Cog):
    """
    Modifications description.
    """
    def __init__(self, client):
        self.client = client


def setup(client):
    client.add_cog(Modifications(client))
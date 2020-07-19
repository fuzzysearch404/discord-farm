import psutil
import pkg_resources
from discord import Embed, Activity
from discord.ext import commands, tasks
from utils import embeds as emb
from utils import checks

class Information(commands.Cog, name="Very Informative"):
    """
    Get information about the bot - news, events, some links, etc.
    """
    def __init__(self, client):
        self.client = client
        self.statusloop.start()
        self.process = psutil.Process()

    @commands.command()
    @checks.embed_perms()
    async def news(self, ctx):
        """
        \ud83d\udcf0 Get latest update and bot's status information.
        """
        embed = Embed(title='\ud83d\udcf0 News', colour=15129855, description=self.client.news)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    async def ping(self, ctx):
        """
        Check if the bot even wants to talk to you.
        """
        await ctx.send('ponh!')

    @commands.command()
    async def invite(self, ctx):
        """
        \ud83d\udcf2 Would you like to invite bot to your own server? Sure, do it!
        """
        await ctx.send("Support server invite: https://discord.gg/MwpxKjF"
        "\nBot invite: <https://discord.com/oauth2/authorize?client_id=526436949481881610&scope=bot&permissions=387136>")

    @commands.command()
    async def donate(self, ctx):
        """
        \u2764\ufe0f If you are really kind and really enjoy this game.
        """
        await ctx.send(
            "Hello, my name is fuzzyseach, and I do bots as a free time hobby. \ud83e\udd13\n"
            "Managing a bot is not an easy task, and it costs time and money. "
            "Any donations are appreciated, they will motivate and support me, to make this bot even better. <3"
            "\nhttps://www.paypal.me/fuzzysearch"
        )

    @commands.command()
    async def about(self, ctx):
        """
        \ud83e\udd16 Shows information about the bot itself.
        """
        embed=Embed(
            title="Discord Farm",
            description="The most advanced farming bot on Discord.",
            color=13145620
        )

        embed.add_field(name="Your server's cluster", value=self.client.cluster_name)
        shards_and_lat = ""
        for shard, lat in self.client.latencies:
            lat = lat * 1000
            shards_and_lat += f"\ud83d\udce1 Shard #{shard} - {'%.0f' % lat}ms\n"
        embed.add_field(name="Cluter's shards", value=shards_and_lat)
        embed.add_field(name="Your server's shard", value=ctx.guild.shard_id)
        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')
        embed.add_field(name='Uptime', value=self.client.uptime)
        embed.add_field(name="Bot version", value=self.client.config.version)
        embed.set_footer(text=f"Made with discord.py v{pkg_resources.get_distribution('discord.py').version}")
        await ctx.send(embed=embed)

    @tasks.loop(seconds=1800)
    async def statusloop(self):
        await self.client.change_presence(activity=Activity(name=self.client.config.activity_status, type=2))

    @statusloop.before_loop
    async def before_statusloop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self.statusloop.cancel()


def setup(client):
    client.add_cog(Information(client))

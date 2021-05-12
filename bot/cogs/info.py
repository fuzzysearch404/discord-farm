import psutil
import pkg_resources
import discord
from discord.ext import commands, tasks

from .utils import time as time_util


class Info(commands.Cog):
    """
    Get information about the bot - news, events, some links, etc.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        self.version = self.bot.config['bot']['version']
        self.activity_status = self.bot.config['bot']['activity-status']
        self.process = psutil.Process()
        self._status_task = self.update_status_task.start()

    @commands.command()
    async def news(self, ctx):
        """
        \ud83d\udcf0 Get latest update and bot's status information

        For more information join official support server.
        """
        embed = discord.Embed(
            title='\ud83d\udcf0 News',
            colour=15129855,
            description=self.bot.game_news
        )
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    async def ping(self, ctx):
        """
        Check if the bot even wants to talk to you
        """
        await ctx.send('ponh!')

    @commands.command(aliases=['support'])
    async def invite(self, ctx):
        """
        \ud83d\udcf2 Invite bot to your own server or join support server
        """
        await ctx.send(
            "Support server invite: https://discord.gg/MwpxKjF"
            "\nBot invite: <https://discord.com/oauth2/authorize?client_id="
            "526436949481881610&scope=bot&permissions=387136>"
        )

    @commands.command()
    async def donate(self, ctx):
        """
        \u2764\ufe0f If you are really kind and like this bot
        """
        await ctx.send(
            "Hello, my name is fuzzyseach, and I do bots as a free time hobby."
            " \ud83e\udd13\nManaging a bot is not an easy task, "
            "and hosting it costs lots of my time and also money.\n"
            "Any donations are appreciated, they are going to cover hosting "
            "expenses and help to make this bot even better. <3"
            "\nhttps://www.paypal.me/fuzzysearch\n"
            "\nYou can also help out, without spending any money, "
            "if you upvote the bot on top.gg every 12 hours:"
            "\n<https://top.gg/bot/526436949481881610>"
        )

    @commands.command()
    async def about(self, ctx):
        """
        \ud83e\udd16 Shows some information about the bot itself
        """
        embed = discord.Embed(
            title="Discord Farm",
            description="The original, most advanced farming bot on Discord.",
            color=discord.Color.random()
        )

        embed.add_field(
            name="Your server's cluster",
            value=self.bot.cluster_name
        )

        shards_and_lat = ""
        for shard, lat in self.bot.latencies:
            lat = lat * 1000
            shards_and_lat += (
                f"\ud83d\udce1 Shard #{shard} - {'%.0f' % lat}ms\n"
            )

        embed.add_field(name="Cluter's shards", value=shards_and_lat)
        embed.add_field(name="Your server's shard", value=ctx.guild.shard_id)
        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(
            name='Process',
            value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU'
        )
        embed.add_field(name='Uptime', value=self.bot.uptime)
        embed.add_field(name="Bot version", value=self.version)
        embed.set_footer(
            text=(
                "Made with discord.py v"
                f"{pkg_resources.get_distribution('discord.py').version}"
            )
        )

        await ctx.send(embed=embed)

    @commands.command()
    async def clusters(self, ctx):
        """\ud83d\udef0\ufe0f View bot's all cluster statuses"""
        embed = discord.Embed(
            title="Clusters information",
            color=discord.Color.random()
        )

        for cluster in self.bot.cluster_data:
            fmt = ""

            for id, ping in cluster.latencies:
                ping = ping * 1000
                fmt += f"#{id} - {'%.0f' % ping}ms\n"

            uptime = time_util.seconds_to_time(cluster.uptime.total_seconds())
            fmt += f"\nUptime: {uptime} "

            embed.add_field(
                name=f"**{cluster.name} ({cluster.guild_count} guilds)**",
                value=fmt
            )

        embed.set_footer(text=f"\nIPC ping: {'%.0f' % self.bot.ipc_ping}ms")

        await ctx.send(embed=embed)

    @tasks.loop(seconds=1800)
    async def update_status_task(self):
        await self.bot.change_presence(
            activity=discord.Activity(
                name=self.activity_status,
                type=2
            )
        )

    @update_status_task.before_loop
    async def before_update_status_task(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self._status_task.cancel()


def setup(bot):
    bot.add_cog(Info(bot))

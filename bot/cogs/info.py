import psutil
import pkg_resources
import discord
from discord.ext import commands, tasks, menus

from .utils import time as time_util
from .utils import pages


class HelpMessageSource(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu, page):
        embed = discord.Embed(
            color=discord.Color.from_rgb(88, 101, 242),
            description=page
        )

        return embed


class HelpCommand(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__(
            verify_checks=False,
            command_attrs={
                "help": "Shows help about a command, or a category",
                "aliases": ["commands", "comands", "cmd", "helpme"]
            }
        )

    def get_command_signature(self, command):
        if command.full_parent_name:
            cmd = (
                f"**{self.context.prefix}{command.full_parent_name} "
                f"{command.name}**"
            )
        else:
            cmd = f"**{self.context.prefix}{command.name}**"

        if command.signature:
            cmd += f" `{command.signature}`"

        return cmd

    def add_bot_commands_formatting(self, commands, heading):
        if commands:
            joined = "\u2002".join(f"`{c.name}`" for c in commands)
            self.paginator.add_line(f"**{heading}**")
            self.paginator.add_line(joined)

    async def send_pages(self):
        # Replace prefix with invoked prefix
        new_pages = []

        for page in self.paginator.pages:
            new_pages.append(page.replace("{prefix}", self.context.prefix))

        paginator = pages.MenuPages(
            source=HelpMessageSource(new_pages)
        )

        await paginator.start(self.context)


class Info(commands.Cog, name="Information"):
    """
    Get information about the bot - news, events, some links, etc.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

        self.version = self.bot.config['bot']['version']
        self.activity_status = self.bot.config['bot']['activity-status']

        self.process = psutil.Process()

        self.old_help_command = bot.help_command
        self.bot.help_command = HelpCommand()

        self._status_task = self.update_status_task.start()

    def cog_unload(self):
        self.bot.help_command = self.old_help_command

        self._status_task.cancel()

    @commands.command()
    async def news(self, ctx):
        """
        \ud83d\udcf0 Get latest update and bot's status information

        For more information join bot's official support server.
        """
        embed = discord.Embed(
            title='\ud83d\udcf0 News',
            colour=discord.Color.from_rgb(222, 222, 222),
            description=self.bot.game_news
        )

        embed.set_footer(
            text="For more information join bot's official support server",
            icon_url=ctx.bot.user.avatar_url
        )

        await ctx.reply(embed=embed)

    @commands.command(hidden=True)
    async def ping(self, ctx):
        """
        Check if the bot even wants to talk to you
        """
        await ctx.reply("ponh!")

    @commands.command(aliases=["support"])
    async def invite(self, ctx):
        """
        \ud83d\udcf2 Invite bot to your own server or join support server
        """
        permissions = discord.Permissions.none()
        permissions.read_messages = True
        permissions.send_messages = True
        permissions.external_emojis = True
        permissions.embed_links = True
        permissions.manage_messages = True
        permissions.read_message_history = True
        permissions.attach_files = True
        permissions.add_reactions = True

        oauth_link = discord.utils.oauth_url(self.bot.user.id, permissions)

        await ctx.reply(
            "Support server invite: https://discord.gg/MwpxKjF"
            f"\nInvite bot to your server: <{oauth_link}>"
        )

    @commands.command()
    async def donate(self, ctx):
        """
        \u2764\ufe0f If you are really kind and like this bot
        """
        message = (
            "Labdien! My name is fuzzysearch. I am the solo developer from "
            "Latvia behind this bot. I do bots as a free time hobby and "
            "lots of other stuff. This bot has been one of my favorite "
            "projects, that I have put countless hours in the recent years. "
            " \ud83e\udd13\nManaging a bot is not an easy task, "
            "and hosting it, costs lots of my time and also money.\n\n"
            "Any donations are appreciated, they are going to cover hosting "
            "expenses and help to make this bot even better. <3"
            "\nhttps://ko-fi.com/fuzzysearch\n"
            "\nYou can also help out, without spending any money, "
            "if you upvote the bot on the \"top.gg\" website every 12 hours "
            f"(This command also unlocks the **{ctx.prefix}hourly** "
            f"bonus command):\n<https://top.gg/bot/{ctx.bot.user.id}>"
        )

        embed = discord.Embed(
            title="\u2764\ufe0f Support Discord Farm",
            color=discord.Color.from_rgb(245, 35, 35),
            description=message
        )

        await ctx.reply(embed=embed)

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
            value=(
                f"**{self.bot.cluster_name}**\n"
                f"IPC ping: {'%.0f' % self.bot.ipc_ping}ms"
            )
        )

        shards_and_lat = ""
        for shard, lat in self.bot.latencies:
            lat = lat * 1000
            shards_and_lat += (
                f"\ud83d\udce1 Shard #{shard} - {'%.0f' % lat}ms\n"
            )

        embed.add_field(name="Cluter's shards", value=shards_and_lat)
        embed.add_field(
            name="Your server's shard",
            value=f"#{ctx.guild.shard_id}"
        )
        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(
            name="Process",
            value=f"{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU"
        )
        embed.add_field(name="Uptime", value=self.bot.uptime)
        embed.add_field(name="Bot version", value=self.version)
        embed.set_footer(
            text=(
                "Made with discord.py v"
                f"{pkg_resources.get_distribution('discord.py').version} "
                "| This bot is not made or maintained by Discord"
            )
        )

        await ctx.reply(embed=embed)

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
                fmt += (
                    f"> **#{id} - {'%.0f' % ping}ms** "
                    f"IPC: {'%.0f' % self.bot.ipc_ping}ms\n"
                )

            uptime = time_util.seconds_to_time(cluster.uptime.total_seconds())
            fmt += f"\n**Uptime: {uptime} **"

            embed.add_field(
                name=f"**{cluster.name} ({cluster.guild_count} guilds)**",
                value=fmt
            )

        await ctx.reply(embed=embed)

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


def setup(bot):
    bot.add_cog(Info(bot))

import psutil
import pkg_resources
import discord
from discord.ext import commands, tasks

from .utils import views
from .utils import checks
from .utils import embeds
from .utils import time as time_util


class HelpMessageSource(views.PaginatorSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)

    async def format_page(self, page, view):
        embed = discord.Embed(
            color=discord.Color.from_rgb(88, 101, 242),
            description=page[0]
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

        paginator = views.ButtonPaginatorView(
            source=HelpMessageSource(new_pages)
        )

        await paginator.start(self.context)


class Info(commands.Cog, name="\ud83e\udd16 Information"):
    """
    Get the latest information about the bot - news, events, some links, etc.
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

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\ud83d\udc65",
            label="Join the official support server for more information",
            url="https://discord.gg/MwpxKjF"
        ))

        await ctx.reply(embed=embed, view=view)

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
        permissions.send_messages_in_threads = True

        oauth_link = discord.utils.oauth_url(
            self.bot.user.id, permissions=permissions,
            scopes=("bot", "applications.commands")
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\ud83e\udd16",
            label="Invite bot to your server",
            url=oauth_link
        ))
        view.add_item(discord.ui.Button(
            emoji="\ud83d\udc65",
            label="Join the official support server",
            url="https://discord.gg/MwpxKjF"
        ))

        await ctx.reply(
            "Here you go! Also consider joining the official support "
            "server \ud83d\ude09", view=view
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
        )

        embed = discord.Embed(
            title="\u2764\ufe0f Support Discord Farm",
            color=discord.Color.from_rgb(245, 35, 35),
            description=message
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\u2764\ufe0f",
            label="Buy me a coffee",
            url="https://ko-fi.com/fuzzysearch"
        ))
        view.add_item(discord.ui.Button(
            emoji="\ud83d\udc99",
            label="Support via PayPal",
            url="https://paypal.me/fuzzysearch"
        ))

        await ctx.reply(embed=embed, view=view)

    @commands.command()
    async def about(self, ctx):
        """
        \ud83e\udd16 Shows some information about the bot itself
        """
        embed = discord.Embed(
            title="Discord Farm",
            description=(
                "The original, most advanced farming strategy game bot on "
                "Discord."
            ),
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

    @commands.command(hidden=True)
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

    @commands.command()
    @commands.has_permissions(administrator=True)
    @checks.avoid_maintenance()
    async def prefix(self, ctx, prefix: str):
        """Customize bot's prefix

        This command let's you choose by what prefix the commands will be
        invoked with. Prefix is the symbol combination before any
        command name. Right now you are using prefix: **{prefix}**

        __Arguments__:
        `prefix` - the new prefix to switch to. If you want a space
        between prefix and the command, put the prefix with a whitespace
        in double quotes. (See the second example below)
        You can even remove the prefix completely, by just specifying
        the prefix as an empty double quotes: `""` (not recommended)

        __Usage examples__:
        {prefix} `prefix !!` - the commands are going to start
        with a "!!" prefix: Example command: !!profile
        {prefix} `prefix "farm "` - the commands are going to start
        with a "farm " prefix: Example command: farm profile
        """
        if len(prefix) > 6:
            return await ctx.reply(
                "\u274c The prefix lenght must be 6 symbols or less!"
            )

        async with ctx.acquire() as conn:
            if prefix == self.bot.def_prefix:
                query = "DELETE FROM guilds WHERE guild_id = $1;"

                await conn.execute(query, ctx.guild.id)

                try:
                    del self.bot.custom_prefixes[ctx.guild.id]
                except KeyError:
                    pass
            else:
                query = """
                        INSERT INTO guilds (guild_id, prefix)
                        VALUES ($1, $2)
                        ON CONFLICT (guild_id) DO UPDATE
                        SET prefix = $2;
                        """

                await conn.execute(query, ctx.guild.id, prefix)

                self.bot.custom_prefixes[ctx.guild.id] = prefix

        await ctx.reply(
            embed=embeds.success_embed(
                title="My prefix got changed! \ud83d\udc4c",
                text=(
                    "From now on my prefix in this server is: "
                    f"\"**{prefix}**\"\nNow, to execute commands, you "
                    f"will have to type: **{prefix}**`command_name`.\n"
                    f"For example: **{prefix}profile**\n\nIf you somehow "
                    "forget your prefix, don't worry, you can still just "
                    "@mention me to use commands too. :)"
                ),
                footer="Don't forget to notify your friends here about this",
                ctx=ctx
            )
        )

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

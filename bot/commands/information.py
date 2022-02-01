import psutil
import typing
import asyncio
import discord
import pkg_resources
from typing import Optional

from core import static
from .util import commands
from .util import exceptions
from .util import views
from .util import time as time_util


class InformationCollection(commands.FarmCommandCollection):
    """Get the latest information about the bot - news, event info, links, etc."""
    help_emoji: str = "\N{NEWSPAPER}"
    help_short_description: str = "Get official bot news, update information etc."

    def __init__(self, client) -> None:
        super().__init__(
            client,
            [HelpCommand, NewsCommand, InviteCommand, AboutCommand],
            name="Information"
        )
        self.activity_status = client.config['bot']['activity-status']
        self.presence_task = self.client.loop.create_task(self.update_presence_task())

    def on_unload(self) -> None:
        self.presence_task.cancel()

    async def update_presence_task(self) -> None:
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            await asyncio.sleep(1800)
            await self.client.change_presence(
                activity=discord.Activity(name=self.activity_status, type=2)
            )


class HelpAllCommandsMessageSource(views.AbstractPaginatorSource):

    def __init__(
        self,
        current_guild_id: int,
        collection: commands.FarmCommandCollection
    ):
        all_commands = []
        for cmd in collection.commands:
            for child in cmd.find_all_lowest_children(cmd):
                # Hide owner only commands
                if child.owner_only:
                    continue
                # Hide guild specific commands if not in the same guild
                if child._guilds_ and current_guild_id not in child._guilds_:
                    continue

                all_commands.append(child)

        super().__init__(all_commands, per_page=8)
        self.collection = collection

    async def format_page(self, page, view):
        embed = discord.Embed(
            title=f"{self.collection.help_emoji} {self.collection.name}",
            description=commands.format_docstring_help(self.collection.description),
            color=discord.Color.blurple()
        )

        for command in page:
            embed.add_field(
                name=f"/{command.get_full_name(command)}",
                value=command._description_,
                inline=False
            )

        embed.set_footer(
            text=(
                "\N{ELECTRIC LIGHT BULB} Use \"/help command_name\" for detailed help "
                "about specific command usage"
            )
        )
        return embed


class HelpCommand(
    commands.FarmSlashCommand,
    name="help",
    description="\N{BLACK QUESTION MARK ORNAMENT} Lists all commands, shows help for command usage"
):
    """
    If you managed to get here, that means you already know how to use the help command to get help
    for a specific command usage information. Amazing! \N{THUMBS UP SIGN}
    """
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    command: Optional[str] = discord.app.Option(
        description="The name of the command to show detailed help for",
        autocomplete=True
    )

    def bot_commands_autocomplete(self, query: str) -> dict:
        # This is fairly slow, maybe we can improve it later
        current_guild_id = self.interaction.guild_id

        options = {}
        for category in self.client.command_collections.values():
            if category.hidden_in_help_command:
                continue

            for command in category.commands:
                for child in command.find_all_lowest_children(command):
                    # Hide owner only commands
                    if child.owner_only:
                        continue
                    # Hide guild specific commands if not in the same guild
                    if child._guilds_ and current_guild_id not in child._guilds_:
                        continue

                    full_name = child.get_full_name(child)
                    options[full_name] = full_name

        return self._find_items_for_autocomplete(options, query)

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.bot_commands_autocomplete(options[focused]))

    async def send_command_help(self) -> None:
        command = self.client.find_loaded_command_by_name(self.command.lower())
        if not command:
            raise exceptions.FarmException(f"Couldn't find a command named \"{self.command}\".")

        command_signature = ""
        param_descriptions = []
        for option in command._arguments_:
            # Checks if the option is typing.Optional
            if typing.get_origin(option.type) is typing.Union \
                    and type(None) in typing.get_args(option.type):
                opt = option.name
                if not isinstance(option.default, discord.utils._MissingSentinel):
                    opt = f"{opt} = {option.default}"

                param_signature = f"[{opt}]"
            else:
                param_signature = f"<{option.name}>"

            command_signature += param_signature + " "
            param_description = option.description if option.description else "No description"
            param_descriptions.append(f"**{param_signature}** - {param_description}")

        embed = discord.Embed(
            title=f"/{self.command.lower()} {command_signature}",
            color=discord.Color.blurple()
        )
        embed.description = command._description_

        if command.__doc__:
            embed.description += "\n\n" + commands.format_docstring_help(command.__doc__)

        def cooldown_fmt(duration: int) -> str:
            if duration > 0:
                cd_fmt = time_util.seconds_to_time(duration)
            else:
                cd_fmt = "Varying"

            return f"\n\N{TIMER CLOCK} **Cooldown duration:** {cd_fmt}"

        command_features = ""
        if command.owner_only:
            command_features += "\n\N{WRENCH} This command can only be used by the bot owners"
        if command.required_level:
            command_features += f"\n\N{TRIDENT EMBLEM} **Required level:** {command.required_level}"
        if command.inner_cooldown:
            command_features += cooldown_fmt(command.inner_cooldown)
        elif command.invoke_cooldown:
            command_features += cooldown_fmt(command.invoke_cooldown)

        if command_features:
            embed.add_field(name="Properties", value=command_features, inline=False)

        if param_descriptions:
            param_desc = "\n".join(param_descriptions)
            param_desc += (
                "\n\nOkay that's all cool, but what are those brackets for? \N{THINKING FACE}\n"
                "It's easy - something in `[]` means that the argument is optional, "
                "`<>` means that it is required."
            )
            embed.add_field(name="Arguments", value=param_desc, inline=False)

        if command._children_:
            subcommands = command._children_.values()
            child_desc = "\n".join(
                [f"**/{c.get_full_name(c)}** - {c._description_}" for c in subcommands]
            )
            embed.add_field(name="Commands", value=child_desc, inline=False)

        await self.reply(embed=embed)

    async def callback(self):
        if self.command:
            return await self.send_command_help()

        options_and_sources = {}
        for collection in self.client.command_collections.values():
            if collection.hidden_in_help_command:
                continue

            opt = discord.SelectOption(
                label=collection.name,
                emoji=collection.help_emoji,
                description=collection.help_short_description
            )

            current_guild_id = self.interaction.guild_id
            options_and_sources[opt] = HelpAllCommandsMessageSource(current_guild_id, collection)

        await views.SelectButtonPaginatorView(
            self,
            options_and_sources,
            select_placeholder="\N{BOOKS} Select a category for commands"
        ).start()


class NewsCommand(
    commands.FarmSlashCommand,
    name="news",
    description="\N{NEWSPAPER} Displays update and announcement information",
):
    """
    Provides information about the latest bot updates.
    As displaying long contents in commands is limited, for more information,
    consider joining the bot's official support server.
    """
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    async def callback(self) -> None:
        embed = discord.Embed(
            title="\N{NEWSPAPER} Your farm newspaper",
            colour=discord.Color.from_rgb(222, 222, 222),
            description=self.client.game_news
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\N{BUSTS IN SILHOUETTE}",
            label="Join the official support server for more information",
            url=static.DISCORD_COMMUNITY_INVITE
        ))

        await self.reply(embed=embed, view=view)


class InviteCommand(
    commands.FarmSlashCommand,
    name="invite",
    description="\N{ENVELOPE WITH DOWNWARDS ARROW ABOVE} Invites this bot to your own server"
):
    """
    You can invite the bot to your own server or join the support server and play the bot there
    with Discord Farm's community.
    """
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    async def callback(self) -> None:
        permissions = discord.Permissions.none()
        permissions.read_messages = True
        permissions.send_messages = True
        permissions.external_emojis = True
        permissions.embed_links = True
        permissions.attach_files = True
        permissions.add_reactions = True
        permissions.send_messages_in_threads = True

        oauth_link = discord.utils.oauth_url(
            self.client.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands")
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\N{ROBOT FACE}",
            label="Invite this bot to your server",
            url=oauth_link
        ))
        view.add_item(discord.ui.Button(
            emoji="\N{BUSTS IN SILHOUETTE}",
            label="Join the official support server",
            url=static.DISCORD_COMMUNITY_INVITE
        ))

        await self.reply(
            "Here you go! Also consider joining the official support server \N{WINKING FACE}",
            view=view
        )


class AboutCommand(
    commands.FarmSlashCommand,
    name="about",
    description="\N{HEAVY BLACK HEART} Shows the bot's status, version and credits"
):
    """Thanks to Aneteee for helping out with the documentation for bot commands."""
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    async def callback(self) -> None:
        embed = discord.Embed(
            title="\N{EAR OF MAIZE} Discord Farm",
            description=(
                "The original, most advanced farming strategy game bot on Discord.\n"
                "If you want to help to cover hosting costs, see the buttons below. "
                "Huge thanks to everyone who have contributed to this bot."
            ),
            color=discord.Color.random()
        )
        embed.add_field(
            name="Your server's cluster",
            value=f"**{self.client.cluster_name}**\nIPC ping: {'%.0f' % self.client.ipc_ping}ms"
        )

        shards_and_lat = ""
        for shard, lat in self.client.latencies:
            shards_and_lat += f"\N{SATELLITE ANTENNA} Shard #{shard} - {'%.0f' % (lat * 1000)}ms\n"

        embed.add_field(name="Cluster's shards", value=shards_and_lat)
        embed.add_field(name="Your server's shard", value=f"#{self.guild.shard_id}")

        memory_usage = self.client.process_info.memory_full_info().uss / 1024 ** 2
        cpu_usage = self.client.process_info.cpu_percent() / psutil.cpu_count()
        embed.add_field(name="Process", value=f"{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU")
        embed.add_field(name="Uptime", value=self.client.uptime)
        embed.add_field(name="Version", value=self.client.config['bot']['version'])

        enhanced_dpy_version = pkg_resources.get_distribution('discord.py').version
        embed.set_footer(
            text=(
                f"Written in Python with enhanced-dpy v{enhanced_dpy_version} "
                "| This bot is not made or maintained by Discord itself"
            )
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            emoji="\N{HOT BEVERAGE}",
            label="Buy me a coffee",
            url="https://ko-fi.com/fuzzysearch"
        ))
        view.add_item(discord.ui.Button(
            emoji="\N{BLUE HEART}",
            label="Help to cover hosting expenses via PayPal",
            url="https://paypal.me/fuzzysearch"
        ))

        await self.reply(embed=embed, view=view)


def setup(client) -> list:
    return [InformationCollection(client)]

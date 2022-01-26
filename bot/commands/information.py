import typing
import discord
from typing import Optional

from .util import commands
from .util import exceptions


class InformationCollection(commands.FarmCommandCollection):
    """\N{NEWSPAPER} Get the latest information about the bot - news, events, links, etc."""

    def __init__(self, client):
        super().__init__(client, [HelpCommand], name="Information")


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
        options = {}

        for category in self.client.command_collections.values():
            if category.hidden_in_help_command:
                continue

            for command in category.commands:
                # Hide owner only commands
                if command.owner_only:
                    continue
                # Hide guild specific commands if not in the same guild
                if command._guilds_ and self.interaction.guild_id not in command._guilds_:
                    continue

                full_name = command.get_full_name(command)
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

        if param_descriptions:
            embed.description += "\n\n__Parameters:__\n"
            embed.description += "\n".join(param_descriptions)

            embed.description += (
                "\n\nOkay that's all cool, but what are those brackets for? \N{THINKING FACE}\n"
                "It's easy - something in `[]` means that the parameter is optional, "
                "`<>` means that it is required."
            )

        await self.reply(embed=embed)

    async def callback(self):
        if self.command:
            return await self.send_command_help()

        await self.reply("Help paginator")


def setup(client) -> list:
    return [InformationCollection(client)]

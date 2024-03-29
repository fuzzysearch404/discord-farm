import discord
import difflib
import traceback
import itertools
from discord.ext import modules

from . import time
from . import embeds
from bot.commands.util import exceptions


AUTOCOMPLETE_RESULTS_LIMIT = 25
AUTOCOMPLETE_CLOSE_MATCHES_CUTOFF = 0.75


class ReportCrashModal(discord.ui.Modal):

    def __init__(self, command, error: Exception) -> None:
        super().__init__("Report this crash to the developers")
        self.command = command
        self.error = error

        self.add_item(
            discord.ui.TextInput(
                label="How did this crash happen?",
                value="This crash happened as I... ",
                style=discord.TextInputStyle.long,
                max_length=1000
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Thanks! We will look into this as soon as possible.",
            ephemeral=True
        )
        embed = discord.Embed(title="Crash report", color=discord.Color.red())

        exc_info = (type(self.error), self.error, self.error.__traceback__)
        exc_fmt = "".join(traceback.format_exception(*exc_info))
        embed.description = f"{self.children[0].value}\n\n```py\n{exc_fmt}```"

        embed.set_author(name=f"{interaction.user} ({interaction.user.id})")
        embed.set_footer(text=f"Command: /{self.command.get_full_name()}")
        await self.command.client.log_to_discord("Crash report:", embed=embed)


class CrashReportView(discord.ui.View):

    def __init__(self, command, error: Exception):
        super().__init__(timeout=60)
        self.command = command
        self.error = error

    @discord.ui.button(label="Report this crash", style=discord.ButtonStyle.secondary)
    async def open_modal(self, button: discord.Button, interaction: discord.Interaction):
        modal = ReportCrashModal(self.command, self.error)
        await interaction.response.send_modal(modal)


class FarmCommandCollection(modules.CommandCollection):
    """Base class for all command collections."""
    hidden_in_help_command: bool = False
    help_emoji: str = None
    help_short_description: str = None


class _DBContextAcquire:

    __slots__ = ("command", "timeout")

    def __init__(self, command, timeout):
        self.command = command
        self.timeout = timeout

    def __await__(self):
        return self.command._acquire(self.timeout).__await__()

    async def __aenter__(self):
        await self.command._acquire(self.timeout)
        return self.command.db

    async def __aexit__(self, *args):
        await self.command.release()


class FarmSlashCommand(discord.app.SlashCommand):
    """Base class for all slash commands."""
    _avoid_maintenance: bool = True
    _owner_only: bool = False
    _requires_account: bool = True
    _required_level: int = 0
    _invoke_cooldown: int = None  # Negative = Shows as "Varying" in help
    _inner_cooldown: int = None  # Managed inside of the command itself
    # The below ones are not for touching
    _db = None
    _level_up: bool = False

    @property
    def author(self) -> discord.User:
        return self.interaction.user

    @property
    def message(self) -> discord.Message:
        return self.interaction.message

    @property
    def channel(self) -> discord.TextChannel:
        return self.interaction.channel

    @property
    def guild(self) -> discord.Guild:
        return self.interaction.guild

    @property
    def permissions(self) -> discord.Permissions:
        return self.interaction.permissions

    @property
    def followup(self) -> discord.Webhook:
        return self.interaction.followup

    @property
    def redis(self):
        return self.client.redis

    @property
    def db(self):
        return self._db if self._db else self.client.db_pool

    @property
    def items(self):
        return self.client.item_pool

    @property
    def users(self):
        return self.client.user_cache

    def _inject_level_up_embed(self, **kwargs) -> dict:
        if not self._level_up:
            return kwargs

        current_embed = kwargs.get("embed", None)
        current_embeds = kwargs.get("embeds", [])
        if current_embed:
            kwargs.pop("embed")
            current_embeds.append(current_embed)
        current_embeds.append(embeds.level_up(self))
        kwargs["embeds"] = current_embeds

        self._level_up = False
        return kwargs

    async def reply(self, *args, **kwargs) -> None:
        kwargs = self._inject_level_up_embed(**kwargs)
        return await self.interaction.response.send_message(*args, **kwargs)

    async def edit(self, *args, **kwargs) -> None:
        kwargs = self._inject_level_up_embed(**kwargs)
        return await self.interaction.edit_original_message(*args, **kwargs)

    def get_full_name(self) -> str:
        """Concats the full name of the command"""
        fmt = self._name_

        if self._parent_:
            fmt = f"{self._parent_.get_full_name(self._parent_)} {fmt}"

        return fmt

    def find_all_lowest_children(self) -> list:
        """Finds all lowest level subcommands for this command (might include self)"""
        results = []

        if self._children_:
            for child in self._children_.values():
                results.extend(child.find_all_lowest_children(child))
        else:
            results.append(self)

        return results

    async def pre_check(self) -> bool:
        if self._avoid_maintenance and self.client.maintenance_mode:
            if not await self.client.is_owner(self.author):
                raise exceptions.GameIsInMaintenanceException()

        if self._owner_only and not await self.client.is_owner(self.author):
            raise exceptions.CommandOwnerOnlyException()

        if self._requires_account:
            try:
                self.user_data = await self.users.get_user(self.author.id)
            except exceptions.UserNotFoundException:
                raise exceptions.UserNotFoundException(
                    "Hey there! It looks like you don't have a game account yet! "
                    "Type **/account create** and let's get your farming journey started! "
                    "\N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE}"
                )

            if self._required_level > self.user_data.level:
                raise exceptions.InsufficientUserLevelException(self._required_level)

        # Check last, to not trigger cooldown if something above failed
        if self._invoke_cooldown is not None:
            cmd_id = self.get_full_name()
            command_ttl = await self.redis.execute_command("TTL", f"cd:{self.author.id}:{cmd_id}")

            if command_ttl == -2:
                await self.redis.execute_command(
                    "SET", f"cd:{self.author.id}:{cmd_id}", cmd_id, "EX", self._invoke_cooldown
                )
            else:
                ttl_fmt = time.seconds_to_time(command_ttl)
                raise exceptions.CommandOnCooldownException(
                    f"\N{ALARM CLOCK} This command is on a cooldown for **{ttl_fmt}**!"
                )

        return True

    async def error(self, exception: Exception) -> None:
        responded = self.interaction.response.is_done()

        if isinstance(exception, exceptions.FarmException):
            if exception.embed:
                if not responded:
                    await self.reply(embed=exception.embed, ephemeral=exception.ephemeral)
                else:
                    await self.edit(embed=exception.embed)
            else:
                if not responded:
                    await self.reply(
                        f"\N{CROSS MARK} {str(exception)}",
                        ephemeral=exception.ephemeral
                    )
                else:
                    await self.edit(content=f"\N{CROSS MARK} {str(exception)}")
        else:
            await self.release()  # If there is a stale database connection - release it

            message = (
                "\N{CROSS MARK} Sorry, an unexpected error occurred, while running this command.\n"
                "\N{PLUNGER} Please try again later. If this issue persists, please report this "
                "to the official support server with as many details, as possible. "
                "Alternatively, you can fill out a crash report below. "
            )
            view = CrashReportView(self, exception)

            if not responded:
                await self.reply(message, view=view, ephemeral=True)
            else:
                await self.edit(content=message, view=view)

            await super().error(exception)

    @staticmethod
    def _find_items_for_autocomplete(item_names_per_id: dict, query: str) -> dict:
        options = {}

        if len(query) == 0:
            for tpl, _ in zip(item_names_per_id.items(), range(AUTOCOMPLETE_RESULTS_LIMIT)):
                options[tpl[0]] = str(tpl[1])
        else:
            for name, id in item_names_per_id.items():
                if name.lower().startswith(query.lower()):
                    options[name] = str(id)

        return dict(itertools.islice(options.items(), AUTOCOMPLETE_RESULTS_LIMIT))

    def all_items_autocomplete(self, query: str) -> dict:
        return self._find_items_for_autocomplete(self.items.all_item_ids_by_name, query)

    def plantables_autocomplete(self, query: str) -> dict:
        return self._find_items_for_autocomplete(self.items.all_plantable_ids_by_name, query)

    def products_autocomplete(self, query: str) -> dict:
        return self._find_items_for_autocomplete(self.items.all_product_ids_by_name, query)

    def chests_autocomplete(self, query: str) -> dict:
        return self._find_items_for_autocomplete(self.items.all_chest_ids_by_name, query)

    def booster_autocomplete(self, query: str) -> dict:
        return self._find_items_for_autocomplete(self.items.all_boost_ids_by_name, query)

    async def lookup_other_player(self, user: discord.Member, conn=None):
        try:
            return await self.users.get_user(user.id, conn=conn)
        except exceptions.UserNotFoundException:
            raise exceptions.UserNotFoundException(
                f"Whoops. {user.mention} doesn't have a game account yet! "
                "Maybe consider inviting them to join this game? \N{THINKING FACE}"
            )

    @staticmethod
    def _lookup_close_match(query: str, items: dict):
        matches = difflib.get_close_matches(
            query.lower(),
            items.keys(),
            n=1,
            cutoff=AUTOCOMPLETE_CLOSE_MATCHES_CUTOFF
        )
        return items[matches[0]] if matches else None

    def lookup_item(self, item_id_or_name: str):
        try:  # Use only first 8 digits, because the ids will never be that huge
            query = int(item_id_or_name[:8])
        except ValueError:
            # Try searching for close matches
            query = self._lookup_close_match(item_id_or_name, self.items.all_item_ids_by_name)

        try:
            return self.items.find_item_by_id(query)
        except exceptions.ItemNotFoundException:
            raise exceptions.ItemNotFoundException(
                f"Whoops. I could not find an item called \"{item_id_or_name}\". \N{WORRIED FACE}\n"
                "\N{RIGHT-POINTING MAGNIFYING GLASS} Could you please take this magnifying glass "
                "and try searching again?"
            )

    def lookup_chest(self, item_id_or_name: str):
        try:  # Use only first 8 digits, because the ids will never be that huge
            query = int(item_id_or_name[:8])
        except ValueError:
            # Try searching for close matches
            query = self._lookup_close_match(item_id_or_name, self.items.all_chest_ids_by_name)

        try:
            # Use only first 8 digits, because the ids will never be that huge
            return self.items.find_chest_by_id(query)
        except exceptions.ItemNotFoundException:
            raise exceptions.ItemNotFoundException(
                f"Whoops. I could not find a chest called \"{item_id_or_name}\". \N{WORRIED FACE}\n"
                "\N{RIGHT-POINTING MAGNIFYING GLASS} Could you please take this magnifying glass "
                "and try searching again?"
            )

    def lookup_booster(self, item_id_or_name: str):
        if item_id_or_name in self.items.all_boost_ids_by_name.values():
            query = item_id_or_name
        else:
            # TODO: Boost names are case sensitive :(
            query = self._lookup_close_match(item_id_or_name, self.items.all_boost_ids_by_name)

        try:
            return self.items.find_booster_by_id(query)
        except exceptions.ItemNotFoundException:
            raise exceptions.ItemNotFoundException(
                f"Whoops. I could not find a booster called \"{item_id_or_name}\". \N{WORRIED FACE}"
                "\n\N{RIGHT-POINTING MAGNIFYING GLASS} Could you please take this magnifying glass "
                "and try searching again?"
            )

    async def get_cooldown_ttl(self, identifier: str, other_user_id: int = None):
        user_id = self.author.id if other_user_id is None else other_user_id
        command_ttl = await self.redis.execute_command("TTL", f"cd:{user_id}:{identifier}")

        return False if command_ttl == -2 else command_ttl

    async def set_cooldown(self, duration: int, identifier: str) -> None:
        await self.redis.execute_command(
            "SET", f"cd:{self.author.id}:{identifier}", identifier, "EX", duration
        )

    async def _acquire(self, timeout: float):
        if self._db is None:
            self._db = await self.client.db_pool.acquire(timeout=timeout)

        return self._db

    def acquire(self, *, timeout: float = 300.0) -> _DBContextAcquire:
        """Acquires database pool connection"""
        return _DBContextAcquire(self, timeout)

    async def release(self) -> None:
        """Releases database pool connection, if acquired"""
        if self._db is not None:
            await self.client.db_pool.release(self._db)
            self._db = None


def format_docstring_help(doc: str) -> str:
    """
    Removes new line characters from the docstring and then replaces our new line placeholders with
    actual newline characters. Also strips the string just in case.
    """
    return " ".join(doc.split()).replace("<br>", "\n")

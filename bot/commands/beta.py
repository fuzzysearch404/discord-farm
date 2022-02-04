import discord
import datetime

from core import static
from core import game_items
from .util import exceptions
from .util.commands import FarmSlashCommand, FarmCommandCollection


class BetaCollection(FarmCommandCollection):
    """Beta version only commands for testing purposes."""
    hidden_in_help_command: bool = True

    def __init__(self, client):
        super().__init__(client, [BetaCommand], name="Beta")

    async def collection_check(self, command) -> None:
        # I am aware that this is a double check when using "owner_only" = True
        if not await self.client.is_owner(command.author):
            raise exceptions.CommandOwnerOnlyException()


class BetaCommand(FarmSlashCommand, name="beta", guilds=static.DEVELOPMENT_GUILD_IDS):
    pass


class SetCommand(FarmSlashCommand, name="set", parent=BetaCommand):
    pass


class SetGoldCommand(
    FarmSlashCommand,
    name="gold",
    description="\N{TEST TUBE} [Beta only] Sets the gold amount",
    parent=SetCommand
):
    owner_only = True  # type: bool

    gold: int = discord.app.Option(description="User's new gold amount")

    async def callback(self) -> None:
        self.user_data.gold = self.gold
        await self.users.update_user(self.user_data)
        await self.reply(f"Gold set to {self.user_data.gold}")


class SetGemsCommand(
    FarmSlashCommand,
    name="gems",
    description="\N{TEST TUBE} [Beta only] Sets the gems amount",
    parent=SetCommand
):
    owner_only = True  # type: bool

    gems: int = discord.app.Option(description="User's new gems amount")

    async def callback(self) -> None:
        self.user_data.gems = self.gems
        await self.users.update_user(self.user_data)
        await self.reply(f"Gems set to {self.user_data.gems}")


class SetXPCommand(
    FarmSlashCommand,
    name="xp",
    description="\N{TEST TUBE} [Beta only] Sets the XP amount",
    parent=SetCommand
):
    owner_only = True  # type: bool

    xp: int = discord.app.Option(description="User's new XP amount")

    async def callback(self) -> None:
        self.user_data.xp = self.xp
        self.user_data.level, self.user_data.next_level_xp = self.user_data._calculate_user_level()
        await self.users.update_user(self.user_data)
        await self.reply(f"XP set to {self.user_data.xp} (level {self.user_data.level})")


class SetFarmSizeCommand(
    FarmSlashCommand,
    name="farmsize",
    description="\N{TEST TUBE} [Beta only] Sets the farm size",
    parent=SetCommand
):
    owner_only = True  # type: bool

    size: int = discord.app.Option(description="User's new farm size")

    async def callback(self) -> None:
        self.user_data.farm_slots = self.size
        await self.users.update_user(self.user_data)
        await self.reply(f"Farm size set to {self.user_data.farm_slots}")


class SetFactorySizeCommand(
    FarmSlashCommand,
    name="factorysize",
    description="\N{TEST TUBE} [Beta only] Sets the factory size",
    parent=SetCommand
):
    owner_only = True  # type: bool

    size: int = discord.app.Option(description="User's new factory size")

    async def callback(self) -> None:
        self.user_data.factory_slots = self.size
        await self.users.update_user(self.user_data)
        await self.reply(f"Factory size set to {self.user_data.factory_slots}")


class SetItemCommand(
    FarmSlashCommand,
    name="item",
    description="\N{TEST TUBE} [Beta only] Gets game items",
    parent=SetCommand
):
    owner_only = True  # type: bool

    item: str = discord.app.Option(description="Item to add", autocomplete=True)
    amount: int = discord.app.Option(description="How many items to add")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.all_items_autocomplete(options[focused]))

    async def callback(self) -> None:
        item = self.lookup_item(self.item)
        await self.user_data.give_item(self, item.id, self.amount)
        await self.reply(f"Obtained {self.amount}x {item.full_name}")


class SetChestCommand(
    FarmSlashCommand,
    name="chest",
    description="\N{TEST TUBE} [Beta only] Gets chests",
    parent=SetCommand
):
    owner_only = True  # type: bool

    chest: str = discord.app.Option(description="Chest to add", autocomplete=True)
    amount: int = discord.app.Option(description="How many chests to add")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.chests_autocomplete(options[focused]))

    async def callback(self) -> None:
        chest = self.lookup_chest(self.chest)
        await self.user_data.give_item(self, chest.id, self.amount)
        await self.reply(f"Obtained {self.amount}x {chest.full_name} chests")


class SetBoosterCommand(
    FarmSlashCommand,
    name="booster",
    description="\N{TEST TUBE} [Beta only] Gets booster",
    parent=SetCommand
):
    owner_only = True  # type: bool

    booster: str = discord.app.Option(description="Booster to add", autocomplete=True)
    duration: int = discord.app.Option(description="Duration in seconds")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.booster_autocomplete(options[focused]))

    async def callback(self) -> None:
        booster = self.lookup_booster(self.booster)
        ends = datetime.datetime.now() + datetime.timedelta(seconds=self.duration)
        boost = game_items.PartialBoost(booster.id, ends)
        await self.user_data.give_boost(self, boost)
        await self.reply(f"Obtained {booster.name} for {self.duration} seconds")


class ActionsCommand(FarmSlashCommand, name="actions", parent=BetaCommand):
    pass


class ActionsFlushRedisCommand(
    FarmSlashCommand,
    name="flushredis",
    description="\N{TEST TUBE} [Beta only] Flushes the redis database",
    parent=ActionsCommand
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool
    owner_only = True  # type: bool

    async def callback(self) -> None:
        await self.client.redis.flushdb()
        await self.reply("Redis database flushed")


def setup(client) -> list:
    return [BetaCollection(client)]

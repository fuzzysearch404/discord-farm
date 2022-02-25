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
        # I am aware that this is a double check when using "_owner_only" = True
        if not await self.client.is_owner(command.author):
            raise exceptions.CommandOwnerOnlyException()


class BetaCommand(FarmSlashCommand, name="beta", guilds=static.DEVELOPMENT_GUILD_IDS):
    _owner_only: bool = True


class SetCommand(BetaCommand, name="set", parent=BetaCommand):
    pass


class SetGoldCommand(
    SetCommand,
    name="gold",
    description="\N{TEST TUBE} [Beta only] Sets the gold amount",
    parent=SetCommand
):
    gold: int = discord.app.Option(description="User's new gold amount")

    async def callback(self) -> None:
        self.user_data.gold = self.gold
        await self.users.update_user(self.user_data)
        await self.reply(f"Gold set to {self.user_data.gold}")


class SetGemsCommand(
    SetCommand,
    name="gems",
    description="\N{TEST TUBE} [Beta only] Sets the gems amount",
    parent=SetCommand
):
    gems: int = discord.app.Option(description="User's new gems amount")

    async def callback(self) -> None:
        self.user_data.gems = self.gems
        await self.users.update_user(self.user_data)
        await self.reply(f"Gems set to {self.user_data.gems}")


class SetXPCommand(
    SetCommand,
    name="xp",
    description="\N{TEST TUBE} [Beta only] Sets the XP amount",
    parent=SetCommand
):
    xp: int = discord.app.Option(description="User's new XP amount")

    async def callback(self) -> None:
        self.user_data.xp = self.xp
        self.user_data.level, self.user_data.next_level_xp = self.user_data._calculate_user_level()
        await self.users.update_user(self.user_data)
        await self.reply(f"XP set to {self.user_data.xp} (level {self.user_data.level})")


class SetFarmSizeCommand(
    SetCommand,
    name="farmsize",
    description="\N{TEST TUBE} [Beta only] Sets the farm size",
    parent=SetCommand
):
    size: int = discord.app.Option(description="User's new farm size")

    async def callback(self) -> None:
        self.user_data.farm_slots = self.size
        await self.users.update_user(self.user_data)
        await self.reply(f"Farm size set to {self.user_data.farm_slots}")


class SetFactorySizeCommand(
    SetCommand,
    name="factorysize",
    description="\N{TEST TUBE} [Beta only] Sets the factory size",
    parent=SetCommand
):
    size: int = discord.app.Option(description="User's new factory size")

    async def callback(self) -> None:
        self.user_data.factory_slots = self.size
        await self.users.update_user(self.user_data)
        await self.reply(f"Factory size set to {self.user_data.factory_slots}")


class SetItemCommand(
    SetCommand,
    name="item",
    description="\N{TEST TUBE} [Beta only] Gets game items",
    parent=SetCommand
):
    item: str = discord.app.Option(description="Item to add", autocomplete=True)
    amount: int = discord.app.Option(description="How many items to add")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.all_items_autocomplete(options[focused]))

    async def callback(self) -> None:
        item = self.lookup_item(self.item)
        async with self.acquire() as conn:
            await self.user_data.give_item(item.id, self.amount, conn)
        await self.reply(f"Obtained {self.amount}x {item.full_name}")


class SetChestCommand(
    SetCommand,
    name="chest",
    description="\N{TEST TUBE} [Beta only] Gets chests",
    parent=SetCommand
):
    chest: str = discord.app.Option(description="Chest to add", autocomplete=True)
    amount: int = discord.app.Option(description="How many chests to add")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.chests_autocomplete(options[focused]))

    async def callback(self) -> None:
        chest = self.lookup_chest(self.chest)
        async with self.acquire() as conn:
            await self.user_data.give_item(chest.id, self.amount, conn)
        await self.reply(f"Obtained {self.amount}x {chest.full_name} chests")


class SetBoosterCommand(
    SetCommand,
    name="booster",
    description="\N{TEST TUBE} [Beta only] Gets booster",
    parent=SetCommand
):
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


class ActionsCommand(BetaCommand, name="actions", parent=BetaCommand):
    pass


class ActionsFlushRedisCommand(
    ActionsCommand,
    name="flushredis",
    description="\N{TEST TUBE} [Beta only] Flushes the redis database",
    parent=ActionsCommand
):
    _avoid_maintenance: bool = False
    _requires_account: bool = False

    async def callback(self) -> None:
        await self.client.redis.flushdb()
        await self.reply("Redis database flushed")


def setup(client) -> list:
    return [BetaCollection(client)]

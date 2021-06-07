from discord.ext import commands

from core import game_items
from core import exceptions


def _string_and_optional_int_splitter(argument) -> tuple:
    """
    This cuts off and tries to cast last potential integer from string
    after last whitespace. If there is no integer, then defaults to 1.
    """
    item = argument
    amount = 1

    split_arg = argument.rsplit(" ", 1)

    try:
        possible_amount = split_arg[1]
        amount = int(possible_amount)

        item = split_arg[0]
    except Exception:
        pass

    return item, amount


def _amount_conversion(argument) -> int:
    try:
        amount = int(argument)
    except ValueError:
        raise exceptions.InvalidAmountException(
            "Hey buddy, please provide amount with numbers. For example: 123"
        )

    if amount < 1 or amount > 1_000_000:
        raise exceptions.InvalidAmountException(
            "Please provide amount in range 1 - 1,000,000 (one million)"
        )

    return amount


def _item_conversion(ctx, argument) -> game_items.GameItem:
    try:
        item_id = int(argument)
        item = ctx.bot.item_pool.find_item_by_id(item_id)

        return item
    except Exception:
        pass

    try:
        return ctx.bot.item_pool.find_item_by_name(argument.lower())
    except exceptions.ItemNotFoundException:
        # I know, that I could just raise,
        # but I just want a friendlier message
        raise exceptions.ItemNotFoundException(
            f"I could not find item \"{argument}\". \ud83d\ude10\n"
            "\ud83d\udca1 Check out item names and IDs you have unlocked with "
            f"**{ctx.prefix}allitems** and try again."
        )


def _chest_conversion(ctx, argument) -> game_items.Chest:
    try:
        chest_id = int(argument)
        chest = ctx.bot.item_pool.find_chest_by_id(chest_id)

        return chest
    except Exception:
        pass

    try:
        # Chest names do not contain word "chest"
        argument = argument.replace("chest", "")

        return ctx.bot.item_pool.find_chest_by_name(argument.lower())
    except exceptions.ItemNotFoundException:
        raise exceptions.ItemNotFoundException(
            f"I could not find chest \"{argument}\". \ud83d\ude10\n"
            f"\ud83d\udca1 Check out chest names with **{ctx.prefix}chests** "
            "and try again."
        )


def _boost_conversion(ctx, argument) -> game_items.Boost:
    try:
        item = ctx.bot.item_pool.find_boost_by_id(argument)

        return item
    except exceptions.ItemNotFoundException:
        pass

    try:
        return ctx.bot.item_pool.find_boost_by_name(argument.lower())
    except exceptions.ItemNotFoundException:
        raise exceptions.ItemNotFoundException(
            f"I could not find boost \"{argument}\". \ud83d\ude10\n"
            "\ud83d\udca1 Maybe you made some kind of typo?"
        )


class Item(commands.Converter):
    async def convert(self, ctx, argument) -> game_items.GameItem:
        return _item_conversion(ctx, argument)


class ItemAndAmount(commands.Converter):
    async def convert(self, ctx, argument) -> tuple:
        item_str, amount = _string_and_optional_int_splitter(argument)

        item = _item_conversion(ctx, item_str)
        amount = _amount_conversion(amount)

        return item, amount


class Chest(commands.Converter):
    async def convert(self, ctx, argument) -> game_items.Chest:
        return _chest_conversion(ctx, argument)


class ChestAndAmount(commands.Converter):
    async def convert(self, ctx, argument) -> tuple:
        chest_str, amount = _string_and_optional_int_splitter(argument)

        chest = _chest_conversion(ctx, chest_str)
        amount = _amount_conversion(amount)

        return chest, amount


class Boost(commands.Converter):
    async def convert(self, ctx, argument) -> game_items.Boost:
        return _boost_conversion(ctx, argument)


class BoostAndAmount(commands.Converter):
    async def convert(self, ctx, argument) -> game_items.Boost:
        boost_str, amount = _string_and_optional_int_splitter(argument)

        boost = _boost_conversion(ctx, boost_str)
        amount = _amount_conversion(amount)

        return boost, amount


class Amount(commands.Converter):
    async def convert(self, ctx, argument) -> int:
        return _amount_conversion(argument)

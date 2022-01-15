
from discord import Member
from discord.ext import commands

from core import exceptions


def user_cooldown(cooldown: int, identifier: str = None) -> commands.check:
    async def predicate(ctx) -> bool:
        cmd_id = ctx.command.qualified_name if identifier is None else identifier

        command_ttl = await ctx.bot.redis.execute_command(
            "TTL", f"cd:{ctx.author.id}:{cmd_id}"
        )

        if command_ttl == -2:
            await ctx.bot.redis.execute_command(
                "SET", f"cd:{ctx.author.id}:{cmd_id}", cmd_id, "EX", cooldown,
            )

            return True
        else:
            raise commands.CommandOnCooldown(ctx, command_ttl, commands.BucketType.user)

    return commands.check(predicate)


async def get_user_cooldown(ctx, identifier: str, other_user_id: int = 0):
    # other_user_id is used if we want to check other user's cooldown
    user_id = other_user_id if other_user_id else ctx.author.id

    command_ttl = await ctx.bot.redis.execute_command(
        "TTL", f"cd:{user_id}:{identifier}"
    )

    if command_ttl == -2:
        return False
    else:
        return command_ttl


async def set_user_cooldown(ctx, cooldown: int, identifier: str) -> None:
    await ctx.bot.redis.execute_command(
        "SET", f"cd:{ctx.author.id}:{identifier}", identifier, "EX", cooldown,
    )


def has_account() -> commands.check:
    async def pred(ctx) -> bool:
        try:
            ctx.user_data = await ctx.users.get_user(ctx.author.id)
            return True
        except exceptions.UserNotFoundException:
            raise exceptions.UserNotFoundException(
                "Hey there! It looks like you don't have a game account yet! "
                "Type **/register** and let's get started!"
                "\ud83d\udc68\u200d\ud83c\udf3e"
            )

    return commands.check(pred)


async def get_other_member(ctx, member: Member, conn=None):
    try:
        return await ctx.users.get_user(member.id, conn=conn)
    except exceptions.UserNotFoundException:
        raise exceptions.UserNotFoundException(
            f"Whoops. {member.mention} does not have a farm. "
            "Maybe tell them to check this bot out? \ud83e\udd14"
        )


def avoid_maintenance() -> commands.check:
    async def pred(ctx) -> bool:
        if not ctx.bot.maintenance_mode or await ctx.bot.is_owner(ctx.author):
            return True

        raise exceptions.GameIsInMaintenance(
            "Game commands are disabled for a bot maintenance or update.\n"
            "\ud83d\udd50 Please try again after a while...\n"
            "\ud83d\udcf0 For more information use command - **/news**"
        )

    return commands.check(pred)

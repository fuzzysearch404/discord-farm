from discord.ext import commands
from discord import Member

class GameIsInMaintenance(commands.CheckFailure):
    """Exception raised when game is in maintenance."""

    pass

class MissingEmbedPermissions(commands.CheckFailure):
    """Exception raised when bot cannot send embeds."""

    pass

class MissingAddReactionPermissions(commands.CheckFailure):
    """Exception raised when bot cannot add reactions."""

    pass

class MissingReadMessageHistoryPermissions(commands.CheckFailure):
    """Exception raised when bot cannot read message history."""

    pass

class GlobalCooldown(commands.CommandOnCooldown):
    """Exception raised when global cooldown is reache."""
    
    pass


def is_owner():
    async def pred(ctx):
        return ctx.author.id in ctx.bot.owner_ids
    return commands.check(pred)


def is_owner_raw(ctx):
    return ctx.author.id in ctx.bot.owner_ids

def user_cooldown(cooldown: int, identifier: str = None):
    async def predicate(ctx):
        if identifier is None:
            cmd_id = ctx.command.qualified_name
        else:
            cmd_id = identifier
        command_ttl = await ctx.bot.redis.execute("TTL", f"cd:{ctx.author.id}:{cmd_id}")
        if command_ttl == -2:
            await ctx.bot.redis.execute(
                "SET", f"cd:{ctx.author.id}:{cmd_id}", cmd_id, "EX", cooldown,
            )
            return True
        else:
            raise commands.CommandOnCooldown(ctx, command_ttl)
            return False

    return commands.check(predicate)

async def get_user_cooldown(ctx, identifier: str):
    command_ttl = await ctx.bot.redis.execute("TTL", f"cd:{ctx.author.id}:{identifier}")
    if command_ttl == -2:
        return False
    else:
        return command_ttl

async def set_user_cooldown(ctx, cooldown: int, identifier: str):
    await ctx.bot.redis.execute(
        "SET", f"cd:{ctx.author.id}:{identifier}", identifier, "EX", cooldown,
    )

async def check_account_data(ctx, lurk=None):
    """Fetches user data from database. lurk: discord.Member."""
    if not lurk:
        userid = ctx.author.id
    else:
        userid = lurk.id

    query = """SELECT * FROM profile WHERE userid = $1;"""
    data = await ctx.bot.db.fetchrow(query, userid)

    if not data and not lurk:
        await ctx.send("\u274c You don't have an account for the game yet. Type `%register` to make a new farm! \ud83e\udd20")
    elif not data and lurk:
        await ctx.send("\u274c This user does not have game account. Maybe tell them to make one? \ud83e\udd14")

    return data

def avoid_maintenance():
    async def pred(ctx):
        if not ctx.bot.maintenance_mode or is_owner_raw(ctx):
            return True
        raise GameIsInMaintenance()

    return commands.check(pred)

def embed_perms():
    async def pred(ctx):
        if ctx.guild is not None:
            permissions = ctx.channel.permissions_for(ctx.guild.me)
        else:
            permissions = ctx.channel.permissions_for(ctx.bot.user)

        if permissions.embed_links:
            return True
        raise MissingEmbedPermissions('Bot does not have embed links permission.')

    return commands.check(pred)

def reaction_perms():
    async def pred(ctx):
        if ctx.guild is not None:
            permissions = ctx.channel.permissions_for(ctx.guild.me)
        else:
            permissions = ctx.channel.permissions_for(ctx.bot.user)

        if permissions.add_reactions:
            return True
        raise MissingAddReactionPermissions('Bot does not have add reactions permission.')

    return commands.check(pred)

def message_history_perms():
    async def pred(ctx):
        if ctx.guild is not None:
            permissions = ctx.channel.permissions_for(ctx.guild.me)
        else:
            permissions = ctx.channel.permissions_for(ctx.bot.user)

        if permissions.read_message_history:
            return True
        raise MissingReadMessageHistoryPermissions('Bot does not have read message history permission.')

    return commands.check(pred)

def can_clear_reactions(ctx):
    if ctx.guild is not None:
        permissions = ctx.channel.permissions_for(ctx.guild.me)
    else:
        permissions = ctx.channel.permissions_for(ctx.bot.user)

    if permissions.manage_messages:
        return True

    return False
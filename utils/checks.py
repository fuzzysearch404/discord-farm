from discord.ext import commands


def is_owner():
    async def pred(ctx):
        return ctx.author.id == 234622520739758080
    return commands.check(pred)


def is_owner_raw(ctx):
    return ctx.author.id == 234622520739758080

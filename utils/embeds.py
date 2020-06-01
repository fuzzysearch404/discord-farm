from discord import Embed


def errorembed(text, ctx=None, long=False, pm=False):
    if len(text) > 256 or long:
        embed = Embed(description=f'\u274c {text}', colour=13118229)
    else:
        embed = Embed(title=f'\u274c {text}', colour=13118229)
    if not pm:
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    else:
        embed.set_footer(text=f'Farm notification from {ctx.guild}', icon_url=ctx.guild.icon_url)
    return embed


def confirmembed(text, ctx=None, long=False, pm=False):
    if len(text) > 256 or long:
        embed = Embed(description=f'\u2705 {text}', colour=955920)
    else:
        embed = Embed(title=f'\u2705 {text}', colour=955920)
    if not pm:
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    else:
        embed.set_footer(text=f'Farm notification from {ctx.guild}', icon_url=ctx.guild.icon_url)
    return embed


def congratzembed(text, ctx=None, long=False, pm=False):
    if len(text) > 256 or long:
        embed = Embed(description=f'\ud83c\udf89 {text}', colour=16776970)
    else:
        embed = Embed(title=f'\ud83c\udf89 {text}', colour=16776970)
    if not pm:
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    else:
        embed.set_footer(text=f' Farm notification from {ctx.guild}', icon_url=ctx.guild.icon_url)
    return embed

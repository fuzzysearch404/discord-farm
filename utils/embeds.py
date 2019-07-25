from discord import Embed


def errorembed(text, ctx):
    embed = Embed(title=f'\u274c {text}', colour=13118229)
    embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    return embed


def confirmembed(text, ctx):
    embed = Embed(title=f'\u2705 {text}', colour=955920)
    embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    return embed


def congratzembed(text, ctx):
    embed = Embed(title=f'\ud83c\udf89 {text}', colour=16776970)
    embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
    return embed

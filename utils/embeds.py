from discord import Embed


def errorembed(text):
    return Embed(title=f'\u274c {text}', colour=13118229)


def confirmembed(text):
    return Embed(title=f'\u2705 {text}', colour=955920)

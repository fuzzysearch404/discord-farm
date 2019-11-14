from discord.ext import commands
import discord


class MessageID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MessageConverter().convert(ctx, argument)
        except commands.BadArgument:
            embed = discord.Embed(colour=16716085, description="\N{CROSS MARK} Invalid message object")
            await ctx.send(embed=embed)
            raise commands.BadArgument(f"{argument} is not a valid message or message ID.") from None
        return m


class MemberNotFound(Exception):
    pass


async def resolve_member(guild, member_id):
    member = guild.get_member(member_id)
    if member is None:
        if guild.chunked:
            raise MemberNotFound()
        try:
            member = await guild.fetch_member(member_id)
        except discord.NotFound:
            raise MemberNotFound() from None
    return member


class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
                m = await resolve_member(ctx.guild, member_id)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
            except MemberNotFound:
                # hackban case
                return discord.Object(id=member_id)
        return m

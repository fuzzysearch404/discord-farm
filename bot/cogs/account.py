from discord.ext import commands

from .utils import checks
from .utils import embeds
from .utils.pages import ConfirmPromptCheck


class Account(commands.Cog):
    """
    Commands for managing your game account.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command(aliases=["start"])
    @checks.avoid_maintenance()
    async def register(self, ctx):
        """
        \ud83c\udd95 Creates a new game account

        You can only use this command if you don't already have an account.
        """
        async with ctx.db.acquire() as conn:
            if await ctx.users.get_user(ctx.author.id, conn=conn):
                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="You already own a farm!",
                        text=(
                            "What do you mean? You already own a cool farm! "
                            "It's time to get back working on the field. "
                            "There's always lots of work to do! "
                            "\ud83d\udc68\u200d\ud83c\udf3e"
                        ),
                        footer=(
                            "Maybe plant some lettuce? Carrots? \ud83e\udd14"
                        ),
                        ctx=ctx
                    )
                )

            await ctx.users.create_user(ctx.author.id, conn=conn)

        await ctx.reply(
            embed=embeds.congratulations_embed(
                # TODO: Better starting tutorial
                title="Your new account is successfully created! \ud83e\udd73",
                text=(
                    f"Check out all commands with **{ctx.prefix}help**\n"
                    "For now, you should be interested in planting commands. "
                    "Firstly you need to plant and grow your first lettuce. "
                    "When it's ready, harvest it and sell it or complete some "
                    "delivery missions. \ud83d\udcdd"
                ),
                ctx=ctx
            )
        )

    @commands.command(aliases=["resetaccount"])
    @checks.user_cooldown(10)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def deleteaccount(self, ctx):
        """
        \u274c Deletes your farm and ALL your game data.

        There is no way to get your farm back after using this command,
        so be careful with your decision.
        However, you can start a new game any any time with the `register`
        command.
        """
        embed = embeds.prompt_embed(
            title="Woah. Are you really, really sure about that?",
            text=(
                "**This is going to delete ALL your current progress** "
                "in game, because then we are transfering your farm to Mary "
                "the pig \ud83d\udc37, and knowing that she is very greedy "
                "and she is never going to give it back to you, "
                "means that your farm is going to be lost FOREVER!"
                "\nBut you can start over again fresh any time... \ud83d\ude43"
            ),
            ctx=ctx
        )

        confirm, msg = await ConfirmPromptCheck(embed=embed).prompt(ctx)

        if not confirm:
            return

        await ctx.users.delete_user(self.bot, ctx.author.id)

        await msg.edit(
            embed=embeds.success_embed(
                title=(
                    f"Goodbye, {ctx.author}! Thanks for playing! \ud83d\udc4b"
                ),
                text=(
                    "Your account has been deleted! "
                    "If you ever consider playing again, then just type "
                    f"**{ctx.prefix}register** again and you are ready to go! "
                    "Take care for now! :)"
                ),
                footer="We are going to miss you!",
                ctx=ctx
            )
        )

    @commands.command(aliases=["dms"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def notifications(self, ctx):
        """
        \ud83d\udce7 Disables or enables Direct Message notifications.

        Allows to disable or reenable various notifications e.g.,
        notifications when someone accepts trade with you.
        """
        user = ctx.user_data
        user.notifications = not user.notifications

        await ctx.users.update_user(user)

        if not user.notifications:
            embed = embeds.success_embed(
                title="Direct message notifications disabled",
                text=(
                    "Okay, so: I told the *mail man* **not to "
                    "bother you** with all those private messages \ud83d\udced"
                ),
                footer=(
                    "He then said: \"Ehhh.. brrrhh.. Will do!\" \ud83d\udc74"
                ),
                ctx=ctx
            )
        else:
            embed = embeds.success_embed(
                title="Direct message notifications enabled",
                text=(
                    "Okay, so: I told the *mail man* **to "
                    "send you** private messages about the game \ud83d\udcec"
                ),
                footer=(
                    "He then said: \"Ehhh.. brrrhh.. Will do!\" \ud83d\udc74"
                ),
                ctx=ctx
            )

        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Account(bot))

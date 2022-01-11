import discord
from discord.ext import commands

from .utils import views
from .utils import checks
from .utils import embeds
from core import exceptions


class Account(commands.Cog):
    """
    Commands for managing your game account.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @property
    def help_meta(self) -> tuple:
        return ("\ud83d\udc64", "Manage your game account")

    async def send_disable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_cog = self.bot.get_cog("Clusters")
        if not cluster_cog:
            self.bot.log.critical("Reminder failed: Cluster cog not loaded!")
            return

        await cluster_cog.send_disable_reminders_message(user_id)

    async def send_enable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_cog = self.bot.get_cog("Clusters")
        if not cluster_cog:
            self.bot.log.critical("Reminder failed: Cluster cog not loaded!")
            return

        await cluster_cog.send_enable_reminders_message(user_id)

    async def send_delete_reminders_to_ipc(self, user_id: int) -> None:
        cluster_cog = self.bot.get_cog("Clusters")
        if not cluster_cog:
            self.bot.log.critical("Reminder failed: Cluster cog not loaded!")
            return

        await cluster_cog.send_delete_reminders_message(user_id)

    @commands.command()
    async def tutorial(self, ctx):
        """
        \ud83d\udcd6 Some quickstart tips for new players
        """
        embed = embeds.congratulations_embed(
            title="Welcome to your new farm! \ud83e\udd73",
            text=(
                "\"Who's this? Are you the new owner? Hey Bob, "
                "look at this - another owner - again! Anyways, welcome "
                "stranger! I have very limited time, but I will try to "
                "explain only the very basics to get you started. The rest "
                "of the stuff you will have to learn on your own...\""
                "\u261d\ufe0f\n\n\u231bWant to read this again later? "
                "Sure, just type **/tutorial**"
            ),
            ctx=ctx
        )

        embed.add_field(
            name="\ud83c\udfe1 Profile",
            value=(
                "The most important profile commands for beginners are:\n"
                "**/profile** - Your profile\n"
                "**/allitems** - Items you have unlocked\n"
                "**/inventory** - Your inventory\n"
                "**/item** - To view some items properties"
            )
        )
        embed.add_field(
            name="\ud83c\udf31 Farm: Planting",
            value=(
                "Your farm has a limited space to plant items in.\n"
                "Right now it is 2 space tiles, but you will be able "
                "to increase it later.\nThis means, that you can plant "
                "2 items at a time.\nYou have unlocked: \ud83e\udd6c Lettuce.\n"
                "Plant 2 lettuce items with the command: **/plant lettuce 2**.\n"
                "To view your farm, check out command **/farm**"
            )
        )
        embed.add_field(
            name="\ud83d\udd5d Farm: Waiting for harvest",
            value=(
                "Different items have different growing durations "
                "and durations while items can be harvested.\n"
                "For example, \ud83e\udd6c Lettuce grows for 2 "
                "minutes, and is harvestable for 3 minutes after those "
                "2 minutes of growing.\nIf you don't harvest your items in "
                "time - they get rotten (lost forever).\nTo monitor your "
                "farm, check out command: **/farm** frequently."
            )
        )
        embed.add_field(
            name="\ud83d\ude9c Farm: Harvesting items",
            value=(
                "When it is finally time to harvest, just use the "
                "**/harvest** command. All of the ready items will be "
                "automatically collected to your **/inventory**\n"
                "If some of your items get rotten - they are going to be "
                "discarded with this command, to free up your farm field space."
            )
        )
        embed.add_field(
            name=f"{ctx.bot.gold_emoji} Earning gold coins",
            value=(
                "You got the harvest? Nice!\nNow it is time to earn some coins.\n"
                "There are multiple ways for doing this, but for now, I "
                "will tell you about two of those:\n1) Selling items to "
                "market - quick way to turn your items into coins BUT the "
                "market prices are changing every hour, so you might not get any "
                "profit at all.\nExample for selling 20x lettuce: **/sell lettuce 20**\n"
                "2) Doing missions - these always get you some nice rewards, but "
                "they might be harder to complete.\nCheck them out: **/missions**"
            )
        )
        embed.add_field(
            name="\u2753 More features and getting help",
            value=(
                "These are just the very, very basics to get you started!\n"
                "There is so much more to do and explore!\n"
                "**Check out all of the bot's features with: /help**\n"
                "For command usage examples and more help, do **/help** `command_name`, "
                "where `command_name` is the name of the command you need help with."
            )
        )

        await ctx.reply(embed=embed)

    @commands.command()
    @checks.avoid_maintenance()
    async def register(self, ctx):
        """
        \ud83c\udd95 Creates a new game account

        You can only use this command if you don't already have an account.
        """
        async with ctx.db.acquire() as conn:
            try:
                await ctx.users.get_user(ctx.author.id, conn=conn)
            except exceptions.UserNotFoundException:
                pass
            else:
                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="You already own a farm!",
                        text=(
                            "What do you mean? You already own a cool farm! "
                            "It's time to get back working on the field. "
                            "There's always lots of work to do! "
                            "\ud83d\udc68\u200d\ud83c\udf3e"
                        ),
                        footer="Maybe plant some lettuce? Carrots? \ud83e\udd14",
                        ctx=ctx
                    )
                )

            await ctx.users.create_user(ctx.author.id, conn=conn)

        await self.tutorial.invoke(ctx)

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def deleteaccount(self, ctx):
        """
        \u274c Deletes your farm and ALL your game data

        There is no way to get your farm back after using this command,
        so be careful with your decision.
        However, you can start a new game any time with the **/register** command.
        """
        embed = embeds.prompt_embed(
            title="Woah. Are you really, really sure about that?",
            text=(
                "**This is going to delete ALL of your current progress in game**, "
                "because then we will be transfering your farm to Mary "
                "the pig \ud83d\udc37, and knowing that she is very greedy "
                "and she is never going to give it back to you, "
                "means that your farm is going to be lost FOREVER!\n"
                "But you can start over again fresh any time... \ud83d\ude43"
            ),
            ctx=ctx
        )

        prompt = views.ConfirmPromptView(
            initial_embed=embed,
            style=discord.ButtonStyle.primary,
            emoji="\u267b\ufe0f",
            label="Delete account forever",
            deny_label="Nevermind, I will just take a break..."
        )
        confirm, msg = await prompt.prompt(ctx)

        if not confirm:
            return

        await ctx.users.delete_user(ctx.author.id)
        # Don't bother the user with remaining remiders
        await self.send_delete_reminders_to_ipc(ctx.author.id)

        await msg.edit(
            embed=embeds.success_embed(
                title=f"Goodbye, {ctx.author.name}! Thanks for playing! \ud83d\udc4b",
                text=(
                    "Your account has been deleted! "
                    "If you ever consider playing again, then just type "
                    "**/register** again and you are ready to go! "
                    "Take care! Bye for now! :)"
                ),
                footer="We are going to miss you!",
                ctx=ctx
            ),
            view=None
        )

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def notifications(
        self,
        ctx,
        enable: bool = commands.Option(
            description="Set to True if you want to receive notifications, otherwise False"
        )
    ):
        """
        \ud83d\udce7 Disables or reenables notifications

        Allows to disable or reenable various notifications e.g.,
        private messages, when someone accepts trade with you, or
        chat mentions when your harvest is ready to be collected.
        Please note that the some notifications might not
        get delivered, so please don't fully rely on these.
        """
        ctx.user_data.notifications = enable
        await ctx.users.update_user(ctx.user_data)

        if not enable:
            embed = embeds.success_embed(
                title="Game notifications disabled",
                text=(
                    "\u26a0\ufe0f **It might take a few minutes for your new "
                    "notifcation settings to take effect**.\n"
                    "\ud83d\udced Okay, so: I told the *mail man* **not to "
                    "bother you** with all those messages."
                ),
                footer="He then said: \"Ehhh.. brrrhh.. Will do!\" \ud83d\udc74",
                ctx=ctx
            )
            await self.send_disable_reminders_to_ipc(ctx.author.id)
        else:
            embed = embeds.success_embed(
                title="Game notifications enabled",
                text=(
                    "\u26a0\ufe0f **It might take a few minutes for your new "
                    "notifcation settings to take effect**.\n"
                    "\ud83d\udcec Okay, so: I told the *mail man* **to "
                    "send you** messages about the game."
                ),
                footer="He then said: \"Ehhh.. brrrhh.. Will do!\" \ud83d\udc74",
                ctx=ctx
            )
            await self.send_enable_reminders_to_ipc(ctx.author.id)

        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Account(bot))

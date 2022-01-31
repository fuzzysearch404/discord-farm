import discord
import datetime

from .clusters import get_cluster_collection
from .util import embeds
from .util import exceptions
from .util import views
from .util.commands import FarmSlashCommand, FarmCommandCollection


class AccountCollection(FarmCommandCollection):
    """Commands for managing your game account."""
    help_emoji: str = "\N{BUSTS IN SILHOUETTE}"
    help_short_description: str = "Manage your game account"

    def __init__(self, client):
        super().__init__(client, [TutorialCommand, AccountCommand], name="Account")


class TutorialCommand(
    FarmSlashCommand,
    name="tutorial",
    description="\N{OPEN BOOK} Shows few brief tips for getting started"
):
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    async def callback(self) -> None:
        embed = embeds.congratulations_embed(
            title="Welcome to your new farm! \N{FACE WITH PARTY HORN AND PARTY HAT}",
            text=(
                "\"Who's this? Are you the new owner? Hey Bob, look at this - another "
                "owner - again! Anyways, welcome stranger! I have very limited time, "
                "but I will try to explain only the very basics to get you started. The rest "
                "of the stuff you will have to learn on your own...\" \N{WHITE UP POINTING INDEX}"
                "\n\n\N{HOURGLASS}Want to read this again later? Sure, just type **/tutorial**"
            ),
            cmd=self
        )

        embed.add_field(
            name="\N{HOUSE WITH GARDEN} Your farm profile",
            value=(
                "The most important general commands for beginners are:\n"
                "**/profile** - Your profile with general information\n"
                "**/inventory** - See your inventory\n"
                "**/items unlocked** - Find all items you have unlocked\n"
                "**/items inspect** - To view the unique properties of an item"
            )
        )
        embed.add_field(
            name="\N{SEEDLING} Farm: Planting",
            value=(
                "Your farm has a very limited space to plant items in.\n"
                "Right now it is 2 space tiles, but you will be able to increase it later.\n"
                "This means, that you can plant 2 items at a time.\n"
                "**You have unlocked: \N{LEAFY GREEN} Lettuce.**\n"
                "Plant 2 lettuce items with the command: **/farm plant** `lettuce` `2`.\n"
                "To view your farm, check out command **/farm field**"
            )
        )
        embed.add_field(
            name="\N{CLOCK FACE TWO-THIRTY} Farm: Waiting for harvest",
            value=(
                "Different items have different growing durations and durations while items can be "
                "harvested.\nFor example, \N{LEAFY GREEN} Lettuce grows for 2 minutes, and is "
                "harvestable for 3 minutes after those initial 2 minutes of growing.\n"
                "If you don't harvest your items in time - they get rotten (lost forever).\n"
                "To monitor your farm status, use the **/farm field** command frequently."
            )
        )
        embed.add_field(
            name="\N{TRACTOR} Farm: Harvesting items",
            value=(
                "When it is finally time to harvest, just use the **/farm harvest** command. "
                "All of the fully grown items are going to be automatically collected to your "
                "**/inventory**.\nIf some of your items are rotten - they are going to be "
                "discarded with this command too - to free up your farm field space for new items."
            )
        )
        embed.add_field(
            name=f"{self.client.gold_emoji} Earning gold coins",
            value=(
                "You got the harvest? Nice!\nNow it's time to earn some golden coins out of it.\n"
                "There are multiple ways for doing this, but for now, I am going to tell you about "
                "two of those:\n1) Selling items to the market - a quick way to turn your items "
                "into coins BUT the market prices are literally changing every hour, so you might "
                "not get any profit at all. Be careful.\nExample for selling 20x lettuce: "
                "**/market sell** `lettuce` `20`\n2) Doing order missions - these always will get "
                "you some decent rewards, but they might be harder to complete.\n"
                "Check them out with this command: **/missions orders**"
            )
        )
        embed.add_field(
            name="\N{BLACK QUESTION MARK ORNAMENT} More features and getting help",
            value=(
                "These are just the very, very basics to get you started!\n"
                "There is so much more to do and explore!\n"
                "**Check out all of the bot features with: /help**.\n"
                "For seeking help on specific command usage, do **/help** `command_name`, "
                "where `command_name` is the name of the command you need help with."
            )
        )
        await self.reply(embed=embed)


class AccountCommand(FarmSlashCommand, name="account"):
    pass


class AccountCreateCommand(
    FarmSlashCommand,
    name="create",
    description="\N{SQUARED NEW} Creates a new game account",
    parent=AccountCommand
):
    """
    You can't have multiple game accounts for a single Discord account.
    If you want to reset your progress, you can delete your game account
    with **/account manage**, and then create a new one with this command.
    """
    requires_account = False  # type: bool

    async def callback(self) -> None:
        async with self.db.acquire() as conn:
            try:
                await self.users.get_user(self.author.id, conn=conn)
            except exceptions.UserNotFoundException:
                pass
            else:
                embed = embeds.error_embed(
                    title="You already own a farm!",
                    text=(
                        "What do you mean? \N{FLUSHED FACE} You already own a cool farm! "
                        "It's time for you to get back working on the field. There's always "
                        "lots of work to do! \N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE}"
                    ),
                    footer="Maybe you want to plant some lettuce? Carrots? \N{THINKING FACE}",
                    cmd=self
                )
                raise exceptions.UserNotFoundException(embed=embed)

            await self.users.create_user(self.author.id, conn=conn)

        await TutorialCommand.callback(self)


class AccountManageCommand(
    FarmSlashCommand,
    name="manage",
    description="\N{PENCIL} Lists and manages your game account settings",
    parent=AccountCommand
):
    """
    **You can delete your game account with this command.** This will delete all of your
    progress permanently. You can't recover your account after this action.<br>
    **You can also set your notification settings with this command.**
    Please note that if you update your notification settings,
    it might take some time for them to take effect.
    """

    async def send_disable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = get_cluster_collection(self.client)
        if cluster_collection:
            await cluster_collection.send_disable_reminders_message(user_id)

    async def send_enable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = get_cluster_collection(self.client)
        if cluster_collection:
            await cluster_collection.send_enable_reminders_message(user_id)

    async def send_delete_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = get_cluster_collection(self.client)
        if cluster_collection:
            await cluster_collection.send_delete_reminders_message(user_id)

    async def delete_account(self) -> None:
        embed = embeds.prompt_embed(
            title="Woah! Are you really, really, really, really sure about that?",
            text=(
                "**This is going to delete ALL of your current progress in game**, "
                "because then we will be transfering your farm to \N{PIG FACE} Mary "
                "(the pig), and knowing that she is very greedy "
                "and she is never going to give it back to you, "
                "means that **your farm is going to be lost FOREVER!!!**\n"
                "But you can start over again fresh any time... \N{UPSIDE-DOWN FACE}"
            ),
            cmd=self
        )

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            style=discord.ButtonStyle.primary,
            emoji="\N{BLACK UNIVERSAL RECYCLING SYMBOL}",
            label="Delete account forever",
            deny_label="Nevermind, I will just take a break..."
        ).prompt()

        if not confirm:
            return

        await self.users.delete_user(self.author.id)

        await self.edit(
            embed=embeds.success_embed(
                title=f"Goodbye, {self.author.name}! Thanks for playing! \N{WAVING HAND SIGN}",
                text=(
                    "Your account has been deleted! If you ever consider playing again, then just "
                    "type **/account create** again and you are ready to go! "
                    "Take care! Bye for now! :)"
                ),
                footer="We are going to miss you!",
                cmd=self
            ),
            view=None
        )
        # Try to not bother the user with remaining reminders
        await self.send_delete_reminders_to_ipc(self.author.id)

    async def manage_notifications(self) -> None:
        enable = not(self.user_data.notifications)
        self.user_data.notifications = enable
        await self.users.update_user(self.user_data)

        if not enable:
            embed = embeds.success_embed(
                title="Game notifications disabled",
                text=(
                    "\N{WARNING SIGN} **It might take a few minutes for your new "
                    "notification settings to take effect**.\n"
                    "\N{OPEN MAILBOX WITH LOWERED FLAG} Okay, so: I told the *mail man* **not to "
                    "bother you** with all those messages."
                ),
                footer="He then said: \"Ehhh.. brrrhh.. Will do!\" \N{OLDER MAN}",
                cmd=self
            )
            await self.send_disable_reminders_to_ipc(self.author.id)
        else:
            embed = embeds.success_embed(
                title="Game notifications enabled",
                text=(
                    "\N{WARNING SIGN} **It might take a few minutes for your new "
                    "notification settings to take effect**.\n"
                    "\N{OPEN MAILBOX WITH RAISED FLAG} Okay, so: I told the *mail man* **to "
                    "send you** messages about the game."
                ),
                footer="He then said: \"Ehhh.. brrrhh.. Will do!\" \N{OLDER MAN}",
                cmd=self
            )
            await self.send_enable_reminders_to_ipc(self.author.id)

        await self.edit(embed=embed, view=None)

    async def callback(self) -> None:
        embed = discord.Embed(
            title="\N{PENCIL} Your game account settings",
            description="These settings manage your overall bot experience.",
            color=discord.Color.fuchsia()
        )

        if self.user_data.notifications:
            notification_settings = f"{self.client.check_emoji} Enabled"
            notification_action = "Disable game notifications"
        else:
            notification_settings = "\N{CROSS MARK} Disabled"
            notification_action = "Enable game notifications"

        embed.add_field(
            name="\N{E-MAIL SYMBOL} Game notifications",
            value=notification_settings
        )

        reg_date = datetime.datetime.combine(self.user_data.registration_date, datetime.time())
        embed.add_field(
            name="\N{SPIRAL CALENDAR PAD} Registration date",
            value=discord.utils.format_dt(reg_date, style="D")
        )

        options = (
            views.OptionButton(
                option=self.manage_notifications,
                style=discord.ButtonStyle.secondary,
                emoji="\N{INCOMING ENVELOPE}",
                label=notification_action
            ),
            views.OptionButton(
                option=self.delete_account,
                style=discord.ButtonStyle.secondary,
                emoji="\N{SKULL AND CROSSBONES}",
                label="Permanently delete account"
            )
        )
        result = await views.MultiOptionView(self, options, initial_embed=embed).prompt()
        if result:
            # Run the selected settings option
            await result()


def setup(client) -> list:
    return [AccountCollection(client)]

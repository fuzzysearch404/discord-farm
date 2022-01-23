from discord.ext.modules import CommandCollection

from .util.commands import FarmSlashCommand
from .util import embeds


class AccountCollection(CommandCollection):
    """Commands for managing your game account."""
    def __init__(self, client):
        super().__init__(client, [TutorialCommand], name="Account")

    def _get_cluster_collection(self):
        try:
            return self.client.get_command_collection("Clusters")
        except KeyError:
            self.client.log.critical("Reminder failed: Cluster collection not loaded!")
            return None

    async def send_disable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = self._get_cluster_collection()
        if cluster_collection:
            await cluster_collection.send_disable_reminders_message(user_id)

    async def send_enable_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = self._get_cluster_collection()
        if cluster_collection:
            await cluster_collection.send_enable_reminders_message(user_id)

    async def send_delete_reminders_to_ipc(self, user_id: int) -> None:
        cluster_collection = self._get_cluster_collection()
        if cluster_collection:
            await cluster_collection.send_delete_reminders_message(user_id)


class TutorialCommand(FarmSlashCommand, name="tutorial"):
    """\N{OPEN BOOK} Some quickstart tips for new players"""
    avoid_maintenance = False  # type: bool
    requires_account = False  # type: bool

    async def callback(self) -> None:
        print(self.__doc__)
        embed = embeds.congratulations_embed(
            title="Welcome to your new farm! \N{FACE WITH PARTY HORN AND PARTY HAT}",
            text=(
                "\"Who's this? Are you the new owner? Hey Bob, "
                "look at this - another owner - again! Anyways, welcome "
                "stranger! I have very limited time, but I will try to "
                "explain only the very basics to get you started. The rest "
                "of the stuff you will have to learn on your own...\""
                "\N{WHITE UP POINTING INDEX}\n\n"
                "\N{HOURGLASS}Want to read this again later? "
                "Sure, just type **/tutorial**"
            ),
            cmd=self
        )

        embed.add_field(
            name="\N{HOUSE WITH GARDEN} Profile",
            value=(
                "The most important profile commands for beginners are:\n"
                "**/profile** - Your profile\n"
                "**/allitems** - Items you have unlocked\n"
                "**/inventory** - Your inventory\n"
                "**/item** - To view some items properties"
            )
        )
        embed.add_field(
            name="\N{SEEDLING} Farm: Planting",
            value=(
                "Your farm has a limited space to plant items in.\n"
                "Right now it is 2 space tiles, but you will be able "
                "to increase it later.\nThis means, that you can plant "
                "2 items at a time.\nYou have unlocked: \N{LEAFY GREEN} Lettuce.\n"
                "Plant 2 lettuce items with the command: **/plant lettuce 2**.\n"
                "To view your farm, check out command **/farm**"
            )
        )
        embed.add_field(
            name="\N{CLOCK FACE TWO-THIRTY} Farm: Waiting for harvest",
            value=(
                "Different items have different growing durations "
                "and durations while items can be harvested.\n"
                "For example, \N{LEAFY GREEN} Lettuce grows for 2 "
                "minutes, and is harvestable for 3 minutes after those "
                "2 minutes of growing.\nIf you don't harvest your items in "
                "time - they get rotten (lost forever).\nTo monitor your "
                "farm, check out command: **/farm** frequently."
            )
        )
        embed.add_field(
            name="\N{TRACTOR} Farm: Harvesting items",
            value=(
                "When it is finally time to harvest, just use the "
                "**/harvest** command. All of the ready items will be "
                "automatically collected to your **/inventory**\n"
                "If some of your items get rotten - they are going to be "
                "discarded with this command, to free up your farm field space."
            )
        )
        embed.add_field(
            name=f"{self.client.gold_emoji} Earning gold coins",
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
            name="\N{BLACK QUESTION MARK ORNAMENT} More features and getting help",
            value=(
                "These are just the very, very basics to get you started!\n"
                "There is so much more to do and explore!\n"
                "**Check out all of the bot's features with: /help**\n"
                "For command usage examples and more help, do **/help** `command_name`, "
                "where `command_name` is the name of the command you need help with."
            )
        )

        await self.reply(embed=embed)


def setup(client) -> list:
    return [AccountCollection(client)]

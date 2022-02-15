from .util.commands import FarmSlashCommand, FarmCommandCollection


class MissionsCollection(FarmCommandCollection):
    """
    Are you looking for some more work to do? Great! There's always tons of tasks to do in
    this town. There are orders from many different local and foreign businesses.
    They tell you what they need, you gather some, and you get paid for that - it's as easy as that.
    Some of them need your help really fast, but they will pay you more than anyone else would pay
    for the regular jobs. And in the port, you can get even sign a contract to export tons of goods,
    while getting a good pay.
    """
    help_emoji: str = "\N{MEMO}"
    help_short_description: str = "Challenge yourself, by completing various missions"

    def __init__(self, client):
        super().__init__(client, [MissionsCommand], name="Missions")


class MissionsCommand(FarmSlashCommand, name="missions"):
    pass


class MissionsOrdersCommand(MissionsCommand, name="orders", parent=MissionsCommand):
    pass


class MissionsOrdersViewCommand(
    FarmSlashCommand,
    name="view",
    description="\N{MEMO} Lists your order missions",
    parent=MissionsOrdersCommand
):
    pass


class MissionsOrdersRefreshCommand(
    FarmSlashCommand,
    name="refresh",
    description="\N{PRINTER} Replaces current order missions with new ones",
    parent=MissionsOrdersCommand
):
    pass


def setup(client) -> list:
    return [MissionsCollection(client)]

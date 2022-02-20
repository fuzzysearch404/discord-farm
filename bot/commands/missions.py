import discord
import datetime
import jsonpickle

from core import game_missions
from .util import views
from .util import time as time_util
from .util import embeds as embed_util
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


async def complete_business_mission(
    cmd: FarmSlashCommand,
    mission: game_missions.BusinessMission,  # Already initialized from partial data
    mission_id: int
) -> None:
    conn = await cmd.acquire()
    # mission_id -1 means that the mission is not in the Postgres database
    if mission_id != -1:
        query = "SELECT payload FROM missions WHERE id = $1;"
        payload = await conn.fetchval(query, mission_id)

        # If user tries to complete already completed mission, after the long prompt.
        if not payload:
            await cmd.release()
            return await cmd.edit(content="Already completed!", view=None)

    user_items = await cmd.user_data.get_all_items(conn)
    user_items_by_id = {item['item_id']: item for item in user_items}

    missing_items = []
    for request in mission.requests:
        item, amount = request[0], request[1]

        try:
            item_data = user_items_by_id[item.id]
            if item_data['amount'] < amount:
                missing_items.append((item, amount - item_data['amount']))
        except KeyError:
            missing_items.append((item, amount))

    if missing_items:
        await cmd.release()

        fmt = ", ".join(f"{item.full_name} x{amount}" for item, amount in missing_items)
        embed = embed_util.error_embed(
            title="You are missing items for completing this mission!",
            text=(
                "Unfortunately we can't deliver this package to the customer, because you are "
                f"missing these requested items: **{fmt}**!"
            ),
            cmd=cmd
        )
        return await cmd.edit(embed=embed, view=None)

    async with conn.transaction():
        if mission_id != -1:
            query = "DELETE FROM missions WHERE id = $1;"
            await conn.execute(query, mission_id)

        to_remove = [(item, amount) for item, amount in mission.requests]
        await cmd.user_data.remove_items(to_remove, conn)

        if mission.chest:
            await cmd.user_data.give_item(mission.chest.id, 1, conn)

        cmd.user_data.gold += mission.gold_reward
        cmd.user_data.give_xp_and_level_up(cmd, mission.xp_reward)
        await cmd.users.update_user(cmd.user_data, conn=conn)
    await cmd.release()

    fmt = ""
    if mission.gold_reward:
        fmt += f"{mission.gold_reward} {cmd.client.gold_emoji} "
    if mission.xp_reward:
        fmt += f"{mission.xp_reward} {cmd.client.xp_emoji} "
    if mission.chest:
        fmt += f"1x {mission.chest.emoji} {mission.chest.name.capitalize()}"

    embed = embed_util.success_embed(
        title="Mission completed! \N{CLAPPING HANDS SIGN}",
        text=(
            "Well done! \N{SMILING FACE WITH SUNGLASSES}\N{THUMBS UP SIGN} The customer was very "
            f"satisfied with your services and sent these as for the reward: **{fmt}**"
        ),
        cmd=cmd
    )
    await cmd.edit(embed=embed, view=None)


class MissionsCommand(FarmSlashCommand, name="missions"):
    pass


class MissionsOrdersCommand(MissionsCommand, name="orders", parent=MissionsCommand):
    pass


class MissionsOrdersViewCommand(
    MissionsOrdersCommand,
    name="view",
    description="\N{MEMO} Lists your order missions",
    parent=MissionsOrdersCommand
):
    """
    Order missions are requests from businesses that require you to gather random items.
    Upon completion, you will get rewarded with gold, experience points and sometimes
    with a random chest. The amount of items required for completion is random, but
    it is increased by your player level. Leveling up also affects how many order
    missions you can choose from. These missions don't have a time limit.<br>
    \N{ELECTRIC LIGHT BULB} You can replace all of your current order missions with new ones
    every 5 hours with the **/missions orders refresh** command.
    """

    def get_mission_count(self) -> int:
        if self.user_data.level < 10:
            return 3
        elif self.user_data.level < 20:
            return 4
        elif self.user_data.level < 30:
            return 5
        else:
            return 6

    async def callback(self):
        mission_count, missions, new_missions = self.get_mission_count(), [], []

        async with self.acquire() as conn:
            query = "SELECT id, payload FROM missions WHERE user_id = $1;"
            existing_missions = await conn.fetch(query, self.author.id)

            for _ in range(mission_count - len(existing_missions)):
                new_mission = game_missions.BusinessMission.generate(self)
                encoded = jsonpickle.encode(new_mission)

                query = "INSERT INTO missions (user_id, payload) VALUES ($1, $2) RETURNING id;"
                id = await conn.fetchval(query, self.author.id, encoded)
                new_missions.append((id, new_mission))

        for existing in existing_missions:
            decoded = jsonpickle.decode(existing['payload'])
            missions.append((existing['id'], decoded))
        # Just to keep the right order...
        for new_mission in new_missions:
            missions.append(new_mission)

        embed = discord.Embed(
            title="\N{MEMO} Your order missions",
            description=(
                "\N{WOMAN}\N{ZERO WIDTH JOINER}\N{BRIEFCASE} Hey boss! \N{WAVING HAND SIGN} "
                "We have these orders from our local business partners.\n"
                "\N{BRIEFCASE} Click a button below to complete any of these orders!\n"
                "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} Don't like any of "
                "these orders? Get new orders with **/missions orders refresh** every 5 hours."
            ),
            color=discord.Color.from_rgb(148, 148, 148)
        )

        buttons = []
        for index, id_mission_tuple in enumerate(missions):
            mission = id_mission_tuple[1]
            mission.initialize_from_partial_data(self)

            embed.add_field(
                name=f"\N{MEMO} Order: #{index + 1}",
                value=mission.format_for_embed(self)
            )

            buttons.append(views.OptionButton(
                option=id_mission_tuple,
                style=discord.ButtonStyle.secondary,
                emoji="\N{MEMO}",
                label=f"Complete order #{index + 1}"
            ))

        result = await views.MultiOptionView(self, buttons, initial_embed=embed).prompt()
        if not result:
            return

        await complete_business_mission(self, result[1], result[0])


class MissionsOrdersRefreshCommand(
    MissionsOrdersCommand,
    name="refresh",
    description="\N{PRINTER} Replaces current order missions with new ones",
    parent=MissionsOrdersCommand
):
    """
    This command deletes all of your current order missions and assigns new ones.<br>
    \N{ELECTRIC LIGHT BULB} To view your order missions, see the **/missions orders view** command.
    """
    _invoke_cooldown: int = 18000

    async def callback(self):
        async with self.acquire() as conn:
            query = "DELETE FROM missions WHERE user_id = $1;"
            await conn.execute(query, self.author.id)

        embed = embed_util.success_embed(
            title="Order missions refreshed!",
            text=(
                "Done! I've called some business partners and got some new jobs for you! "
                "\N{BLACK TELEPHONE}\nCheck them out with **/missions orders view** \N{MEMO}"
            ),
            cmd=self
        )
        await self.reply(embed=embed)


class MissionsOrdersUrgentCommand(
    MissionsOrdersCommand,
    name="urgent",
    description="\N{LOWER LEFT FOUNTAIN PEN} Offers an urgent, limited time, order mission",
    parent=MissionsOrdersCommand
):
    """
    Similar to the **/missions orders view** command, but this command provides a single mission,
    that is temporary - it can only be completed for a few seconds, after executing this
    command. However, this mission provides better rewards than the regular order missions.
    """
    _invoke_cooldown: int = 3600

    async def callback(self) -> None:
        mission = game_missions.BusinessMission.generate(self, reward_multiplier=1.2)
        mission.initialize_from_partial_data(self)

        embed = discord.Embed(
            title="\N{LOWER LEFT FOUNTAIN PEN} Urgent order offer!",
            description=(
                "\N{ALARM CLOCK} **You only have a few seconds to decide if you approve!**\n\n"
                "\N{WOMAN}\N{ZERO WIDTH JOINER}\N{PERSONAL COMPUTER} Boss, quick! This business "
                "partner is urgently looking for these items and is going to pay extra rewards:"
            ),
            color=discord.Color.from_rgb(198, 20, 9)
        )
        embed.add_field(name="The order:", value=mission.format_for_embed(self))

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            emoji=self.client.check_emoji,
            label="Complete the order"
        ).prompt()

        if not confirm:
            return

        await complete_business_mission(self, mission, -1)


class MissionsExportCommand(MissionsCommand, name="export", parent=MissionsCommand):
    _required_level: int = 10


class MissionsExportShipCommand(
    MissionsExportCommand,
    name="ship",
    description="\N{SHIP} Starts a new export mission or displays the already active export",
    parent=MissionsExportCommand
):
    """
    These missions are different than the other mission types. You have to sign an export contract
    and load the cargo ship with as much resources as you can, before ship leaves your port.
    The more packages of items you load - the better the rewards get. If you don't sign
    any of the offered export contracts, when first running this command, you will be on
    a cooldown. If you already have chosen a contract, this command is going to show
    information about the current contract and your current export progression.<br>
    \N{ELECTRIC LIGHT BULB} To load a package to the ship, use the **/missions export load**
    command.
    """
    _inner_cooldown: int = 3600

    async def start_new_mission(self):
        contract_cooldown = await self.get_cooldown_ttl(self.get_full_name())
        if contract_cooldown:
            ttl_fmt = time_util.seconds_to_time(contract_cooldown)
            embed = embed_util.error_embed(
                title="\N{SCROLL} Waiting for new export contracts",
                text=(
                    "You recently were offered a list of export contracts, but you didn't sign "
                    f"any of them. New contracts are going to appear in: **{ttl_fmt}** "
                    "\N{HOURGLASS WITH FLOWING SAND}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        embed = discord.Embed(
            title="\N{PENCIL} Please choose an export contract",
            description=(
                "\N{FERRY} Welcome to the port! \N{CONSTRUCTION WORKER} We have these three cargo "
                "ships leaving to high seas today and they have the following offers:\n"
                "\N{CLOCK FACE ONE OCLOCK} You can only choose one and if you don't choose any, "
                "you will have to wait an hour for new contracts."
            ),
            color=discord.Color.from_rgb(217, 158, 130)
        )
        embed.set_footer(text=(
            "\N{STOPWATCH} Choose a contract quickly, because you have limited time to do so"
        ))

        buttons = []
        for num in range(3):
            export = game_missions.ExportMission.generate(self)

            embed.add_field(
                name=f"\N{MEMO} Contract: #{num + 1}",
                value=export.format_for_embed(self)
            )
            buttons.append(views.OptionButton(
                option=export,
                style=discord.ButtonStyle.secondary,
                emoji="\N{PENCIL}",
                label=f"Start contract #{num + 1}"
            ))

        result = await views.MultiOptionView(
            self,
            buttons,
            initial_embed=embed,
            deny_label="Deny all"
        ).prompt()

        if not result:  # Forbid from picking new contract for an hour.
            return await self.set_cooldown(3600, self.get_full_name())

        await self.redis.execute_command(
            "SET", f"export:{self.author.id}", jsonpickle.encode(result),
            "EX", result.DURATION_SECONDS
        )
        await self.show_current_export(result)

    async def show_current_export(self, export: game_missions.ExportMission):
        ttl = await self.redis.execute_command("TTL", f"export:{self.author.id}")
        leave_time = datetime.datetime.now() + datetime.timedelta(seconds=ttl)

        embed = discord.Embed(
            title="\N{SHIP} Load the cargo ship",
            description=(
                "\N{PACKAGE} Load items into the cargo ship with the **/missions export load** "
                "command!\n\N{ARROW POINTING RIGHTWARDS THEN CURVING UPWARDS} "
                "You will get higher rewards for each package you load into the cargo ship.\n"
                "\N{TIMER CLOCK} You can load a package every 15 minutes."
            ),
            color=discord.Color.from_rgb(34, 102, 153)
        )
        embed.add_field(name="\N{ANCHOR} Current contract", value=export.format_for_embed(self))
        embed.add_field(
            name="\N{PACKAGE} Loaded packages",
            value=f"{export.shipments} of {export.MAX_SHIPMENTS}"
        )
        embed.add_field(
            name="\N{CLOCK FACE ONE OCLOCK} Cargo ship will leave",
            value=time_util.maybe_timestamp(leave_time)
        )

        load_cooldown = await self.get_cooldown_ttl("export_load")
        if load_cooldown:
            load_cooldown = datetime.datetime.now() + datetime.timedelta(seconds=load_cooldown)
            time_fmt = time_util.maybe_timestamp(load_cooldown)
            embed.description += (
                f"\n\N{CONSTRUCTION WORKER} The cargo ship is going to be idle again: {time_fmt}."
            )

        if self.interaction.response.is_done():
            await self.edit(embed=embed, view=None)
        else:
            await self.reply(embed=embed)

    async def callback(self):
        current_export = await self.client.redis.execute_command("GET", f"export:{self.author.id}")
        if not current_export:
            await self.start_new_mission()
        else:
            await self.show_current_export(jsonpickle.decode(current_export))


class MissionsExportLoadCommand(
    MissionsExportCommand,
    name="load",
    description="\N{PACKAGE} Loads a package into the cargo ship",
    parent=MissionsExportCommand
):
    """
    This command is going to load a single package onto your current export ship and
    pay the rewards based on the amount of previously loaded packages.
    You have to wait 15 minutes between each successful load.<br>
    \N{ELECTRIC LIGHT BULB} For more help about export missions, please see help
    for the **/missions export ship** command.
    """
    _inner_cooldown: int = 900

    async def callback(self):
        export = await self.client.redis.execute_command("GET", f"export:{self.author.id}")
        if not export:
            embed = embed_util.error_embed(
                title="\N{SCROLL} No active export contract!",
                text=(
                    "You don't have an active export contract in this port. "
                    "Sign a new contract with **/missions export ship** \N{ANCHOR}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        export = jsonpickle.decode(export)

        if export.shipments >= export.MAX_SHIPMENTS:
            embed = embed_util.error_embed(
                title="\N{PACKAGE} The cargo ship is already full!",
                text=(
                    "We can't load another package, because the cargo ship has reached it's "
                    "maximum cargo capacity! \N{CONSTRUCTION WORKER}\nAnyways, well done! "
                    "We now have to wait until it leaves the port! You don't have to do "
                    "anything tho, you can just watch as it enters the sea, if you wish. "
                    "\N{SUNRISE}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        cooldown = await self.get_cooldown_ttl("export_load")
        if cooldown:
            time_fmt = time_util.seconds_to_time(cooldown)
            embed = embed_util.error_embed(
                title="Package loading onto cargo ship in progress! \N{SHIP}\N{PACKAGE}",
                text=(
                    "We have to wait for your last package to get loaded onto the cargo ship! "
                    f"Please check back again in **{time_fmt}**. It should be done by that "
                    "time. \N{CONSTRUCTION WORKER}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        conn = await self.acquire()
        item, amount = export.item, export.amount
        item_data = await self.user_data.get_item(item.id, conn)

        if not item_data or item_data['amount'] < amount:
            await self.release()
            missing_amount = amount - item_data['amount'] if item_data else amount
            embed = embed_util.error_embed(
                title="\N{PACKAGE} Not enough items for this package!",
                text=(
                    "We can't load this package onto the cargo ship! The cargo ship's capacity "
                    "must be used effectively, so the package must be full to the top. "
                    "\N{CONSTRUCTION WORKER}\N{ABACUS}\n\n"
                    f"**You are missing: {missing_amount}x {item.full_name}**"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        rewards = export.rewards_for_shipment()  # gold, xp, chest_id
        self.user_data.gold += rewards[0]
        self.user_data.give_xp_and_level_up(self, rewards[1])

        async with conn.transaction():
            await self.user_data.remove_item(item.id, amount, conn)
            await self.users.update_user(self.user_data, conn=conn)
            # Award chest, if any. Always one.
            if rewards[2]:
                await self.user_data.give_item(rewards[2], 1, conn)
        await self.release()

        ttl = await self.redis.execute_command("TTL", f"export:{self.author.id}")
        # Just in case if it somehow already ended
        ttl = ttl if ttl > 0 else 1

        export.shipments += 1
        await self.redis.execute_command(
            "SET", f"export:{self.author.id}", jsonpickle.encode(export),
            "EX", ttl
        )
        await self.set_cooldown(self._inner_cooldown, "export_load")

        if rewards[2]:
            chest = self.items.find_chest_by_id(rewards[2])
            chest_fmt = f"1x {chest.emoji} {chest.name.capitalize()}"
        else:
            chest_fmt = ""

        embed = embed_util.success_embed(
            title="Package is now being loaded onto the cargo ship!",
            text=(
                f"Well done! \N{THUMBS UP SIGN} We started loading your package: **{amount}x "
                f"{item.full_name}** onto the cargo ship! **You received: {rewards[0]} "
                f"{self.client.gold_emoji} {rewards[1]} {self.client.xp_emoji} {chest_fmt}**"
            ),
            cmd=self
        )
        await self.reply(embed=embed)


def setup(client) -> list:
    return [MissionsCollection(client)]

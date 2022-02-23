import discord
from typing import Optional

from core import game_items
from core import modifications
from .util import views
from .util import time as time_util
from .util import embeds as embeds_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


class LaboratoryCollection(FarmCommandCollection):
    """
    Are your crops growing too slowly or getting rotten too fast? Or maybe you want your crops to
    grow in larger quantities? Then the laboratory is the place you are looking for! Invest golden
    coins into the research and scientists will do the rest. You can even increase the productivity
    of your animals! No need to worry - they are not getting hurt in any way, just like when
    collecting products from them. The technology for that was invented by these same scientists.
    """
    help_emoji: str = "\N{TEST TUBE}"
    help_short_description: str = "Upgrade your plants and animals"

    def __init__(self, client):
        super().__init__(client, [LaboratoryCommand], name="Laboratory")


class LaboratorySource(views.AbstractPaginatorSource):
    def __init__(
        self,
        entries: list,
        target_user: discord.Member,
        lab_cooldown: str
    ):
        super().__init__(entries, per_page=12)
        self.target_name = target_user.nick or target_user.name
        self.lab_cooldown = lab_cooldown

    def format_item_modifications(self, view, data_row) -> str:
        item = view.command.items.find_item_by_id(data_row['item_id'])

        def fmt_level(lvl):
            return f"{lvl}/10" if lvl < 10 else "Max."

        return (
            f"**{item.full_name}:** "
            f"\N{MANTELPIECE CLOCK} {fmt_level(data_row['time1'])} "
            f"\N{MANTELPIECE CLOCK} {fmt_level(data_row['time2'])} "
            f"\N{SCALES} {fmt_level(data_row['volume'])}"
        )

    async def format_page(self, page, view):
        embed = discord.Embed(
            title=f"\N{DNA DOUBLE HELIX} {self.target_name}'s laboratory",
            color=discord.Color.from_rgb(146, 102, 204),
            description=(
                "\N{MAN}\N{ZERO WIDTH JOINER}\N{MICROSCOPE} Welcome to the town's laboratory! "
                "What crop, tree or animal would you like to upgrade? \N{MICROBE}\n"
                "\N{LEFT-POINTING MAGNIFYING GLASS} Use the **/laboratory research** command to "
                "view or apply upgrades for an item.\n\n"
            )
        )

        if self.lab_cooldown:
            embed.description += (
                "\N{BROOM} This laboratory is closed for a maintenance: "
                f"**{self.lab_cooldown}**\n\n"
            )

        if page:
            header = (
                "\N{TEST TUBE} __**Currently upgraded items:**__\n"
                "| \N{LABEL} Item | \N{MANTELPIECE CLOCK} Growing time | "
                "\N{MANTELPIECE CLOCK} Harvesting time | \N{SCALES} Max. Volume |\n\n"
            )
            fmt = [self.format_item_modifications(view, m) for m in page]
            embed.description += header + "\n".join(fmt)
        else:
            embed.description += "\N{PETRI DISH} **No items have been modified yet...**"

        return embed


class LaboratoryCommand(FarmSlashCommand, name="laboratory"):
    _required_level: int = 2


class LaboratoryViewCommand(
    LaboratoryCommand,
    name="view",
    description="\N{TEST TUBE} Shows your or someone else's laboratory",
    parent=LaboratoryCommand
):
    """
    This command displays your or someone else's current item upgrades.<br>
    \N{ELECTRIC LIGHT BULB} To upgrade an item, use the **/laboratory research** command.
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose laboratory to view"
    )

    async def callback(self):
        async with self.acquire() as conn:
            if not self.player:
                user = self.user_data
                target_user = self.author
            else:
                user = await self.lookup_other_player(self.player, conn=conn)
                target_user = self.player

            query = "SELECT * FROM modifications WHERE user_id = $1 ORDER BY item_id;"
            modifications_data = await conn.fetch(query, target_user.id)

        lab_cooldown = await self.get_cooldown_ttl("recent_research", other_user_id=user.user_id)
        if lab_cooldown:
            lab_cooldown = time_util.seconds_to_time(lab_cooldown)

        await views.ButtonPaginatorView(
            self,
            source=LaboratorySource(modifications_data, target_user, lab_cooldown)
        ).start()


class LaboratoryResearchCommand(
    LaboratoryCommand,
    name="research",
    description="\N{DNA DOUBLE HELIX} Upgrades an item",
    parent=LaboratoryCommand
):
    """
    This command displays the current upgrades for an item and information about the next upgrade
    perks, costs and cooldowns. The upgrades can be purchased with this same command, by pressing
    the corresponding buttons. You can only purchase one upgrade at a time and you will have to
    wait a while to be able to do any other upgrades in the laboratory. The price and the cooldown
    increases with each new upgrade level. These item upgrades are permanent.
    """
    _inner_cooldown: int = -1

    item: str = discord.app.Option(description="Item to upgrade", autocomplete=True)

    def calculate_modification_cost(self, item: game_items.PurchasableItem, level: int) -> int:
        return int(round(item.gold_price * (level ** 1.55), -1))

    def calculate_modification_cooldown(self, level: int) -> int:
        return 60 + int(round((level ** 4.9362), -1))  # Max (10): 1 day

    def format_upgrade_costs(self, upgrade: str, cooldown_fmt: str, cost: int) -> str:
        return (
            f"\N{SQUARED NEW} Next level: **{upgrade}**\n\n"
            f"\N{TIMER CLOCK} Research cooldown:\n**{cooldown_fmt}**\n"
            f"\N{MONEY BAG} Research costs:\n**{cost} {self.client.gold_emoji}**"
        )

    async def perform_upgrade(self, upgrade_type: str, item: game_items.PlantableItem) -> None:
        cooldown = await self.get_cooldown_ttl("recent_research")
        if cooldown:
            cooldown = time_util.seconds_to_time(cooldown)
            embed = embeds_util.error_embed(
                title="The laboratory is under a maintenance! \N{BROOM}",
                text=(
                    "We are still cleaning things up after your last item's upgrade!\n"
                    f"Please come again in: **{cooldown}** \N{ALARM CLOCK}"
                ),
                cmd=self
            )
            return await self.edit(embed=embed, view=None)

        conn = await self.acquire()
        modifications = await self.user_data.get_item_modification(item.id, conn)
        current_level = modifications[upgrade_type] if modifications else 0

        if current_level >= 10:
            await self.release()
            embed = embeds_util.error_embed(
                title="Already upgraded to the maximum level!",
                text=(
                    "You have reached the last possible upgrade level for this property of "
                    f"**{item.full_name}**!\nMaybe in some ten or couple hundred years "
                    "the science is going to allow going futher than this... "
                    "\N{WOMAN}\N{ZERO WIDTH JOINER}\N{MICROSCOPE}"
                ),
                cmd=self
            )
            return await self.edit(embed=embed, view=None)

        gold_cost = self.calculate_modification_cost(item, current_level + 1)
        self.user_data = await self.users.get_user(self.author.id, conn=conn)

        if gold_cost > self.user_data.gold:
            await self.release()
            return await self.edit(embed=embeds_util.no_money_embed(self, gold_cost), view=None)

        async with conn.transaction():
            self.user_data.gold -= gold_cost
            await self.users.update_user(self.user_data, conn=conn)

            query = f"""
                    INSERT INTO modifications (user_id, item_id, {upgrade_type})
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, item_id)
                    DO UPDATE SET {upgrade_type} = modifications.{upgrade_type} + $3;
                    """
            await conn.execute(query, self.user_data.user_id, item.id, 1)
        await self.release()

        cooldown = self.calculate_modification_cooldown(current_level + 1)
        await self.set_cooldown(cooldown, "recent_research")

        embed = embeds_util.congratulations_embed(
            title="Modification successful!",
            text=(
                "Our experiments went smoothly and we are happy to tell you that the modification "
                f"has been applied to your **{item.full_name}**! \N{CONFETTI BALL}\n If you are "
                "ready to try these out, go ahead, you can already start growing some! "
                "\N{FACE WITH COWBOY HAT}"
            ),
            cmd=self
        )
        await self.edit(embed=embed, view=None)

    async def autocomplete(self, options, focused):
        return discord.app.AutoCompleteResponse(self.plantables_autocomplete(options[focused]))

    async def callback(self):
        item = self.lookup_item(self.item)

        if not isinstance(item, game_items.PlantableItem):
            embed = embeds_util.error_embed(
                title="This item can't be upgraded!",
                text=(
                    f"With a deep regret, I have to tell you that **{item.full_name}** can't be "
                    "upgraded!\nThe science has not developed so far yet... "
                    "\N{MAN}\N{ZERO WIDTH JOINER}\N{MICROSCOPE}\n"
                    "You can only upgrade items that you can grow in your farm. \N{SEEDLING}"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        if self.user_data.level < item.level:
            embed = embeds_util.error_embed(
                title="\N{LOCK} You haven't unlocked this item yet!",
                text=(
                    f"Our laboratory can't upgrade **{item.full_name}**, because you don't even "
                    "have access to this item. Sorry. \N{CONFUSED FACE}"
                ),
                footer=f"This item is going to be unlocked at experience level {item.level}.",
                cmd=self
            )
            return await self.reply(embed=embed)

        time1_mod = time2_mod = vol_mod = 0

        async with self.acquire() as conn:
            current_modifications = await self.user_data.get_item_modification(item.id, conn)

        if current_modifications:
            time1_mod = current_modifications['time1']
            time2_mod = current_modifications['time2']
            vol_mod = current_modifications['volume']

        embed = discord.Embed(
            title=f"\N{MICROSCOPE} Item upgrades: {item.full_name}",
            description=(
                "\N{WOMAN}\N{ZERO WIDTH JOINER}\N{MICROSCOPE} These are all the possible upgrades "
                f"for your: **{item.full_name}**\n\N{BROOM} The upgrade will be done instantly, "
                "but we are going to need some time to clean up the lab, before we can upgrade "
                "your next item.\n\N{WARNING SIGN} Your currently growing items in farm won't be "
                "affected by this upgrade and this means that this upgrade is going to take effect "
                "only upon your next planting!"
            ),
            color=discord.Color.from_rgb(146, 102, 204)
        )

        grow_time = time_util.seconds_to_time(modifications.get_growing_time(item, time1_mod))
        collect_time = time_util.seconds_to_time(modifications.get_harvest_time(item, time2_mod))
        max_volume = modifications.get_volume(item, vol_mod)
        max_level_fmt = "\N{SHOOTING STAR} **Max. level**"

        if time1_mod < 10:
            next_grow_time = modifications.get_growing_time(item, time1_mod + 1)
            next_grow_time = time_util.seconds_to_time(next_grow_time)
            cooldown = self.calculate_modification_cooldown(time1_mod + 1)
            cooldown = time_util.seconds_to_time(cooldown)
            price = self.calculate_modification_cost(item, time1_mod + 1)
            fmt = self.format_upgrade_costs(next_grow_time, cooldown, price)
        else:
            fmt = max_level_fmt

        embed.add_field(
            name="\N{MANTELPIECE CLOCK} Growing duration",
            value=(
                f"\N{TEST TUBE} Upgrades: {time1_mod}/10\n"
                f"\N{DNA DOUBLE HELIX} Current: **{grow_time}**\n{fmt}"
            )
        )

        if time2_mod < 10:
            next_collect_time = modifications.get_harvest_time(item, time2_mod + 1)
            next_collect_time = time_util.seconds_to_time(next_collect_time)
            cooldown = self.calculate_modification_cooldown(time2_mod + 1)
            cooldown = time_util.seconds_to_time(cooldown)
            price = self.calculate_modification_cost(item, time2_mod + 1)
            fmt = self.format_upgrade_costs(next_collect_time, cooldown, price)
        else:
            fmt = max_level_fmt

        embed.add_field(
            name="\N{MANTELPIECE CLOCK} Harvestable for",
            value=(
                f"\N{TEST TUBE} Upgrades: {time2_mod}/10\n"
                f"\N{DNA DOUBLE HELIX} Current: **{collect_time}**\n{fmt}"
            )
        )

        if vol_mod < 10:
            next_max_volume = modifications.get_volume(item, vol_mod + 1)
            next_max_volume = f"{item.amount} - {next_max_volume} items"
            cooldown = time_util.seconds_to_time(self.calculate_modification_cooldown(vol_mod + 1))
            price = self.calculate_modification_cost(item, vol_mod + 1)
            fmt = self.format_upgrade_costs(next_max_volume, cooldown, price)
        else:
            fmt = max_level_fmt

        vol_amount_fmt = f"{item.amount} - {max_volume}" if vol_mod else str(max_volume)
        embed.add_field(
            name="\N{SCALES} Max. harvest volume",
            value=(
                f"\N{TEST TUBE} Upgrades: {vol_mod}/10\n"
                f"\N{DNA DOUBLE HELIX} Current: **{vol_amount_fmt} items**\n{fmt}"
            )
        )

        embed.set_footer(text=(
            "\N{SHOPPING TROLLEY} Press a button to purchase the selected modification"
        ))

        options = (
            ("growing duration", "time1"),
            ("harvesting duration", "time2"),
            ("maximum volume", "volume")
        )
        buttons = []
        for option in options:
            buttons.append(views.OptionButton(
                option=option[1],
                style=discord.ButtonStyle.primary,
                emoji=self.client.gold_emoji,
                label=f"Upgrade {option[0]}"
            ))

        result = await views.MultiOptionView(self, buttons, initial_embed=embed).prompt()
        if not result:
            return

        await self.perform_upgrade(result, item)


def setup(client) -> list:
    return [LaboratoryCollection(client)]

import discord
import datetime
from typing import Literal

from core import game_items
from .util import views
from .util import embeds as embed_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


TRADES_COST_INCREASE_PER_SLOT = 7500

PROFILE_ATTR_FARM_SLOTS = "farm_slots"
PROFILE_ATTR_FACTORY_SLOTS = "factory_slots"
PROFILE_ATTR_FACTORY_LEVEL = "factory_level"
PROFILE_ATTR_STORE_SLOTS = "store_slots"


def check_if_upgrade_maxed(user_data, attr: str) -> bool:
    checks_for_maxed = {
        PROFILE_ATTR_FARM_SLOTS: lambda: user_data.farm_slots >= 30,
        PROFILE_ATTR_FACTORY_SLOTS: lambda: user_data.factory_slots >= 15,
        PROFILE_ATTR_FACTORY_LEVEL: lambda: user_data.factory_level >= 10,
        PROFILE_ATTR_STORE_SLOTS: lambda: user_data.store_slots >= 10
    }
    return checks_for_maxed[attr]()


class ShopCollection(FarmCommandCollection):
    """
    Welcome to the town's marketplace! You have come to the right place for buying and selling
    stuff. Here you can view the prices of the things you can grow in your farm, sell your
    harvest to the global market or trade with other players in your neighborhood.
    There also are specialists who can help you to upgrade your property and gear or provide
    some special services - some locals call those services as "boosters".
    """
    help_emoji: str = "\N{SHOPPING TROLLEY}"
    help_short_description: str = "Purchase upgrades. Sell items to the market or your friends"

    def __init__(self, client) -> None:
        super().__init__(client, [ShopCommand], name="Shop")


class ShopCommand(FarmSlashCommand, name="shop"):
    pass


class ShopUpgradesCommand(FarmSlashCommand, name="upgrades", parent=ShopCommand):
    pass


class ShopUpgradesViewCommand(
    FarmSlashCommand,
    name="view",
    description="\N{WHITE MEDIUM STAR} Lists upgrades available for purchase",
    parent=ShopUpgradesCommand
):
    """
    With this command you can see the upgrades available for you to purchase.<br>
    \N{ELECTRIC LIGHT BULB} For information about buying upgrades, please see
    **/help "shop upgrades buy"**.
    """

    async def callback(self):
        user_data = self.user_data
        trades_cost = user_data.store_slots * TRADES_COST_INCREASE_PER_SLOT

        embed = discord.Embed(
            title="\N{WHITE MEDIUM STAR} Upgrades shop",
            description="\N{BRICK} Purchase upgrades to make your game progression more dynamic!",
            color=discord.Color.from_rgb(255, 162, 0)
        )
        if not check_if_upgrade_maxed(self.user_data, PROFILE_ATTR_FARM_SLOTS):
            embed.add_field(
                name=f"{self.client.tile_emoji} Farm: Expand size",
                value=(
                    "Plant more items at a time in your farm!\n"
                    f"**\N{SQUARED NEW} {user_data.farm_slots} \N{RIGHTWARDS ARROW} "
                    f"{user_data.farm_slots + 1} farm tiles**\n"
                    f"\N{MONEY BAG} Price: **1** {self.client.gem_emoji}\n\n"
                    "\N{SHOPPING TROLLEY} **/shop upgrades buy \"farm size\"**"
                )
            )
        if not check_if_upgrade_maxed(self.user_data, PROFILE_ATTR_FACTORY_SLOTS):
            embed.add_field(
                name="\N{FACTORY} Factory: Larger capacity",
                value=(
                    "Queue more products for production in factory!\n"
                    f"**\N{SQUARED NEW} {user_data.factory_slots} \N{RIGHTWARDS ARROW} "
                    f"{user_data.factory_slots + 1} factory capacity**\n"
                    f"\N{MONEY BAG} Price: **1** {self.client.gem_emoji}\n\n"
                    "\N{SHOPPING TROLLEY} **/shop upgrades buy \"factory capacity\"**"
                )
            )
        if not check_if_upgrade_maxed(self.user_data, PROFILE_ATTR_FACTORY_LEVEL):
            embed.add_field(
                name="\N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING} Factory: Hire more workers",
                value=(
                    "Make products in factory faster!\n"
                    f"**\N{SQUARED NEW} {user_data.factory_level * 5} \N{RIGHTWARDS ARROW} "
                    f"{(user_data.factory_level + 1) * 5}% faster production "
                    f"speed**\n\N{MONEY BAG} Price: **1** {self.client.gem_emoji}"
                    "\n\n\N{SHOPPING TROLLEY} **/shop upgrades buy \"factory workers\"**"
                )
            )
        if not check_if_upgrade_maxed(self.user_data, PROFILE_ATTR_STORE_SLOTS):
            embed.add_field(
                name="\N{HANDSHAKE} Trading: More deals",
                value=(
                    "Post more trade offers!\n"
                    f"**\N{SQUARED NEW} {user_data.store_slots} \N{RIGHTWARDS ARROW} "
                    f"{user_data.store_slots + 1} maximum trades**\n"
                    f"\N{MONEY BAG} Price: **{trades_cost}** {self.client.gold_emoji}"
                    "\n\n\N{SHOPPING TROLLEY} **/shop upgrades buy \"trade deals\"**"
                )
            )

        await self.reply(embed=embed)


class ShopUpgradesBuyCommand(
    FarmSlashCommand,
    name="buy",
    description="\N{SHOPPING TROLLEY} Purchases an upgrade",
    parent=ShopUpgradesCommand
):
    """
    Permanently upgrades some game feature property, resulting in unlocking new capabilities
    or even a new functionalities.<br>
    \N{ELECTRIC LIGHT BULB} For information about each individual upgrade, use the
    **/shop upgrades view** command.
    """
    upgrade: Literal["farm size", "factory capacity", "factory workers", "trade deals"] = \
        discord.app.Option(description="The upgrade to perform")

    async def reject_for_level(self, required_level: int):
        embed = embed_util.error_embed(
            title="\N{LOCK} This upgrade is not available for you yet!",
            text=(
                "**This upgrade is for a feature that is not unlocked for your current level!**\n"
                "The feature and this upgrade is going to be unlocked at level "
                f"\N{TRIDENT EMBLEM} {required_level}."
            ),
            cmd=self
        )
        await self.reply(embed=embed)

    async def reject_for_being_maxed(self, edit_msg: bool):
        embed = embed_util.error_embed(
            title="\N{SHOOTING STAR} This upgrade is already maxed out!",
            text=(
                "**Woah! You have already maxed out this particular upgrade!** \N{HUSHED FACE}\n"
                "You will have to upgrade something else instead. Anyways, congratulations "
                "for your success! \N{PERSON RAISING BOTH HANDS IN CELEBRATION}"
            ),
            cmd=self
        )
        if not edit_msg:
            await self.reply(embed=embed)
        else:
            await self.edit(embed=embed, view=None)

    async def perform_upgrade(
        self,
        profile_attribute: str,
        title: str,
        description: str,
        item_description: str,
        price: int = 1,
        costs_gems: bool = True
    ):
        if check_if_upgrade_maxed(self.user_data, profile_attribute):
            return await self.reject_for_being_maxed(False)

        embed = embed_util.prompt_embed(
            title=f"Purchase upgrade: \"{title}\"?",
            text=(
                "Are you sure that you want to purchase this upgrade? "
                "This is an expensive investment, so think ahead! "
                "\N{MAN}\N{ZERO WIDTH JOINER}\N{BRIEFCASE}"
            ),
            cmd=self
        )
        embed.add_field(name="\N{WHITE MEDIUM STAR} Upgrade", value=item_description)
        embed.add_field(name="\N{BOOKS} Description", value=description)
        currency_emoji = self.client.gem_emoji if costs_gems else self.client.gold_emoji
        embed.add_field(name="\N{MONEY BAG} Price", value=f"**{price}** {currency_emoji}")

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            emoji=currency_emoji,
            label="Purchase this upgrade!"
        ).prompt()

        if not confirm:
            return

        conn = await self.acquire()
        # Refetch user data, because user could have no money or be already maxed
        self.user_data = await self.users.get_user(self.author.id, conn=conn)
        if check_if_upgrade_maxed(self.user_data, profile_attribute):
            await self.release()
            return await self.reject_for_being_maxed(True)

        if costs_gems:
            if self.user_data.gems < price:
                await self.release()
                return await self.edit(
                    embed=embed_util.no_gems_embed(cmd=self, cost=price),
                    view=None
                )
            self.user_data.gems -= price
        else:
            if self.user_data.gold < price:
                await self.release()
                return await self.edit(
                    embed=embed_util.no_money_embed(cmd=self, cost=price),
                    view=None
                )
            self.user_data.gold -= price

        setattr(self.user_data, profile_attribute, getattr(self.user_data, profile_attribute) + 1)
        await self.users.update_user(self.user_data, conn=conn)
        await self.release()

        embed = embed_util.congratulations_embed(
            title=f"Upgrade complete - {title}!",
            text=(
                "Congratulations on your **HUGE** investment! \N{GRINNING FACE WITH STAR EYES}\n"
                "This upgrade is going to help you a lot in the long term! Nice! "
                "\N{CLAPPING HANDS SIGN}"
            ),
            cmd=self
        )
        await self.edit(embed=embed, view=None)

    async def upgrade_farm_size(self):
        await self.perform_upgrade(
            profile_attribute=PROFILE_ATTR_FARM_SLOTS,
            title=f"{self.client.tile_emoji} Farm: Expand size",
            description="Plant more items at a time in your farm!",
            item_description=(
                f"**\N{SQUARED NEW} {self.user_data.farm_slots} \N{RIGHTWARDS ARROW} "
                f"{self.user_data.farm_slots + 1} farm tiles**"
            )
        )

    async def upgrade_factory_capacity(self):
        if self.user_data.level < 3:
            return await self.reject_for_level(3)

        await self.perform_upgrade(
            profile_attribute=PROFILE_ATTR_FACTORY_SLOTS,
            title="\N{FACTORY} Factory: Larger capacity",
            description="Queue more products for production in factory!",
            item_description=(
                f"**\N{SQUARED NEW} {self.user_data.factory_slots} \N{RIGHTWARDS ARROW} "
                f"{self.user_data.factory_slots + 1} factory capacity**"
            )
        )

    async def upgrade_factory_workers(self):
        if self.user_data.level < 3:
            return await self.reject_for_level(3)

        await self.perform_upgrade(
            profile_attribute=PROFILE_ATTR_FACTORY_LEVEL,
            title="\N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING} Factory: Hire more workers",
            description="Make products in factory faster!",
            item_description=(
                f"**\N{SQUARED NEW} {self.user_data.factory_level * 5} \N{RIGHTWARDS ARROW} "
                f"{(self.user_data.factory_level + 1) * 5}% faster production**"
            )
        )

    async def upgrade_trade_deals(self):
        if self.user_data.level < 5:
            return await self.reject_for_level(5)

        await self.perform_upgrade(
            profile_attribute=PROFILE_ATTR_STORE_SLOTS,
            title="\N{HANDSHAKE} Trading: More deals",
            description="Post more trade offers!",
            item_description=(
                f"**\N{SQUARED NEW} {self.user_data.store_slots} \N{RIGHTWARDS ARROW} "
                f"{self.user_data.store_slots + 1} maximum trades**"
            ),
            price=self.user_data.store_slots * TRADES_COST_INCREASE_PER_SLOT,
            costs_gems=False
        )

    async def callback(self):
        upgrade_methods = {
            "farm size": self.upgrade_farm_size,
            "factory capacity": self.upgrade_factory_capacity,
            "factory workers": self.upgrade_factory_workers,
            "trade deals": self.upgrade_trade_deals
        }
        await upgrade_methods[self.upgrade]()


class ShopBoostersCommand(FarmSlashCommand, name="boosters", parent=ShopCommand):
    pass


class ShopBoostersViewCommand(
    FarmSlashCommand,
    name="view",
    description="\N{UPWARDS BLACK ARROW} Lists boosters available for purchase",
    parent=ShopBoostersCommand
):
    """
    With this command you can see the boosters available for you to purchase.<br>
    \N{ELECTRIC LIGHT BULB} For information about buying boosters, please see
    **/help "shop boosters buy"**.
    """
    required_level = 7  # type: int

    async def callback(self):
        embed = discord.Embed(
            title="\N{UPWARDS BLACK ARROW} Booster shop",
            description=(
                "Purchase boosters to speed up your overall game progression in various ways "
                "\N{SUPERHERO}"
            ),
            color=discord.Color.from_rgb(39, 128, 184)
        )

        for boost in self.items.all_boosts_by_id.values():
            embed.add_field(
                name=f"{boost.emoji} {boost.name}",
                value=(
                    f"{boost.info}\n"
                    f"\N{SHOPPING TROLLEY} **/shop boosters buy \"{boost.name.lower()}\"**"
                )
            )
        await self.reply(embed=embed)


class ShopBoostersBuyCommand(
    FarmSlashCommand,
    name="buy",
    description="\N{SHOPPING TROLLEY} Purchases a booster",
    parent=ShopBoostersCommand
):
    """
    Activates a booster. When running this command, you are going to be prompted to choose
    a boost duration and you will be able to view the corresponding prices for each duration.
    When buying a booster, that is already active, the duration will be extended.
    Booster prices are dynamically calculated based on various, your current progression related,
    factors such as your experience level.
    """
    required_level = 7  # type: int

    booster: str = discord.app.Option(description="The booster to activate", autocomplete=True)

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.booster_autocomplete(options[focused]))

    async def callback(self):
        booster = self.lookup_booster(self.booster)

        if booster.required_level > self.user_data.level:
            embed = embed_util.error_embed(
                title="\N{LOCK} This booster is not available for you yet!",
                text=(
                    "**This booster is used for a feature that is not unlocked for your current "
                    "level!**\nThe feature and this booster is going to be unlocked at level "
                    f"\N{TRIDENT EMBLEM} {booster.required_level}."
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        embed = embed_util.prompt_embed(
            title=f"Activate the {booster.emoji} {booster.name} booster?",
            text=(
                "\N{SHOPPING TROLLEY} **Are you sure that you want to purchase the "
                f"\"{booster.emoji} {booster.name}\" booster?\nConfirm, by pressing a button "
                "with your desired boost duration.**\n\N{CLOCK FACE TEN OCLOCK} If you already "
                "have this boost active, buying again is going to extend your previous duration.\n"
                f"\N{OPEN BOOK} Booster description: *{booster.info}*"
            ),
            cmd=self
        )
        embed.set_footer(text=f"You have a total of {self.user_data.gold} gold coins")

        options = (
            (
                "\N{MONEY BAG} 1 day price",
                "Activate for 1 day",
                game_items.BoostDuration.ONE_DAY
            ),
            (
                "\N{MONEY BAG} 3 days price",
                "Activate for 3 days",
                game_items.BoostDuration.THREE_DAYS
            ),
            (
                "\N{MONEY BAG} 7 days price",
                "Activate for 7 days",
                game_items.BoostDuration.SEVEN_DAYS
            )
        )

        buttons = []
        for option in options:
            price = booster.get_boost_price(option[2], self.user_data)
            embed.add_field(name=option[0], value=f"**{price}** {self.client.gold_emoji}")
            buttons.append(views.OptionButton(
                option=option[2],
                style=discord.ButtonStyle.primary,
                emoji=self.client.gold_emoji,
                label=option[1]
            ))

        duration = await views.MultiOptionView(self, buttons, initial_embed=embed).prompt()
        if not duration:
            return

        actual_price = booster.get_boost_price(duration, self.user_data)

        conn = await self.acquire()
        # Refetch user data, because user could have no money after prompt
        user_data = await self.users.get_user(self.author.id, conn=conn)

        if actual_price > user_data.gold:
            await self.release()
            return await self.edit(
                embed=embed_util.no_money_embed(self, actual_price),
                view=None
            )

        user_data.gold -= actual_price
        await self.users.update_user(user_data, conn=conn)
        await self.release()

        partial_boost = game_items.PartialBoost(
            booster.id,
            datetime.datetime.now() + datetime.timedelta(seconds=duration.value)
        )
        await self.user_data.give_boost(self, partial_boost)

        embed = embed_util.success_embed(
            title="Booster successfully activated!",
            text=(
                f"You activated the **{booster.emoji} {booster.name}** booster! "
                "Have fun! \N{SUPERHERO}"
            ),
            cmd=self
        )
        await self.edit(embed=embed, view=None)


def setup(client) -> list:
    return [ShopCollection(client)]

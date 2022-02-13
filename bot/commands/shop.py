import discord
import datetime
from contextlib import suppress
from typing import Optional, Literal

from core import game_items
from .util import views
from .util import embeds as embed_util
from .util.commands import FarmSlashCommand, FarmCommandCollection


TRADES_COST_INCREASE_PER_SLOT = 7500

PROFILE_ATTR_FARM_SLOTS = "farm_slots"
PROFILE_ATTR_FACTORY_SLOTS = "factory_slots"
PROFILE_ATTR_FACTORY_LEVEL = "factory_level"
PROFILE_ATTR_STORE_SLOTS = "store_slots"


def check_if_upgrade_maxed(user_data, profile_attribute: str) -> bool:
    checks_for_maxed = {
        PROFILE_ATTR_FARM_SLOTS: lambda: user_data.farm_slots >= 30,
        PROFILE_ATTR_FACTORY_SLOTS: lambda: user_data.factory_slots >= 15,
        PROFILE_ATTR_FACTORY_LEVEL: lambda: user_data.factory_level >= 10,
        PROFILE_ATTR_STORE_SLOTS: lambda: user_data.store_slots >= 10
    }
    return checks_for_maxed[profile_attribute]()


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
        super().__init__(client, [ShopCommand, MarketCommand, TradesCommand], name="Shop")


class ShopSource(views.AbstractPaginatorSource):
    def __init__(self, entries, section: str):
        super().__init__(entries, per_page=6)
        self.section = section

    async def format_page(self, page, view):
        fmt = ""
        for item in page:
            fmt += (
                f"**[\N{TRIDENT EMBLEM} {item.level}] {item.full_name}** - **{item.gold_price} "
                f"{view.command.client.gold_emoji} / farm tile** \n\N{SHOPPING TROLLEY} "
                f"Start growing in your farm: **/farm plant \"{item.name}\"**\n\n"
            )

        return discord.Embed(
            title=f"\N{CONVENIENCE STORE} Shop: {self.section}",
            color=discord.Color.from_rgb(70, 145, 4),
            description=fmt
        )


class MarketSource(views.AbstractPaginatorSource):
    def __init__(self, entries, section: str):
        super().__init__(entries, per_page=6)
        self.section = section

    async def format_page(self, page, view):
        next_refresh = datetime.datetime.now().replace(
            microsecond=0,
            second=0,
            minute=0
        ) + datetime.timedelta(hours=1)
        refresh_fmt = discord.utils.format_dt(next_refresh, style="t")

        fmt = f"\N{ALARM CLOCK} Market prices are going to change at: **{refresh_fmt}**\n\n"
        for item in page:
            fmt += (
                f"**{item.full_name}** - Market is buying for: "
                f"**{item.gold_reward} {view.command.client.gold_emoji} / unit**\n"
                f"\N{SCALES} Sell to the market: **/market sell \"{item.name}\"**\n\n"
            )

        return discord.Embed(
            title=f"\N{SCALES} Market: {self.section}",
            color=discord.Color.from_rgb(255, 149, 0),
            description=fmt
        )


class TradesSource(views.AbstractPaginatorSource):
    def __init__(self, entries, server_name: str, own_trades: bool = False):
        super().__init__(entries, per_page=6)
        self.server_name = discord.utils.escape_markdown(server_name)
        self.own_trades = own_trades

    async def format_page(self, page, view):
        who = "All" if not self.own_trades else "Your"
        title = f"\N{HANDSHAKE} {who} trade offers in \"{self.server_name}\""
        embed = discord.Embed(title=title, color=discord.Color.from_rgb(229, 232, 21))

        embed.description = (
            f"\N{MAN IN TUXEDO} Welcome to the *\"{self.server_name}\"* trading hall! "
            "Here you can trade items with your friends!\n\N{SQUARED NEW} "
            "To create a new trade in this server, use the **/trades create** command\n\n"
        )

        if not page:
            embed.description += (
                "\N{CROSS MARK} It's empty in here! There are only some cricket noises... "
                "\N{CRICKET}"
            )
            return embed

        for trade in page:
            item = view.command.items.find_item_by_id(trade['item_id'])

            if not self.own_trades:
                fmt = (
                    f"\N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE} Seller: {trade['username']}\n"
                    f"\N{SHOPPING TROLLEY} Buy: **/trades accept {trade['id']}**"
                )
            else:
                fmt = f"\N{WASTEBASKET} Delete: **/trades delete {trade['id']}**"

            gold_emoji = view.command.client.gold_emoji
            embed.add_field(
                name=f"{item.full_name} x{trade['amount']} for {gold_emoji} {trade['price']}",
                value=fmt,
                inline=False
            )

        return embed


class ShopCommand(FarmSlashCommand, name="shop"):
    pass


class ShopUpgradesCommand(FarmSlashCommand, name="upgrades", parent=ShopCommand):
    pass


class ShopUpgradesViewCommand(
    FarmSlashCommand,
    name="view",
    description="\N{WHITE MEDIUM STAR} Lists all upgrades available for purchase",
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
    description="\N{UPWARDS BLACK ARROW} Lists all boosters available for purchase",
    parent=ShopBoostersCommand
):
    """
    With this command you can see the boosters available for you to purchase.<br>
    \N{ELECTRIC LIGHT BULB} For information about buying boosters, please see
    **/help "shop boosters buy"**.
    """
    _required_level: int = 7

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
    _required_level: int = 7

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


class ShopItemsCommand(
    FarmSlashCommand,
    name="items",
    description="\N{CONVENIENCE STORE} Lists all items available for purchase",
    parent=ShopCommand
):
    """With this command you can see all of the game items that you can ever purchase."""
    _requires_account: bool = False

    category: Literal["crops", "trees and bushes", "animal products"] = \
        discord.app.Option(description="The category of items to view")

    async def callback(self):
        class_per_category = {
            "crops": game_items.Crop,
            "trees and bushes": game_items.Tree,
            "animal products": game_items.Animal
        }
        item_class = class_per_category[self.category]

        await views.ButtonPaginatorView(
            self,
            source=ShopSource(
                entries=[item for item in self.items.all_items if isinstance(item, item_class)],
                section=f"{item_class.inventory_emoji} {item_class.inventory_name}"
            )
        ).start()


class MarketCommand(FarmSlashCommand, name="market"):
    pass


class MarketViewCommand(
    FarmSlashCommand,
    name="view",
    description="\N{SCALES} Lists all items available for selling",
    parent=MarketCommand
):
    """
    With this command you can see all of the game items that you can ever sell.<br>
    \N{ELECTRIC LIGHT BULB} For information about selling items, please see
    **/help "market sell"**.
    """
    _requires_account: bool = False

    category: Literal[
        "crops",
        "trees and bushes",
        "animal products",
        "factory products",
        "other items"
    ] = discord.app.Option(description="The category of items to view")

    async def callback(self):
        class_per_category = {
            "crops": game_items.Crop,
            "trees and bushes": game_items.Tree,
            "animal products": game_items.Animal,
            "factory products": game_items.Product,
            "other items": game_items.Special
        }
        item_class = class_per_category[self.category]

        await views.ButtonPaginatorView(
            self,
            source=MarketSource(
                entries=[item for item in self.items.all_items if isinstance(item, item_class)],
                section=f"{item_class.inventory_emoji} {item_class.inventory_name}"
            )
        ).start()


class MarketSellCommand(
    FarmSlashCommand,
    name="sell",
    description="\N{BANKNOTE WITH DOLLAR SIGN} Sells your items to the market",
    parent=MarketCommand
):
    """
    Sell your goodies to game market. The price, at what your items are sold, is determined by the
    in-game market price, that is updated every hour. The market price can be so low, that you
    might not profit from selling your items, or it can be so high, that you might earn a lot
    more than you spent for getting these items.<br>
    \N{ELECTRIC LIGHT BULB} To check the current market price for an item, you can use
    the **/market view** and **/items inspect** commands.
    """
    item: str = discord.app.Option(description="Item to sell to the market", autocomplete=True)
    amount: int = discord.app.Option(description="How many items to sell", min=1, max=100_000)

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.all_items_autocomplete(options[focused]))

    async def callback(self):
        item = self.lookup_item(self.item)

        if not isinstance(item, game_items.SellableItem):
            embed = embed_util.error_embed(
                title="This item cannot be sold to the market",
                text=f"Sorry, you can't sell **{item.full_name}** to our market!",
                cmd=self
            )
            return await self.reply(embed=embed)

        async with self.acquire() as conn:
            item_data = await self.user_data.get_item(self, item.id, conn=conn)

        if not item_data or item_data['amount'] < self.amount:
            return await self.reply(embed=embed_util.not_enough_items(self, item, self.amount))

        total_reward = item.gold_reward * self.amount

        embed = embed_util.prompt_embed(
            title="Please confirm market deal details",
            text="So do you really want to sell these? Let me know if you approve",
            cmd=self
        )
        embed.add_field(name="\N{SCALES} Item", value=f"{self.amount}x {item.full_name}")
        embed.add_field(name=f"{self.client.gold_emoji} Price per unit", value=item.gold_reward)
        embed.add_field(
            name="\N{MONEY BAG} Total earnings",
            value=f"**{total_reward}** {self.client.gold_emoji}"
        )

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            emoji=self.client.gold_emoji,
            label="Sell items to the market"
        ).prompt()

        if not confirm:
            return

        conn = await self.acquire()
        # Must refetch or users can exploit the long prompts and duplicate selling
        item_data = await self.user_data.get_item(self, item.id, conn=conn)
        if not item_data or item_data['amount'] < self.amount:
            await self.release()
            embed = embed_util.not_enough_items(self, item, self.amount)
            return await self.edit(embed=embed, view=None)

        async with conn.transaction():
            await self.user_data.remove_item(self, item.id, self.amount, conn=conn)
            self.user_data.gold += total_reward
            await self.users.update_user(self.user_data, conn=conn)
        await self.release()

        embed = embed_util.success_embed(
            title="Your items have been sold to the market! \N{SCALES}",
            text=(
                "Thank you for selling these items to the market! "
                "\N{SMILING FACE WITH SMILING EYES} We will be looking forward to working with "
                f"you again! You sold **{item.full_name} x{self.amount}** for **{total_reward} "
                f"{self.client.gold_emoji}**"
            ),
            footer=f"You now have {self.user_data.gold} gold coins!",
            cmd=self
        )
        await self.edit(embed=embed, view=None)


class TradesCommand(FarmSlashCommand, name="trades"):
    pass


class TradesListCommand(
    FarmSlashCommand,
    name="list",
    description="\N{PAGE WITH CURL} Lists all active trades in this server",
    parent=TradesCommand
):
    """
    Trades are a way to sell and buy items between players. Trade offers are created per
    server. You can post a limited amount of trade offers per server, but you can buy
    more trading slots with gold from the **/shop**.<br>
    \N{ELECTRIC LIGHT BULB} To create a trade offer, use the **/trades create** command.
    """
    _required_level: int = 5

    owned: Optional[bool] = discord.app.Option(
        description="Set to true, to only list your created trades",
        default=False
    )

    async def callback(self):
        async with self.acquire() as conn:
            if not self.owned:
                query = "SELECT * FROM store WHERE guild_id = $1;"
                trades_data = await conn.fetch(query, self.guild.id)
            else:
                query = "SELECT * FROM store WHERE guild_id = $1 AND user_id = $2;"
                trades_data = await conn.fetch(query, self.guild.id, self.author.id)

        await views.ButtonPaginatorView(
            self,
            source=TradesSource(
                entries=trades_data,
                server_name=self.guild.name,
                own_trades=self.owned
            )
        ).start()


class TradesCreateCommand(
    FarmSlashCommand,
    name="create",
    description="\N{SQUARED NEW} Creates a new trade offer",
    parent=TradesCommand
):
    """
    This command posts a new trade offer in the Discord server you are currently in.
    When creating a trade offer, you have to specify the item you want to sell, the amount
    of items you want to sell, and the price you want to sell them for.
    When trade offer is created, the corresponding items are removed from your inventory.<br>
    \N{ELECTRIC LIGHT BULB} To view already posted trade offers in this server, use the
    **/trades list** command.
    """
    _required_level: int = 5

    item: str = discord.app.Option(description="Item to trade", autocomplete=True)
    amount: int = discord.app.Option(description="How many items to trade", min=1, max=2000)
    price: Literal["cheap", "average", "expensive", "very expensive"] = \
        discord.app.Option(description="Price for the items you want to sell")

    async def autocomplete(self, options, focused):
        return discord.AutoCompleteResponse(self.all_items_autocomplete(options[focused]))

    async def callback(self):
        item = self.lookup_item(self.item)

        if not isinstance(item, game_items.MarketItem):
            embed = embed_util.error_embed(
                title="This item can't be traded!",
                text=f"Sorry, you can't trade **{item.full_name}** here!",
                cmd=self
            )
            return await self.reply(embed=embed)

        conn = await self.acquire()

        item_data = await self.user_data.get_item(self, item.id, conn=conn)
        if not item_data or item_data['amount'] < self.amount:
            await self.release()
            return await self.reply(embed=embed_util.not_enough_items(self, item, self.amount))

        base_min, base_max = item.min_market_price, item.max_market_price
        prices_map = {
            "cheap": lambda: base_min * self.amount,
            "average": lambda: int(((base_min + base_max) / 2) * self.amount),
            "expensive": lambda: base_max * self.amount,
            "very expensive": lambda: int((base_max * self.amount) * 1.25)
        }
        total_price = prices_map[self.price]()

        query = "SELECT COUNT(*) FROM store WHERE user_id = $1 AND guild_id = $2;"
        used_slots = await conn.fetchval(query, self.author.id, self.guild.id)
        if used_slots >= self.user_data.store_slots:
            await self.release()

            embed = embed_util.error_embed(
                title="You have reached maximum active trade offers in this server!",
                text=(
                    "Oh no! We can't create this trade offer, because you already have used "
                    f"**{used_slots} of your {self.user_data.store_slots}** available trading "
                    "deals! \N{BAR CHART}\n\n"
                    "\N{ELECTRIC LIGHT BULB} What you can do about this:\na) Wait for someone "
                    "to accept any of your current trades.\nb) Delete some trades.\n"
                    "c) Upgrade your max. deal capacity with the "
                    "**/shop upgrades buy \"trade deals\"** command."
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        async with conn.transaction():
            await self.user_data.remove_item(self, item.id, self.amount, conn=conn)

            # We store username, to avoid fetching the user from Discord's
            # API just to get the username every time someone wants to view
            # the trades. (we don't store members data in bot's cache)
            query = """
                    INSERT INTO store
                    (guild_id, user_id, username, item_id, amount, price)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id;
                    """
            trade_id = await conn.fetchval(
                query,
                self.guild.id,
                self.author.id,
                self.author.name,
                item.id,
                self.amount,
                total_price
            )

        await self.release()

        embed = embed_util.success_embed(
            title="Trade offer is successfully created!",
            text=(
                "All set! The trade offer is up! \N{THUMBS UP SIGN}\n"
                f"You have put **{self.amount}x {item.full_name}** for sale at a price of "
                f"**{total_price}** {self.client.gold_emoji} for this server members!\n\n"
                "\N{BUSTS IN SILHOUETTE} If you know the person you are selling your items to, "
                f"they can use this command to buy your items: **/trades accept {trade_id}**\n"
                "\N{WASTEBASKET} If you want to cancel this trade offer use: "
                f"**/trades delete {trade_id}**"
            ),
            cmd=self
        )
        await self.reply(embed=embed)


class TradesAcceptCommand(
    FarmSlashCommand,
    name="accept",
    description="\N{HANDSHAKE} Accepts someone else's trade offer",
    parent=TradesCommand
):
    """
    This command accepts a trade offer and purchases the listed items from the other player.
    You can only purchase items that are listed in the current Discord server you are in.<br>
    \N{ELECTRIC LIGHT BULB} To create a trade offer in this server, use the
    **/trades create** command.<br>
    You can't accept your own trades, but you can delete them with the **/trades delete** command.
    """
    _required_level: int = 5

    id: int = discord.app.Option(
        description="Trade ID of the trade to accept",
        min=1,
        max=2147483647  # PostgreSQL's max int value
    )

    async def reject_for_not_found(self, edit: bool):
        embed = embed_util.error_embed(
            title="Trade not found!",
            text=(
                f"I could not find a trade with **ID: {self.id}**! \N{CONFUSED FACE}\n"
                "This trade might already be accepted by someone else or deleted by the "
                "trader itself. View all the available trades with the **/trades list** "
                "command. \N{CLIPBOARD}"
            ),
            cmd=self
        )
        if not edit:
            await self.reply(embed=embed)
        else:
            await self.edit(embed=embed, view=None)

    async def callback(self):
        async with self.acquire() as conn:
            query = "SELECT * FROM store WHERE id = $1 AND guild_id = $2;"
            trade_data = await conn.fetchrow(query, self.id, self.guild.id)

        if not trade_data:
            return await self.reject_for_not_found(False)

        if trade_data['user_id'] == self.author.id:
            embed = embed_util.error_embed(
                title="You can't trade with yourself!",
                text=(
                    "\N{WASTEBASKET} If you want to cancel this trade, use: "
                    f"**/trades delete {self.id}**"
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        item = self.items.find_item_by_id(trade_data['item_id'])
        amount, price = trade_data['amount'], trade_data['price']

        if item.level > self.user_data.level:
            embed = embed_util.error_embed(
                title="\N{LOCK} Insufficient experience level!",
                text=(
                    f"Sorry, you can't buy **{item.full_name}** just yet! "
                    "What are you planning to do with an item, that you can't even use yet? "
                    "I'm just curious... \N{THINKING FACE}"
                ),
                footer=f"This item is going to be unlocked at experience level {item.level}.",
                cmd=self
            )
            return await self.reply(embed=embed)

        try:
            seller_member = await self.guild.fetch_member(trade_data['user_id'])
        except discord.HTTPException as e:
            if e.status != 404:
                raise e

            async with self.acquire() as conn:
                query = "DELETE FROM store WHERE id = $1;"
                await conn.execute(query, self.id)

            embed = embed_util.error_embed(
                title="Oops, the trader has vanished!",
                text=(
                    "Looks like this trader has left this cool server, so their trade isn't "
                    "available anymore. Sorry! \N{CRYING FACE}"
                ),
                footer="Let's hope that they will join back later",
                cmd=self
            )
            return await self.reply(embed=embed)

        embed = embed_util.prompt_embed(
            title="Do you accept this trade offer?",
            text="Are you sure that you want to buy these items from this user?",
            cmd=self
        )
        embed.add_field(
            name="\N{MAN}\N{ZERO WIDTH JOINER}\N{EAR OF RICE} Seller",
            value=seller_member.mention
        )
        embed.add_field(name="\N{LABEL} Item", value=f"{amount}x {item.full_name}")
        embed.add_field(name="\N{MONEY BAG} Total price", value=f"{price} {self.client.gold_emoji}")

        confirm = await views.ConfirmPromptView(
            self,
            initial_embed=embed,
            emoji=self.client.gold_emoji,
            label="Accept trade offer",
            deny_label="Deny trade offer"
        ).prompt()

        if not confirm:
            return

        conn = await self.acquire()
        # Trade might already be deleted by now
        query = "SELECT * FROM store WHERE id = $1;"
        trade_data = await conn.fetchrow(query, self.id)

        if not trade_data:
            await self.release()
            return await self.reject_for_not_found(True)

        user_data = await self.users.get_user(self.author.id, conn=conn)
        trade_user_data = await self.users.get_user(trade_data['user_id'], conn=conn)

        if user_data.gold < price:
            await self.release()
            return await self.edit(embed=embed_util.no_money_embed(self, price), view=None)

        async with conn.transaction():
            query = "DELETE FROM store WHERE id = $1;"
            await conn.execute(query, self.id)
            await user_data.give_item(self, item.id, amount, conn=conn)
            user_data.gold -= price
            trade_user_data.gold += price
            await self.users.update_user(user_data, conn=conn)
            await self.users.update_user(trade_user_data, conn=conn)
        await self.release()

        embed = embed_util.success_embed(
            title="Successfully bought items!",
            text=(
                f"You bought **{amount}x {item.full_name}** from {seller_member.mention} for "
                f"**{price}** {self.client.gold_emoji}\n"
                "What a great trade you both just made! \N{HANDSHAKE}"
            ),
            cmd=self
        )
        await self.edit(embed=embed, view=None)

        if not trade_user_data.notifications:
            return

        embed = embed_util.success_embed(
            title="Congratulations! You just made a sale!",
            text=(
                f"Hey boss! I only came to say that {self.author.mention} just accepted your trade "
                f"offer and bought your **{amount}x {item.full_name}** for **{price}** "
                f"{self.client.gold_emoji}"
            ),
            cmd=self,
            private=True
        )
        # User might have direct messages disabled
        with suppress(discord.HTTPException):
            await seller_member.send(embed=embed)


class TradesDeleteCommand(
    FarmSlashCommand,
    name="delete",
    description="\N{WASTEBASKET} Cancels your trade offer",
    parent=TradesCommand
):
    """
    This command is used to cancel a trade offer. You can only cancel your own trade offers.
    Canceling a trade offer will return the items to your inventory.
    """
    _required_level: int = 5

    id: int = discord.app.Option(
        description="Trade ID of the trade to delete",
        min=1,
        max=2147483647  # PostgreSQL's max int value
    )

    async def callback(self):
        conn = await self.acquire()
        # It is fine if they delete their own trades from other guilds
        query = "SELECT * FROM store WHERE id = $1 AND user_id = $2;"
        trade_data = await conn.fetchrow(query, self.id, self.author.id)

        if not trade_data:
            await self.release()
            embed = embed_util.error_embed(
                title="Trade offer not found!",
                text=(
                    f"Hmm... I could not find your trade **ID: {self.id}**! You might have "
                    "provided wrong ID or this trade that does not exist anymore. \N{THINKING FACE}"
                    "\nCheck your created trades in this server with the **/trades list** command."
                ),
                cmd=self
            )
            return await self.reply(embed=embed)

        async with conn.transaction():
            query = "DELETE FROM store WHERE id = $1;"
            await conn.execute(query, self.id)
            item_id, amount = trade_data['item_id'], trade_data['amount']
            await self.user_data.give_item(self, item_id, amount, conn=conn)
        await self.release()

        item = self.items.find_item_by_id(trade_data['item_id'])
        embed = embed_util.success_embed(
            title="Trade offer canceled!",
            text=(
                f"\N{WASTEBASKET} Okay, I removed your trade offer: **{trade_data['amount']}x "
                f"{item.full_name} for {trade_data['price']} {self.client.gold_emoji}**"
            ),
            footer="These items are now moved back to your /inventory",
            cmd=self
        )
        await self.reply(embed=embed)


def setup(client) -> list:
    return [ShopCollection(client)]

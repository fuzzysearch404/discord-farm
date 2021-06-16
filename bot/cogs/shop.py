import discord
from datetime import datetime, timedelta
from discord.ext import commands, menus

from .utils import pages
from .utils import time
from .utils import checks
from .utils import embeds
from .utils import converters
from core import game_items


class MarketSource(menus.ListPageSource):
    def __init__(self, entries, section: str):
        super().__init__(entries, per_page=6)
        self.section = section

    async def format_page(self, menu, page):
        next_refresh = datetime.now().replace(
                microsecond=0,
                second=0,
                minute=0
            ) + timedelta(hours=1)

        time_until = next_refresh - datetime.now()
        timer = time.seconds_to_time(time_until.total_seconds())

        head = (
            "\u23f0 Market prices are going to change in: "
            f"**{timer}**\n\n"
        )

        fmt = ""
        for item in page:
            fmt += (
                f"**{item.emoji} {item.name.capitalize()}** - "
                f"Buying for: **{item.gold_reward} {menu.bot.gold_emoji} "
                "/ unit** \n\u2696\ufe0f Sell items to market: **"
                f"{menu.ctx.prefix}sell {item.name}**\n\n"
            )

        embed = discord.Embed(
            title=f"\u2696\ufe0f Market: {self.section}",
            color=discord.Color.from_rgb(255, 149, 0),
            description=head + fmt
        )

        embed.set_footer(
            text=(
                f"Page {menu.current_page + 1}/{self.get_max_pages()} | "
                "Sell multiple units at a time, by providing amount. For "
                "example: \"sell lettuce 40\"."
            )
        )

        return embed


class ShopSource(menus.ListPageSource):
    def __init__(self, entries, section: str):
        super().__init__(entries, per_page=6)
        self.section = section

    async def format_page(self, menu, page):
        fmt = ""
        for item in page:
            fmt += (
                f"**[\ud83d\udd31 {item.level}] "
                f"{item.emoji} {item.name.capitalize()}** - "
                f"**{item.gold_price} {menu.bot.gold_emoji} "
                "/ farm tile** \n\ud83d\uded2 Start growing in your farm: **"
                f"{menu.ctx.prefix}plant {item.name}**\n\n"
            )

        embed = discord.Embed(
            title=f"\ud83c\udfea Shop: {self.section}",
            color=discord.Color.from_rgb(70, 145, 4),
            description=fmt
        )

        embed.set_footer(
            text=(
                f"Page {menu.current_page + 1}/{self.get_max_pages()} | "
                "Plant in multiple farm tiles at a time, by providing amount. "
                "For example: \"plant lettuce 2\"."
            )
        )

        return embed


class Shop(commands.Cog):
    """
    Welcome to the shop! Here you can view the prices of plants,
    upgrade your farm, buy boosters and sell your items to the
    market. Market prices are changing every hour, so be
    responsible about your selling things here.
    """
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.group(case_insensitive=True)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market(self, ctx):
        """
        \ud83d\udecd\ufe0f Access the market to sell items

        Market is organized in some subcategories.
        """
        if ctx.invoked_subcommand:
            return

        embed = discord.Embed(
            title="\ud83d\udecd\ufe0f Please choose a market category",
            description=(
                "\ud83d\udc4b Hey there fellow farmer! "
                "\ud83d\udc68\u200d\ud83d\udcbb We are looking forward "
                "to do business with you. Please note that our deals are "
                "changing every hour. So what would you like to sell?"
            ),
            colour=discord.Color.from_rgb(255, 149, 0)
        )
        embed.add_field(
            name="\ud83c\udf3d Crops Harvest",
            value=f"**{ctx.prefix}market crop**"
        )
        embed.add_field(
            name="\ud83c\udf52 Trees and Bushes Harvest",
            value=f"**{ctx.prefix}market tree**"
        )
        embed.add_field(
            name="\ud83d\udc3d Animal Harvest",
            value=f"**{ctx.prefix}market animal**"
        )
        embed.add_field(
            name="\ud83c\udf66 Factory Products",
            value=f"**{ctx.prefix}market factory**"
        )
        embed.add_field(
            name="\ud83d\udce6 Other items",
            value=f"**{ctx.prefix}market other**"
        )
        embed.set_footer(text="The market is split into some subcategories")

        await ctx.reply(embed=embed)

    @market.command(name="crop", aliases=["crops", "c"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_crops(self, ctx):
        """\ud83c\udf3d View current prices for crops harvest"""
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_crops,
                section="\ud83c\udf3d Crops Harvest"
            )
        )

        await paginator.start(ctx)

    @market.command(name="tree", aliases=["trees", "t", "bush", "bushes", "b"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_tree(self, ctx):
        """\ud83c\udf52 View current prices for trees and bushes harvest"""
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_trees,
                section="\ud83c\udf52 Trees and Bushes Harvest"
            )
        )

        await paginator.start(ctx)

    @market.command(name="animal", aliases=["animals", "a"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_animal(self, ctx):
        """\ud83d\udc3d View current prices for animal harvest"""
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_animals,
                section="\ud83d\udc3d Animal Harvest"
            )
        )

        await paginator.start(ctx)

    @market.command(name="factory", aliases=["products", "f", "p"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_factory(self, ctx):
        """\ud83c\udf66 View current prices for factory products"""
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_products,
                section="\ud83c\udf66 Factory Products"
            )
        )

        await paginator.start(ctx)

    @market.command(name="other", aliases=["others", "o"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_other(self, ctx):
        """\ud83d\udce6 View current prices for other items"""
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_specials,
                section="\ud83d\udce6 Other items"
            )
        )

        await paginator.start(ctx)

    @commands.group(case_insensitive=True)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop(self, ctx):
        """
        \ud83c\udfea Access the shop to plant items, buy upgrades or boosters

        Shop is organized in some subcategories.
        """
        if ctx.invoked_subcommand:
            return

        embed = discord.Embed(
            title="\ud83c\udfea Please choose a shop category",
            description=(
                "\ud83d\udc4b Hey there fellow farmer! "
                "Welcome to our shop! Here you can buy something to plant "
                "in your farm, various upgrades and boosters. \ud83d\uded2 "
                "What would you like to buy?"
            ),
            colour=discord.Color.from_rgb(70, 145, 4)
        )
        embed.add_field(
            name="\ud83c\udf3d Crops",
            value=f"**{ctx.prefix}shop crop**"
        )
        embed.add_field(
            name="\ud83c\udf52 Trees and Bushes",
            value=f"**{ctx.prefix}shop tree**"
        )
        embed.add_field(
            name="\ud83d\udc3d Animals",
            value=f"**{ctx.prefix}shop animal**"
        )
        embed.add_field(
            name="\u2b06 Boosters",
            value=f"**{ctx.prefix}shop boosters**"
        )
        embed.add_field(
            name="\u2b50 Upgrades",
            value=f"**{ctx.prefix}shop upgrades**"
        )
        embed.set_footer(text="The shop is split into some subcategories")

        await ctx.reply(embed=embed)

    @shop.command(name="crop", aliases=["crops", "c"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop_crops(self, ctx):
        """\ud83c\udf3d View current costs for planting crops"""
        paginator = pages.MenuPages(
            source=ShopSource(
                entries=ctx.items.all_crops,
                section="\ud83c\udf3d Crops"
            )
        )

        await paginator.start(ctx)

    @shop.command(name="tree", aliases=["trees", "t", "bush", "bushes", "b"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop_tree(self, ctx):
        """\ud83c\udf52 View current costs for planting trees and bushes"""
        paginator = pages.MenuPages(
            source=ShopSource(
                entries=ctx.items.all_trees,
                section="\ud83c\udf52 Trees and Bushes"
            )
        )

        await paginator.start(ctx)

    @shop.command(name="animal", aliases=["animals", "a"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop_animal(self, ctx):
        """\ud83d\udc3d View current costs for growing animals"""
        paginator = pages.MenuPages(
            source=ShopSource(
                entries=ctx.items.all_animals,
                section="\ud83d\udc3d Animal"
            )
        )

        await paginator.start(ctx)

    @shop.command(name="boosters", aliases=["boosts", "boost"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop_boosters(self, ctx):
        """\u2b06 View booster shop"""
        embed = discord.Embed(
            title="\u2b06 Booster shop",
            description=(
                "Purchase boosters to speed up your overall game "
                "progression in various ways \ud83e\uddb8"
            ),
            color=discord.Color.from_rgb(39, 128, 184)
        )

        for boost in ctx.items.all_boosts:
            embed.add_field(
                name=f"{boost.emoji} {boost.name}",
                value=(
                    f"{boost.info}\n\ud83d\uded2 "
                    f"**{ctx.prefix}boost {boost.name.lower()}**"
                )
            )

        await ctx.reply(embed=embed)

    @commands.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def boost(self, ctx, *, booster: converters.Boost):
        """
        \u2b06 Purchase and activate a booster

        For booster types and descriptions,
        check out command **{prefix}shop boosters**.
        If you already have a booster active of the same type,
        buying again is going to extend your previous duration.

        __Arguments__:
        `booster` - booster to lookup for purchase

        __Usage examples__:
        {prefix} `boost Leo` - activate "Leo" booster
        """
        embed = embeds.prompt_embed(
            title="Activate booster?",
            text=(
                f"\ud83d\uded2 **Are you sure that you want to purchase "
                f"booster {booster.emoji} {booster.name}? Confirm, by "
                "pressing a button with your desired boost duration.**\n"
                "\ud83d\udd59 If you already have this boost active, buying "
                "again is going to extend your previous duration.\n"
                f"\ud83d\udcd6 Booster description: *{booster.info}*"
            ),
            ctx=ctx
        )

        price_one = booster.get_boost_price(
            game_items.BoostDuration.ONE_DAY, ctx.user_data
        )
        embed.add_field(
            name="1\ufe0f\u20e3 1 day price",
            value=f"**{price_one}** {self.bot.gold_emoji}"
        )
        price_three = booster.get_boost_price(
            game_items.BoostDuration.THREE_DAYS, ctx.user_data
        )
        embed.add_field(
            name="3\ufe0f\u20e3 3 days price",
            value=f"**{price_three}** {self.bot.gold_emoji}"
        )
        price_seven = booster.get_boost_price(
            game_items.BoostDuration.SEVEN_DAYS, ctx.user_data
        )
        embed.add_field(
            name="7\ufe0f\u20e3 7 days price",
            value=f"**{price_seven}** {self.bot.gold_emoji}"
        )

        duration, msg = await pages.BoostPurchasePrompt(
            embed=embed).prompt(ctx)

        if not duration:
            return

        actual_price = booster.get_boost_price(duration, ctx.user_data)

        async with ctx.acquire() as conn:
            # Refetch user data, because user could have no money after prompt
            user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

            if actual_price > ctx.user_data.gold:
                return await msg.edit(
                    embed=embeds.no_money_embed(ctx, user_data, actual_price)
                )

            user_data.gold -= actual_price
            await ctx.users.update_user(user_data, conn=conn)

        obtained_boost = game_items.ObtainedBoost(
            booster.id, datetime.now() + timedelta(seconds=duration.value)
        )
        await ctx.user_data.give_boost(ctx, obtained_boost)

        await msg.edit(
            embed=embeds.success_embed(
                title="Booster activated!",
                text=(
                    f"You bought **{booster.emoji} {booster.name}** booster! "
                    "The booster has been activated! Have fun! \ud83e\uddb8"
                ),
                ctx=ctx
            )
        )

    def get_next_trades_slot_cost(self, current_count: int):
        return current_count * 6000

    @shop.command(name="upgrades", aliases=["upgrade", "u"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def shop_upgrades(self, ctx):
        """\u2b50 View upgrades shop"""
        user_data = ctx.user_data
        trades_cost = self.get_next_trades_slot_cost(user_data.store_slots)

        embed = discord.Embed(
            title="\u2b50 Upgrades shop",
            description=(
                "\u2699\ufe0f Purchase upgrades to make your game "
                "progress faster! "
            ),
            color=discord.Color.from_rgb(255, 162, 0)
        )
        embed.add_field(
            name=f"{self.bot.tile_emoji} Farm: Expand size",
            value=(
                f"Plant more items in your farm!\n"
                f"**\ud83c\udd95 {user_data.farm_slots} \u2192 "
                f"{user_data.farm_slots + 1} farm tiles**\n"
                f"\ud83d\udcb0 Price: **1** {self.bot.gem_emoji}\n\n"
                f"\ud83d\uded2 **{ctx.prefix}upgrade farm**"
            )
        )
        embed.add_field(
            name="\ud83c\udfed Factory: Capacity",
            value=(
                f"Queue more products to produce in factory!\n"
                f"**\ud83c\udd95 {user_data.factory_slots} \u2192 "
                f"{user_data.factory_slots + 1} factory capacity**\n"
                f"\ud83d\udcb0 Price: **1** {self.bot.gem_emoji}\n\n"
                f"\ud83d\uded2 **{ctx.prefix}upgrade capacity**"
            )
        )
        if user_data.factory_level < 10:
            embed.add_field(
                name=(
                    "\ud83d\udc68\u200d\ud83c\udf73 Factory: Workers"
                ),
                value=(
                    f"Make products in factory faster!\n"
                    f"**\ud83c\udd95 {user_data.factory_level * 5} \u2192 "
                    f"{(user_data.factory_level + 1) * 5}% faster production "
                    f"speed**\n\ud83d\udcb0 Price: **1** {self.bot.gem_emoji}"
                    f"\n\n\ud83d\uded2 **{ctx.prefix}upgrade workers**"
                )
            )
        embed.add_field(
            name="\ud83e\udd1d Trading: More deals",
            value=(
                f"Post more trade offers!\n"
                f"**\ud83c\udd95 {user_data.store_slots} \u2192 "
                f"{user_data.store_slots + 1} maximum trades**\n"
                f"\ud83d\udcb0 Price: **{trades_cost}** {self.bot.gold_emoji}"
                f"\n\n\ud83d\uded2 **{ctx.prefix}upgrade trading**"
            )
        )

        await ctx.reply(embed=embed)

    @commands.command(aliases=["s"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def sell(self, ctx, *, item: converters.ItemAndAmount, amount=1):
        """
        \u2696\ufe0f Sell your goodies to game's market

        You can only sell your harvest and factory production.

        __Arguments__:
        `item` - item to lookup for selling (item's name or ID)
        __Optional arguments__:
        `amount` - specify how many units to sell

        __Usage examples__:
        {prefix} `sell lettuce` - sell just a single lettuce item unit
        {prefix} `sell lettuce 50` - sell fifty lettuce item units
        {prefix} `sell 1 50` - sell fifty units of lettuce items (by using ID)
        """
        item, amount = item

        # Should not happen, but just in case
        if not isinstance(item, game_items.SellableItem):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="This item can't be sold!",
                    text=(
                        f"Sorry, you can't sell **{item.emoji} "
                        f"{item.name.capitalize()}** in our market!"
                    ),
                    ctx=ctx
                )
            )

        item_data = await ctx.user_data.get_item(ctx, item.id)
        if not item_data or item_data['amount'] < amount:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=f"You don't have enough {item.name}!",
                    text=(
                        "Either you don't own or you don't "
                        f"have enough **({amount}x) {item.emoji} "
                        f"{item.name.capitalize()} ** in your warehouse!"
                    ),
                    footer=(
                        "Check your warehouse with the \"invenotory\" command"
                    ),
                    ctx=ctx
                )
            )

        total_reward = item.gold_reward * amount

        embed = embeds.prompt_embed(
            title="Please confirm market deal details",
            text="So are you selling these items? Let me know if you approve",
            ctx=ctx
        )
        embed.add_field(
            name="\u2696\ufe0f Item",
            value=f"{amount}x {item.emoji} {item.name.capitalize()}"
        )
        embed.add_field(
            name=f"{self.bot.gold_emoji} Price per unit",
            value=item.gold_reward
        )
        embed.add_field(
            name="\ud83d\udcb0 Total earnings",
            value=f"**{total_reward}** {self.bot.gold_emoji}"
        )
        if amount == 1:
            embed.set_footer(
                text=(
                    "\ud83d\udca1 Sell more than one unit at a time, by "
                    "specifying the amount. For example: "
                    f"\"sell {item.name} 50\""
                )
            )

        menu = pages.ConfirmPrompt(pages.CONFIRM_COIN_BUTTTON, embed=embed)
        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        async with ctx.acquire() as conn:
            async with conn.transaction():
                # Must refetch or user can exploit the long prompts and dupe
                item_data = await ctx.user_data.get_item(
                    ctx, item.id, conn=conn
                )
                if not item_data or item_data['amount'] < amount:
                    return await msg.edit(
                        embed=embeds.error_embed(
                            title=f"You don't have enough {item.name}!",
                            text=(
                                "Either you don't own or you don't "
                                f"have enough **({amount}x) {item.emoji} "
                                f"{item.name.capitalize()} ** in your "
                                "warehouse!"
                            ),
                            footer=(
                                "Check your warehouse with the \"inventory\" "
                                "command"
                            ),
                            ctx=ctx
                        )
                    )

                await ctx.user_data.remove_item(
                    ctx, item.id, amount, conn=conn
                )

                ctx.user_data.gold += total_reward
                await ctx.users.update_user(ctx.user_data, conn=conn)

        await msg.edit(
            embed=embeds.success_embed(
                title="Your items have been sold to the market! \u2696\ufe0f",
                text=(
                    "Thank you for the selling these items to the market! "
                    "\ud83d\ude0a We will be looking forward to working "
                    f"with you again! You sold **{item.emoji} "
                    f"{item.name.capitalize()} x{amount}** for **"
                    f"{total_reward} {self.bot.gold_emoji}**"
                ),
                footer=f"You now have {ctx.user_data.gold} gold coins!",
                ctx=ctx
            )
        )

    @commands.group(case_insensitive=True)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def upgrade(self, ctx):
        """
        \u2b50 Upgrade something!

        For available upgrades please see **{prefix}shop upgrades**
        """
        if ctx.invoked_subcommand:
            return

        await self.shop_upgrades.invoke(ctx)

    async def perform_upgrade(
        self,
        ctx,
        attr: str,
        title: str,
        description: str,
        item_str: str,
        price: int,
        with_gem: bool = True
    ):
        embed = embeds.prompt_embed(
            title=f"Purchase upgrade: {title}?",
            text=(
                "Are you sure that you want to purchase this upgrade? "
                "This is an expensive investment, so think ahead! "
                "\ud83d\udc68\u200d\ud83d\udcbc"
            ),
            ctx=ctx
        )
        embed.add_field(name="\u2b50 Upgrade", value=item_str)
        embed.add_field(name="\ud83d\udcda Description", value=description)
        emoji = self.bot.gem_emoji if with_gem else self.bot.gold_emoji
        embed.add_field(
            name="\ud83d\udcb0 Price",
            value=f"**{price}** {emoji}"
        )

        if with_gem:
            menu = pages.ConfirmPrompt(pages.CONFIRM_GEM_BUTTON, embed=embed)
        else:
            menu = pages.ConfirmPrompt(pages.CONFIRM_COIN_BUTTTON, embed=embed)

        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        async with ctx.acquire() as conn:
            async with conn.transaction():
                # Refetch user data, because user could have no money
                user_data = await ctx.users.get_user(ctx.author.id, conn=conn)

                if with_gem:
                    if user_data.gems < price:
                        return await msg.edit(
                            embed=embeds.no_gems_embed(ctx, user_data, price)
                        )

                    user_data.gems -= price
                else:
                    if user_data.gold < price:
                        return await msg.edit(
                            embed=embeds.no_money_embed(ctx, user_data, price)
                        )

                    user_data.gold -= price

                old_value = getattr(user_data, attr)
                setattr(user_data, attr, old_value + 1)

                await ctx.users.update_user(user_data, conn=conn)

        return await msg.edit(
            embed=embeds.congratulations_embed(
                title=f"Upgrade complete - {title}",
                text=(
                    "Congratulations on your **HUUGE** investment! "
                    "\ud83e\udd29\n This upgrade is going to "
                    "change a lot for you in a long term! Nice! \ud83d\udc4f"
                ),
                ctx=ctx
            )
        )

    @upgrade.command(aliases=["field"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def farm(self, ctx):
        """
        \ud83d\uded2 Expand farm, by adding more tiles

        If you currently can plant only 2 items per time in your farm,
        then after this upgrade you will be able to plant 3 items simultanesly.
        """
        await self.perform_upgrade(
            ctx=ctx,
            attr="farm_slots",
            title=f"{self.bot.tile_emoji} Farm: Expand size",
            description="Plant more items in your farm!",
            item_str=(
                f"**\ud83c\udd95 {ctx.user_data.farm_slots} \u2192 "
                f"{ctx.user_data.farm_slots + 1} farm tiles**"
            ),
            price=1
        )

    @upgrade.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def capacity(self, ctx):
        """
        \ud83c\udd95 Add more capacity for factory

        If you currently can queue 2 items for production in factory,
        then after this upgrade you will be able to queue 3 items simultanesly.
        """
        await self.perform_upgrade(
            ctx=ctx,
            attr="factory_slots",
            title="\ud83c\udfed Factory: Capacity",
            description="Queue more products to produce in factory!",
            item_str=(
                f"**\ud83c\udd95 {ctx.user_data.factory_slots} \u2192 "
                f"{ctx.user_data.factory_slots + 1} factory capacity**"
            ),
            price=1
        )

    @upgrade.command(aliases=["worker"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def workers(self, ctx):
        """
        \ud83d\udc68\u200d\ud83c\udf73 Increase production speed for factory

        If your current factory item production speed bonus is 5%,
        then after this upgrade your production speed bonus is going to be 10%.
        """
        if ctx.user_data.factory_level >= 10:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=(
                        "Maximum factory workers amount reached! "
                        "\ud83d\udc68\u200d\ud83c\udf73"
                    ),
                    text=(
                        "You already have reached the maximum factory worker "
                        "amount! Enjoy the **__super speed__**! \ud83d\udca5"
                    ),
                    ctx=ctx
                )
            )

        await self.perform_upgrade(
            ctx=ctx,
            attr="factory_level",
            title="\ud83d\udc68\u200d\ud83c\udf73 Factory: Workers",
            description="Make products in factory faster!",
            item_str=(
                f"**\ud83c\udd95 {ctx.user_data.factory_level * 5} \u2192 "
                f"{(ctx.user_data.factory_level + 1) * 5}% faster production**"
            ),
            price=1
        )

    @upgrade.command(aliases=["trades", "trade"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def trading(self, ctx):
        """
        \ud83e\udd1d Increase the limit of your trading deals

        If you currently can post 2 trading deals per time,
        then after this upgrade you will be able to post 3 trading deals
        simultanesly.
        """
        await self.perform_upgrade(
            ctx=ctx,
            attr="store_slots",
            title="\ud83e\udd1d Trading: More deals",
            description="Post more trade offers!",
            item_str=(
                f"**\ud83c\udd95 {ctx.user_data.store_slots} \u2192 "
                f"{ctx.user_data.store_slots + 1} maximum trades**"
            ),
            price=self.get_next_trades_slot_cost(ctx.user_data.store_slots),
            with_gem=False
        )


def setup(bot):
    bot.add_cog(Shop(bot))

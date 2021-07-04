import discord
import asyncio
from contextlib import suppress
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
                f"**{item.full_name}** - Buying for: **"
                f"{item.gold_reward} {menu.bot.gold_emoji} "
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
                f"{item.full_name}** - **{item.gold_price} "
                f"{menu.bot.gold_emoji} / farm tile** \n\ud83d\uded2 "
                "Start growing in your farm: **"
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


class TradesSource(menus.ListPageSource):
    def __init__(self, entries, server_name: str, own_trades: bool = False):
        super().__init__(entries, per_page=6)
        self.server_name = server_name
        self.own_trades = own_trades

    async def format_page(self, menu, page):
        if self.own_trades:
            title = f"\ud83e\udd1d Your trade offers in \"{self.server_name}\""
        else:
            title = f"\ud83e\udd1d All trade offers in \"{self.server_name}\""

        embed = discord.Embed(
            title=title,
            color=discord.Color.from_rgb(229, 232, 21)
        )

        head = (
            f"\ud83e\udd35 Welcome to the *\"{self.server_name}\"* trading "
            "hall! Here you can trade items with your friends!\n\ud83c\udd95 "
            "To create a new trade in this server, use the "
            f"**{menu.ctx.prefix}trades create** command\n\n"
        )

        if not page:
            fmt = (
                "\u274c It's empty in here! There are only some "
                "cricket noises... \ud83e\udd97"
            )
        else:
            fmt = "\n\n".join(page)

        embed.description = head + fmt

        embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
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

    @market.command(name="tree", aliases=["trees", "t", "bush", "bushes"])
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

    @shop.command(name="tree", aliases=["trees", "t", "bush", "bushes"])
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

    @shop.command(name="boosters", aliases=["boosts", "boost", "b"])
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
        embed.set_footer(
            text=f"You have a total of {ctx.user_data.gold} gold coins"
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
        if user_data.farm_slots < 30:
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
        if user_data.factory_slots < 15:
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
                        f"Sorry, you can't sell **{item.full_name}** "
                        "in our market!"
                    ),
                    ctx=ctx
                )
            )

        item_data = await ctx.user_data.get_item(ctx, item.id)
        if not item_data or item_data['amount'] < amount:
            return await ctx.reply(
                embed=embeds.not_enough_items(ctx, item, amount)
            )

        total_reward = item.gold_reward * amount

        embed = embeds.prompt_embed(
            title="Please confirm market deal details",
            text="So are you selling these items? Let me know if you approve",
            ctx=ctx
        )
        embed.add_field(
            name="\u2696\ufe0f Item",
            value=f"{amount}x {item.full_name}"
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
                    "\ud83d\udca1 Sell more than one units at a time, by "
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
                        embed=embeds.not_enough_items(ctx, item, amount)
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
                    f"with you again! You sold **{item.full_name} "
                    f"x{amount}** for **{total_reward} {self.bot.gold_emoji}**"
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
        if ctx.user_data.farm_slots >= 30:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Maximum farm size reached! \ud83d\ude9c",
                    text=(
                        "You already have reached the maximum farm size! We "
                        "have no more nearby land to expand to! \ud83d\ude31"
                    ),
                    ctx=ctx
                )
            )

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
        if ctx.user_data.factory_slots >= 15:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Maximum factory size reached! \ud83c\udfed",
                    text=(
                        "You already have reached the maximum factory size! "
                        "There is no more space for storing "
                        "more raw materials! \ud83d\ude33"
                    ),
                    ctx=ctx
                )
            )

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

    @commands.group(aliases=["trade", "trading", "t"], case_insensitive=True)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def trades(self, ctx):
        """
        \ud83e\udd1d Sell items to friends in your server.

        Trades are per server. If you post a trade in server "X",
        then your trades are only going to be available in server "X".
        You can only post limited amount of trade offers, but you
        can upgrade your trading capacity in the shop.
        """
        if ctx.invoked_subcommand:
            return

        async with ctx.acquire() as conn:
            query = """
                    SELECT * FROM store
                    WHERE guild_id = $1;
                    """

            trades_data = await conn.fetch(query, ctx.guild.id)

        entries = []

        for trade in trades_data:
            item = ctx.items.find_item_by_id(trade['item_id'])

            entries.append(
                f"\ud83d\udc68\u200d\ud83c\udf3e Seller: {trade['username']}\n"
                f"\ud83c\udff7\ufe0f Items: **{trade['amount']}x "
                f"{item.full_name} for {self.bot.gold_emoji} {trade['price']}"
                f"**\n\ud83d\uded2 Buy: **{ctx.prefix}trades accept "
                f"{trade['id']}**"
            )

        paginator = pages.MenuPages(
            source=TradesSource(
                entries=entries,
                server_name=ctx.guild.name
            )
        )

        await paginator.start(ctx)

    @trades.command(name="list")
    @checks.has_account()
    @checks.avoid_maintenance()
    async def trades_list(self, ctx):
        """
        \ud83d\udcc3 List your created trades
        """
        async with ctx.acquire() as conn:
            query = """
                    SELECT * FROM store
                    WHERE guild_id = $1
                    AND user_id = $2;
                    """

            trades_data = await conn.fetch(query, ctx.guild.id, ctx.author.id)

        entries = []

        for trade in trades_data:
            item = ctx.items.find_item_by_id(trade['item_id'])

            entries.append(
                f"\ud83c\udff7\ufe0f Items: **{trade['amount']}x "
                f"{item.full_name} for {self.bot.gold_emoji} {trade['price']}"
                f"**\n\ud83d\uddd1\ufe0f Delete: **{ctx.prefix}trades delete "
                f"{trade['id']}**"
            )

        paginator = pages.MenuPages(
            source=TradesSource(
                entries=entries,
                server_name=ctx.guild.name,
                own_trades=True
            )
        )

        await paginator.start(ctx)

    @trades.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def accept(self, ctx, trade_id: int):
        """
        \ud83e\udd1d Accept player's trade offer

        __Arguments__:
        `trade_id` - ID of the trade you want to accept

        __Usage examples__:
        {prefix} `trade accept 123` - accept trade offer with ID 123.
        """
        def trade_not_found_embed():
            return embeds.error_embed(
                title="Trade not found!",
                text=(
                    f"I could not find a trade **ID: {trade_id}**! "
                    "\ud83d\ude15\nThis trade might already be accepted "
                    "by someone else or deleted by the trader itself. "
                    "View all the available trades with the "
                    f"**{ctx.prefix}trades** command. \ud83d\udccb"
                ),
                ctx=ctx
            )

        if trade_id < 1 or trade_id > 2147483647:
            return await ctx.reply("\u274c Invalid trade ID")

        async with ctx.acquire() as conn:
            query = """
                    SELECT * FROM store
                    WHERE id = $1
                    AND guild_id = $2;
                    """

            trade_data = await conn.fetchrow(query, trade_id, ctx.guild.id)

        if not trade_data:
            return await ctx.reply(embed=trade_not_found_embed())

        if trade_data['user_id'] == ctx.author.id:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="You can't trade with yourself!",
                    text=(
                        "\ud83d\uddd1\ufe0f If you want to cancel this trade, "
                        f"then use: **{ctx.prefix}trades delete {trade_id}**"
                    ),
                    ctx=ctx
                )
            )

        item = ctx.items.find_item_by_id(trade_data['item_id'])
        amount = trade_data['amount']
        price = trade_data['price']

        if item.level > ctx.user_data.level:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="\ud83d\udd12 Insufficient experience level!",
                    text=(
                        f"**Sorry, you can't buy {item.full_name} just yet!** "
                        "What are you planning to do with an item, that you "
                        "can't even use yet? I'm just curious... \ud83e\udd14"
                    ),
                    footer=(
                        "This item is going to be unlocked at "
                        f"experience level {item.level}."
                    ),
                    ctx=ctx
                )
            )

        try:
            seller_member = await ctx.guild.fetch_member(trade_data['user_id'])
        except discord.HTTPException as e:
            if e.status != 404:
                raise e

            async with ctx.acquire() as conn:
                query = "DELETE FROM store WHERE id = $1;"

                await conn.execute(query, trade_id)

            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Oops, the trader has vanished!",
                    text=(
                        "Looks like this trader has left this cool "
                        "server, so their trade also isn't "
                        "available anymore. Sorry! \ud83d\ude22"
                    ),
                    footer="Let's hope that they will join back later",
                    ctx=ctx
                )
            )

        embed = embeds.prompt_embed(
            title="Do you accept this trade offer?",
            text=(
                "Are you sure that you want to buy these items "
                "from this user?"
            ),
            ctx=ctx
        )
        embed.add_field(
            name="\ud83d\udc68\u200d\ud83c\udf3e Seller",
            value=seller_member.mention
        )
        embed.add_field(
            name="\ud83c\udff7\ufe0f Item",
            value=f"{amount}x {item.full_name}"
        )
        embed.add_field(
            name="\ud83d\udcb0 Total price",
            value=f"{price} {self.bot.gold_emoji}"
        )

        menu = pages.ConfirmPrompt(pages.CONFIRM_COIN_BUTTTON, embed=embed)
        confirm, msg = await menu.prompt(ctx)

        if not confirm:
            return

        async with ctx.acquire() as conn:
            async with conn.transaction():
                query = """
                        SELECT * FROM store
                        WHERE id = $1;
                        """
                # Might already be deleted by now
                trade_data = await conn.fetchrow(query, trade_id)

                if not trade_data:
                    return await msg.edit(embed=trade_not_found_embed())

                user_data = await ctx.users.get_user(ctx.author.id, conn=conn)
                # If there is a trade, then the user must exist too (no check)
                trade_user_data = await ctx.users.get_user(
                    trade_data['user_id'], conn=conn
                )

                if user_data.gold < price:
                    return await ctx.reply(
                        embed=embeds.no_money_embed(ctx, user_data, price)
                    )

                query = "DELETE FROM store WHERE id = $1;"
                await conn.execute(query, trade_id)

                await user_data.give_item(ctx, item.id, amount, conn=conn)

                user_data.gold -= price
                trade_user_data.gold += price
                await ctx.users.update_user(user_data, conn=conn)
                await ctx.users.update_user(trade_user_data, conn=conn)

        await msg.edit(
            embed=embeds.success_embed(
                title="Successfully bought items!",
                text=(
                    f"You bought **{amount}x {item.full_name}** "
                    f"from {seller_member.mention} for **{price}** "
                    f"{self.bot.gold_emoji}\nWhat a great trade you "
                    "both just made! \ud83e\udd1d"
                ),
                ctx=ctx
            )
        )

        if not trade_user_data.notifications:
            return

        with suppress(discord.HTTPException):
            await seller_member.send(
                embed=embeds.success_embed(
                    title="Congratulations! You just made a sale!",
                    text=(
                        "Hey boss! I only came to say that "
                        f"{ctx.author.mention} just accepted your trade "
                        f"offer and bought your **{amount}x "
                        f"{item.full_name}** for **{price}** "
                        f"{self.bot.gold_emoji}"
                    ),
                    ctx=ctx,
                    private=True
                )
            )

    @trades.command(aliases=["new", "start"])
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def create(
        self,
        ctx,
        *,
        item: converters.ItemAndAmount,
        amount: int = 1
    ):
        """
        \ud83c\udd95 Create a new trade offer

        __Arguments__:
        `item` - item to lookup for trading (item's name or ID)
        __Optional arguments__:
        `amount` - specify how many units to trade

        __Usage examples__:
        {prefix} `trades create lettuce` - create a trade with 1 lettuce unit.
        {prefix} `trades create lettuce 50` - create a trade with 50
        lettuce units.
        {prefix} `trades create 1 50` - create a trade with 50 lettuce units.
        (by using ID)
        """
        item, amount = item

        if not isinstance(item, game_items.MarketItem):
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="This item can't be traded!",
                    text=f"Sorry, you can't trade **{item.full_name}**!",
                    ctx=ctx
                )
            )

        item_data = await ctx.user_data.get_item(ctx, item.id)
        if not item_data or item_data['amount'] < amount:
            return await ctx.reply(
                embed=embeds.not_enough_items(ctx, item, amount)
            )

        min_price = int((item.min_market_price * amount))
        max_price = int((item.max_market_price * amount) * 1.35)

        embed = embeds.prompt_embed(
            title="What is going to be the price for this trade?",
            text=(
                "\u270f\ufe0f **Please input a desired price in the chat with "
                "numbers**!\n\ud83d\udc49 No need to add extra symbols or "
                "commands before the number. For example, if you want to "
                f"trade it for: {self.bot.gold_emoji} {max_price}, then just "
                f"type \"{max_price}\""
            ),
            ctx=ctx
        )
        embed.add_field(
            name="\ud83c\udff7\ufe0f Item",
            value=f"{amount}x {item.full_name}"
        )
        embed.add_field(
            name="\ud83d\udcb0 Allowed price range",
            value=f"{min_price} - {max_price} {self.bot.gold_emoji}"
        )

        if amount == 1:
            embed.set_footer(
                text=(
                    "\ud83d\udca1 Trade more than one units at a time, by "
                    "specifying the amount. For example: "
                    f"\"trades create {item.name} 50\""
                )
            )

        await ctx.reply(embed=embed)

        def message_check(msg):
            return msg.author.id == ctx.author.id and \
                msg.channel == ctx.channel and \
                msg.content.isdigit()

        try:
            msg = await self.bot.wait_for(
                "message", check=message_check, timeout=45.0
            )
        except asyncio.TimeoutError:
            return await ctx.reply(
                "\u274c I've been waiting too long "
                "for your message... Please try again"
            )

        user_price = int(msg.content)

        if user_price < min_price or user_price > max_price:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title="Nope, we can't sell those for this price!",
                    text=(
                        "We only allow fair trades here. \ud83d\ude0c Your "
                        "price is too low or too high!\nPlease try creating a "
                        f"new trade for {amount}x {item.full_name} that "
                        "is in this price range: **"
                        f"{min_price} - {max_price} {self.bot.gold_emoji}**"
                    ),
                    ctx=ctx
                )
            )

        async with ctx.acquire() as conn:
            query = """
                    SELECT COUNT(*) FROM store
                    WHERE user_id = $1
                    AND guild_id = $2;
                    """
            used_slots = await conn.fetchval(
                query, ctx.author.id, ctx.guild.id
            )

            if used_slots >= ctx.user_data.store_slots:
                slots = ctx.user_data.store_slots

                return await ctx.reply(
                    embed=embeds.error_embed(
                        title=(
                            "You have reached maximum active trade offers "
                            "in this server!"
                        ),
                        text=(
                            "Oh no! We can't create this trade offer, because "
                            f"you already have used **{used_slots} of your "
                            f"{slots}** available deal slots! \ud83d\udcca\n\n"
                            "What you can do about this:\na) Wait for someone "
                            "to accept any of your current trades.\nb) "
                            "Delete some trades.\nc) Upgrade your max. deal "
                            f"capacity with the **{ctx.prefix}upgrade "
                            "trading** command."
                        ),
                        ctx=ctx
                    )
                )

            item_data = await ctx.user_data.get_item(
                ctx, item.id, conn=conn
            )
            if not item_data or item_data['amount'] < amount:
                return await ctx.reply(
                    embed=embeds.not_enough_items(ctx, item, amount)
                )

            async with conn.transaction():
                await ctx.user_data.remove_item(
                    ctx, item.id, amount, conn=conn
                )

                # We store username, to avoid fetching the user from Discord's
                # API just to get the username every time someone wants to view
                # some trades. (we don't store members data in bot's cache)
                query = """
                        INSERT INTO store
                        (guild_id, user_id, username,
                        item_id, amount, price)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id;
                        """

                trade_id = await conn.fetchval(
                    query,
                    ctx.guild.id,
                    ctx.author.id,
                    ctx.author.name,
                    item.id,
                    amount,
                    user_price
                )

        await ctx.reply(
            embed=embeds.success_embed(
                title="Trade offer is successfully created!",
                text=(
                    "All set! The trade offer is up! \ud83d\udc4d\n"
                    f"You have put for sale **{amount}x {item.full_name}** "
                    f"at a price of **{user_price}** {self.bot.gold_emoji} "
                    "for this server's members!\n\n"
                    "\ud83d\udc65 If you know the person you are selling your "
                    "items to, they can use this command to buy your items: "
                    f"**{ctx.prefix}trades accept {trade_id}**\n"
                    "\ud83d\uddd1\ufe0f If you want to cancel the trade "
                    f"offer use: **{ctx.prefix}trades delete {trade_id}**"
                ),
                ctx=ctx
            )
        )

    @trades.command(aliases=["remove"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def delete(self, ctx, trade_id: int):
        """
        \ud83d\uddd1\ufe0f Remove a trade offer

        You can only remove your own trades.

        __Arguments__:
        `trade_id` - ID of the trade to remove

        __Usage examples__:
        {prefix} `trades remove 1234` - remove trade with ID "1234"
        """
        if trade_id < 1 or trade_id > 2147483647:
            return await ctx.reply("\u274c Invalid trade ID")

        async with ctx.acquire() as conn:
            # It is fine if they delete their own trades from other guilds
            query = """
                    SELECT * FROM store
                    WHERE id = $1
                    AND user_id = $2;
                    """

            trade_data = await conn.fetchrow(query, trade_id, ctx.author.id)

            if not trade_data:
                return await ctx.reply(
                    embed=embeds.error_embed(
                        title="Trade not found!",
                        text=(
                            "Hmm... I could not find your trade **ID: "
                            f"{trade_id}**! You might have provided a wrong "
                            "ID or trade that does not exist anymore. "
                            "\ud83e\udd14\nCheck your created trades in this "
                            f"server with the **{ctx.prefix}trades list** "
                            "command."
                        ),
                        ctx=ctx
                    )
                )

            async with conn.transaction():
                query = """
                        DELETE FROM store
                        WHERE id = $1;
                        """

                await conn.execute(query, trade_id)

                await ctx.user_data.give_item(
                    ctx, trade_data['item_id'], trade_data['amount'], conn=conn
                )

        item = ctx.items.find_item_by_id(trade_data['item_id'])

        await ctx.reply(
            embed=embeds.success_embed(
                title="Trade offer canceled!",
                text=(
                    "\ud83d\uddd1\ufe0f Okey, I removed your trade offer: "
                    f"**{trade_data['amount']}x {item.full_name} for "
                    f"{trade_data['price']} {self.bot.gold_emoji}**"
                ),
                footer="These items are now moved back to your inventory",
                ctx=ctx
            )
        )


def setup(bot):
    bot.add_cog(Shop(bot))

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
                f"**{item.emoji} {item.name.capitalize()}** - "
                f"**{item.gold_price} {menu.bot.gold_emoji} "
                "/ farm tile** \n\ud83d\uded2 Start growing in your farm: **"
                f"{menu.ctx.prefix}plant {item.name}**\n\n"
            )

        embed = discord.Embed(
            title=f"\ud83c\udfea Shop: {self.section}",
            color=discord.Color.from_rgb(52, 125, 235),
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
            colour=discord.Color.from_rgb(52, 125, 235)
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
        """\ud83d\udc3d View current prices for growing animals"""
        paginator = pages.MenuPages(
            source=ShopSource(
                entries=ctx.items.all_animals,
                section="\ud83d\udc3d Animal"
            )
        )

        await paginator.start(ctx)

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

        confirm, msg = await pages.ConfirmPromptCoin(embed=embed).prompt(ctx)

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


def setup(bot):
    bot.add_cog(Shop(bot))

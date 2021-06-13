import discord
from datetime import datetime, timedelta
from discord.ext import commands, menus

from .utils import pages
from .utils import time
from .utils import checks


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
                "/ item** \n\u2696\ufe0f Sell items to market: **"
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
                "Sell multiple items at a time, by providing amount. For "
                "example: \"sell lettuce 40\"."
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
        \ud83d\udecd\ufe0f Access the market to sell items.
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
            name="\ud83c\udf52 Trees Harvest",
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

    @market.command(name="tree", aliases=["trees", "t"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_tree(self, ctx):
        """
        \ud83c\udf52 View current prices for trees harvest
        """
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_trees,
                section="\ud83c\udf52 Trees Harvest"
            )
        )

        await paginator.start(ctx)

    @market.command(name="animal", aliases=["animals", "a"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def market_animal(self, ctx):
        """
        \ud83d\udc3d View current prices for animal harvest
        """
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
        """
        \ud83c\udf66 View current prices for factory products
        """
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
        """
        \ud83d\udce6 View current prices for other items
        """
        paginator = pages.MenuPages(
            source=MarketSource(
                entries=ctx.items.all_specials,
                section="\ud83d\udce6 Other items"
            )
        )

        await paginator.start(ctx)


def setup(bot):
    bot.add_cog(Shop(bot))

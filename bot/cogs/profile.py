import aiohttp
import discord
import random
from discord.ext import commands, menus
from datetime import datetime

from core import game_items
from core import modifications
from core.exceptions import ItemNotFoundException
from .utils import checks
from .utils import time
from .utils import embeds
from .utils import pages
from .utils import converters


class InventorySource(menus.ListPageSource):
    def __init__(self, entries, target_user: discord.Member):
        super().__init__(entries, per_page=30)
        self.target = target_user

    async def format_page(self, menu, page):
        target = self.target

        embed = discord.Embed(
            title=(
                f"{menu.bot.warehouse_emoji} "
                f"{target.nick or target.name}'s warehouse"
            ),
            color=discord.Color.from_rgb(234, 231, 231)
        )

        if not page:
            fmt = "\ud83d\udc00 It's empty. There are only a few rats in here"
        else:
            # NOTE: We have different ID prefixes for different item classes.
            # Also we have ordered the items by ID in our query for this.

            def get_item_class_name(item_and_amount):
                return item_and_amount.item.__class__.__name__ + "s"

            last_class = get_item_class_name(page[0])
            fmt = f"**{last_class}**\n"

            iteration = 0
            for item_and_amount in page:
                iteration += 1

                current_item_class = get_item_class_name(item_and_amount)
                if current_item_class != last_class:
                    last_class = current_item_class

                    fmt += f"\n**{last_class}**\n"
                    iteration = 1

                item = item_and_amount.item
                amount = item_and_amount.amount

                # 3 items per line
                if iteration <= 3:
                    fmt += f"{item.emoji} {item.name.capitalize()} x{amount} "
                else:
                    fmt += (
                        f"\n{item.emoji} {item.name.capitalize()} x{amount} "
                    )
                    iteration = 1

            embed.set_footer(
                text=(
                    f"Page {menu.current_page + 1}/{self.get_max_pages()} | "
                    "These items can only be accessed by their owner"
                ),
                icon_url=target.avatar_url
            )

        embed.description = fmt

        return embed


class AllItemsSource(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=15)

    async def format_page(self, menu, page):
        head = (
            "| \ud83c\udff7\ufe0f Item | \ud83d\udd0e View item "
            "command |\n\n"
        )

        embed = discord.Embed(
            title="\ud83d\udd13 Items unlocked for your level:",
            color=discord.Color.from_rgb(255, 172, 51),
            description=head + "\n".join(page)
        )

        embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )

        return embed


class Profile(commands.Cog):
    """
    Common commands relating to your profile.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        self.topgg_token = bot.config['topgg']['auth_token']

    @commands.command(aliases=["prof", "account", "acc"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def profile(self, ctx, member: discord.Member = None):
        """
        \ud83c\udfe0 Shows your or someone's profile

        Useful command for your overall progress tracking.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `profile` - view your profile
        {prefix} `profile @user` - view user's profile
        """
        if not member:
            user = ctx.user_data
        else:
            user = await checks.get_other_member(ctx, member)

        bot = self.bot
        prefix = ctx.prefix
        target_user = member or ctx.author

        all_boosts = await user.get_all_boosts(ctx)
        boost_ids = [x.id for x in all_boosts]

        farm_slots = user.farm_slots
        farm_slots_formatted = farm_slots
        factory_slots_formatted = user.factory_slots

        if "farm_slots" in boost_ids:
            farm_slots += 2
            farm_slots_formatted = f"**{farm_slots}** \ud83d\udc39"
        if "factory_slots" in boost_ids:
            factory_slots_formatted = \
                f"**{user.factory_slots + 2}** \ud83e\udd89"

        async with ctx.db.acquire() as conn:
            query = """
                    SELECT sum(amount) FROM inventory
                    WHERE user_id = $1;
                    """

            inventory_size = await conn.fetchval(query, user.user_id)

            query = """
                    SELECT ends, (SELECT sum(fields_used)
                    FROM farm WHERE user_id = $1)
                    FROM farm WHERE user_id = $1
                    ORDER BY ends LIMIT 1;
                    """

            field_data = await conn.fetchrow(query, user.user_id)

            query = """
                    SELECT ends FROM factory
                    WHERE user_id = $1 ORDER BY ends;
                    """

            nearest_factory = await conn.fetchval(query, user.user_id)

            query = """
                    SELECT count(id) FROM store
                    WHERE user_id = $1
                    AND guild_id = $2;
                    """

            used_store_slots = await conn.fetchval(
                query, user.user_id, ctx.guild.id
            )

        inventory_size = inventory_size or 0

        datetime_now = datetime.now()

        if not field_data:
            nearest_harvest = "-"
            free_farm_slots = farm_slots
        else:
            nearest_harvest = field_data[0]

            if nearest_harvest > datetime_now:
                nearest_harvest = nearest_harvest - datetime_now
                nearest_harvest = \
                    time.seconds_to_time(nearest_harvest.total_seconds())
            else:
                nearest_harvest = "\u2705"

            free_farm_slots = farm_slots - field_data[1]
            if free_farm_slots < 0:  # Expired slots booster visual bug fix
                free_farm_slots = 0

        if not nearest_factory:
            nearest_factory = "-"
        else:
            if nearest_factory > datetime_now:
                nearest_factory = nearest_factory - datetime_now
                nearest_factory = \
                    time.seconds_to_time(nearest_factory.total_seconds())

        lab_cooldown = await checks.get_user_cooldown(
            ctx, "recent_research", other_user_id=user.user_id
        )
        lab_info = f"\ud83d\udd0e **{prefix}lab** {target_user.mention}"

        if lab_cooldown:
            lab_info = (
                "\ud83e\uddf9 Busy for "
                f"{time.seconds_to_time(lab_cooldown)}\n"
            ) + lab_info

        embed = discord.Embed(
            title=(
                f"\ud83c\udfe1 {target_user.nick or target_user.name}'s "
                "profile"
            ),
            color=discord.Color.from_rgb(189, 66, 17)
        )
        embed.add_field(
            name=f"\ud83d\udd31 {user.level}. level",
            value=f"{bot.xp_emoji} {user.xp}/{user.next_level_xp}"
        )
        embed.add_field(name=f"{bot.gold_emoji} Gold", value=user.gold)
        embed.add_field(name=f"{bot.gem_emoji} Gems", value=user.gems)
        embed.add_field(
            name=f"{bot.warehouse_emoji} Warehouse",
            value=(
                f"\ud83c\udff7\ufe0f {inventory_size} inventory items"
                f"\n\ud83d\udd0e **{prefix}inventory** {target_user.mention}"
            )
        )
        embed.add_field(
            name='\ud83c\udf31 Farm',
            value=(
                f"{bot.tile_emoji} {free_farm_slots}/{farm_slots_formatted} "
                f"free tiles\n\u23f0 Next harvest: {nearest_harvest}"
                f"\n\ud83d\udd0e **{prefix}farm** {target_user.mention}"
            )
        )
        if user.level > 2:
            embed.add_field(
                name='\ud83c\udfed Factory',
                value=(
                    f"\ud83d\udce6 Max. capacity: {factory_slots_formatted}"
                    "\n\ud83d\udc68\u200d\ud83c\udf73 Workers: "
                    f"{user.factory_level}/10"
                    f"\n\u23f0 Next production: {nearest_factory}"
                    f"\n\ud83d\udd0e **{prefix}factory** {target_user.mention}"
                )
            )
        else:
            embed.add_field(
                name="\ud83c\udfed Factory",
                value="\ud83d\udd12 Unlocks at level 3."
            )
        embed.add_field(
            name='\ud83e\udd1d Server trades',
            value=(
                "\ud83d\udcb0 Active trades: "
                f"{used_store_slots}/{user.store_slots}\n"
                f"\ud83d\udd0e **{prefix}trades** {target_user.mention}"
            )
        )
        embed.add_field(
            name="\ud83e\uddec Laboratory",
            value=lab_info
        )
        embed.add_field(
            name="\u2b06 Boosters",
            value=(
                f"\ud83d\udcc8 {len(all_boosts)} boosters active"
                f"\n\ud83d\udd0e **{prefix}boosts** {target_user.mention}"
            )
        )

        await ctx.reply(embed=embed)

    @commands.command(aliases=["bal", "gold", "gems", "money"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def balance(self, ctx):
        """
        \ud83d\udcb0 Quickly check your gold and gem amounts

        For more detailed information about your profile,
        check out command {prefix}`profile`.
        """
        await ctx.reply(
            f"{self.bot.gold_emoji} **Gold:** {ctx.user_data.gold} "
            f"{self.bot.gem_emoji} **Gems:** {ctx.user_data.gems}"
        )

    @commands.command(aliases=["warehouse", "inv"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def inventory(self, ctx, member: discord.Member = None):
        """
        \ud83d\udd12 Shows your or someone's inventory

        Useful to see what items you or someone else owns in their warehouse.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `inventory` - view your inventory
        {prefix} `inventory @user` - view user's inventory
        """
        if not member:
            user = ctx.user_data
        else:
            user = await checks.get_other_member(ctx, member)

        target_user = member or ctx.author

        async with ctx.db.acquire() as conn:
            all_items_data = await user.get_all_items(ctx, conn=conn)

        items_and_amounts = []
        for data in all_items_data:
            try:
                item = ctx.items.find_item_by_id(data['item_id'])
            except ItemNotFoundException:
                # Could be a chest
                continue

            item_and_amt = game_items.ItemAndAmount(item, data['amount'])
            items_and_amounts.append(item_and_amt)

        paginator = pages.MenuPages(
            source=InventorySource(items_and_amounts, target_user)
        )

        await paginator.start(ctx)

    @commands.group(case_insensitive=True, aliases=["chest"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def chests(self, ctx):
        """
        \ud83e\uddf0 Shows your chests

        Chests are containing random goodies, that you can obtain, by
        opening these chests. Each different chest type has different
        possible rewards and odds. You can obtain chests in various ways
        by playing the game, for example, by collecting daily bonuses.
        """
        if ctx.invoked_subcommand:
            return

        async with ctx.db.acquire() as conn:
            # When adding new chests, please increase this range
            query = """
                    SELECT * FROM inventory
                    WHERE user_id = $1
                    AND
                    item_id BETWEEN 1000 AND 1005;
                    """

            chest_data = await conn.fetch(query, ctx.author.id)

        chest_ids_and_amounts = {}
        if chest_data:
            for chest in chest_data:
                chest_ids_and_amounts[chest['item_id']] = chest['amount']

        embed = discord.Embed(
            title="\ud83e\uddf0 Your chests",
            color=discord.Color.from_rgb(196, 145, 16),
            description=(
                f"Open chests by typing **{ctx.prefix}chests open name**. "
                f"For example: **{ctx.prefix}chests open rare**"
            )
        )

        for chest in ctx.items.all_chests:
            try:
                amount = chest_ids_and_amounts[chest.id]
            except KeyError:
                amount = 0

            embed.add_field(
                name=f"{chest.emoji} {chest.name.capitalize()} chest",
                value=(f"Available: **{amount}**")
            )

        await ctx.reply(embed=embed)

    @chests.command()
    @checks.has_account()
    @checks.avoid_maintenance()
    async def open(self, ctx, *, chest: converters.Chest):
        """
        \ud83e\uddf0 Opens a chest (if you own one)

        __Arguments__:
        `chest` - chest to open. Can be chest name or chest ID

        __Usage examples__:
        {prefix} `chests open rare` - opens "rare" chest (by chest's name)
        {prefix} `chests open 1002` - opens "rare" chest (by chest's ID)
        """
        async with ctx.db.acquire() as conn:
            chest_data = await ctx.user_data.get_item(ctx, chest.id, conn=conn)

        if not chest_data:
            return await ctx.reply(
                embed=embeds.error_embed(
                    title=f"You don't have any {chest.name} chests",
                    text=(
                        "I just contacted our warehouse manager, and with a "
                        "deep regret, I have to say that *inhales*, you don't "
                        f"have any **{chest.emoji} {chest.name.capitalize()} "
                        "chests** in your inventory. "
                        "Obtain one or try another chest."
                    ),
                    ctx=ctx
                )
            )

        user_level = ctx.user_data.level

        gold_reward, gems_reward = 0, 0
        items_won = []

        base_growables_multiplier = int(user_level / 5) + 1

        # This time we just hardcode this all in.
        # Gold chest
        if chest.id == 1000:
            min_gold = 25 * user_level
            max_gold = 100 * user_level

            gold_reward = random.randint(min_gold, max_gold)
        # Common
        elif chest.id == 1001:
            if bool(random.getrandbits(1)):
                multiplier = int(base_growables_multiplier / 2) or 1

                items_won = ctx.items.get_random_items(
                    user_level,
                    growables_multiplier=multiplier,
                    products=False,
                    total_draws=1
                )
            else:
                min_gold = 5 * user_level
                max_gold = 10 * user_level

                gold_reward = random.randint(min_gold, max_gold)
        # Uncommon
        elif chest.id == 1002:
            items_won = ctx.items.get_random_items(
                user_level,
                extra_luck=0.05,
                growables_multiplier=base_growables_multiplier,
                products=False,
                total_draws=random.randint(1, 2)
            )

            if not random.randint(0, 4):
                min_gold = 3 * user_level
                max_gold = 6 * user_level

                gold_reward = random.randint(min_gold, max_gold)
        # Rare
        elif chest.id == 1003:
            items_won = ctx.items.get_random_items(
                user_level,
                extra_luck=0.25,
                growables_multiplier=base_growables_multiplier + 1,
                total_draws=random.randint(1, 3)
            )

            if not random.randint(0, 4):
                min_gold = 4 * user_level
                max_gold = 8 * user_level

                gold_reward = random.randint(min_gold, max_gold)
        # Epic
        elif chest.id == 1004:
            if not random.randint(0, 9):
                base_growables_multiplier += random.randint(1, 3)

            items_won = ctx.items.get_random_items(
                user_level,
                extra_luck=0.455,
                growables_multiplier=base_growables_multiplier + 5,
                products_multiplier=2,
                total_draws=random.randint(2, 4)
            )

            if bool(random.getrandbits(1)):
                min_gold = 8 * user_level
                max_gold = 15 * user_level

                gold_reward = random.randint(min_gold, max_gold)
        # Legendary
        elif chest.id == 1005:
            if not random.randint(0, 4):
                base_growables_multiplier += random.randint(1, 5)

            items_won = ctx.items.get_random_items(
                user_level,
                extra_luck=0.777,
                growables_multiplier=base_growables_multiplier + 8,
                products_multiplier=3,
                total_draws=random.randint(3, 5)
            )

            min_gold = 10 * user_level
            max_gold = 30 * user_level

            if not random.randint(0, 4):
                min_gold += 20 * user_level
                max_gold += 50 * user_level

            gold_reward = random.randint(min_gold, max_gold)

            if not random.randint(0, 14):
                gems_reward = 1

        if gold_reward:
            ctx.user_data.gold += gold_reward
        if gems_reward:
            ctx.user_data.gems += gems_reward

        async with ctx.db.acquire() as conn:
            async with conn.transaction():
                await ctx.user_data.remove_item(ctx, chest.id, 1, conn=conn)

                if gold_reward or gems_reward:
                    await ctx.users.update_user(ctx.user_data, conn=conn)

                if items_won:
                    await ctx.user_data.give_items(ctx, items_won, conn=conn)

        rewards = "\n\n"

        if items_won:
            for item, amount in items_won:
                rewards += (
                    f"**{item.emoji} {item.name.capitalize()}**: {amount} "
                )
        if gold_reward:
            rewards += f"**{self.bot.gold_emoji} {gold_reward} gold** "
        if gems_reward:
            rewards += f"**{self.bot.gem_emoji} {gems_reward} gems** "

        await ctx.reply(
            embed=embeds.congratulations_embed(
                title=f"{chest.name.capitalize()} chest opened!",
                text=(
                    f"{ctx.author.mention} tried their luck, by opening "
                    f"their {chest.emoji} **{chest.name.capitalize()} "
                    "chest**, and won these awesome rewards:" + rewards
                ),
                footer="These items are now moved to your inventory",
                ctx=ctx
            )
        )

    @commands.command(aliases=["boosts"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def boosters(self, ctx, member: discord.Member = None):
        """
        \u2b06 Lists your or someone else's boosters

        Boosters speed up your overall game progression in various ways
        or alters your gameplay.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        {prefix} `boosters` - view your active boosters
        {prefix} `boosters @user` - view user's active boosters
        """
        if not member:
            user = ctx.user_data
        else:
            user = await checks.get_other_member(ctx, member)

        target_user = member or ctx.author

        all_boosts = await user.get_all_boosts(ctx)

        if not all_boosts:
            if not member:
                error_title = "Nope, you don't have any active boosters!"
            else:
                error_title = (
                    f"Nope, {member} does not have any active boosters!"
                )

            return await ctx.reply(
                embed=embeds.error_embed(
                    title=error_title,
                    text=(
                        "\u2b06\ufe0f Purchase boosters with the "
                        f"**{ctx.prefix}shop boosters** command"
                    ),
                    ctx=ctx
                )
            )

        embed = discord.Embed(
            title=f"\u2b06\ufe0f {target_user}'s active boosters",
            color=discord.Color.from_rgb(39, 128, 184),
            description=(
                "\ud83d\udecd\ufe0f Purchase boosters with the "
                f"**{ctx.prefix}shop boosters** command"
            )
        )

        for boost in all_boosts:
            boost_info = ctx.items.find_boost_by_id(boost.id)

            remaining_duration = boost.duration - datetime.now()
            time_str = time.seconds_to_time(remaining_duration.total_seconds())

            embed.add_field(
                name=f"{boost_info.emoji} {boost_info.name}",
                value=f"{time_str} remaining"
            )

        await ctx.reply(embed=embed)

    @commands.command(aliases=["all", "unlocked"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def allitems(self, ctx):
        """
        \ud83d\udd0d Shows all unlocked items for your level

        Useful to check what items you can grow or make.
        As you level up, this command is going to show more items.
        """
        all_items = ctx.items.find_all_items_by_level(
            ctx.user_data.level
        )

        fmt = []
        for item in all_items:
            fmt.append(
                f"{item.emoji} {item.name.capitalize()} - "
                f"**{ctx.prefix}item {item.id}**"
            )

        paginator = pages.MenuPages(source=AllItemsSource(fmt))

        await paginator.start(ctx)

    @commands.command(aliases=["dailybonus"])
    @checks.user_cooldown(82800)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def daily(self, ctx):
        """
        \ud83c\udfb0 Get free random chest every day.
        """
        # Yes, there is no common chest in here.
        chests_and_rarities = {
            1000: 75.0,  # Gold
            1002: 100.0,  # Uncommon
            1003: 65.0,  # Rare
            1004: 20.0,  # Epic
            1005: 2.0  # Legendary
        }

        chest = random.choices(
            population=list(chests_and_rarities.keys()),
            weights=chests_and_rarities.values(),
            k=1
        )[0]

        await ctx.user_data.give_item(ctx, chest, 1)

        chest_data = ctx.items.find_chest_by_id(chest)

        await ctx.reply(
            embed=embeds.congratulations_embed(
                title="Daily bonus chest received!",
                text=(
                    f"You won {chest_data.emoji} "
                    f"**{chest_data.name.capitalize()} chest** as "
                    "your daily bonus! \ud83e\udd20"
                ),
                footer=(
                    f"Use command \"chests open {chest_data.name}\", to open"
                ),
                ctx=ctx
            )
        )

    @commands.command(aliases=["hourlybonus"])
    @checks.user_cooldown(5)
    @checks.has_account()
    @checks.avoid_maintenance()
    async def hourly(self, ctx):
        """
        \ud83d\udcb8 Get more rewards every hour, if you have upvoted this bot

        Upvote this bot once per 12 hours on bot list site "top.gg", and
        unlock getting additional rewards every hour with this command.
        """
        user_cooldown = await checks.get_user_cooldown(ctx, "hourly_bonus")

        if user_cooldown:
            raise commands.CommandOnCooldown(ctx, user_cooldown)

        headers = {
            "Authorization": self.topgg_token
        }
        url = (
            f"https://top.gg/api/bots/{self.bot.user.id}/"
            f"check?userId={ctx.author.id}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as r:
                if r.status != 200:
                    return await ctx.reply(
                        embed=embeds.error_embed(
                            title="Oopsie doopsie!",
                            text=(
                                "We are currently having some problems with "
                                "hourly bonuses. \ud83d\ude28 We got this "
                                "cool squid \ud83d\udc49\ud83e\udd91 fixing "
                                "things already, so could you please check "
                                "hourly bonus again a bit later? \ud83d\ude14"
                            ),
                            ctx=ctx
                        )
                    )

                js = await r.json()

        voted = js['voted']

        if not voted:
            upvote_url = f"<https://top.gg/bot/{ctx.bot.user.id}>"

            await ctx.reply(
                embed=embeds.error_embed(
                    title="Please upvote this bot, to unlock!",
                    text=(
                        "\ud83d\udd10 To unlock hourly bonuses, you have to "
                        f"upvote the bot here: {upvote_url}\n"
                        "\ud83d\udcb8 After upvoting, you will unlock this "
                        "command for 12 hours, and you will be able to collect"
                        " your hourly bonuses, by using this same command. "
                    ),
                    footer=(
                        "The site you are about to visit might contain some"
                        " ads, sorry about that"
                    ),
                    ctx=ctx
                )
            )
        else:
            chests_and_rarities = {
                1000: 2.0,  # Gold
                1001: 100.0,  # Common
                1002: 50.0,  # Uncommon
                1003: 5.0  # Rare
            }

            chest = random.choices(
                population=list(chests_and_rarities.keys()),
                weights=chests_and_rarities.values(),
                k=1
            )[0]

            amount = 1
            # If common chest, give multiple
            if chest == 1001:
                min = int(ctx.user_data.level / 10) or 1
                max = int(ctx.user_data.level / 5) or 1
                amount = random.randint(min, max)

            await ctx.user_data.give_item(ctx, chest, amount)
            await checks.set_user_cooldown(ctx, 3600, "hourly_bonus")

            chest_data = ctx.items.find_chest_by_id(chest)

            await ctx.reply(
                embed=embeds.congratulations_embed(
                    title="Hourly bonus chest received!",
                    text=(
                        f"You won {chest_data.emoji} "
                        f"**{amount}x {chest_data.name.capitalize()} "
                        "chest** as your hourly bonus! \ud83e\udd20"
                    ),
                    footer=(
                        f"Use command \"chests open {chest_data.name}\""
                        ", to open"
                    ),
                    ctx=ctx
                )
            )

    @commands.command(aliases=["i", "info"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def item(self, ctx, *, item: converters.Item):
        """
        \ud83c\udf7f Shows detailed information about a game item

        This command is useful to get various information about some
        item in the game e.g. prices, growing times, rewards etc.

        __Arguments__:
        `item` - item to lookup information for (item's name or ID)

        __Usage examples__:
        {prefix} `item lettuce` - view lettuce stats
        {prefix} `item 1` - view lettuce stats
        """
        embed = discord.Embed(
            title=f"{item.emoji} {item.name.capitalize()}",
            description=f"\ud83d\udd0e **Item ID: {item.id}**",
            color=discord.Color.from_rgb(38, 202, 49)
        )

        embed.add_field(
            name="\ud83d\udd31 Required level",
            value=f"{item.level}"
        )
        embed.add_field(
            name=f"{ctx.bot.xp_emoji} Experience reward",
            value=f"{item.xp} xp / per unit"
        )
        if isinstance(item, game_items.PurchasableItem):
            embed.add_field(
                name="\ud83d\udcb0 Shop price (growing costs)",
                value=f"{item.gold_price} {ctx.bot.gold_emoji}"
            )

        if isinstance(item, game_items.MarketItem):
            embed.add_field(
                name="\ud83d\uded2 Market price range",
                value=(
                    f"{item.min_market_price} - {item.max_market_price}"
                    f" {ctx.bot.gold_emoji} / unit"
                )
            )

        if isinstance(item, game_items.SellableItem):
            embed.add_field(
                name="\ud83d\udcc8 Current market price",
                value=f"{item.gold_reward} {ctx.bot.gold_emoji} / per unit"
            )

        if isinstance(item, game_items.ReplantableItem):
            embed.add_field(
                name="\ud83d\udd01 Production cycles",
                value=f"Grows {item.iterations} times"
            )

        if isinstance(item, game_items.PlantableItem):
            mods = await ctx.user_data.get_item_modification(ctx, item.id)

            grow_time = time.seconds_to_time(item.grow_time)
            harv_time = time.seconds_to_time(item.collect_time)
            volume = item.amount

            if mods:
                time1_mod = mods['time1']
                time2_mod = mods['time2']
                vol_mod = mods['volume']

                if time1_mod:
                    new_time = modifications.get_growing_time(item, time1_mod)
                    fmt = time.seconds_to_time(new_time)
                    grow_time = f"\ud83e\uddec {fmt}"
                if time2_mod:
                    new_time = modifications.get_harvest_time(item, time2_mod)
                    fmt = time.seconds_to_time(new_time)
                    harv_time = f"\ud83e\uddec {fmt}"
                if vol_mod:
                    new_vol = modifications.get_volume(item, vol_mod)
                    volume = f"\ud83e\uddec {new_vol}"

                embed.set_footer(
                    text=(
                        "The \ud83e\uddec emoji is indicating, that the "
                        "property is upgraded for this item"
                    )
                )

            embed.add_field(
                name="\u2696 Harvest volume",
                value=f"{volume} units"
            )
            embed.add_field(
                name="\ud83d\udd70 Growing time",
                value=f"{grow_time}"
            )
            embed.add_field(
                name="\ud83d\udd70 Harvestable for",
                value=f"{harv_time}"
            )
            embed.add_field(
                name=f"{item.emoji} Grow",
                value=f"**{ctx.prefix}grow {item.name}**"
            )

        if isinstance(item, game_items.Product):
            made_from = ""
            for iaa in item.made_from:
                i = iaa.item
                made_from += f"{i.emoji} {i.name.capitalize()} x{iaa.amount}\n"

            embed.add_field(
                name="\ud83d\udcdc Required raw materials",
                value=made_from
            )
            embed.add_field(
                name="\ud83d\udd70 Production duration",
                value=time.seconds_to_time(item.craft_time)
            )
            embed.add_field(
                name=f"{item.emoji} Produce",
                value=f"**{ctx.prefix}make {item.name}**"
            )
            embed.color = discord.Color.from_rgb(113, 204, 39)

        if hasattr(item, "image_url"):
            embed.set_thumbnail(url=item.image_url)

        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Profile(bot))

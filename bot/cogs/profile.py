import discord
from discord.ext import commands
from datetime import datetime, timedelta

from .utils import checks
from .utils import time
from. utils import embeds


class Profile(commands.Cog):
    """
    Common commands relating to your profile.
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

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
        `%profile` - view your profile
        `%profile @user` - view user's profile
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
        lab_info = f"\u2139 **{prefix}lab** {target_user.mention}"

        if lab_cooldown:
            lab_info = (
                "\ud83e\uddf9 Busy for "
                f"{time.seconds_to_time(lab_cooldown)}\n"
            ) + lab_info

        embed = discord.Embed(
            title=f"{target_user}'s profile",
            color=discord.Color.from_rgb(189, 66, 17)
        )
        embed.add_field(
            name=f"\ud83d\udd31 {user.level}. level",
            value=f"{bot.xp_emoji}{user.xp}/{user.next_level_xp}"
        )
        embed.add_field(name=f"{bot.gold_emoji} Gold", value=user.gold)
        embed.add_field(name=f"{bot.gem_emoji} Gems", value=user.gems)
        embed.add_field(
            name="\ud83d\udd12 Warehouse",
            value=(
                f"\ud83c\udff7\ufe0f {inventory_size} inventory items"
                f"\n\u2139 **{prefix}inventory** {target_user.mention}"
            )
        )
        embed.add_field(
            name='\ud83c\udf31 Farm',
            value=(
                f"{bot.tile_emoji} {free_farm_slots}/{farm_slots_formatted} "
                f"free tiles\n\u23f0 Next harvest: {nearest_harvest}"
                f"\n\u2139 **{prefix}farm** {target_user.mention}"
            )
        )
        if user.level > 2:
            embed.add_field(
                name='\ud83c\udfed Factory',
                value=(
                    f"\ud83d\udce6 Max. capacity: {factory_slots_formatted}"
                    "\n\ud83d\udc68\u200d\ud83c\udfed Workers: "
                    f"{user.factory_level}/10"
                    f"\n\u23f0 Next production: {nearest_factory}"
                    f"\n\u2139 **{prefix}factory** {target_user.mention}"
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
                f"\u2139 **{prefix}trades** {target_user.mention}"
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
                f"\n\u2139 **{prefix}boosts** {target_user.mention}"
            )
        )

        await ctx.reply(embed=embed)

    @commands.command(aliases=["boosts"])
    @checks.has_account()
    @checks.avoid_maintenance()
    async def boosters(self, ctx, member: discord.Member = None):
        """
        \u2b06 Lists your or someone else's boosters.

        Boosters speed up your overall game progression in various ways.

        __Optional arguments__:
        `member` - some user in your server. (tagged user or user's ID)

        __Usage examples__:
        `%boosters` - view your active boosters
        `%boosters @user` - view user's active boosters
        """
        if not member:
            user = ctx.user_data
        else:
            user = await checks.get_other_member(ctx, member)

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
                        f"**{ctx.prefix}boost** command"
                    ),
                    ctx=ctx
                )
            )

        target_user = member or ctx.author

        embed = discord.Embed(
            title=f"\u2b06\ufe0f {target_user}'s active boosters",
            color=discord.Color.from_rgb(39, 128, 184),
            description=(
                "\ud83d\udecd\ufe0f Purchase boosters with the "
                f"**{ctx.prefix}boost** command"
            )
        )

        for boost in all_boosts:
            boost_info = self.bot.item_pool.find_boost_by_id(boost.id)

            remaining_duration = boost.duration - datetime.now()
            time_str = time.seconds_to_time(remaining_duration.total_seconds())

            embed.add_field(
                name=f"{boost_info.emoji} {boost_info.name}",
                value=f"{time_str} remaining"
            )

        await ctx.reply(embed=embed)

    @commands.command()
    @checks.has_account()
    async def boost_test(self, ctx):
        # TODO: temp for testing
        from core import game_items

        b = game_items.ObtainedBoost("farm_slots", datetime.now() + timedelta(seconds=60))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("factory_slots", datetime.now() + timedelta(seconds=160))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("cat", datetime.now() + timedelta(seconds=86900))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("cat", datetime.now() + timedelta(seconds=10))
        await ctx.user_data.give_boost(ctx, b)
        b = game_items.ObtainedBoost("dog_1", datetime.now() + timedelta(seconds=101))
        await ctx.user_data.give_boost(ctx, b)


def setup(bot):
    bot.add_cog(Profile(bot))

import discord
from discord.ext import commands
from datetime import datetime, timedelta

from .utils import checks
from .utils import time


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
                f"\ud83c\udff7\ufe0f{inventory_size} inventory items"
                f"\n\u2139 **{prefix}inventory** {target_user.mention}"
            )
        )
        embed.add_field(
            name='\ud83c\udf31 Farm',
            value=(
                f"{bot.tile_emoji}{free_farm_slots}/{farm_slots_formatted} "
                f"free tiles\n\u23f0 Next harvest: {nearest_harvest}"
                f"\n\u2139 **{prefix}farm** {target_user.mention}"
            )
        )
        if user.level > 2:
            embed.add_field(
                name='\ud83c\udfed Factory',
                value=(
                    f"\ud83d\udce6Max. capacity: {factory_slots_formatted}"
                    "\n\ud83d\udc68\u200d\ud83c\udfedWorkers: "
                    f"{user.factory_level}/10"
                    f"\n\u23f0 Next production: {nearest_factory}"
                    f"\n\u2139 **{prefix}factory** {target_user.mention}"
                )
            )
        else:
            embed.add_field(
                name="\ud83c\udfed Factory",
                value="Unlocks at level 3."
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
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)

    @commands.command()
    @checks.has_account()
    async def boost_test(self, ctx):
        # TODO: temp for testing
        from core import game_items

        b = game_items.ObtainedBoost("farm_slots", datetime.now() + timedelta(seconds=60))
        await ctx.user_data.give_boost(ctx, b)


def setup(bot):
    bot.add_cog(Profile(bot))

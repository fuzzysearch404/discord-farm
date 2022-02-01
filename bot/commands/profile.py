import discord
import datetime
from typing import Optional

from .util.commands import FarmSlashCommand, FarmCommandCollection
from .util import time as time_util


class ProfileCollection(FarmCommandCollection):
    """Commands for general use, mostly related to your individual profile."""
    help_emoji: str = "\N{HOUSE WITH GARDEN}"
    help_short_description: str = "Various game profile and item commands"

    def __init__(self, client) -> None:
        super().__init__(
            client,
            [ProfileCommand],
            name="Profile"
        )


class ProfileCommand(
    FarmSlashCommand,
    name="profile",
    description="\N{HOUSE BUILDING} Shows your or someone else's profile"
):
    """
    This is the first command to use, when you want to see your overall game progress.<br>
    It provides a lot of information about your profile, including your current level, resources,
    timers on different features, and more.<br>
    Looking at other people's profiles is also possible, and it is a nice way to see how other
    people are doing.
    """
    player: Optional[discord.Member] = discord.app.Option(
        description="Other user, whose profile to view"
    )

    async def callback(self) -> None:
        if not self.player:
            user = self.user_data
            target_user = self.author
            mention = ""
        else:
            user = await self.lookup_other_player(self.player)
            target_user = self.player
            mention = target_user.mention

        total_farm_slots = user.farm_slots
        has_boosters_unlocked: bool = user.level > 6
        if has_boosters_unlocked:
            all_boosts = await user.get_all_boosts(self)
            all_active_boost_ids = [x.id for x in all_boosts]

            if "farm_slots" in all_active_boost_ids:
                total_farm_slots += 2
                total_farm_slots_formatted = f"**{total_farm_slots}** \N{HAMSTER FACE}"
            else:
                total_farm_slots_formatted = total_farm_slots
            if "factory_slots" in all_active_boost_ids:
                factory_slots_formatted = f"**{user.factory_slots + 2}** \N{OWL}"
            else:
                factory_slots_formatted = user.factory_slots
        else:
            total_farm_slots_formatted = total_farm_slots
            factory_slots_formatted = user.factory_slots

        async with self.acquire() as conn:
            # See schema.sql for this function
            query = "SELECT get_profile_stats($1, $2);"
            profile_stats = await conn.fetchrow(query, user.user_id, self.guild.id)
            # Function returns a nested record
            profile_stats = profile_stats[0]

        inventory_size = profile_stats.get("inventory_size") or 0
        farm_slots_used = profile_stats.get("farm_slots_used") or 0
        store_slots_used = profile_stats.get("store_slots_used") or 0

        free_farm_slots = total_farm_slots - farm_slots_used
        if free_farm_slots < 0:  # Expired +2 farm slots booster visual bug fix
            free_farm_slots = 0

        datetime_now = datetime.datetime.now()

        nearest_harvest = profile_stats.get("nearest_harvest")
        if nearest_harvest:
            if nearest_harvest > datetime_now:
                nearest_harvest = time_util.maybe_timestamp(nearest_harvest, since=datetime_now)
            else:
                nearest_harvest = self.client.check_emoji
        else:
            nearest_harvest = "-"

        nearest_factory = profile_stats.get("nearest_factory_production")
        if nearest_factory:
            if nearest_factory > datetime_now:
                nearest_factory = time_util.maybe_timestamp(nearest_factory, since=datetime_now)
            else:
                nearest_factory = self.client.check_emoji
        else:
            nearest_factory = "-"

        has_lab_unlocked: bool = user.level > 1
        if has_lab_unlocked:
            lab_cd = await self.get_cooldown_ttl("recent_research", other_user_id=user.user_id)
            lab_info = f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/laboratory** {mention}"

            if lab_cd:
                lab_cd_ends = datetime_now + datetime.timedelta(seconds=lab_cd)
                lab_info = (
                    f"\N{BROOM} Available again: {time_util.maybe_timestamp(lab_cd_ends)}\n"
                ) + lab_info

        embed = discord.Embed(
            title=f"\N{HOUSE WITH GARDEN} {target_user.nick or target_user.name}'s profile",
            color=discord.Color.from_rgb(184, 124, 59)
        )
        embed.add_field(
            name=f"\N{TRIDENT EMBLEM} {user.level}. level",
            value=f"{self.client.xp_emoji} {user.xp}/{user.next_level_xp}"
        )
        embed.add_field(name=f"{self.client.gold_emoji} Gold", value=user.gold)
        embed.add_field(name=f"{self.client.gem_emoji} Gems", value=user.gems)
        embed.add_field(
            name=f"{self.client.warehouse_emoji} Warehouse",
            value=(
                f"\N{LABEL} {inventory_size} inventory items\n"
                f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/inventory** {mention}"
            )
        )
        embed.add_field(
            name="\N{SEEDLING} Farm",
            value=(
                f"{self.client.tile_emoji} {free_farm_slots}/{total_farm_slots_formatted} "
                f"free tiles\n\N{ALARM CLOCK} Next harvest: {nearest_harvest}\n"
                f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/farm field** {mention}"
            )
        )

        if user.level > 2:
            embed.add_field(
                name="\N{FACTORY} Factory",
                value=(
                    f"\N{PACKAGE} Max. capacity: {factory_slots_formatted}\n"
                    f"\N{MAN}\N{ZERO WIDTH JOINER}\N{COOKING} Workers: {user.factory_level}/10\n"
                    f"\N{ALARM CLOCK} Next production: {nearest_factory}\n"
                    f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/factory queue** {mention}"
                )
            )
        else:
            embed.add_field(name="\N{FACTORY} Factory", value="\N{LOCK} Unlocks at level 3")

        if user.level > 4:
            embed.add_field(
                name="\N{HANDSHAKE} Server trades",
                value=(
                    f"\N{MONEY BAG} Active trades: {store_slots_used}/{user.store_slots}\n"
                    "\N{RIGHT-POINTING MAGNIFYING GLASS} **/trades list**"
                )
            )
        else:
            embed.add_field(name="\N{HANDSHAKE} Server trades", value="\N{LOCK} Unlocks at level 5")

        if has_lab_unlocked:
            embed.add_field(name="\N{DNA DOUBLE HELIX} Laboratory", value=lab_info)
        else:
            embed.add_field(
                name="\N{DNA DOUBLE HELIX} Laboratory",
                value="\N{LOCK} Unlocks at level 2"
            )

        if has_boosters_unlocked:
            embed.add_field(
                name="\N{UPWARDS BLACK ARROW} Boosters",
                value=(
                    f"\N{CHART WITH UPWARDS TREND} {len(all_boosts)} boosters active\n"
                    f"\N{RIGHT-POINTING MAGNIFYING GLASS} **/boosters** {mention}"
                )
            )
        else:
            embed.add_field(
                name="\N{UPWARDS BLACK ARROW} Boosters",
                value="\N{LOCK} Unlocks at level 7"
            )

        await self.reply(embed=embed)


def setup(client) -> list:
    return [ProfileCollection(client)]

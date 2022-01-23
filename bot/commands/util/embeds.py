from discord import Embed, Color


def _create_embed(
    color: Color,
    emoji: str,
    title: str,
    text: str,
    cmd,
    footer: str = None,
    private: bool = False
) -> Embed:
    embed = Embed(
        title=emoji + " " + title,
        description=text,
        color=color
    )

    if not private:
        if footer:
            embed.set_footer(text=footer, icon_url=cmd.author.display_avatar.url)
    else:
        guild_icon = cmd.guild.icon.url if cmd.guild.icon else None

        if not footer:
            embed.set_footer(
                text=f"Discord Farm notification from \"{cmd.guild}\" server",
                icon_url=guild_icon
            )
        else:
            embed.set_footer(text=footer, icon_url=guild_icon)

    return embed


def error_embed(
    text: str,
    cmd,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(221, 46, 68),
        emoji="\ud83d\udeab",
        text=text,
        cmd=cmd,
        title=title,
        footer=footer,
        private=private
    )


def success_embed(
    text: str,
    cmd,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(0, 128, 1),
        emoji=cmd.client.check_emoji,
        text=text,
        cmd=cmd,
        title=title,
        footer=footer,
        private=private
    )


def congratulations_embed(
    text: str,
    cmd,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(217, 234, 25),
        emoji="\ud83c\udf89",
        text=text,
        cmd=cmd,
        title=title,
        footer=footer,
        private=private
    )


def prompt_embed(
    text: str,
    cmd,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(204, 214, 221),
        emoji="\u2754",
        text=text,
        cmd=cmd,
        title=title,
        footer=footer,
        private=private
    )


def no_money_embed(cmd, cost: int) -> Embed:
    return error_embed(
        title="Insufficient gold coins!",
        text=(
            f"\ud83c\udfe6 **You are missing {cost - cmd.user_data.gold} {cmd.client.gold_emoji} "
            "for this purchase!** I just smashed the piggy and there were no coins left too! "
            "No, not the pig! \ud83d\udc37 The piggy bank!\n "
        ),
        footer=f"You have a total of {cmd.user_data.gold} gold coins",
        cmd=cmd
    )


def no_gems_embed(cmd, cost: int) -> Embed:
    return error_embed(
        title="Insufficient gems!",
        text=(
            f"\ud83c\udfe6 **You are missing {cost - cmd.user_data.gems} {cmd.client.gem_emoji} "
            "for this purchase!** Oh no! We are going need more of those shiny rocks! \ud83d\ude2f"
        ),
        footer=f"You have a total of {cmd.user_data.gems} gems",
        cmd=cmd
    )


def not_enough_items(cmd, item, req_amount: int) -> Embed:
    return error_embed(
        title=f"You don't have enough {item.name}!",
        text=(
            f"{cmd.client.warehouse_emoji} Either you don't own or you don't have enough "
            f"**({req_amount}x) {item.full_name}** in your warehouse!"
        ),
        footer="Check your warehouse with the /inventory command",
        cmd=cmd
    )


def level_up(cmd) -> Embed:
    new_level = cmd.user_data.level

    embed = congratulations_embed(
        title=f"Level up! You have reached: \ud83d\udd31 Level **{new_level}**",
        text=f"\ud83c\udfe6 The bank has rewarded you with a shiny {cmd.client.gem_emoji} gem!",
        footer=f"Congratulations, {cmd.author.nick or cmd.author.name}!",
        cmd=cmd
    )

    features_per_level = {
        3: "\ud83c\udfed Factory",
        17: "\ud83c\udfa3 Fishing"
    }

    try:
        unlocked_feature = features_per_level[new_level]
        embed.description += "\n\ud83c\udd95 **New feature unlocked:** " + unlocked_feature
    except KeyError:
        pass

    unlocked_items = cmd.items.find_items_by_level(new_level)
    if unlocked_items:
        fmt = [x.full_name for x in unlocked_items]
        embed.description += "\n\n\ud83d\udd13 And also you have unlocked the following items: "
        embed.description += ", ".join(fmt)

    return embed

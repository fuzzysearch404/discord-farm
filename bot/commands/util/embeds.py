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
        emoji="\N{NO ENTRY SIGN}",
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
        emoji="\N{PARTY POPPER}",
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
        emoji="\N{WHITE QUESTION MARK ORNAMENT}",
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
            f"\N{BANK} **You are missing {cost - cmd.user_data.gold} {cmd.client.gold_emoji} "
            "for this purchase!** I just smashed the piggy and there were no coins left too! "
            "No, not the pig! \N{PIG FACE} The piggy bank!\n "
        ),
        footer=f"You have a total of {cmd.user_data.gold} gold coins",
        cmd=cmd
    )


def no_gems_embed(cmd, cost: int) -> Embed:
    return error_embed(
        title="Insufficient gems!",
        text=(
            f"\N{BANK} **You are missing {cost - cmd.user_data.gems} {cmd.client.gem_emoji} "
            "for this purchase!** Oh no! We are going need more of those shiny rocks! "
            "\N{HUSHED FACE}"
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
        title=f"Level up! You have reached: \N{TRIDENT EMBLEM} Level **{new_level}**",
        text=f"\N{BANK} The bank has rewarded you with a shiny {cmd.client.gem_emoji} gem!",
        footer=f"Congratulations, {cmd.author.nick or cmd.author.name}!",
        cmd=cmd
    )

    features_per_level = {
        2: "\N{DNA DOUBLE HELIX} Laboratory - You can now upgrade your items!",
        3: "\N{FACTORY} Factory - You can now craft products!",
        5: "\N{HANDSHAKE} Server trades - You can now trade with other players!",
        7: "\N{UPWARDS BLACK ARROW} Boosters - You can now purchase boosters!",
        10: "\N{SHIP} Export missions - You can now start export missions!",
        17: "\N{FISHING POLE AND FISH} Fishing - You can now go fishing!"
    }

    try:
        unlocked_feature = features_per_level[new_level]
        embed.description += "\n\N{SQUARED NEW} **New feature unlocked:** " + unlocked_feature
    except KeyError:
        pass

    unlocked_items = cmd.items.find_items_by_level(new_level)
    if unlocked_items:
        fmt = [x.full_name for x in unlocked_items]
        embed.description += "\n\n\N{OPEN LOCK} And also you have unlocked the following items: "
        embed.description += ", ".join(fmt)

    return embed

from discord import Embed, Color


def _create_embed(
    color: Color,
    emoji: str,
    title: str,
    text: str,
    ctx,
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
            embed.set_footer(text=footer, icon_url=ctx.author.display_avatar.url)
    else:
        guild_icon = ctx.guild.icon.url if ctx.guild.icon else None

        if not footer:
            embed.set_footer(
                text=f"Discord Farm notification from \"{ctx.guild}\" server",
                icon_url=guild_icon
            )
        else:
            embed.set_footer(text=footer, icon_url=guild_icon)

    return embed


def error_embed(
    text: str,
    ctx,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(221, 46, 68),
        emoji="\ud83d\udeab",
        text=text,
        ctx=ctx,
        title=title,
        footer=footer,
        private=private
    )


def success_embed(
    text: str,
    ctx,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(0, 128, 1),
        emoji=ctx.bot.check_emoji,
        text=text,
        ctx=ctx,
        title=title,
        footer=footer,
        private=private
    )


def congratulations_embed(
    text: str,
    ctx,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(217, 234, 25),
        emoji="\ud83c\udf89",
        text=text,
        ctx=ctx,
        title=title,
        footer=footer,
        private=private
    )


def prompt_embed(
    text: str,
    ctx,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    return _create_embed(
        color=Color.from_rgb(204, 214, 221),
        emoji="\u2754",
        text=text,
        ctx=ctx,
        title=title,
        footer=footer,
        private=private
    )


def no_money_embed(ctx, user_data, cost: int) -> Embed:
    return error_embed(
        title="Insufficient gold coins!",
        text=(
            f"**You are missing {cost - user_data.gold} {ctx.bot.gold_emoji} for this purchase!** "
            "I just smashed the piggy and there were no coins left too! "
            "No, not the pig! \ud83d\udc37 The piggy bank!\n "
        ),
        footer=f"You have a total of {user_data.gold} gold coins",
        ctx=ctx
    )


def no_gems_embed(ctx, user_data, cost: int) -> Embed:
    return error_embed(
        title="Insufficient gems!",
        text=(
            f"**You are missing {cost - user_data.gems} {ctx.bot.gem_emoji} for this purchase!** "
            "Oh no! We need more of those shiny rocks! \ud83d\ude2f"
        ),
        footer=f"You have a total of {user_data.gems} gems",
        ctx=ctx
    )


def not_enough_items(ctx, item, req_amount: int):
    return error_embed(
        title=f"You don't have enough {item.name}!",
        text=(
            "Either you don't own or you don't have enough "
            f"**({req_amount}x) {item.full_name}** in your warehouse!"
        ),
        footer="Check your warehouse with the /inventory command",
        ctx=ctx
    )

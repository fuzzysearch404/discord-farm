from discord import Embed, Color


def _create_embed(
    color: Color,
    emoji: str,
    text: str,
    ctx,
    title: str = None,
    footer: str = None,
    private: bool = False
) -> Embed:
    embed = Embed(color=color)

    if title:
        title = emoji + " " + title
    else:
        text = emoji + " " + text

    if len(text) > 256 or title:
        embed.title = title
        embed.description = text
    else:
        embed.title = text

    if not private:
        if not footer:
            embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        else:
            embed.set_footer(text=footer, icon_url=ctx.author.avatar_url)
    else:
        if not footer:
            embed.set_footer(
                text=f"Farming notification from \"{ctx.guild}\" server",
                icon_url=ctx.guild.icon_url
            )
        else:
            embed.set_footer(text=footer, icon_url=ctx.guild.icon_url)

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
        color=Color.from_rgb(119, 178, 85),
        emoji="\u2705",
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
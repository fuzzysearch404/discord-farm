import discord
from discord.ext import menus

from core.game_items import BoostDuration


class MenuPages(menus.Menu):
    """
    I have modified the default MenuPages a bit for my own usage
    The stop button seems quite useless, since nobody is ever
    using it, the first and last page buttons show up
    when there are only 3 pages (I want more).


    Attributes
    ------------
    current_page: :class:`int`
        The current page that we are in. Zero-indexed
        between [0, :attr:`PageSource.max_pages`).
    """
    def __init__(self, source, **kwargs):
        self._source = source
        self.current_page = 0
        super().__init__(**kwargs)

    @property
    def source(self):
        """:class:`PageSource`: The source where the data comes from."""
        return self._source

    async def change_source(self, source):
        """|coro|

        Changes the :class:`PageSource` to a different one at runtime.

        Once the change has been set, the menu is moved to the first
        page of the new source if it was started. This effectively
        changes the :attr:`current_page` to 0.

        Raises
        --------
        TypeError
            A :class:`PageSource` was not passed.
        """

        if not isinstance(source, menus.PageSource):
            raise TypeError(
                'Expected {0!r} not {1.__class__!r}.'.format(
                    menus.PageSource, source
                )
            )

        self._source = source
        self.current_page = 0
        if self.message is not None:
            await source._prepare_once()
            await self.show_page(0)

    def should_add_reactions(self):
        return self._source.is_paginating()

    async def _get_kwargs_from_page(self, page):
        value = await discord.utils.maybe_coroutine(
            self._source.format_page, self, page
        )
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}

    async def show_page(self, page_number):
        page = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self.message.edit(**kwargs)

    async def send_initial_message(self, ctx, channel):
        """|coro|

        The default implementation of :meth:`Menu.send_initial_message`
        for the interactive pagination session.

        This implementation shows the first page of the source.
        """
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        return await ctx.reply(**kwargs)

    async def start(self, ctx, *, channel=None, wait=False):
        await self._source._prepare_once()
        await super().start(ctx, channel=channel, wait=wait)

    async def show_checked_page(self, page_number):
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_current_page(self):
        if self._source.is_paginating():
            await self.show_page(self.current_page)

    def _skip_double_triangle_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages <= 4

    @menus.button(
        '\u23ee\ufe0f',
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button(
        '\u25c0\ufe0f',
        position=menus.First(1)
    )
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @menus.button(
        '\u25b6\ufe0f',
        position=menus.Last(0)
    )
    async def go_to_next_page(self, payload):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @menus.button(
        '\u23ed\ufe0f',
        position=menus.Last(1),
        skip_if=_skip_double_triangle_buttons
    )
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)


class ConfirmPrompt(menus.Menu):
    def __init__(self, msg: str = None, embed=None):
        super().__init__(timeout=30.0, clear_reactions_after=True)
        self.msg = msg
        self.embed = embed
        self._result = False

    async def send_initial_message(self, ctx, channel):
        return await ctx.reply(self.msg, embed=self.embed)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)

        return self._result, self.message


class ConfirmPromptCheck(ConfirmPrompt):

    @menus.button("\u2705")
    async def do_confirm(self, payload):
        self._result = True
        self.stop()


class ConfirmPromptCoin(ConfirmPrompt):

    @menus.button("<:gold:840961597148102717>")
    async def do_confirm(self, payload):
        self._result = True
        self.stop()


class ConfirmPromptGem(ConfirmPrompt):

    @menus.button("<a:gem:722191212706136095>")
    async def do_confirm(self, payload):
        self._result = True
        self.stop()


class BoostPurchasePrompt(menus.Menu):
    def __init__(self, msg: str = None, embed=None):
        super().__init__(timeout=30.0)
        self.msg = msg
        self.embed = embed
        self._result = None

    async def send_initial_message(self, ctx, channel):
        return await ctx.reply(self.msg, embed=self.embed)

    @menus.button("1\ufe0f\u20e3")
    async def do_single_day(self, payload):
        self._result = BoostDuration.ONE_DAY
        self.stop()

    @menus.button("3\ufe0f\u20e3")
    async def do_three_days(self, payload):
        self._result = BoostDuration.THREE_DAYS
        self.stop()

    @menus.button("7\ufe0f\u20e3")
    async def do_seven_days(self, payload):
        self._result = BoostDuration.SEVEN_DAYS
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)

        return self._result, self.message

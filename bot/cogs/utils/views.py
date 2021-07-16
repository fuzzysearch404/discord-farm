"""
Paginator with paginator sources concept inspired by:
https://github.com/Rapptz/discord-ext-menus
"""
import discord


class PaginatorSource:
    def __init__(self, entries: list, per_page: int = 10) -> None:
        self.entries = entries
        self.per_page = per_page

        pages, left_over = divmod(len(entries), per_page)
        if left_over:
            pages += 1

        self.max_pages = pages

    def should_paginate(self) -> bool:
        return len(self.entries) > self.per_page

    def get_page_contents(self, page_number: int) -> list:
        if self.per_page == 1:
            return [self.entries[page_number]]
        else:
            base = page_number * self.per_page

            return self.entries[base:base + self.per_page]

    async def format_page(
        self,
        page: list,
        view: discord.ui.View
    ) -> discord.Embed:
        raise NotImplementedError("Page format not implemented")


class ButtonPaginatorView(discord.ui.View):
    def __init__(self, source: PaginatorSource) -> None:
        super().__init__(timeout=180.0)
        self.source = source
        self.current_page = 0

        self.msg = None
        self.author = None

        self.update_page_counter_label()

    async def on_timeout(self) -> None:
        for ui_item in self.children:
            if isinstance(ui_item, discord.ui.Button):
                ui_item.disabled = True

        await self.msg.edit(view=self)

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if self.author == interaction.user:
            return True

        await interaction.response.send_message(
            f"This menu can only be used by {self.author.mention}, "
            "because they used this command.",
            ephemeral=True
        )

        return False

    def update_page_counter_label(self) -> None:
        self.counter.label = (
            f"Page {self.current_page + 1}/{self.source.max_pages}"
        )

    async def current_page_embed(self) -> discord.Embed:
        page_contents = self.source.get_page_contents(self.current_page)

        return await discord.utils.maybe_coroutine(
            self.source.format_page, page_contents, self
        )

    def update_button_states(self) -> None:
        if self.current_page == 0:
            self.first_page.disabled = True
            self.previous_page.disabled = True
        else:
            self.first_page.disabled = False
            self.previous_page.disabled = False

        if self.current_page >= self.source.max_pages - 1:
            self.last_page.disabled = True
            self.next_page.disabled = True
        else:
            self.last_page.disabled = False
            self.next_page.disabled = False

    async def update_page_view(self) -> None:
        # Update counter here too
        self.update_page_counter_label()

        embed = await self.current_page_embed()
        await self.msg.edit(embed=embed, view=self)

    @discord.ui.button(
        emoji="\u23ee\ufe0f",
        style=discord.ButtonStyle.blurple,
        disabled=True
    )
    async def first_page(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ) -> None:
        self.current_page = 0
        self.update_button_states()
        await self.update_page_view()

    @discord.ui.button(
        emoji="\u25c0\ufe0f",
        style=discord.ButtonStyle.blurple,
        disabled=True
    )
    async def previous_page(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ) -> None:
        self.current_page -= 1
        self.update_button_states()
        await self.update_page_view()

    @discord.ui.button(style=discord.ButtonStyle.grey, disabled=True)
    async def counter(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ) -> None:
        # This is a dummy button just to show the current page number
        pass

    @discord.ui.button(
        emoji="\u25b6\ufe0f",
        style=discord.ButtonStyle.blurple
    )
    async def next_page(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ) -> None:
        self.current_page += 1
        self.update_button_states()
        await self.update_page_view()

    @discord.ui.button(
        emoji="\u23ed\ufe0f",
        style=discord.ButtonStyle.blurple
    )
    async def last_page(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ) -> None:
        self.current_page = self.source.max_pages - 1
        self.update_button_states()
        await self.update_page_view()

    async def start(self, ctx) -> discord.Message:
        self.author = ctx.author
        embed = await self.current_page_embed()
        # No need for a paginator? - Not adding it.
        if not self.source.should_paginate():
            return await ctx.reply(embed=embed)

        self.msg = await ctx.reply(embed=embed, view=self)

        return self.msg

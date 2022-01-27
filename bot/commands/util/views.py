"""
Paginator with paginator sources concept inspired by: https://github.com/Rapptz/discord-ext-menus
"""
import discord


class AbstractPaginatorSource:

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

    async def format_page(self, page: list, view: discord.ui.View) -> discord.Embed:
        raise NotImplementedError("Page format not implemented")


class ButtonPaginatorView(discord.ui.View):

    def __init__(self, source: AbstractPaginatorSource) -> None:
        super().__init__(timeout=180.0)
        self.source = source
        self.current_page = 0

        self.command = None
        self.author = None

        self.update_page_counter_label()
        self.update_button_states()

    async def on_timeout(self) -> None:
        for ui_item in self.children:
            if hasattr(ui_item, "disabled"):
                ui_item.disabled = True

        await self.command.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author == interaction.user:
            return True

        await interaction.response.send_message(
            f"\N{CROSS MARK} This menu can only be used by {self.author.mention}, "
            "because they used this command.",
            ephemeral=True
        )
        return False

    def update_page_counter_label(self) -> None:
        self.counter.label = f"Page {self.current_page + 1}/{self.source.max_pages}"

    async def current_page_embed(self) -> discord.Embed:
        page_contents = self.source.get_page_contents(self.current_page)
        return await discord.utils.maybe_coroutine(self.source.format_page, page_contents, self)

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
        await self.command.edit(embed=embed, view=self)

    @discord.ui.button(
        emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
        style=discord.ButtonStyle.blurple,
        disabled=True
    )
    async def first_page(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self.current_page = 0
        self.update_button_states()
        await self.update_page_view()

    @discord.ui.button(
        emoji="\N{BLACK LEFT-POINTING TRIANGLE}",
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
    async def counter(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        # This is a dummy button just to show the current page number
        pass

    @discord.ui.button(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}", style=discord.ButtonStyle.blurple)
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self.current_page += 1
        self.update_button_states()
        await self.update_page_view()

    @discord.ui.button(
        emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
        style=discord.ButtonStyle.blurple
    )
    async def last_page(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self.current_page = self.source.max_pages - 1
        self.update_button_states()
        await self.update_page_view()

    async def start(self, command) -> discord.Message:
        self.command = command
        self.author = command.interaction.user

        embed = await self.current_page_embed()
        # No need for a paginator? - Not adding it.
        if not self.source.should_paginate():
            return await command.reply(embed=embed)

        return await command.reply(embed=embed, view=self)


class SelectButtonPaginatorView(ButtonPaginatorView):
    """
    A paginator type that can display multiple paginator sources,
    by selecting them with a select component.
    """
    def __init__(self, options_and_sources: dict, select_placeholder: str = None) -> None:
        """
        options_and_sources: A dictionary of select options and their corresponding
        paginator sources.
        """
        self.keys_and_sources = {}

        for option, source in options_and_sources.items():
            self.keys_and_sources[option.value] = source

        first_option = next(iter(options_and_sources))
        first_source = options_and_sources[first_option]
        super().__init__(first_source)

        self.select_source.options = list(options_and_sources.keys())
        self.select_source.placeholder = select_placeholder

    @discord.ui.select(min_values=1, max_values=1, row=4)
    async def select_source(
        self,
        select: discord.ui.Select,
        interaction: discord.Interaction
    ) -> None:
        self.source = self.keys_and_sources[select.values[0]]
        self.current_page = 0

        self.update_button_states()
        await self.update_page_view()

    async def start(self, command) -> discord.Message:
        self.command = command
        self.author = command.interaction.user

        embed = await self.current_page_embed()
        return await command.reply(embed=embed, view=self)


class AbstractOptionPromptView(discord.ui.View):
    """
    Base class for option prompt views that can take multiple options.
    This class should be inherited futher to implement the actual options.
    """
    def __init__(
        self,
        initial_msg: str = None,
        initial_embed: discord.Embed = None,
        deny_button: bool = True,
        deny_label: str = "Cancel",
        timeout: int = 60
    ) -> None:
        super().__init__(timeout=timeout)
        # Message or/and embed to send as an initial message
        self.initial_msg = initial_msg
        self.initial_embed = initial_embed
        # Context from the original command invoke
        self.ctx = None
        # Message with the view itself
        self._msg = None

        self._result = None

        self.create_option_buttons()

        # We do this here to make the deny button appear last
        if deny_button:
            self.deny_label = deny_label
            self.create_deny_button()

    async def on_timeout(self) -> None:
        await self.disable_all_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.ctx.author == interaction.user:
            return True

        await interaction.response.send_message(
            f"\N{CROSS MARK} This menu can only be used by {self.ctx.author.mention}, "
            "because they used this command.",
            ephemeral=True
        )
        return False

    def create_option_buttons(self) -> None:
        raise NotImplementedError("Option buttons not implemented")

    def create_deny_button(self) -> None:
        deny_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            emoji="\N{HEAVY MULTIPLICATION X}",
            label=self.deny_label
        )

        # This time we do an extra step and disable the buttons
        # Because in most of the code the command execution
        # just stops in this case anyways
        async def deny_callback(interaction) -> None:
            self._result = False
            await self.disable_all_items()
            self.stop()

        deny_button.callback = deny_callback
        self.add_item(deny_button)

    async def disable_all_items(self) -> None:
        for ui_item in self.children:
            if hasattr(ui_item, "disabled"):
                ui_item.disabled = True

        await self._msg.edit(view=self)

    async def send_initial_message(self) -> None:
        self._msg = await self.ctx.reply(self.initial_msg, embed=self.initial_embed, view=self)

    async def prompt(self, ctx) -> tuple:
        self.ctx = ctx
        await self.send_initial_message()
        # Wait until the view times out or user clicks a button
        await self.wait()

        return self._result, self._msg


class ConfirmPromptView(AbstractOptionPromptView):
    """
    Option prompt view that only has one "positive" option.
    Can be used to prompt for boolean type of responses.
    """
    def __init__(
        self,
        style: discord.ButtonStyle = discord.ButtonStyle.green,
        emoji: str = "\N{WHITE HEAVY CHECK MARK}",
        label: str = None,
        *args,
        **kwargs
    ) -> None:
        self.style = style
        self.emoji = emoji
        self.label = label
        super().__init__(*args, **kwargs)

    def create_option_buttons(self) -> None:
        approve_button = discord.ui.Button(
            style=self.style,
            emoji=self.emoji,
            label=self.label
        )

        async def approve_callback(interaction) -> None:
            self._result = True
            # Here we don't disable or send request to remove the buttons,
            # because most likely we will edit the "self._msg" message
            # by just passing view as None or this empty view
            # to not do an extra request to API just to remove these
            self.clear_items()
            self.stop()

        approve_button.callback = approve_callback
        self.add_item(approve_button)


class OptionButton(discord.ui.Button):
    """
    A button instance that also holds an option.
    These type of buttons are used for MultiOptionView.
    On callback sets the option as a result onto the view.
    """
    def __init__(self, option, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.option = option

    async def callback(self, interaction: discord.Interaction):
        view: MultiOptionView = self.view
        view._result = self.option
        view.clear_items()
        view.stop()


class MultiOptionView(AbstractOptionPromptView):
    """
    Option prompt view that takes list of OptionButton for the prompt.
    """
    def __init__(self, options: list, *args, **kwargs) -> None:
        self.options = options
        super().__init__(*args, **kwargs)

    def create_option_buttons(self) -> None:
        for option in self.options:
            self.add_item(option)

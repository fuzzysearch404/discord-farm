import itertools
import discord
import asyncio
import utils.embeds as emb
from discord.ext import commands
from random import randint
from utils.paginator import Pages
from utils import checks
from classes import user as userutils

DEFAULT_XP = 0
DEFAULT_MONEY = 150
DEFAULT_GEMS = 0
DEFAULT_TILES = 2
DEFAULT_FACTORY_SLOTS = 1
DEFAULT_STORE_SLOTS = 1

class HelpPaginator(Pages):
    def __init__(self, help_command, ctx, entries, *, per_page=4):
        super().__init__(ctx, entries=entries, per_page=per_page)
        self.reaction_emojis.append(('\N{WHITE QUESTION MARK ORNAMENT}', self.show_bot_help))
        self.total = len(entries)
        self.help_command = help_command
        self.prefix = help_command.clean_prefix
        self.is_bot = False

    def get_bot_page(self, page):
        cog, description, commands = self.entries[page - 1]
        self.title = f'{cog} Commands'
        self.description = description
        return commands

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()
        self.embed.description = self.description
        self.embed.title = self.title

        if self.is_bot:
            value ='For more help, join the official bot support server: https://discord.gg/MwpxKjF'
            self.embed.add_field(name='Support', value=value, inline=False)

        self.embed.set_footer(text=f'Use "{self.prefix}help command" for more info on a command.')

        for entry in entries:
            signature = f'{entry.qualified_name} {entry.signature}'
            self.embed.add_field(name=signature, value=entry.short_doc or "No help given", inline=False)

        if self.maximum_pages:
            self.embed.set_author(name=f'Page {page}/{self.maximum_pages} ({self.total} commands)')

    async def show_help(self):
        """shows this message"""

        self.embed.title = 'Paginator help'
        self.embed.description = 'Hello! Welcome to the help page.'

        messages = [f'{emoji} {func.__doc__}' for emoji, func in self.reaction_emojis]
        self.embed.clear_fields()
        self.embed.add_field(name='What are these reactions for?', value='\n'.join(messages), inline=False)

        self.embed.set_footer(text=f'We were on page {self.current_page} before this message.')
        await self.message.edit(embed=self.embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

    async def show_bot_help(self):
        """shows how to use the bot"""

        self.embed.title = 'Using the bot'
        self.embed.description = 'Hello! Welcome to the help page.'
        self.embed.clear_fields()

        entries = (
            ('<argument>', 'This means the argument is __**required**__.'),
            ('[argument]', 'This means the argument is __**optional**__.'),
            ('[A|B]', 'This means that it can be __**either A or B**__.'),
            ('[argument...]', 'This means you can have multiple arguments.\n' \
                              'Now that you know the basics, it should be noted that...\n' \
                              '__**You do not type in the brackets!**__')
        )

        self.embed.add_field(name='How do I use this bot?', value='Reading the bot signature is pretty simple.')

        for name, value in entries:
            self.embed.add_field(name=name, value=value, inline=False)

        self.embed.set_footer(text=f'We were on page {self.current_page} before this message.')
        await self.message.edit(embed=self.embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(verify_checks=False,
            command_attrs={
            'help': 'Shows help about the bot, a command, or a category',
            'aliases': ['commands', 'cmd', 'cmds', 'helpme'],
            'checks': [checks.reaction_perms(), checks.embed_perms()]
        })

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(str(error.original))

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent:
                fmt = f'{parent} {fmt}'
            alias = fmt
        else:
            alias = command.name if not parent else f'{parent} {command.name}'
        return f'{alias} {command.signature}'

    async def send_bot_help(self, mapping):
        def key(c):
            return c.cog_name or '\u200bNo Category'

        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True, key=key)
        nested_pages = []
        per_page = 9
        total = 0

        for cog, commands in itertools.groupby(entries, key=key):
            commands = sorted(commands, key=lambda c: c.name)
            if len(commands) == 0:
                continue

            total += len(commands)
            actual_cog = bot.get_cog(cog)
            # get the description if it exists (and the cog is valid) or return Empty embed.
            description = (actual_cog and actual_cog.description) or discord.Embed.Empty
            nested_pages.extend((cog, description, commands[i:i + per_page]) for i in range(0, len(commands), per_page))

        # a value of 1 forces the pagination session
        pages = HelpPaginator(self, self.context, nested_pages, per_page=1)

        # swap the get_page implementation to work with our nested pages.
        pages.get_page = pages.get_bot_page
        pages.is_bot = True
        pages.total = total
        await pages.paginate()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        pages = HelpPaginator(self, self.context, entries)
        pages.title = f'{cog.qualified_name} Commands'
        pages.description = cog.description

        await pages.paginate()

    def common_command_formatting(self, page_or_embed, command):
        page_or_embed.title = self.get_command_signature(command)
        if command.description:
            page_or_embed.description = f'{command.description}\n\n{command.help}'
        else:
            page_or_embed.description = command.help or 'No help found...'

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.blurple())
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        pages = HelpPaginator(self, self.context, entries)
        self.common_command_formatting(pages, group)

        await pages.paginate()

class Registration(commands.Cog, name="Game Account"):
    """
    Commands for game account management.
    """
    def __init__(self, client):
        self.client = client
        client.help_command = PaginatedHelpCommand()

    @commands.command(aliases=['start'])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def register(self, ctx):
        """
        \ud83c\udd95 Creates a new game account (new farm).
        
        You can only use this command if you don't already
        have an account.
        """
        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """INSERT INTO profile(userid, xp,
                money, gems, tiles, factoryslots, storeslots, faction)
                VALUES($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING;"""
                result = await self.client.db.execute(
                    query, ctx.author.id, DEFAULT_XP, DEFAULT_MONEY,
                    DEFAULT_GEMS, DEFAULT_TILES, DEFAULT_FACTORY_SLOTS,
                    DEFAULT_STORE_SLOTS, randint(1, 3)
                )

        if result[-1:] != '0':
            embed = emb.congratzembed(
                "Your account is successfully created!\n"
                "\u2139Now check out the commands with `%help`.\n"
                "\ud83d\udcdaTo get detailed information on specific command's "
                "usage, use `%help command_name`",
                ctx
            )
            await ctx.send(embed=embed)
        else:
            embed = emb.errorembed('You already own a farm!', ctx)
            await ctx.send(embed=embed)
    
    @commands.command(aliases=["deleteaccount"])
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def resetaccount(self, ctx):
        """
        \u274c Deletes your farm and all your game data.
        
        There is no way to get your farm back after using this command,
        so be careful with your decision.
        However, you can start a new game after using this command
        with command `%register`.
        """
        embed = emb.errorembed(
            "Do you really want to delete your account? This **cannot** be undone!!!",
            ctx
        )
        message = await ctx.send(embed=embed)
        await message.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705'

        try:
            reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await message.clear_reactions()
            else: return

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """DELETE FROM profile WHERE userid = $1;"""
                await self.client.db.execute(query, ctx.author.id)

        embed = emb.confirmembed("Thank You for playing! \ud83d\ude0a Your account is now deleted. "
        "If you want, you can start all over again with the `%register` command. \ud83d\ude0c", ctx)
        await ctx.send(embed=embed)

    @commands.command(aliases=["dms"])
    @checks.avoid_maintenance()
    async def notifications(self, ctx):
        """
        \ud83d\udce7 Disables or enables Direct Message notifications.

        Allows to disable various notifications e.g., notifications when
        someone accepts trade with you, or to enable them again.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        

        if useracc.notifications:
            await useracc.toggle_notifications(False)
            await ctx.send("\u2705 Direct Message notifications disabled!")
        else:
            await useracc.toggle_notifications(True)
            await ctx.send("\u2705 Direct Message notifications enabled!")


def setup(client):
    client.add_cog(Registration(client))

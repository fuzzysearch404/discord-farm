import discord
import logging
import json
import asyncpg
import utils.item as items
from discord.ext import commands
from utils import checks

extensions = (
    'cogs.admin',
    'cogs.test',
    'cogs.main',
    'cogs.shop'
)
unloaded = []
with open("settings.json", "r", encoding="UTF8") as file:
    settings = json.load(file)

log = logging.getLogger('discord')
log.setLevel(logging.INFO)
handler = logging.FileHandler(filename='farm.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
log.addHandler(handler)


class MyClient(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix='%', *args, **kwargs)
        self.add_command(self.load)
        self.add_command(self.unload)
        self.add_command(self.modules)
        self.add_command(self.unloaded)
        self.add_command(self.reload)
        self.add_command(self.reloadsettings)
        self.add_command(self.reconnectdatabase)
        self.initemojis()
        self.allitems = {}
        self.loadvariables()
        self.loop.create_task(self.connectdb())

    async def connectdb(self):
        credentials = {"user": settings['dbuser'], "password": settings['dbpassword'], "database": settings['dbname'], "host": "127.0.0.1"}
        self.db = await asyncpg.create_pool(**credentials)

    def loadvariables(self):
        self.loadcropseeds()

    def loadcropseeds(self):
        self.cropseeds = items.cropseedloader()
        self.crops = items.croploader()
        self.allitems.update(self.cropseeds)
        self.allitems.update(self.crops)

    def initemojis(self):
        self.gold = '<:gold:603145892811505665>'
        self.xp = '<:xp:603145893029347329>'
        self.gem = '<:diamond:603145893025415178>'
        self.tile = '<:tile:603160625417420801>'

    # Commands

    @commands.command(name='fixdb')
    @checks.is_owner()
    async def reconnectdatabase(ctx):
        client.connectdb()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send("\N{WHITE HEAVY CHECK MARK}", delete_after=5)

    @commands.command(name='reloadsettings')
    @checks.is_owner()
    async def reloadsettings(ctx):
        client.loadvariables()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send("\N{WHITE HEAVY CHECK MARK}", delete_after=5)

    @commands.command(name='unloaded')
    @checks.is_owner()
    async def unloaded(ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(unloaded, delete_after=15)

    @commands.command(name='modules')
    @checks.is_owner()
    async def modules(ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(extensions, delete_after=15)

    @commands.command(name='load')
    @checks.is_owner()
    async def load(ctx, extension: str):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        try:
            client.load_extension('cogs.' + extension.lower())
            unloaded.remove(extension)
            print(f'Loaded {extension}')
            await ctx.send(f'{extension} ielādēts', delete_after=5)
        except Exception as error:
            print(f'{extension} cannot be loaded. [{error}]')
            await ctx.send(f'{extension} netika ielādēts [{error}]', delete_after=30)

    @commands.command(name='unload')
    @checks.is_owner()
    async def unload(ctx, extension: str):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        try:
            client.unload_extension('cogs.' + extension.lower())
            unloaded.append(extension)
            print(f'Unloaded {extension}')
            await ctx.send(f'{extension} noņemts', delete_after=5)
        except Exception as error:
            print(f'{extension} cannot be unloaded. [{error}]')
            await ctx.send(f'{extension} netika noņemts [{error}]', delete_after=30)

    @commands.command(name='reload')
    @checks.is_owner()
    async def reload(ctx, extension: str):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        try:
            client.reload_extension('cogs.' + extension.lower())
            print(f'Reloaded {extension}')
            await ctx.send(f'{extension} atjaunots', delete_after=5)
        except Exception as error:
            print(f'{extension} cannot be reloaded. [{error}]')
            await ctx.send(f'{extension} netika atjaunots [{error}]', delete_after=15)

    # Events

    async def on_ready(self):
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not message.guild:
            return

        try:
            await self.process_commands(message)
        except Exception:
            print('Command Error Caught At Top Level')
            print(message.content)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CheckFailure):
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            await ctx.send('Tev nav tiesību izmantot šo komandu', delete_after=10)
            return
        if isinstance(error, commands.errors.CommandNotFound):
            return
        raise error

    async def on_error(self, event, args, kwargs):
        print(event, args, kwargs)
        log.error(f'{event} {args} {kwargs}')

    async def on_command(self, ctx):
        log.info(
            f'{ctx.author.id} executed {ctx.prefix}{ctx.invoked_with} Failed:{ctx.command_failed} '
            f'Guild: {ctx.guild.id} Channel: {ctx.channel.id}'
        )


client = MyClient()
if __name__ == '__main__':
    for extension in extensions:
        try:
            client.load_extension(extension)
            print(f'{extension} auto-loaded')
        except Exception as error:
            print(f'{extension} cannot be loaded. [{error}]')
            unloaded.append(extension)
    print('------')
client.remove_command('help')
client.run(settings['token'])

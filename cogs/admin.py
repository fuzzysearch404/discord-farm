"""Most of the code from https://github.com/Rapptz/RoboDanny/"""

from discord.ext import commands
import importlib
import asyncio
import traceback
import discord
import inspect
import textwrap
import io
import json
import copy
import subprocess
import datetime
from contextlib import redirect_stdout
from typing import Union, Optional

from utils.paginator import TextPages
from utils import checks

# to expose to the eval command
from collections import Counter


class Admin(commands.Cog, command_attrs={'hidden': True}):
    """Admin-only commands that make the bot dynamic."""

    def __init__(self, client):
        self.client = client
        self._last_result = None
        self.sessions = set()

    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.client.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    async def send_eval(self, command, content, ctx):
        self.client.eval_wait = True
        try:
            await self.client.websocket.send(json.dumps({'command': command, 'content': content}).encode('utf-8'))
            msgs = []
            while True:
                try:
                    msg = await asyncio.wait_for(self.client.responses.get(), timeout=3)
                except asyncio.TimeoutError:
                    break
                msgs.append(f'[Cluster-{msg["author"]}]: {msg["response"]}')
            await ctx.send(' '.join(f'```py\n{m}\n```' for m in msgs))
        finally:
            self.client.eval_wait = False

    @commands.command(hidden=True)
    @commands.is_owner()
    async def evall(self, ctx, *, body: str):
        """Evaluates a code on all clusters"""
        await self.send_eval("eval", body, ctx)

    @commands.command(pass_context=True, hidden=True, name='eval')
    @checks.is_owner()
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            'client': self.client,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def repl(self, ctx):
        """Launches an interactive REPL session."""
        variables = {
            'ctx': ctx,
            'client': self.client,
            'message': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send('Already running a REPL session in this channel. Exit it with `quit`.')
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send('Enter code to execute or evaluate. `exit()` or `quit` to exit.')

        def check(m):
            return m.author.id == ctx.author.id and \
                   m.channel.id == ctx.channel.id and \
                   m.content.startswith('`')

        while True:
            try:
                response = await self.client.wait_for('message', check=check, timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send('Exiting REPL session.')
                self.sessions.remove(ctx.channel.id)
                break

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception as e:
                value = stdout.getvalue()
                fmt = f'```py\n{value}{traceback.format_exc()}\n```'
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f'```py\n{value}{result}\n```'
                    variables['_'] = result
                elif value:
                    fmt = f'```py\n{value}\n```'

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await ctx.send('Content too big to be printed.')
                    else:
                        await ctx.send(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send(f'Unexpected error: `{e}`')

    @commands.command(hidden=True)
    @checks.is_owner()
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""
        # the imports are here because I imagine some people would want to use
        # this cog as a base for their other cog, and since this one is kinda
        # odd and unnecessary for most people, I will make it easy to remove
        # for those people.
        from utils.formats import TabularData, plural
        import time

        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = self.client.db.execute
        else:
            strategy = self.client.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def sudo(self, ctx, who: Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user."""
        msg = copy.copy(ctx.message)
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.client.get_context(msg, cls=type(ctx))
        #new_ctx._db = ctx._db
        await self.client.invoke(new_ctx)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def do(self, ctx, times: int, *, command):
        """Repeats a command a specified number of times."""
        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + command

        new_ctx = await self.client.get_context(msg, cls=type(ctx))
        #new_ctx._db = ctx._db

        for i in range(times):
            await new_ctx.reinvoke()

    @commands.command(hidden=True)
    @checks.is_owner()
    async def sh(self, ctx, *, command):
        """Runs a shell command."""

        async with ctx.typing():
            stdout, stderr = await self.run_process(command)

        if stderr:
            text = f'stdout:\n{stdout}\nstderr:\n{stderr}'
        else:
            text = stdout

        try:
            pages = TextPages(ctx, text)
            await pages.paginate()
        except Exception as e:
            await ctx.send(str(e))

    @commands.command(name='logout', hidden=True)
    @checks.is_owner()
    async def botlogout(self, ctx):
        await self.send_eval("logout", "", ctx)
        for task in asyncio.Task.all_tasks():
            task.cancel()
        asyncio.get_event_loop().stop()
        await self.client.close()

    @commands.command()
    @checks.is_owner()
    async def uptime(self, ctx):
        """
        \ud83d\udd70\ufe0f Bot's uptime.
        """
        await ctx.send(self.client.uptime)

    @commands.command()
    @checks.is_owner()
    async def reimport(self, ctx, ext: str):
        """
        \ud83d\udce5 Reimports some module on this cluster.
        """
        try:
            importlib.reload(importlib.import_module(ext))
            await ctx.send("\u2705")
        except Exception as e:
            await ctx.send(e)

    @commands.command()
    @checks.is_owner()
    async def reloaditems(self, ctx):
        """
        \ud83d\udcd2 Reloads game item data on all clusters.
        """
        await self.send_eval("reloaditems", "", ctx)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def load(self, ctx, extension: str, all: Optional[str]="on"):
        """
        \ud83d\udcd2 Loads a module. Defaults to all clusters.
        
        Parameters:
        `all` - all clusters. (on/off)
        """
        if all == "on":
            await self.send_eval("load", extension, ctx)
        elif all == "off":
            try:
                self.client.load_extension(extension)
                await ctx.send("\u2705")
            except Exception as e:
                self.client.log.error(traceback.format_exc())
                await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            await ctx.send("On/Off")

    @commands.command(hidden=True)
    @checks.is_owner()
    async def unload(self, ctx, extension: str, all: Optional[str]="on"):
        """
        \ud83d\udcd2 Unloads a module. Defaults to all clusters.

        Parameters:
        `all` - all clusters. (on/off)
        """
        if all == "on":
            await self.send_eval("unload", extension, ctx)
        elif all == "off":
            try:
                self.client.unload_extension(extension)
                await ctx.send("\u2705")
            except Exception as e:
                self.client.log.error(traceback.format_exc())
                await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            await ctx.send("On/Off")

    @commands.command(hidden=True)
    @checks.is_owner()
    async def reload(self, ctx, extension: str, all: Optional[str]="on"):
        """
        \ud83d\udcd2 Reloads a module. Defaults to all clusters.

        Parameters:
        `all` - all clusters. (on/off)
        """
        if all == "on":
            await self.send_eval("reload", extension, ctx)
        elif all == "off":
            try:
                self.client.reload_extension(extension)
                await ctx.send("\u2705")
            except Exception as e:
                self.client.log.error(traceback.format_exc())
                await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            await ctx.send("On/Off")


def setup(client):
    client.add_cog(Admin(client))

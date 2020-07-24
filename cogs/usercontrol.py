import asyncio
import json
from discord.ext import commands
from datetime import datetime, timedelta

from utils import checks
from utils import embeds as emb


class Usercontrol(commands.Cog, name="User Control", command_attrs={'hidden': True}):
    """Admin-only commands for user control."""
    def __init__(self, client):
        self.client = client

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

    @commands.command()
    @checks.is_owner()
    async def maintenance(self, ctx, body: str):
        """
        \u2699\ufe0f Enable/disable maintenance.

        Parameters:
        `body` - on or off.
        """
        if body != "off" and body != "on":
            return await ctx.send("Invalid option")
        
        await self.send_eval("maintenance", body, ctx)

    @commands.command()
    @checks.is_owner()
    async def enableguard(self, ctx, seconds: int = 1800):
        """
        \u2699\ufe0f Enable farm guard mode.

        Parameters:
        `seconds` - how long the guard mode will last.
        """
        await self.send_eval("guard", seconds, ctx)

    @commands.command()
    @checks.is_owner()
    async def editnews(self, ctx):
        """
        \ud83d\udcf0 Edits the newspaper.
        """
        content = ctx.message.clean_content.replace("%editnews ", "")
        with open('files/news.txt', "w", encoding='utf-8') as f:
            f.write(content)

        await self.send_eval("readnews", "", ctx)
        
        embed = emb.confirmembed(self.client.news, ctx)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Usercontrol(client))

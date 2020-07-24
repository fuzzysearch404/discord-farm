import operator
import asyncio
from discord.ext import commands, tasks
from discord import Embed, HTTPException
from datetime import datetime, timedelta
from typing import Optional

import utils.embeds as emb
from utils import checks
from utils.paginator import Pages
from utils.time import secstotime
from classes.item import finditem, update_market_prices
from classes import user as userutils


class Market(commands.Cog):
    """
    You can sell your harvested and produced items to the game's market.

    You can't sell your seeds, animals and trees.
    Market prices are changing every hour, so watch the item prices.
    """
    def __init__(self, client):
        self.client = client
        self._market_refresh_loop.start()
        self.sellable_types = (
            'crop', 'treeproduct', 'animalproduct', 'crafteditem', 'special'
        )
        self.not_sellable_types = (
            'cropseed', 'tree', 'animal'
        )

    def get_next_market_refresh_seconds(self):
        next_refresh = datetime.now().replace(microsecond=0, second=0, minute=0) + timedelta(hours=1)
        seconds_until = next_refresh - datetime.now()

        return seconds_until.total_seconds()

    @tasks.loop()
    async def _market_refresh_loop(self):
        await asyncio.sleep(self.get_next_market_refresh_seconds())

        update_market_prices(self.client)

    @_market_refresh_loop.before_loop
    async def before__market_refresh_loop(self):
        await self.client.wait_until_ready()

    def cog_unload(self):
        self._market_refresh_loop.cancel()

    async def market_pages(self, ctx, item_dict, category):
        client, texts = self.client, []

        refreshin = secstotime(self.get_next_market_refresh_seconds())
        texts.append(f'\u23f0 Market prices are going to be refreshed in {refreshin}\n')

        for item in item_dict.values():
            text = (
                f"{item.emoji}**{item.name.capitalize()}** - "
                f"Buying for: **{item.marketprice}**{client.gold}/item.\n"
                f"\u2696 `%sell {item.name}` \u2139 `%item {item.name}`\n"
            )
            texts.append(text)
        try:
            p = Pages(ctx, entries=texts, per_page=7, show_entry_count=False)
            p.embed.title = '\u2696 Market: ' + category
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.group()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def market(self, ctx):
        """
        \ud83d\udecd\ufe0f Access the market to sell items. Market has some subcategories.
        """
        if ctx.invoked_subcommand:
            return

        embed = Embed(title='Please choose a category', colour=1563808)
        embed.add_field(name='\ud83c\udf3d Harvest', value='`%market harvest`')
        embed.add_field(name='\ud83d\udc3d Animal products', value='`%market animal`')
        embed.add_field(name='\ud83c\udf66 Factory production', value='`%market factory`')
        embed.add_field(name='\ud83d\udce6 Other items', value='`%market other`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @market.command(aliases=['harvested', 'crops', 'crop'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def harvest(self, ctx):
        """
        \ud83c\udf3d Market category for items harvested from plants, trees and bushes.
        """
        item_dict = {}
        item_dict.update(self.client.crops)
        item_dict.update(self.client.treeproducts)
        sortedlist = sorted(item_dict.items(), key=lambda i: i[1].level)

        await self.market_pages(ctx, dict(sortedlist), "\ud83c\udf3dHarvest")

    @market.command(aliases=['animals'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def animal(self, ctx):
        """
        \ud83d\udc3d Market category for items collected from animals.
        """
        await self.market_pages(ctx, self.client.animalproducts, "\ud83d\udc3dAnimal products")

    @market.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def factory(self, ctx):
        """
        \ud83c\udf66 Market category for items crafted in factory.
        """
        await self.market_pages(ctx, self.client.crafteditems, "\ud83c\udf66Factory production")

    @market.command(aliases=['special'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def other(self, ctx):
        """
        \ud83d\udce6 Market category for special and other items.
        """
        await self.market_pages(ctx, self.client.specialitems, "\ud83d\udce6 Other items")

    @commands.command(aliases=['s'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def sell(self, ctx, *, item_search, amount: Optional[int] = 1):
        """
        \u2696\ufe0f Sell your goods to the market.

        Parameters:
        `item_search` - item to lookup for selling (item's name or ID).
        Additional parameters:
        `amount` - specify how many items to sell.

        Usage examples for selling 2 green salad items:
        `%sell green salad 2` - by using item's name.
        `%sell 701 2` - by using item's ID.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        customamount = False
        try:
            possibleamount = item_search.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            item_search = item_search.rsplit(' ', 1)[0]
            if amount > 0 and amount < 2147483647:
                customamount = True
        except Exception:
            pass

        item = await finditem(client, ctx, item_search)
        if not item:
            return

        itemtype = item.type
        if itemtype in self.sellable_types:
            pass
        elif itemtype in self.not_sellable_types:
            item = item.expandsto
        else:
            embed = emb.errorembed(
                f"Sorry, you can't sell **{item.emoji}{item.name.capitalize()}** in the market!",
                ctx
            )
            return await ctx.send(embed=embed)

        itemdata = await useracc.check_inventory_item(item)
        if not itemdata:
            embed = emb.errorembed(
                f"You don't have **{item.emoji}{item.name.capitalize()}** in your warehouse!",
                ctx
                )
            return await ctx.send(embed=embed)

        current_amount = itemdata['amount']

        sellembed = Embed(title='Selling details', colour=9309837)
        sellembed.add_field(
            name='Item',
            value=f'{item.emoji}**{item.name.capitalize()}**\n\ud83d\udcddItem ID: {item.id}'
        )
        sellembed.add_field(
            name='Price',
            value=f'{client.gold}{item.marketprice}'
        )
        sellembed.set_footer(
            text=ctx.author, icon_url=ctx.author.avatar_url
        )

        if not customamount:
            sellembed.add_field(
                name='Amount',
                value=("Please enter the amount in the chat\n"
                "To cancel, type `X`.\n"
                f"You currently have {current_amount}{item.emoji} in your warehouse.")
            )

            sellinfomessage = await ctx.send(embed=sellembed)

            def check(m):
                return m.author == ctx.author

            entry = None
            try:
                entry = await client.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                embed = emb.errorembed(
                    f'Too long. {item.emoji}{item.name.capitalize()} selling canceled.',
                    ctx
                )
                await ctx.send(embed=embed)

            if not entry: return

            if entry.clean_content.lower() == 'x':
                embed = emb.confirmembed(f'Okey, {item.emoji}{item.name.capitalize()} selling canceled.', ctx)
                return await ctx.send(embed=embed)
            
            try:
                amount = int(entry.clean_content)
                if amount < 1 or amount > 2147483647:
                    embed = emb.errorembed(
                        f'Invalid amount. {item.emoji}{item.name.capitalize()} selling to market canceled.',
                        ctx
                    )
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed(
                    f'Invalid amount. {item.emoji}{item.name.capitalize()} selling to market canceled.',
                    ctx
                )
                return await ctx.send(embed=embed)

            sellembed.set_field_at(
                index=2,
                name='Amount',
                value=amount
            )
        else:
            sellembed.add_field(
                name='Amount',
                value=amount
            )
        sellembed.add_field(
            name='Total',
            value=f'{client.gold}{item.marketprice * amount}'
        )
        sellembed.add_field(
            name='Confirmation',
            value='React with \u2705, to finish selling these items'
        )
        sellinfomessage = await ctx.send(embed=sellembed)
        ctx.reply_message = sellinfomessage # To pass it to outside function
        await sellinfomessage.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705' and reaction.message.id == sellinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await sellinfomessage.clear_reactions()
            else: return

        await self.sell_with_gold(ctx, item, amount)

    async def sell_with_gold(self, ctx, item, amount):
        # Check again (after another user input time period)
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        total = item.marketprice * amount

        itemdata = await useracc.check_inventory_item(item)
        if not itemdata:
            embed = emb.errorembed(
                f"You do not have **{item.emoji}{item.name.capitalize()}** in your warehouse!",
                ctx
                )
            try:
                return await ctx.reply_message.edit(embed=embed)
            except HTTPException:
                return

        if amount > itemdata['amount']:
            embed = emb.errorembed(
                f"You only have **{itemdata['amount']}**x {item.emoji}{item.name.capitalize()} in yout warehouse!",
                ctx
                )
            try:
                return await ctx.reply_message.edit(embed=embed)
            except HTTPException:
                return

        await useracc.remove_item_from_inventory(item, amount)
        await useracc.give_money(total)

        embed = emb.confirmembed(
            f"You successfully sold {amount}x {item.emoji}{item.name.capitalize()} for {total}{self.client.gold}!",
            ctx
            )
        try:
            await ctx.reply_message.edit(embed=embed)
        except HTTPException:
            pass

def setup(client):
    client.add_cog(Market(client))
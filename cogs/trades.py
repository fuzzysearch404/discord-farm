from asyncio import TimeoutError
from discord.ext import commands
from discord import Embed, HTTPException
from typing import Optional
from utils import checks
from utils import embeds as emb
from utils.paginator import Pages
from utils.convertors import MemberID
from classes.item import finditem
from classes import user as userutils
from classes import trade as tradeutils

class Trades(commands.Cog, name="Trading"):
    """
    Trade items with your friends.

    Trades are per server. If you create a trade in server "A",
    then your trades will only be available to "A" server's members -
    not for server "B" or "C" or even "D" members.
    """
    def __init__(self, client):
        self.client = client
        self.tradeable_types = (
            'crop', 'crafteditem', 'treeproduct',
            'animalproduct', 'special'
        )
        self.not_tradable_types = (
            'cropseed', 'tree', 'animal'
        )

    @commands.command(aliases=['at'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def alltrades(self, ctx):
        """
        \ud83d\uddc2\ufe0f Lists all currently active trades in the current server.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        information = []

        storedata = await useracc.get_guild_store(ctx.guild)
        if not storedata:
            embed = emb.errorembed(
                f'Nobody is trading anything in this server yet.',
                ctx
            )
            return await ctx.send(embed=embed)

        for data in storedata:
            try:
                item = client.allitems[data['itemid']]
            except KeyError:
                raise Exception(f"Could not find item {data['itemid']}")

            information.append((
                f"\ud83d\udc68\u200d\ud83c\udf3e**{data['username']}**\n"
                f"\ud83d\udccb**Selling {data['amount']}x {item.emoji}{item.name.capitalize()} "
                f"for {data['price']}**{client.gold}\n\ud83e\udd1dAccept trade - `%trade {data['id']}`\n"
            ))

        try:
            p = Pages(ctx, entries=information, per_page=7, show_entry_count=False)
            p.embed.title = f"\ud83e\udd1d{ctx.guild} server's active trades"
            p.embed.color = 7995937
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def trades(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83e\udd1d Lists your or someone's currently active trades.

        Additional parameters:
        `member` - some user in your server. (tagged user or user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)
        
        crops, citems, animalp, special = {}, {}, {}, {}
        information = []
        member = member or ctx.author

        storedata = await useracc.get_user_store(ctx.guild)
        if not storedata:
            embed = emb.errorembed(
                f'{member} does not trade anything in this server',
                ctx
            )
            return await ctx.send(embed=embed)
        for data in storedata:
            try:
                item = client.allitems[data['itemid']]
                itemtype = item.type

                if itemtype == 'crop' or itemtype == 'treeproduct':
                    crops[data] = item
                elif itemtype == 'crafteditem':
                    citems[data] = item
                elif itemtype == 'animalproduct':
                    animalp[data] = item
                else:
                    special[data] = item
            except KeyError:
                raise Exception(f"Could not find item {data['itemid']}")

        def cycle_dict(dct):
            for data, item in dct.items():
                fmt = (f"{item.emoji}**{item.name.capitalize()}** x{data['amount']} "
                f"{client.gold}{data['price']} \ud83d\uded2 `%trade {data['id']}`")
                information.append(fmt)

        if len(crops) > 0: cycle_dict(crops)
        if len(citems) > 0: cycle_dict(citems)
        if len(animalp) > 0: cycle_dict(animalp)
        if len(special) > 0: cycle_dict(special)

        try:
            p = Pages(ctx, entries=information, per_page=15, show_entry_count=False)
            p.embed.title = f"\ud83e\udd1d{member}'s trades"
            p.embed.color = 7995937
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command(hidden=True)
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def trade(self, ctx, id: int):
        """
        \ud83e\udd1d Accept player's trade offer.

        You can trade with yourself for free.
        This is useful, if you want to remove your own trade.

        Parameters:
        `id` - ID of the trade you want to accept.

        Usage example:
        `%trade 123` - accept trade offer with ID 123.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        tradedata = await tradeutils.get_trade(client, id, ctx.guild)
        if not tradedata:
            embed = emb.errorembed(
                "Someone already accepted this trade or invalid ID provided",
                ctx
            )
            return await ctx.send(embed=embed)

        traderid, itemid = tradedata['userid'], tradedata['itemid']
        cost, amount = tradedata['price'], tradedata['amount']

        try:
            item = client.allitems[itemid]
        except KeyError:
            raise Exception("Could not find item ID " + itemid)

        if useracc.level < item.level:
            embed = emb.errorembed(
                "Sorry, your experience level is too low to buy these items.",
                ctx
            )
            return await ctx.send(embed=embed)

        if cost > useracc.money and traderid != useracc.userid:
            embed = emb.errorembed(
                "You do not have enough gold to buy these items.",
                ctx
            )
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Purchase details', color=8052247)
        buyembed.set_footer(
            text=f"{ctx.author} Gold: {useracc.money} Gems: {useracc.gems}",
            icon_url=ctx.author.avatar_url,
        )
        buyembed.add_field(
            name='Items',
            value=f"{amount}x{item.emoji}{item.name.capitalize()}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gold}{cost}"
        )
        buyembed.add_field(name='Confirmation', value=f'React with {client.gold}')
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gold and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await buyinfomessage.clear_reactions()
            else: return

        if not str(reaction.emoji) == client.gold:
            return

        selfbuy = traderid == useracc.userid
        if useracc.money < cost and not selfbuy:
            embed = emb.errorembed(
                "You do not have enough gold to buy these items.",
                ctx
            )
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        tradedata = await tradeutils.get_trade(client, id, ctx.guild)
        if not tradedata:
            embed = emb.errorembed(
                'Oops! Somebody managed to buy these items before you.',
                ctx
            )
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        trader = ctx.guild.get_member(traderid)
        if not trader:
            trader = await ctx.guild.fetch_member(traderid)
            if not trader: return ctx.send("Something went terribly wrong here...")
        
        traderdata = await checks.check_account_data(ctx, lurk=trader)
        if not traderdata: return
        traderacc = userutils.User.get_user(traderdata, client)

        await tradeutils.delete_trade(client, tradedata['id'])
        await useracc.add_item_to_inventory(item, amount)

        if not selfbuy:
            await useracc.give_money(cost * -1)
            await traderacc.give_money(cost)

        if selfbuy: sum = 0
        else: sum = cost
        embed = emb.confirmembed(
            f"You purchased {amount}x{item.emoji}{item.name.capitalize()} for {sum}{client.gold}",
            ctx
        )
        try:
            await buyinfomessage.edit(embed=embed)
        except HTTPException:
            pass

        if selfbuy: return
        
        if traderacc.notifications:
            embed = emb.confirmembed(
                f"{ctx.author} accepted your trade -  {amount}x{item.emoji}{item.name.capitalize()} for {cost}{client.gold}!",
                ctx, pm=True
            )
            try:
                await trader.send(embed=embed)
            except HTTPException:
                pass

    @commands.command(aliases=['ct', 'addtrade'])
    @checks.user_cooldown(30)
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def createtrade(self, ctx, *, item_search, amount: Optional[int] = 1):
        """
        \ud83d\udcb0 Creates item trade in the current server.

        This command has a short cooldown.

        Parameters:
        `item_search` - item to lookup for to trade (item's name or ID).
        Additional parameters:
        `amount` - specify how many items to trade.

        Usage examples for creating trade offer for 20 lettuce items:
        `%createtrade lettuce 20` - by item's name.
        `%createtrade 101 20` - by item's ID.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        try:
            possibleamount = item_search.rsplit(' ', 1)[1]
            amount = int(possibleamount)
            item_search = item_search.rsplit(' ', 1)[0]
            if not amount > 0 or amount > 2147483647:
                raise Exception('Invalid amount')
        except Exception:
            embed = emb.errorembed(
                "Sorry, the amount is required to create the trade.\n"
                "Enter amount at the end of the command.\n"
                "Example: `%createtrade carrots 20`",
                ctx
            )
            return await ctx.send(embed=embed)

        item = await finditem(client, ctx, item_search)
        if not item:
            return

        itemtype = item.type
        if itemtype in self.tradeable_types:
            pass
        elif itemtype in self.not_tradable_types:
            item = item.expandsto
        else:
            embed = emb.errorembed(
                f"Sorry, you can't trade {item.emoji}{item.name.capitalize()}!",
                ctx
            )
            return await ctx.send(embed=embed)

        minprice = item.minprice * amount
        maxprice = item.maxprice * amount
        maxprice = maxprice + int(maxprice * 0.25)

        sellembed = Embed(title='Create trade offer', colour=8052247)
        sellembed.add_field(
            name='Item',
            value=f'{item.emoji}**{item.name.capitalize()}**\nItem ID: {item.id}'
        )
        sellembed.set_footer(
            text=ctx.author, icon_url=ctx.author.avatar_url
        )
        sellembed.add_field(
            name='Amount',
            value=amount
        )
        sellembed.add_field(
            name=f'Allowed price range',
            value=f"**{minprice} - {maxprice} {client.gold}**"
        )
        sellembed.add_field(
            name=f'{client.gold}Price',
            value=("Please enter the price in the chat\n"
            "To cancel, type `X`.")
        )
        sellinfomessage = await ctx.send(embed=sellembed)

        def check(m):
            return m.author == ctx.author

        entry = None
        try:
            entry = await client.wait_for('message', check=check, timeout=30.0)
        except TimeoutError:
            embed = emb.errorembed('Too long... Trade creation canceled.', ctx)
            await ctx.send(embed=embed)

        if not entry: return
        elif entry.clean_content.lower() == 'x':
            embed = emb.confirmembed(f'Trade creation canceled.', ctx)
            return await ctx.send(embed=embed)

        try:
            price = int(entry.clean_content)
            if price < 1:
                embed = emb.errorembed('Invalid price', ctx)
                return await ctx.send(embed=embed)
        except ValueError:
            embed = emb.errorembed(
                'Invalid price. Try again and enter the price with numbers',
                ctx
            )
            return await ctx.send(embed=embed)

        if price > maxprice or price < minprice:
            embed = emb.errorembed(
                'Invalid price.\n'
                f'You can only set price range: **{minprice} - {maxprice} {client.gold}**',
                ctx
            )
            return await ctx.send(embed=embed)

        sellembed.remove_field(index=2)
        sellembed.remove_field(index=2)
        sellembed.add_field(
            name='Desired profit',
            value=f'{client.gold}{price}'
        )
        sellembed.add_field(
            name='Confirmation',
            value='To finish, react with \u2705'
        )
        sellinfomessage = await ctx.send(embed=sellembed)
        await sellinfomessage.add_reaction('\u2705')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '\u2705' and reaction.message.id == sellinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=10.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await sellinfomessage.clear_reactions()
            else: return

        usedslots = await useracc.get_used_store_slot_count(ctx.guild)

        if usedslots >= useracc.storeslots:
            embed = emb.errorembed(
                "Insufficient trading capacity.\n"
                "You can upgrade the your trading capacity with the "
                "`%upgrade trading` command.",
                ctx
            )
            try:
                return await sellinfomessage.edit(embed=embed)
            except HTTPException:
                return

        itemdata = await useracc.check_inventory_item(item)
        if not itemdata:
            embed = emb.errorembed(
                f"You do not have {item.emoji}{item.name.capitalize()} in you warehouse!",
                ctx
            )
            try:
                return await sellinfomessage.edit(embed=embed)
            except HTTPException:
                return

        if amount > itemdata['amount']:
            embed = emb.errorembed(
                f"You only have {itemdata['amount']}x {item.emoji}{item.name.capitalize()}!",
                ctx
            )
            try:
                return await sellinfomessage.edit(embed=embed)
            except HTTPException:
                return

        await useracc.remove_item_from_inventory(item, amount)

        async with self.client.db.acquire() as connection:
            async with connection.transaction():
                query = """INSERT INTO store(guildid, userid, itemid, amount, price, username)
                VALUES ($1, $2, $3, $4, $5, $6);"""
                await client.db.execute(
                    query, ctx.guild.id, useracc.userid, item.id, amount, price, str(ctx.author)
                )

        embed = emb.confirmembed(
            f"You added {amount}x{item.emoji}{item.name.capitalize()} trade offer for {price}{self.client.gold}",
            ctx
        )
        
        try:
            await sellinfomessage.edit(embed=embed)
        except HTTPException:
            pass


def setup(client):
    client.add_cog(Trades(client))

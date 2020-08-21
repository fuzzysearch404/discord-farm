from asyncio import TimeoutError
from discord import Embed, HTTPException
from discord.ext import commands
from typing import Optional

import utils.embeds as emb
from utils import checks
from utils.time import secstodays
from utils.paginator import Pages
from classes.item import finditem
from classes import user as userutils
from classes import boost as boostutils


class Shop(commands.Cog):
    """
    In the shop you can buy seeds, animals and other stuff, that is 
    required for your farm.
    """
    def __init__(self, client):
        self.client = client
        self.purchasable_types = (
            'cropseed', 'tree', 'animal'
        )
        self.not_purchasable_types = (
            'crop', 'treeproduct', 'animalproduct'
        )

    async def shop_pages(self, ctx, item_dict, category):
        client, texts = self.client, []

        for item in item_dict.values():
            text = (
                f"\ud83d\udd31{item.level} {item.emoji}**{item.name.capitalize()}** - "
                f"Price: **{item.gold_cost}**{client.gold}\n"
                f"\ud83d\uded2 `%buy {item.name}` \u2139 `%item {item.name}`\n"
            )
            texts.append(text)
        try:
            p = Pages(ctx, entries=texts, per_page=7, show_entry_count=False)
            p.embed.title = '\ud83d\uded2 Shop: ' + category
            p.embed.color = 82247
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.group()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def shop(self, ctx):
        """
        \ud83c\udfea Access the shop to buy items. Shop has some subcategories.
        """
        if ctx.invoked_subcommand:
            return

        embed = Embed(title='Please choose a category', colour=822472)
        embed.add_field(name='\ud83c\udf3d Crop seeds', value='`%shop crops`')
        embed.add_field(name='\ud83c\udf33 Tree plants', value='`%shop trees`')
        embed.add_field(name='\ud83d\udc14 Animals', value='`%shop animals`')
        embed.add_field(name='\u2b06 Boosters', value='`%shop boosts`')
        embed.add_field(name='\u2b50 Upgrades', value='`%shop upgrades`')
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @shop.command(aliases=['crop', 'seed', 'seeds'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def crops(self, ctx):
        """
        \ud83c\udf3d Shop category for crop seeds.
        """
        await self.shop_pages(ctx, self.client.cropseeds, "\ud83c\udf3dCrop seeds")

    @shop.command(aliases=['tree'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def trees(self, ctx):
        """
        \ud83c\udf33 Shop category for tree plants.
        """
        await self.shop_pages(ctx, self.client.trees, "\ud83c\udf33Tree plants")

    @shop.command(aliases=['animal'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def animals(self, ctx):
        """
        \ud83d\udc14 Shop category for animals.
        """
        await self.shop_pages(ctx, self.client.animals, "\ud83d\udc14Animals")

    @shop.command(aliases=['boosters', 'boost'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def boosts(self, ctx):
        """
        \u2b06 Shop category for boosters.
        """
        embed = Embed(title='\u2b06 Boosters', color=82247)
        embed.add_field(
            name='\ud83d\udc29Squealer',
            value="""Protects your field. Or does it?
            `%boost dog1`"""
        )
        embed.add_field(
            name='\ud83d\udc36Saliva Toby',
            value="""Protects your land, but sometimes likes to play around.
            `%boost dog2`"""
        )
        embed.add_field(
            name='\ud83d\udc15Rex',
            value="""Protects your farm and your conscience.
            `%boost dog3`"""
        )
        embed.add_field(
            name='\ud83d\udc31Leo',
            value="""Keeps your harvest fresh. Don't ask me how...
            `%boost cat`"""
        )
        embed.set_footer(
            text="To view your currently active boosters, use the %boosts command", 
            icon_url=ctx.author.avatar_url
        )
        await ctx.send(embed=embed)

    @shop.command(aliases=['upgrade'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def upgrades(self, ctx):
        """
        \u2b50 Shop category for upgrades.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        embed = Embed(title='\u2b50 Upgrades', color=82247)
        embed.add_field(
            name=f'\ud83d\udd313 {client.tile}Expand farm size',
            value=(f"\ud83c\udd95 {useracc.tiles} \u2192 {useracc.tiles + 1} size\n"
            f"{client.gem}1\n"
            "\ud83d\uded2 `%upgrade farm`")
        )
        embed.add_field(
            name=f'\ud83d\udd313 \ud83c\udfedFactory upgrade - capacity',
            value=(f"\ud83c\udd95 {useracc.factoryslots} \u2192 {useracc.factoryslots + 1} capacity\n"
            f"{client.gem}1\n"
            "\ud83d\uded2 `%upgrade factory1`")
        )
        if useracc.factorylevel < 10:
            embed.add_field(
                name=f'\ud83d\udd313 \ud83c\udfedFactory upgrade - workers',
                value=(f"\ud83c\udd95 {useracc.factorylevel * 5}% \u2192 "
                f"{(useracc.factorylevel + 1) *5}% faster production speed\n"
                f"{client.gem}1\n"
                "\ud83d\uded2 `%upgrade factory2`")
            )
        embed.add_field(
            name=f'\ud83e\udd1dTrading upgrade',
            value=(f"\ud83c\udd95 {useracc.storeslots} \u2192 {useracc.storeslots + 1} max. trades\n"
            f"{client.gold}{useracc.get_store_upgrade_cost()}\n"
            "\ud83d\uded2 `%upgrade trading`")
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['b'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def buy(self, ctx, *, item_search, amount: Optional[int] = 1):
        """
        \ud83d\uded2 Buy items from the shop.

        Parameters:
        `item_search` - item to lookup for buying (item's name or ID).
        Additional parameters:
        `amount` - specify how many items to buy.

        Usage examples for buying 2 lettuce seed items:
        `%buy lettuce seeds 2` - by using item's name.
        `%buy lettuce 2` - by using item's shorter name.
        `%buy 1 2` - by using item's ID.
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
        if itemtype in self.purchasable_types:
            pass
        elif itemtype in self.not_purchasable_types:
            item = item.madefrom
        else:
            embed = emb.errorembed(
                f"Sorry, you can't buy **{item.emoji}{item.name.capitalize()}** from the shop!",
                ctx
            )
            return await ctx.send(embed=embed)

        if useracc.level < item.level:
            embed = emb.errorembed(
                f"Sorry, your experience level is too low level to buy **{item.emoji}{item.name.capitalize()}**!\n"
                f"\ud83d\udd31 Required level: {item.level}.",
                ctx
            )
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f'{item.emoji}**{item.name.capitalize()}**\n\ud83d\udcddID: {item.id}'
        )
        buyembed.add_field(
            name='Price',
            value=f'{client.gold}{item.gold_cost}'
        )
        buyembed.set_footer(
            text=f"{ctx.author} Gold: {useracc.money} Gems: {useracc.gems}",
            icon_url=ctx.author.avatar_url,
        )

        if not customamount:
            buyembed.add_field(
                name='Amount',
                value=("Please enter the amount in the chat.\n"
                "To cancel, type `X`.")
            )

            buyinfomessage = await ctx.send(embed=buyembed)

            def check(m):
                return m.author == ctx.author

            entry = None
            try:
                entry = await client.wait_for('message', check=check, timeout=30.0)
            except TimeoutError:
                embed = emb.errorembed(
                    f'Too long. {item.emoji}{item.name.capitalize()} purchase canceled.',
                    ctx
                )
                await ctx.send(embed=embed)

            if not entry: return

            if entry.clean_content.lower() == 'x':
                embed = emb.confirmembed(f'Okey, {item.emoji}{item.name.capitalize()} purchase canceled.', ctx)
                return await ctx.send(embed=embed)

            try:
                amount = int(entry.clean_content)
                if amount < 1 or amount > 2147483647:
                    embed = emb.errorembed(
                        f'Invalid amount. {item.emoji}{item.name.capitalize()} purchase canceled.',
                        ctx
                    )
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = emb.errorembed(
                    f'Invalid amount. {item.emoji}{item.name.capitalize()} purchase canceled.', 
                    ctx
                )
                return await ctx.send(embed=embed)

            buyembed.set_field_at(
                index=2,
                name='Amount',
                value=amount
            )
        else:
            buyembed.add_field(
                name='Amount',
                value=amount
            )
        buyembed.add_field(
            name='Total',
            value=f'{client.gold}{item.gold_cost * amount}'
        )
        buyembed.add_field(
            name='Confirmation',
            value=f'React with {client.gold}, to finish the purchase'
        )
        buyinfomessage = await ctx.send(embed=buyembed)
        ctx.reply_message = buyinfomessage # To pass it to outside function
        await buyinfomessage.add_reaction(client.gold)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gold and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await buyinfomessage.clear_reactions()
            else: return

        await self.buy_item_with_gold(ctx, item, amount)

    async def buy_item_with_gold(self, ctx, item, amount):
        # Check again (after another user input time period)
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        total = item.gold_cost * amount

        if useracc.money < total:
            embed = emb.errorembed(
                'You do not have enough gold to buy these items!',
                ctx
            )
            try:
                return await ctx.reply_message.edit(embed=embed)
            except HTTPException:
                return

        await useracc.add_item_to_inventory(item, amount)
        await useracc.give_money(total * -1)

        embed = emb.confirmembed(
            f"You successfully purchased {amount}x{item.emoji}{item.name.capitalize()} for {total}{self.client.gold}!",
            ctx
        )
        try:
            await ctx.reply_message.edit(embed=embed)
        except HTTPException:
            pass

    @commands.group()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def upgrade(self, ctx):
        """
        \u2b50 Purchase various upgrades for faster game progression.
        """
        if ctx.invoked_subcommand:
            return

        await self.upgrades.invoke(ctx)

    @upgrade.command(aliases=['field'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def farm(self, ctx):
        """
        \ud83d\uded2 [Unlocks from level 3] Adds another farm size tile.

        If you previously could grow 2 items on your field at the time,
        after purchasing this upgrade, you can grow 3 items at the time. 
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        if useracc.level < 3:
            embed = emb.errorembed(
                'Farm field expansions are available from experience level 3.',
                ctx
            )
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"{client.tile} {useracc.tiles} \u2192 {useracc.tiles + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gem}1"
        )
        buyembed.add_field(name='Confirmation', value=f'React with {client.gem}')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await buyinfomessage.clear_reactions()
            else: return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return

        if userdata['gems'] < 1:
            embed = emb.errorembed(
                'You do not have enough gems for this purchase!',
                ctx
                )
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        await useracc.add_fields(1)
        await useracc.give_gems(-1)
        embed = emb.congratzembed(
            f"You now have {client.tile} {useracc.tiles + 1} farm field tiles!",
            ctx
        )
        try:
            await buyinfomessage.edit(embed=embed)
        except HTTPException:
            pass

    @upgrade.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def factory1(self, ctx):
        """
        \ud83d\uded2 [Unlocks from level 3] Adds another factory capacity slot.

        If you previously could queue 2 items for production at the time,
        after purchasing this upgrade, you can queue 3 items at the time. 
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        if useracc.level < 3:
            embed = emb.errorembed(
                'Factory upgrades are available from experience level 3.',
                ctx
            )
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"\ud83c\udfed\ud83d\udce6 {useracc.factoryslots} \u2192 {useracc.factoryslots + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gem}1"
        )
        buyembed.add_field(name='Confirmation', value=f'React with {client.gem}')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await buyinfomessage.clear_reactions()
            else: return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return

        if userdata['gems'] < 1:
            embed = emb.errorembed('You do not have enough gems for this purchase!', ctx)
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        await useracc.add_factory_slots(1)
        await useracc.give_gems(-1)
        embed = emb.congratzembed(
            f"Your factory has now production capatity of {useracc.factoryslots + 1}!",
            ctx
        )
        try:
            await buyinfomessage.edit(embed=embed)
        except HTTPException:
            pass

    @upgrade.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def factory2(self, ctx):
        """
        \ud83d\udc68\u200d\ud83c\udfed [Unlocks from level 3] Increases factory production speed by 5%.

        Makes your factory production speed a bit faster.
        Max. factory workers: 10.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        if useracc.level < 3:
            embed = emb.errorembed(
                'Factory upgrades are available from experience level 3.',
                ctx
            )
            return await ctx.send(embed=embed)

        if useracc.factorylevel >= 10:
            embed = emb.errorembed(
                'You already have reached the maximum factory worker amount.',
                ctx
            )
            return await ctx.send(embed=embed)

        buyembed = Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"\ud83c\udfed\ud83d\udc68\u200d\ud83c\udfed {useracc.factorylevel} \u2192 {useracc.factorylevel + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gem}1"
        )
        buyembed.add_field(name='Confirmation', value=f'React with {client.gem}')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        buyinfomessage = await ctx.send(embed=buyembed)
        await buyinfomessage.add_reaction(client.gem)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == client.gem and reaction.message.id == buyinfomessage.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await buyinfomessage.clear_reactions()
            else: return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return

        if userdata['gems'] < 1:
            embed = emb.errorembed('You do not have enough gems for this purchase!', ctx)
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        if userdata['factorylevel'] >= 10:
            embed = emb.errorembed(
                'You already have reached the maximum factory worker amount.',
                ctx
            )
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        await useracc.add_factory_level(1)
        await useracc.give_gems(-1)
        embed = emb.congratzembed(
            f"Your factory now produces items {(useracc.factorylevel + 1) * 5}% faster!",
            ctx
        )
        try:
            await ctx.send(embed=embed)
        except HTTPException:
            pass

    @upgrade.command(aliases=['trade', 'trades'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def trading(self, ctx):
        """
        \ud83d\uded2 Adds another trading capacity slot.

        If you previously could trade 2 items at the time,
        after purchasing this upgrade, you can trade 3 items at the time. 
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        cost = useracc.get_store_upgrade_cost()

        buyembed = Embed(title='Purchase details', colour=9309837)
        buyembed.add_field(
            name='Item',
            value=f"\ud83c\udfea {useracc.storeslots} \u2192 {useracc.storeslots + 1}"
        )
        buyembed.add_field(
            name='Price',
            value=f"{client.gold}{cost}"
        )
        buyembed.add_field(name='Confirmation', value=f'React with {client.gold}')
        buyembed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
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

        userdata = await checks.check_account_data(ctx)
        if not userdata: return

        if userdata['money'] < cost:
            embed = emb.errorembed(
                'You do not have enough gold for this purchase!',
                ctx
            )
            try:
                return await buyinfomessage.edit(embed=embed)
            except HTTPException:
                return

        await useracc.add_store_slots(1)
        await useracc.give_money(cost * -1)
        embed = emb.congratzembed(
            f"You can now create up to {useracc.storeslots + 1} trades!",
            ctx
        )
        try:
            await buyinfomessage.edit(embed=embed)
        except HTTPException:
            pass

    @commands.group()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def boost(self, ctx):
        """
        \u2b06 Purchase various boosts for faster game progression.
        """
        if ctx.invoked_subcommand:
            return

        await self.boosts.invoke(ctx)

    @boost.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def dog1(self, ctx):
        """
        \ud83d\udc29 Purchase dog "Squealer" to protect your farm's field.

        Enables low protection against your farm's raids for the period
        of booster's duration.
        Boost's price increases by increasing the farm field size.
        """
        await self.prepare_boost(ctx, boostutils.dog1)

    @boost.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def dog2(self, ctx):
        """
        \ud83d\udc36 Purchase dog "Saliva Toby" to protect your farm's field.

        Enables medium protection against your farm's raids for the period
        of booster's duration.
        Boost's price increases by increasing the farm field size.
        """
        await self.prepare_boost(ctx, boostutils.dog2)

    @boost.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def dog3(self, ctx):
        """
        \ud83d\udc15 Purchase dog "Rex" to protect your farm's field.

        Enables highest protection against your farm's raids for the period
        of booster's duration.
        Boost's price increases by increasing the farm field size.
        """
        await self.prepare_boost(ctx, boostutils.dog3)

    @boost.command()
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def cat(self, ctx):
        """
        \ud83d\udc31 Purchase cat "Leo" to look after your farm's field.

        Allows to collect rotten crops and rotten production from your farm's 
        field for the period of booster's duration.
        Boost's price increases by increasing the farm field size.
        """
        await self.prepare_boost(ctx, boostutils.cat)

    async def prepare_boost(self, ctx, boost):
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        tiles = useracc.tiles
        price_one_day = boostutils.get_boost_price(boost.one_day_price, tiles)
        price_three_day = boostutils.get_boost_price(boost.three_day_price, tiles)
        price_seven_day = boostutils.get_boost_price(boost.seven_day_price, tiles)

        emojis_prices = {
            '1\u20e3': price_one_day,
            '3\u20e3': price_three_day,
            '7\u20e3': price_seven_day
        }

        embed = Embed(title=f'Get {boost.emoji} booster')
        embed.add_field(
            name='For 1 day',
            value=f"{price_one_day}{client.gold}"
            )
        embed.add_field(
            name='For 3 days',
            value=f"{price_three_day}{client.gold}"
            )
        embed.add_field(
            name='For 7 days',
            value=f"{price_seven_day}{client.gold}"
            )
        message = await ctx.send(embed=embed)
        await message.add_reaction('1\u20e3')
        await message.add_reaction('3\u20e3')
        await message.add_reaction('7\u20e3')

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in emojis_prices.keys() and reaction.message.id == message.id

        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=30.0)
        except TimeoutError:
            if checks.can_clear_reactions(ctx):
                return await message.clear_reactions()
            else: return

        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        
        price = emojis_prices[str(reaction.emoji)]

        if userdata['money'] < price:
            embed = emb.errorembed(
                'You do not have enough gold for this booster!',
                ctx
            )
            try:
                return await message.edit(embed=embed)
            except HTTPException:
                return

        duration = boostutils.DURATIONS[int(str(reaction.emoji)[0])]

        await useracc.give_money(price * -1)
        await useracc.add_boost(boost, duration)

        embed = emb.confirmembed(
            f"Booster {boost.emoji} activated for {secstodays(duration)}!",
            ctx
        )
        try:
            await message.edit(embed=embed)
        except HTTPException:
            pass


def setup(client):
    client.add_cog(Shop(client))

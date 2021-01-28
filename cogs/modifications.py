from discord import Embed
from typing import Optional
from discord.ext import commands

import utils.embeds as emb
from utils import checks
from utils import time
from utils.paginator import Pages
from utils.convertors import MemberID
from classes import user as userutils
from classes import item as itemutils


class Modifications(commands.Cog):
    """
    Are crops growing too slow? Are you too slow to collect the
    harvest? There is a solution - genetic modifications.
    You can upgrade your seeds, trees and bushes, even your
    animals in your laboratory.
    """
    def __init__(self, client):
        self.client = client
        self.modifiable_item_types = (
            itemutils.CropSeed, itemutils.Tree, itemutils.Animal
        )
        self.non_modifiable_item_types = (
            itemutils.Crop, itemutils.TreeProduct, itemutils.AnimalProduct
        )

    def calculate_mod_cost(self, item, level):
        if level < 3:
            return item.gold_cost * level
        elif level < 5:
            return item.gold_cost * level * 4
        elif level < 8:
            return item.gold_cost * level * 5
        else:
            return item.gold_cost * level * 6

    def calculate_mod_cooldown(self, level):
        if level == 1:
            return 120
        elif level < 5:
            return level * 300
        elif level < 8:
            return level * 400
        else:
            return level * 500

    @commands.command(aliases=['lab'])
    @checks.message_history_perms()
    @checks.reaction_perms()
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def laboratory(self, ctx, *, member: Optional[MemberID] = None):
        """
        \ud83e\uddea Lists the upgraded items and shows their bonuses.

        Additional parameters:
        `member` - some user in your server. (tagged user or user's ID)
        """
        userdata = await checks.check_account_data(ctx, lurk=member)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        member = member or ctx.author
        information = []

        mod_data = await useracc.get_all_item_modifications()
        if not mod_data:
            information.append(("\u274c No item modifications.\n\ud83d\udd2cUpgrade items with "
            "command `%modifications item_name`"))
        else:
            information.append("Item - Growing time - Harvesting time - Item volume\n")
            for data in mod_data:
                item = client.allitems[data['itemid']]
                itemchild = item.expandsto
                
                grow = time.secstotime(item.grows - int(item.grows / 100 * (data['time1'] * 5)))
                harv = time.secstotime(item.dies + int(item.dies / 100 * (data['time2'] * 10)))
                vol = itemchild.amount + int(itemchild.amount / 100 * (data['volume'] * 10))
                information.append((
                    f"{item.emoji} \ud83d\udd70\ufe0f{grow} \ud83d\udd70\ufe0f{harv} "
                    f"\u2696\ufe0f{vol} items\n`%modifications {item.name}`"
                ))
        
        try:
            p = Pages(ctx, entries=information, per_page=12, show_entry_count=False)
            p.embed.title = f"\ud83e\uddec {member}'s laboratory"
            p.embed.color = 143995
            p.embed.set_footer(
                text=ctx.author,
                icon_url=ctx.author.avatar_url
            )
            await p.paginate()
        except Exception as e:
            print(e)

    @commands.command(aliases=['mods'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def modifications(self, ctx, *, item_search):
        """
        \ud83e\uddec Shows upgrades for specific item.

        Parameters:
        `item_search` - item to lookup for to show upgrades for (item's name or ID).

        Usage examples for lettuce seeds:
        `%modifications lettuce seeds` - by using item's name.
        `%modifications lettuce` - by using item's shorter name.
        `%modifications 1` - by using item's ID.
        """
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        item = await itemutils.finditem(self.client, ctx, item_search)
        if not item:
            return

        if item.level > useracc.level:
            return await ctx.send(
                embed=emb.errorembed(f"You haven't unlocked this item yet!", ctx)
            )

        if isinstance(item, self.modifiable_item_types):
            pass
        elif isinstance(item, self.non_modifiable_item_types):
            item = item.madefrom
        else:
            return await ctx.send(
                embed=emb.errorembed(
                    f"Sorry, you start can't start a research on this type of item!",
                    ctx
                )
            )

        current_mods_data = await useracc.get_item_modification(item)
        
        def calculate_mod_data(upgrade):
            if not current_mods_data:
                return self.calculate_mod_cost(item, 1)
            elif current_mods_data[upgrade] >= 10:
                return False
            else:
                return self.calculate_mod_cost(item, current_mods_data[upgrade] + 1)

        embed = Embed(
            title=f"\ud83e\uddec {item.name.capitalize()} upgrades",
            color=143995,
            description=(
                f"\ud83e\uddea Upgrade **{item.emoji}{item.name.capitalize()}** "
                "for faster growing, longer harvesting or more items."
            )
        )
        
        grow_cost = calculate_mod_data("time1")
        if grow_cost:
            if current_mods_data:
                currentlevel = current_mods_data["time1"]
                oldtime = time.secstotime(item.grows - int(item.grows / 100 * (currentlevel * 5)))
            else:
                currentlevel = 0
                oldtime = time.secstotime(item.grows)
            
            newtime = time.secstotime(item.grows - int(item.grows / 100 * ((currentlevel+1) * 5)))
            desc = (
                f"\ud83d\udd2cLevel {currentlevel+1}/10\n"
                f"**\ud83c\udd95 {oldtime} -> {newtime}\n**"
                f"{client.gold} {grow_cost}\n"
                f"\ud83d\uded2`%research growing {item.name}`"
            )
        else:
            desc = (
                "\ud83d\udd2cMax. level\n"
                f"**{time.secstotime(item.grows - int(item.grows / 100 * 50))}**"
            )
        embed.add_field(name="\ud83d\udd70\ufe0fGrowing time", value=desc)
        
        harv_cost = calculate_mod_data("time2")
        if harv_cost:
            if current_mods_data:
                currentlevel = current_mods_data["time2"]
                oldtime = time.secstotime(item.dies + int(item.dies / 100 * (currentlevel * 10)))
            else:
                currentlevel = 0
                oldtime = time.secstotime(item.dies)
            
            newtime = time.secstotime(item.dies + int(item.dies / 100 * ((currentlevel+1) * 10)))
            desc = (
                f"\ud83d\udd2cLevel {currentlevel+1}/10\n"
                f"**\ud83c\udd95 {oldtime} -> {newtime}\n**"
                f"{client.gold} {harv_cost}\n"
                f"\ud83d\uded2`%research harvesting {item.name}`"
            )
        else:
            desc = (
                "\ud83d\udd2cMax. level\n"
                f"**{time.secstotime(item.dies * 2)}**"
            )
        embed.add_field(name="\ud83d\udd70\ufe0fHarvesting time", value=desc)
        
        itemchild = item.expandsto

        vol_cost = calculate_mod_data("volume")
        if vol_cost:
            if current_mods_data:
                currentlevel = current_mods_data["volume"]
                oldvolume = itemchild.amount + int(itemchild.amount / 100 * (currentlevel * 10))
            else:
                currentlevel = 0
                oldvolume = itemchild.amount
            newvolume = itemchild.amount + int(itemchild.amount / 100 * ((currentlevel+1) * 10))
            desc = (
                f"\ud83d\udd2cLevel {currentlevel+1}/10\n"
                f"**\ud83c\udd95 {oldvolume} -> {newvolume} items\n**"
                f"{client.gold} {vol_cost}\n"
                f"\ud83d\uded2`%research volume {item.name}`"
            )
        else:
            desc = (
                "\ud83d\udd2cMax. level\n"
                f"**{itemchild.amount * 2} items**"
            )
        embed.add_field(name="\u2696\ufe0fVolume", value=desc)

        embed.set_footer(
            text=ctx.author, 
            icon_url=ctx.author.avatar_url
        )
        await ctx.send(embed=embed)
        

    async def start_research(self, ctx, item_search, upgrade):
        userdata = await checks.check_account_data(ctx)
        if not userdata: return
        client = self.client
        useracc = userutils.User.get_user(userdata, client)

        item = await itemutils.finditem(self.client, ctx, item_search)
        if not item:
            return

        if item.level > useracc.level:
            return await ctx.send(
                embed=emb.errorembed(f"You haven't unlocked this item yet!", ctx)
            )

        if isinstance(item, self.modifiable_item_types):
            pass
        elif isinstance(item, self.non_modifiable_item_types):
            item = item.madefrom
        else:
            return await ctx.send(
                embed=emb.errorembed(
                    f"Sorry, you start can't start a research on this type of item!",
                    ctx
                )
            )

        cooldown = await checks.get_user_cooldown(ctx, "recent_research")
        if cooldown:
            return await ctx.send(
                f"\u274c The lab is being cleaned up after your last research! \ud83e\uddf9 You have to wait **{time.secstotime(cooldown)}**!"
            )

        moddata = await useracc.get_item_modification(item)
        if not moddata:
            current_mod_level = 0
        else:
            current_mod_level = moddata[upgrade]

        if current_mod_level >= 10:
            return await ctx.send(
                embed=emb.errorembed(
                    f"You already have max. level for this type of upgrade on this item!",
                    ctx
                )
            )

        mod_cost = self.calculate_mod_cost(item, current_mod_level + 1)

        if mod_cost > useracc.money:
            return await ctx.send(
                embed=emb.errorembed(
                    f"Oops, you don't have enough gold to start this research!",
                    ctx
                )
            )
        async with client.db.acquire() as connection:
            async with connection.transaction():
                query = f"""INSERT INTO modifications(userid, itemid, {upgrade})
                VALUES($1, $2, $3) ON CONFLICT(userid, itemid) DO UPDATE
                SET {upgrade} = $3;
                """
                await client.db.execute(query, useracc.userid, item.id, current_mod_level + 1)

        await useracc.give_money(mod_cost * -1)

        mod_cooldown = self.calculate_mod_cooldown(current_mod_level + 1)
        await checks.set_user_cooldown(ctx, mod_cooldown, "recent_research")

        await ctx.send(embed=emb.congratzembed(f"{item.emoji}{item.name.capitalize()} upgrade complete!", ctx))


    @commands.group(hidden=True)
    async def research(self, ctx):
        """
        \ud83d\udd2c Upgrades an item.

        You have to specify what item upgrade would you like to purchase.
        """
        if ctx.invoked_subcommand:
            return

        await self.laboratory.invoke(ctx)

    @research.command(aliases=['grow', 'g'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def growing(self, ctx, *, item_search):
        """
        \ud83d\udd2c Upgrades item's grow time.

        The item will grow in a shorter period of time.

        Parameters:
        `item_search` - item to lookup for to upgrade (item's name or ID).

        Usage examples for lettuce seeds:
        `%research growing lettuce seeds` - by using item's name.
        `%research growing lettuce` - by using item's shorter name.
        `%research growing 1` - by using item's ID.
        """
        await self.start_research(ctx, item_search, "time1")

    @research.command(aliases=['harvest', 'h'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def harvesting(self, ctx, *, item_search):
        """
        \ud83d\udd2c Upgrades item's harvest time.

        The item will be harvestable for a longer period of time.

        Parameters:
        `item_search` - item to lookup for to upgrade (item's name or ID).

        Usage examples for lettuce seeds:
        `%research harvesting lettuce seeds` - by using item's name.
        `%research harvesting lettuce` - by using item's shorter name.
        `%research harvesting 1` - by using item's ID.
        """
        await self.start_research(ctx, item_search, "time2")


    @research.command(aliases=['vol', 'amount'])
    @checks.embed_perms()
    @checks.avoid_maintenance()
    async def volume(self, ctx, *, item_search):
        """
        \ud83d\udd2c Upgrades item's harvest item volume.

        The item will grow larger amount of items.

        Parameters:
        `item_search` - item to lookup for to upgrade (item's name or ID).

        Usage examples for lettuce seeds:
        `%research volume lettuce seeds` - by using item's name.
        `%research volume lettuce` - by using item's shorter name.
        `%research volume 1` - by using item's ID.
        """
        await self.start_research(ctx, item_search, "volume")


def setup(client):
    client.add_cog(Modifications(client))

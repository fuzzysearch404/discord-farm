from . import game_items


def get_growing_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.grow_time - int(item.grow_time / 100 * (mod_level * 5))


def get_harvest_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.collect_time + int(item.collect_time / 100 * (mod_level * 10))


def get_volume(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.amount + int(item.amount / 100 * (mod_level * 10))


async def get_item_mods(ctx, item: game_items.GameItem, conn=None) -> tuple:
    grow_time = item.grow_time
    collect_time = item.collect_time
    base_volume = item.amount

    mods = await ctx.user_data.get_item_modification(ctx, item.id, conn=conn)

    if mods:
        time1_mod = mods['time1']
        time2_mod = mods['time2']
        vol_mod = mods['volume']

        if time1_mod:
            grow_time = get_growing_time(item, time1_mod)
        if time2_mod:
            collect_time = get_harvest_time(item, time2_mod)
        if vol_mod:
            base_volume = get_volume(item, vol_mod)

    return grow_time, collect_time, base_volume

from . import game_items


def get_growing_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.grow_time - int(item.grow_time / 100 * (mod_level * 5))


def get_harvest_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.collect_time + int(item.collect_time / 100 * (mod_level * 10))


def get_volume(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.amount + int(item.amount / 100 * (mod_level * 10))


async def get_item_mods_for_user(cmd, item: game_items.GameItem, conn) -> tuple:
    grow_time, collect_time, base_volume = item.grow_time, item.collect_time, item.amount

    mods = await cmd.user_data.get_item_modification(item.id, conn)
    if mods:
        grow_time = get_growing_time(item, mods['time1'])
        collect_time = get_harvest_time(item, mods['time2'])
        base_volume = get_volume(item, mods['volume'])

    return grow_time, collect_time, base_volume

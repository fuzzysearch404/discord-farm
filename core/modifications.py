from . import game_items


def get_growing_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.grow_time - int(item.grow_time / 100 * (mod_level * 5))


def get_harvest_time(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.collect_time + int(item.collect_time / 100 * (mod_level * 10))


def get_volume(item: game_items.PlantableItem, mod_level: int) -> int:
    return item.amount + int(item.amount / 100 * (mod_level * 10))

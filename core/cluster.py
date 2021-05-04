from datetime import datetime
from dataclasses import dataclass

@dataclass
class Cluster:

    __slots__ = (
        'name',
        'latencies',
        'guild_count',
        'last_ping'
    )

    name: str
    latencies: list
    guild_count: int
    last_ping: datetime
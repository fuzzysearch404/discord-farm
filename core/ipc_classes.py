from dataclasses import dataclass
from datetime import datetime


@dataclass
class IPCMessage:

    __slots__ = (
        'author',
        'action',
        'reply_global',
        'data',
    )

    author: str
    action: str
    reply_global: bool
    data: dict


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

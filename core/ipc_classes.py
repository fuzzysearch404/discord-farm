from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class IPCMessage:

    __slots__ = (
        "author",
        "action",
        "reply_global",
        "data",
    )

    author: str
    action: str
    reply_global: bool
    data: dict


@dataclass
class Cluster:

    __slots__ = (
        "name",
        "latencies",
        "ipc_latency",
        "guild_count",
        "last_ping",
        "uptime"
    )

    name: str
    latencies: list
    ipc_latency: datetime
    guild_count: int
    last_ping: datetime
    uptime: timedelta

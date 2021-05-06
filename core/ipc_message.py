from dataclasses import dataclass


@dataclass
class IPCMessage:

    __slots__ = (
        'author',
        'action',
        'data'
    )

    author: str
    action: str
    data: dict

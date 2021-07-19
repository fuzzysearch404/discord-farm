from discord import utils
from datetime import datetime, timedelta


def seconds_to_time(secs: int) -> str:
    return str(timedelta(seconds=secs)).split(".")[0]


def maybe_timestamp(when: datetime, since: datetime = None) -> str:
    since = since or datetime.now()
    secs_from_now = (when - since).total_seconds()

    if secs_from_now > 10800:  # 3 hours
        return utils.format_dt(when, style="f")
    elif secs_from_now > 60:
        return utils.format_dt(when, style="R")
    else:
        return f"in {'%.0f' % secs_from_now} seconds"

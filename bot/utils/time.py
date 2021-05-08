from datetime import timedelta


def seconds_to_time(secs: int) -> str:
    return str(timedelta(seconds=secs)).split(".")[0]

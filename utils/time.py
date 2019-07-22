def secstotime(secs):
    secs = round(secs, 2)
    days, remainder = divmod(int(secs), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days != 0:
        result = f'{days}d {hours}h {minutes}m {secs}s'
    elif hours != 0:
        result = f'{hours}h {minutes}m {secs}s'
    elif minutes != 0:
        result = f'{minutes}m {secs}s'
    else:
        result = f'{secs} sekundes'
    return result

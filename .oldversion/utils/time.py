from datetime import timedelta

def secstotime(secs):
    return str(timedelta(seconds=secs)).split(".")[0]

def secstodays(secs):
    secs = round(secs, 2)
    days, remainder = divmod(int(secs), 86400)

    if days == 1:
        return "1 day"
    else:
        return f"{days} days"

from datetime import datetime

DURATIONS = {
    1: 86400,
    3: 259200,
    7: 604800
}

class Boost:
    __slots__ = ('id', 'emoji', 'one_day_price',
    'three_day_price', 'seven_day_price')
    
    def __init__(self, id, emoji, one_day_price, 
    three_day_price, seven_day_price):
        self.id = id
        self.emoji = emoji
        self.one_day_price = one_day_price
        self.three_day_price = three_day_price
        self.seven_day_price = seven_day_price


def get_boost_price(price, tiles):
    if tiles < 5:
        return price * tiles
    elif tiles < 10:
        return price * int(tiles * 1.5)
    elif tiles < 15:
        return price * int(tiles * 2)
    else:
        return price * int(tiles * 2.5)

def boostvalid(date):
    if not date:
        return False
    return date > datetime.now()

# emoji 100% 90% 75%
dog1 = Boost('dog1', '\ud83d\udc29', 50, 135, 262)
dog2 = Boost('dog2', '\ud83d\udc36', 125, 337, 656)
dog3 = Boost('dog3', '\ud83d\udc15', 250, 675, 1312)
cat = Boost('cat', '\ud83d\udc31', 280, 756, 1470)

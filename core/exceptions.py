class FarmException(Exception):
    """Base exception class"""
    pass


class ItemNotFoundException(FarmException):
    """Exception for handling cases when game item can't be found"""
    pass

class FarmException(Exception):
    """Base exception class"""
    pass


class ItemNotFoundException(FarmException):
    """Exception for handling cases when game item can't be found"""
    pass


class UserNotFoundException(FarmException):
    """Exception raised when user profile could not be found"""
    pass

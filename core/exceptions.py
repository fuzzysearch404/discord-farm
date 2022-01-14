from discord.ext import commands


class FarmException(commands.CommandError):
    """Base exception class"""
    pass


class GameIsInMaintenance(FarmException):
    """Exception raised when game is in maintenance."""
    pass


class ItemNotFoundException(FarmException):
    """Exception for handling cases when game item can't be found"""
    pass


class UserNotFoundException(FarmException):
    """Exception raised when user profile could not be found"""
    pass


class InvalidAmountException(FarmException):
    """Exception raised when user inputs negative or invalid number"""
    pass

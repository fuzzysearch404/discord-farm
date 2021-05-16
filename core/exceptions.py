from discord.ext import commands


class GlobalCooldownException(commands.CommandOnCooldown):
    """Exception raised when user is spamming commands"""
    pass


class GameIsInMaintenance(commands.CheckFailure):
    """Exception raised when game is in maintenance."""

    pass


class FarmException(commands.CommandError):
    """Base exception class"""
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

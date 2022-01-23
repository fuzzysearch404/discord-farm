from . import embeds


class FarmException(RuntimeError):
    """Base exception class"""
    def __init__(self, message: str = None, **kwargs) -> None:
        super().__init__(message)
        self.embed = kwargs.get("embed", None)


class GameIsInMaintenance(FarmException):
    """Exception raised when game is in maintenance"""

    def __init__(self) -> None:
        super().__init__(
            "Game commands are disabled for a bot maintenance or update.\n"
            "\ud83d\udd50 Please try again after a while...\n"
            "\ud83d\udcf0 For more information use command - **/news**"
        )


class CommandOnCooldown(FarmException):
    """Exception raised when command cooldown has been reached"""
    pass


class UserNotFoundException(FarmException):
    """Exception raised when user profile could not be found"""
    pass


class ItemNotFoundException(FarmException):
    """Exception for handling cases when game item can't be found"""
    pass


class InsufficientUserLevelException(FarmException):
    """Exception for handling cases when user has insufficient user level"""

    def __init__(self, required_level: int) -> None:
        super().__init__(
            f"\ud83d\udd12 This feature unlocks at player level \ud83d\udd31 **{required_level}**!"
        )


class InsufficientGoldException(FarmException):
    """Exception for handling cases when user has insufficient gold"""
    def __init__(self, cmd, cost: int):
        super().__init__(
            "User has insufficient gold to perform this action",
            embed=embeds.no_money_embed(cmd, cost)
        )


class InsufficientGemsException(FarmException):
    """Exception for handling cases when user has insufficient gems"""
    def __init__(self, cmd, cost: int):
        super().__init__(
            "User has insufficient gems to perform this action",
            embed=embeds.no_gems_embed(cmd, cost)
        )


class InsufficientItemException(FarmException):
    """Exception for handling cases when user has insufficient item amount"""
    def __init__(self, cmd, item, req_amount: int):
        super().__init__(
            "User has insufficient item amount to perform this action",
            embed=embeds.not_enough_items(cmd, item, req_amount)
        )


class FarmException(RuntimeError):
    """Base exception class"""

    def __init__(self, message: str = None, **kwargs) -> None:
        super().__init__(message)
        self.embed = kwargs.get("embed", None)
        self.ephemeral = kwargs.get("ephemeral", False)


class CommandOwnerOnlyException(FarmException):
    """Exception for owner-only commands"""

    def __init__(self) -> None:
        super().__init__(
            "Sorry, this command is only available to the owners of this bot",
            ephemeral=True
        )


class CommandOnCooldownException(FarmException):
    """Exception raised when command cooldown has been reached"""
    pass


class GameIsInMaintenanceException(FarmException):
    """Exception raised when game is in maintenance"""

    def __init__(self) -> None:
        super().__init__(
            "Game commands are disabled for a bot maintenance or update.\n"
            "\N{CLOCK FACE ONE OCLOCK} Please try again after a while...\n"
            "\N{NEWSPAPER} For more information use command - **/news**"
        )


class UserNotFoundException(FarmException):
    """Exception raised when user profile could not be found"""

    def __init__(self, message: str = None) -> None:
        super().__init__(message, ephemeral=True)


class ItemNotFoundException(FarmException):
    """Exception for handling cases when game item can't be found"""

    def __init__(self, message: str) -> None:
        super().__init__(message, ephemeral=True)


class InsufficientUserLevelException(FarmException):
    """Exception for handling cases when user has insufficient user level"""

    def __init__(self, required_level: int) -> None:
        super().__init__(
            "\N{LOCK} This feature unlocks at player level "
            f"\N{TRIDENT EMBLEM} **{required_level}**!"
        )

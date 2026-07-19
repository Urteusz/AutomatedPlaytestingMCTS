"""Public exception hierarchy shared by backend adapters."""


class MiniDungeonsError(Exception):
    """Base exception for expected application-level failures."""


class MapNotFoundError(MiniDungeonsError):
    """Requested benchmark map does not exist."""


class GameNotFoundError(MiniDungeonsError):
    """Requested in-memory game session does not exist."""


class InvalidGameActionError(MiniDungeonsError):
    """Action cannot be parsed or is illegal in the current state."""

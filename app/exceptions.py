class MiniDashError(Exception):
    """Base application exception for MiniDash."""
    pass


class NotFoundError(MiniDashError):
    """Raised when an entity is not found in the database."""
    pass


class ValidationError(MiniDashError):
    """Raised when request data fails business logic validation."""
    pass

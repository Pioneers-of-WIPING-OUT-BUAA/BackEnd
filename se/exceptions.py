class ExternalServiceError(RuntimeError):
    """An external dependency could not complete the requested operation."""


class InvalidInputError(ValueError):
    """The request contains invalid data."""

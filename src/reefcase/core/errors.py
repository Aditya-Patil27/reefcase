"""Exceptions raised by ReefCase (architecture §4).

The hierarchy is additive only: later stories subclass these, never rename or
move them. ``core`` stays import-free here, so a raising module never has to
drag in the stack it reports on.
"""

__all__ = [
    "CitationError",
    "ConfigError",
    "ExternalServiceError",
    "NotFoundError",
    "ReefCaseError",
    "StoreError",
    "ToolError",
]


class ReefCaseError(Exception):
    """Base for everything reefcase raises."""


class ConfigError(ReefCaseError):
    """Bad or missing environment configuration."""


class NotFoundError(ReefCaseError):
    """Unknown site, survey, frame or other entity id."""


class StoreError(ReefCaseError):
    """DuckDB, migration or blob storage failure."""


class ToolError(ReefCaseError):
    """A context tool could not produce a result."""


class ExternalServiceError(ToolError):
    """An upstream HTTP call failed.

    Carries just enough context to retry or explain the failure without the
    caller parsing a message string.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.retry_after = retry_after


class CitationError(ReefCaseError):
    """A citation could not be verified against stored evidence."""

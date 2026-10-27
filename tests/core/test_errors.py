"""Contract tests for ``reefcase.core.errors`` (Story 1.2, task 4).

Architecture §4 names the module but not its contents; this hierarchy is
additive only, so these tests pin the shared base and the one error that
carries data (``ExternalServiceError``).
"""

import pytest

from reefcase.core.errors import (
    CitationError,
    ConfigError,
    ExternalServiceError,
    NotFoundError,
    ReefCaseError,
    StoreError,
    ToolError,
)

SUBCLASSES = [ConfigError, NotFoundError, StoreError, ToolError, CitationError]


@pytest.mark.parametrize("error_type", SUBCLASSES, ids=lambda cls: cls.__name__)
def test_every_error_derives_from_the_base(error_type: type[ReefCaseError]) -> None:
    assert issubclass(error_type, ReefCaseError)
    assert issubclass(ReefCaseError, Exception)


def test_external_service_error_is_a_tool_error() -> None:
    assert issubclass(ExternalServiceError, ToolError)
    assert issubclass(ExternalServiceError, ReefCaseError)


def test_external_service_error_defaults_to_none() -> None:
    error = ExternalServiceError("upstream timed out")

    assert str(error) == "upstream timed out"
    assert error.status_code is None
    assert error.url is None
    assert error.retry_after is None


def test_external_service_error_carries_context() -> None:
    error = ExternalServiceError(
        "rate limited",
        status_code=429,
        url="https://example.test/tools/heat-stress",
        retry_after=2.5,
    )

    assert error.status_code == 429
    assert error.url == "https://example.test/tools/heat-stress"
    assert error.retry_after == 2.5

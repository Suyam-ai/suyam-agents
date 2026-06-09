"""Typed exception hierarchy for suyam-agents.

SuyamError
  ├── TransientError   — retryable: HTTP 5xx, timeout, rate limit
  └── FatalError       — halt immediately: auth failures, bad config

This is a local copy — zero imports from suyam core (AGENTS-03).
"""


class SuyamError(Exception):
    """Base exception for all Suyam errors."""


class TransientError(SuyamError):
    """Retryable error. Raised by step handlers for transient failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FatalError(SuyamError):
    """Non-retryable error. Halts workflow execution immediately."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

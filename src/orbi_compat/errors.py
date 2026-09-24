"""Normalized ORBI compatibility errors."""

from __future__ import annotations


class OrbiCompatError(Exception):
    code = "ORBI_COMPAT_ERROR"
    retryable = False


class PolicyDenied(OrbiCompatError):
    code = "POLICY_DENIED"


class UnsupportedOperation(OrbiCompatError):
    code = "UNSUPPORTED_OPERATION"


class ReplayDenied(OrbiCompatError):
    code = "REPLAY_DENIED"


class RequestIdConflict(OrbiCompatError):
    code = "REQUEST_ID_CONFLICT"


class ProviderFailure(OrbiCompatError):
    code = "PROVIDER_FAILURE"


class ReconciliationError(OrbiCompatError):
    code = "RECONCILIATION_ERROR"


class PendingExecutionNotFound(ReconciliationError):
    code = "PENDING_EXECUTION_NOT_FOUND"


class AlreadyReconciled(ReconciliationError):
    code = "ALREADY_RECONCILED"


class ProviderUnavailable(ProviderFailure):
    code = "PROVIDER_UNAVAILABLE"
    retryable = True


def normalize_exception(exc: Exception) -> tuple[str, str, bool]:
    if isinstance(exc, OrbiCompatError):
        return exc.code, str(exc), bool(exc.retryable)
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "PROVIDER_UNAVAILABLE", str(exc), True
    return "PROVIDER_FAILURE", str(exc), False

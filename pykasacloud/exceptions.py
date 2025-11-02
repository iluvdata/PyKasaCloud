"""Extension of python-kasa exceptions for Kasa Cloud integration."""

from enum import IntEnum

from kasa.exceptions import KasaException


class KasaCloudError(KasaException):
    """Exception raised for errors in the Kasa Cloud API interaction."""

    def __init__(self, msg: str) -> None:
        """Initialize the KasaCloudError with a message."""
        super().__init__(msg)


class MissingCredentials(KasaCloudError):
    """Exception raised when credentials are missing."""


class CloudErrorCode(IntEnum):
    """Enum for cloud error codes."""

    SUCCESS = 0
    TOKEN_EXPIRED = -20651
    MISSING_METHOD = -20103
    MISSING_PARAMETER = -20104
    MISSING_REQUEST_DATA = -20573
    DEVICE_OFFLINE = -20571
    ACCOUNT_NOT_FOUND = -20600
    INVALID_EMAIL_OR_PASSWORD = -20601

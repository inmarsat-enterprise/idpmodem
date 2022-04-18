"""Base classes for AT command errors.
"""

class AtException(Exception):
    """Base class for AT command exceptions."""


class AtTimeout(AtException):
    """Indicates a timeout waiting for response."""


class AtGnssTimeout(AtException):
    """Indicates a timeout waiting for a GNSS fix."""


class AtCrcError(AtException):
    """Indicates a detected CRC mismatch on a response."""


class AtCrcConfigError(AtException):
    """Indicates a CRC response was received when none expected or vice versa.
    """


class AtUnsolicited(AtException):
    """Indicates unsolicited data was received from the modem."""

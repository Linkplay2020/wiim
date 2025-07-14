# wiim/exceptions.py
class WiimException(Exception):
    """Base exception for WiiM SDK."""

    pass


class WiimRequestException(WiimException):
    """Raised when an HTTP request to the WiiM device fails."""

    pass


class WiimInvalidDataException(WiimException):
    """Raised when invalid data is received from the WiiM device."""

    def __init__(self, message: str = "Invalid data received", data: str | None = None):
        super().__init__(message)
        self.data = data


class WiimDeviceException(WiimException):
    """Raised for errors specific to WiimDevice operations (e.g., UPnP failure)."""

    pass

# wiim/__init__.py
"""WiiM Asynchronous Python SDK."""

from .__version__ import __version__
from .controller import WiimController
from .discovery import (
    async_create_http_api_endpoint,
    async_create_wiim_device,
    verify_wiim_device,
)
from .endpoint import WiimApiEndpoint, WiimBaseEndpoint
from .exceptions import (
    WiimException,
    WiimRequestException,
    WiimInvalidDataException,
    WiimDeviceException,
)
from .models import (
    WiimLoopState,
    WiimMediaMetadata,
    WiimGroupRole,
    WiimGroupSnapshot,
    WiimPreset,
    WiimQueueItem,
    WiimQueueSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)
from .wiim_device import WiimDevice
from .consts import (
    PlayingStatus,
    PlayingMode,
    LoopMode,
    EqualizerMode,
    MuteMode,
    ChannelType,
    SpeakerType,
    AudioOutputHwMode,
    # DeviceAttribute,
    # PlayerAttribute,
    # MultiroomAttribute,
    # MetaInfo,
    # MetaInfoMetaData,
    # WiimHttpCommand,
)
from .handler import parse_last_change_event

__all__ = [
    "__version__",
    "WiimDevice",
    "WiimController",
    "WiimApiEndpoint",
    "WiimBaseEndpoint",
    "async_create_http_api_endpoint",
    "async_create_wiim_device",
    "verify_wiim_device",
    "WiimException",
    "WiimRequestException",
    "WiimInvalidDataException",
    "WiimDeviceException",
    "WiimLoopState",
    "WiimMediaMetadata",
    "WiimGroupRole",
    "WiimGroupSnapshot",
    "WiimPreset",
    "WiimQueueItem",
    "WiimQueueSnapshot",
    "WiimRepeatMode",
    "WiimTransportCapabilities",
    "PlayingStatus",
    "PlayingMode",
    "LoopMode",
    "EqualizerMode",
    "MuteMode",
    "ChannelType",
    "SpeakerType",
    "AudioOutputHwMode",
    "parse_last_change_event",
]

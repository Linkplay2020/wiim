# wiim/__init__.py
"""WiiM Asynchronous Python SDK."""

from .__version__ import __version__
from .consts import (
    AudioOutputHwMode,
    # DeviceAttribute,
    # PlayerAttribute,
    # MultiroomAttribute,
    # MetaInfo,
    # MetaInfoMetaData,
    # WiimHttpCommand,
    ChannelType,
    EqualizerMode,
    LoopMode,
    MuteMode,
    PlayingMode,
    PlayingStatus,
    SpeakerType,
)
from .controller import WiimController
from .discovery import (
    async_create_http_api_endpoint,
    async_create_wiim_device,
    async_probe_wiim_device,
    verify_wiim_device,
)
from .endpoint import WiimApiEndpoint, WiimBaseEndpoint
from .exceptions import (
    WiimDeviceException,
    WiimException,
    WiimInvalidDataException,
    WiimRequestException,
)
from .handler import parse_last_change_event
from .models import (
    WiimGroupRole,
    WiimGroupSnapshot,
    WiimLoopState,
    WiimMediaMetadata,
    WiimPreset,
    WiimProbeResult,
    WiimQueueItem,
    WiimQueueSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)
from .wiim_device import WiimDevice

__all__ = [
    "AudioOutputHwMode",
    "ChannelType",
    "EqualizerMode",
    "LoopMode",
    "MuteMode",
    "PlayingMode",
    "PlayingStatus",
    "SpeakerType",
    "WiimApiEndpoint",
    "WiimBaseEndpoint",
    "WiimController",
    "WiimDevice",
    "WiimDeviceException",
    "WiimException",
    "WiimGroupRole",
    "WiimGroupSnapshot",
    "WiimInvalidDataException",
    "WiimLoopState",
    "WiimMediaMetadata",
    "WiimPreset",
    "WiimProbeResult",
    "WiimQueueItem",
    "WiimQueueSnapshot",
    "WiimRepeatMode",
    "WiimRequestException",
    "WiimTransportCapabilities",
    "__version__",
    "async_create_http_api_endpoint",
    "async_create_wiim_device",
    "async_probe_wiim_device",
    "parse_last_change_event",
    "verify_wiim_device",
]

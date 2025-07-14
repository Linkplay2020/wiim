# wiim/__init__.py
"""WiiM Asynchronous Python SDK."""

from .__version__ import __version__
from .wiim_device import WiimDevice
from .controller import WiimController
from .endpoint import WiimApiEndpoint, WiimBaseEndpoint
from .exceptions import (
    WiimException,
    WiimRequestException,
    WiimInvalidDataException,
    WiimDeviceException,
)
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
    "WiimException",
    "WiimRequestException",
    "WiimInvalidDataException",
    "WiimDeviceException",
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

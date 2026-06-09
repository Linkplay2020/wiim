from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class WiimMediaMetadata:
    """Normalized media metadata exposed by the SDK."""

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    image_url: str | None = None
    uri: str | None = None
    duration: int | None = None
    position: int | None = None


class WiimRepeatMode(StrEnum):
    """Normalized repeat mode independent of Home Assistant."""

    OFF = "off"
    ONE = "one"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class WiimLoopState:
    """Normalized loop/shuffle state exposed by the SDK."""

    repeat: WiimRepeatMode
    shuffle: bool


@dataclass(frozen=True, slots=True)
class WiimTransportCapabilities:
    """Normalized transport capabilities derived from MEDIA_INFO."""

    can_next: bool = True
    can_previous: bool = True
    can_repeat: bool = False
    can_shuffle: bool = False
    play_medium: str = ""
    track_source: str = ""


@dataclass(frozen=True, slots=True)
class WiimPreset:
    """A normalized preset entry."""

    preset_id: int
    title: str
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class WiimQueueItem:
    """A normalized queue item."""

    queue_index: int
    title: str
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class WiimQueueSnapshot:
    """Normalized queue browse state."""

    items: tuple[WiimQueueItem, ...]
    source_name: str | None = None
    play_medium: str = ""
    track_source: str = ""
    is_active: bool = False


class WiimGroupRole(StrEnum):
    """Normalized multiroom role for a device."""

    LEADER = "leader"
    FOLLOWER = "follower"
    STANDALONE = "standalone"


@dataclass(frozen=True, slots=True)
class WiimGroupSnapshot:
    """Normalized group state for a device."""

    role: WiimGroupRole
    leader_udn: str
    member_udns: tuple[str, ...]

    @property
    def command_target_udn(self) -> str:
        """Return the device UDN that should receive direct commands."""
        return self.leader_udn


@dataclass(frozen=True, slots=True)
class WiimProbeResult:
    """Normalized probe result for discovery/config flows."""

    udn: str
    name: str
    model: str
    host: str
    location: str


@dataclass(frozen=True, slots=True)
class WiimDeviceDiagnostics:
    """Stable device diagnostics exposed by the SDK."""

    name: str
    udn: str
    model_name: str
    manufacturer: str | None
    firmware_version: str | None
    ip_address: str | None
    available: bool
    supports_http_api: bool
    presentation_url_available: bool
    event_subscriptions_active: bool
    input_modes: tuple[str, ...]
    output_modes: tuple[str, ...]
    play_mode: str
    output_mode: str | None
    volume: int
    muted: bool

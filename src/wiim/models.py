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

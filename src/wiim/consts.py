import logging
from enum import IntFlag, StrEnum, unique

SDK_LOGGER = logging.getLogger("wiim.sdk")

API_ENDPOINT: str = "{}/httpapi.asp?command={}"
API_TIMEOUT: int = 10
UNKNOWN_TRACK_PLAYING: str = "Unknown"

UPNP_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"

UPNP_AV_TRANSPORT_SERVICE_ID = "urn:schemas-upnp-org:service:AVTransport:1"
UPNP_RENDERING_CONTROL_SERVICE_ID = "urn:schemas-upnp-org:service:RenderingControl:1"
UPNP_WIIM_PLAY_QUEUE_SERVICE_ID = "urn:schemas-wiimu-com:service:PlayQueue:1"
UPNP_TIMEOUT_TIME = 1800
AUDIO_AUX_MODE_IDS = ("FF98F359", "FF98FC04")


class WiimHttpCommand(StrEnum):
    """Defines the WiiM HTTP API commands."""

    DEVICE_STATUS = "getStatusEx"
    POSITION_INFO = "GetPositionInfo"
    MEDIA_INFO = "GetInfoEx"
    REBOOT = "StartRebootTime:1"
    PLAYER_STATUS = "getPlayerStatusEx"
    SWITCH_MODE = "setPlayerCmd:switchmode:{}"
    MULTIROOM_LIST = "multiroom:getSlaveList"
    MULTIROOM_UNGROUP = "multiroom:Ungroup"
    MULTIROOM_LEAVEGROUP = "multiroom:LeaveGroup"
    MULTIROOM_KICK = "multiroom:SlaveKickout:{}"
    MULTIROOM_JOIN = "multiroom:JoinGroup:IP={}:uuid={}"
    PLAY_PRESET = "MCUKeyShortClick:{}"
    TIMESYNC = "timeSync:{}"
    AUDIO_OUTPUT_HW_MODE_SET = "setAudioOutputHardwareMode:{}"
    AUDIO_OUTPUT_HW_MODE = "getNewAudioOutputHardwareMode"

class SpeakerType(StrEnum):
    MAIN_SPEAKER = "0"
    SUB_SPEAKER = "1"
    
class ChannelType(StrEnum):
    STEREO = "0"
    LEFT_CHANNEL = "1"
    RIGHT_CHANNEL = "2"

class EqualizerMode(StrEnum):
    NONE = "None"
    CLASSIC = "Classic"
    POP = "Pop"
    JAZZ = "Jazz"
    VOCAL = "Vocal"
    FLAT = "Flat"
    ACOUSTIC = "Acoustic"
    BASS_BOOSTER = "Bass Booster"
    BASS_REDUCER = "Bass Reducer"
    CLASSICAL = "Classical"
    DANCE = "Dance"
    DEEP = "Deep"
    ELECTRONIC = "Electronic"
    HIP_HOP = "Hip-Hop"
    LATIN = "Latin"
    LOUDNESS = "Loudness"
    LOUNGE = "Lounge"
    PIANO = "Piano"
    R_B = "R&B"
    ROCK = "Rock"
    SMALL_SPEAKERS = "Small Speakers"
    SPOKEN_WORD = "Spoken Word"
    TREBLE_BOOSTER = "Treble Booster"
    TREBLE_REDUCER = "Treble Reducer"
    VOCAL_BOOSTER = "Vocal Booster"


class LoopMode(IntFlag):
    NONE_MODE_ERROR = -1
    SHUFFLE_DISABLE_REPEAT_ALL = 0
    SHUFFLE_DISABLE_REPEAT_ONE = 1
    SHUFFLE_ENABLE_REPEAT_ALL = 2
    SHUFFLE_ENABLE_REPEAT_NONE = 3
    SHUFFLE_DISABLE_REPEAT_NONE = 4
    SHUFFLE_ENABLE_REPEAT_ONE = 5


class PlayingStatus(StrEnum):
    PLAYING = "PLAYING"
    LOADING = "TRANSITIONING"
    STOPPED = "STOPPED"
    PAUSED = "PAUSED_PLAYBACK"
    UNKNOWN = "NO_MEDIA_PRESENT"


class PlayerStatus(StrEnum):
    PLAYING = "play"
    LOADING = "load"
    STOPPED = "stop"
    PAUSED = "pause"


_PLAYER_TO_PLAYING: dict[PlayerStatus, PlayingStatus] = {
    PlayerStatus.PLAYING: PlayingStatus.PLAYING,
    PlayerStatus.LOADING: PlayingStatus.LOADING,
    PlayerStatus.STOPPED: PlayingStatus.STOPPED,
    PlayerStatus.PAUSED: PlayingStatus.PAUSED,
}


class MuteMode(StrEnum):
    UNMUTED = "0"
    MUTED = "1"


# Player attributes from getPlayerStatusEx JSON response
class PlayerAttribute(StrEnum):
    SPEAKER_TYPE = "type"
    CHANNEL_TYPE = "ch"
    PLAYBACK_MODE = "mode"
    PLAYLIST_MODE = "loop"
    EQUALIZER_MODE = "eq"
    PLAYING_STATUS = "status"
    CURRENT_POSITION = "curpos"
    OFFSET_POSITION = "offset_pts"
    TOTAL_LENGTH = "totlen"
    TITLE = "Title"
    ARTIST = "Artist"
    ALBUM = "Album"
    VOLUME = "vol"
    MUTED = "mute"


# Device attributes from getStatusEx JSON response
class DeviceAttribute(StrEnum):
    UUID = "uuid"
    DEVICE_NAME = "DeviceName"
    SSID = "ssid"
    LANGUAGE = "language"
    FIRMWARE = "firmware"
    HARDWARE = "hardware"
    BUILD = "build"
    PROJECT = "project"
    RELEASE = "Release"
    INTERNET = "internet"
    MAC_ADDRESS = "MAC"
    STA_MAC_ADDRESS = "STA_MAC"
    NET_STAT = "netstat"
    APCLI0 = "apcli0"
    ETH0 = "eth0"
    NEW_VER = "NewVer"
    MCU_VER = "mcu_ver"
    UPNP_VERSION = "upnp_version"
    PLAYMODE_SUPPORT = "plm_support"
    PRESET_KEY = "preset_key"
    SPOTIFY_ACTIVE = "spotify_active"
    RSSI = "RSSI"
    BATTERY = "battery"
    BATTERY_PERCENT = "battery_percent"
    UPNP_UUID = "upnp_uuid"
    ETH_MAC_ADDRESS = "ETH_MAC"
    BT_MAC = "BT_MAC"
    EQ_SUPPORT = "EQ_support"


# Multiroom attributes from multiroom:getSlaveList JSON response
class MultiroomAttribute(StrEnum):
    NUM_FOLLOWERS = "slaves"
    FOLLOWER_LIST = "slave_list"
    UUID = "uuid"
    IP = "ip"


class MetaInfo(StrEnum):
    METADATA = "metaData"


class MetaInfoMetaData(StrEnum):
    ALBUM_TITLE = "album"
    TRACK_TITLE = "title"
    TRACK_SUBTITLE = "subtitle"
    ALBUM_ART = "albumArtURI"
    SAMPLE_RATE = "sampleRate"
    BIT_DEPTH = "bitDepth"
    BIT_RATE = "bitRate"
    TRACK_ID = "trackId"


MANUFACTURER_WIIM = "Linkplay"


@unique
class AudioOutputHwMode(IntFlag):
    OPTICAL = (1, "Optical Out", 1, "AUDIO_OUTPUT_SPDIF_MODE")
    LINE_OUT = (2, "Line Out", 2, "AUDIO_OUTPUT_AUX_MODE")
    COAXIAL = (4, "COAX Out", 3, "AUDIO_OUTPUT_COAX_MODE")
    HEADPHONES = (8, "Headphone Out", 4, "AUDIO_OUTPUT_PHONE_JACK_MODE")
    SPEAKER_OUT = (16, "Speaker Out", 7, "AUDIO_OUTPUT_SPEAKER_MODE")
    OTHER_OUT = (64, "Other Out", 64, "AUDIO_OTHER_OUT_MODE")

    def __new__(cls, value: int, display_name: str, cmd: int, command_str: str):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.display_name = display_name  # type: ignore[attr-defined]
        obj.cmd = cmd  # type: ignore[attr-defined]
        obj.command_str = command_str  # type: ignore[attr-defined]
        return obj

    def __str__(self):
        return self.display_name


CMD_TO_MODE_MAP: dict[int, AudioOutputHwMode] = {
    member.cmd: member for member in AudioOutputHwMode  # type: ignore[attr-defined]
}


@unique
class InputMode(IntFlag):
    WIFI = (1, "Network", "wifi")
    BLUETOOTH = (2, "Bluetooth", "bluetooth")
    LINE_IN = (4, "Line In", "line-in")
    OPTICAL = (8, "Optical In", "optical")
    HDMI = (16, "TV", "HDMI")
    PHONO = (32, "Phono In", "phono")

    def __new__(cls, value: int, display_name: str, command_name: str):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.display_name = display_name  # type: ignore[attr-defined]
        obj.command_name = command_name  # type: ignore[attr-defined]
        return obj

    def __str__(self):
        return self.display_name


class PlayingMode(StrEnum):
    NETWORK = "10"
    BLUETOOTH = "41"
    LINE_IN = "40"
    OPTICAL = "43"
    HDMI = "49"
    PHONO = "54"


PLAYING_TO_INPUT_MAP: dict[PlayingMode, InputMode] = {
    # PlayingMode.NETWORK: InputMode.WIFI,
    PlayingMode.BLUETOOTH: InputMode.BLUETOOTH,
    PlayingMode.LINE_IN: InputMode.LINE_IN,
    PlayingMode.OPTICAL: InputMode.OPTICAL,
    PlayingMode.HDMI: InputMode.HDMI,
    PlayingMode.PHONO: InputMode.PHONO,
}

SUPPORTED_INPUT_MODES_BY_MODEL = {
    "WiiM Pro": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL,
    "WiiM Pro Plus": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL,
    "WiiM Ultra": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL
    | InputMode.HDMI
    | InputMode.PHONO,
    "WiiM Amp": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL
    | InputMode.HDMI,
    "WiiM Amp Pro": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL
    | InputMode.HDMI,
    "WiiM Amp Ultra": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL
    | InputMode.HDMI,
    "WiiM CI MOD A80": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL
    | InputMode.HDMI,
    "WiiM CI MOD S": InputMode.WIFI
    | InputMode.BLUETOOTH
    | InputMode.LINE_IN
    | InputMode.OPTICAL,
}

SUPPORTED_OUTPUT_MODES_BY_MODEL = {
    "WiiM Pro": AudioOutputHwMode.LINE_OUT
    | AudioOutputHwMode.OPTICAL
    | AudioOutputHwMode.COAXIAL
    | AudioOutputHwMode.OTHER_OUT,
    "WiiM Pro Plus": AudioOutputHwMode.LINE_OUT
    | AudioOutputHwMode.OPTICAL
    | AudioOutputHwMode.COAXIAL
    | AudioOutputHwMode.OTHER_OUT,
    "WiiM Ultra": AudioOutputHwMode.LINE_OUT
    | AudioOutputHwMode.OPTICAL
    | AudioOutputHwMode.COAXIAL
    | AudioOutputHwMode.HEADPHONES
    | AudioOutputHwMode.OTHER_OUT,
    "WiiM Amp": AudioOutputHwMode.SPEAKER_OUT | AudioOutputHwMode.OTHER_OUT,
    "WiiM Amp Pro": AudioOutputHwMode.SPEAKER_OUT | AudioOutputHwMode.OTHER_OUT,
    "WiiM Amp Ultra": AudioOutputHwMode.SPEAKER_OUT | AudioOutputHwMode.OTHER_OUT,
    "WiiM CI MOD A80": AudioOutputHwMode.SPEAKER_OUT | AudioOutputHwMode.OTHER_OUT,
    "WiiM CI MOD S": AudioOutputHwMode.LINE_OUT
    | AudioOutputHwMode.OPTICAL
    | AudioOutputHwMode.COAXIAL
    | AudioOutputHwMode.OTHER_OUT,
}

wiimDeviceType = {
    "FF970016": "WiiM Mini",
    "FF98F09C": "WiiM Pro",
    "FF98F3C7": "WiiM Pro",  # no mfi
    "FF98FCDE": "WiiM Pro Plus",
    "FF98F0BC": "WiiM Pro Plus",  # no mfi
    "FF98F359": "WiiM Amp",
    "FF98FC04": "WiiM Amp",  # no mfi
    "FF98F2F7": "WiiM Amp",  # 4layer
    "FF49BC43": "WiiM Amp",  # castlite
    "FF98FC37": "WiiM Amp Pro",
    "FF98F9ED": "WiiM Amp Ultra",
    "FF98F56B": "WiiM CI MODE A80",
    "FF98FB4F": "WiiM CI MODE S",
    # "FF98F824": "Sub Pro",
    "FF98F7F4": "WiiM Ultra",
}

PlayMediumToInputMode = {
    "BLUETOOTH": 2,
    "LINE-IN": 4,
    "OPTICAL": 8,
    "HDMI": 16,
    "PHONO": 32,
}

VALID_PLAY_MEDIUMS = {
    "SONGLIST-LOCAL",
    "SONGLIST-LOCAL_TF",
    "SONGLIST-NETWORK",
    "QPLAY",
    "TIDAL_CONNECT",
    "Samba",
}

PLAY_MEDIUMS_CTRL = {
    "RADIO-NETWORK",
    "THIRD-DLNA",
    "LINE-IN",
    "OPTICAL",
    "HDMI",
    "PHONO",
}

TRACK_SOURCES_CTRL = {
    "Pandora2",
    "SoundMachine",
    "Soundtrack",
    "iHeartRadio",
}

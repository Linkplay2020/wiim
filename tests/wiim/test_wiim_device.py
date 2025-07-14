# test_wiim_device.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from wiim.wiim_device import WiimDevice
from wiim.endpoint import WiimApiEndpoint
from wiim.consts import (
    DeviceAttribute,
    PlayerAttribute,
    PlayingStatus,
    MuteMode,
    WiimHttpCommand,
    InputMode,
)


@patch("wiim.wiim_device.AiohttpNotifyServer", MagicMock())
@patch("wiim.wiim_device.UpnpEventHandler", MagicMock())
class TestWiimDevice:
    """Tests for the WiimDevice class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_upnp_device, mock_session):
        """Test that the device initializes correctly from a UpnpDevice object."""
        device = WiimDevice(mock_upnp_device, mock_session)

        assert device.name == "WiiM Test Device"
        assert device.udn == "uuid:12345678-1234-1234-1234-1234567890ab"
        assert device.model_name == "WiiM Pro"
        assert device.ip_address == "192.168.1.100"
        assert device.playing_status == PlayingStatus.STOPPED

    @pytest.mark.asyncio
    async def test_async_update_http_status_parses_data_correctly(
        self, mock_upnp_device, mock_session
    ):
        """Test that device state is correctly updated from HTTP API responses."""
        device = WiimDevice(mock_upnp_device, mock_session)
        http_api = AsyncMock(spec=WiimApiEndpoint)
        device._http_api = http_api

        # Mock responses from the device's HTTP API
        device_status_response = {
            DeviceAttribute.DEVICE_NAME: "Living Room Speaker",
            DeviceAttribute.FIRMWARE: "1.2.3",
            DeviceAttribute.PROJECT: "WiiM_Pro_with_gc4a",
        }
        player_status_response = {
            PlayerAttribute.VOLUME: "50",
            PlayerAttribute.MUTED: "0",
            PlayerAttribute.PLAYING_STATUS: "play",
            PlayerAttribute.TITLE: "Test Song",
            PlayerAttribute.ARTIST: "Test Artist",
            PlayerAttribute.ALBUM: "Test Album",
            PlayerAttribute.PLAYBACK_MODE: "40",  # line-in
        }
        http_api.json_request.side_effect = [
            device_status_response,
            player_status_response,
        ]

        await device.async_update_http_status()

        assert device.name == "Living Room Speaker"
        assert device.firmware_version == "1.2.3"
        assert device.model_name == "WiiM Pro"
        assert device.volume == 50
        assert not device.is_muted
        assert device.playing_status == PlayingStatus.PLAYING
        assert device.play_mode == InputMode.LINE_IN.display_name
        assert device._player_properties[PlayerAttribute.TITLE] == "Test Song"

    @pytest.mark.asyncio
    async def test_upnp_actions_are_called_correctly(
        self, mock_upnp_device, mock_session
    ):
        """Test that high-level methods call the correct underlying UPnP actions."""
        device = WiimDevice(mock_upnp_device, mock_session)

        device.av_transport = mock_upnp_device.service(
            "urn:schemas-upnp-org:service:AVTransport:1"
        )
        device.rendering_control = mock_upnp_device.service(
            "urn:schemas-upnp-org:service:RenderingControl:1"
        )

        # Test Play
        await device.async_play()
        device.av_transport.action("Play").async_call.assert_called_with(
            InstanceID=0, Speed="1"
        )

        # Test Pause
        await device.async_pause()
        device.av_transport.action("Pause").async_call.assert_called_with(InstanceID=0)

        # Test Set Volume
        await device.async_set_volume(75)
        device.rendering_control.action("SetVolume").async_call.assert_called_with(
            InstanceID=0, Channel="Master", DesiredVolume=75
        )

        # Test Mute
        await device.async_set_mute(True)
        device.rendering_control.action("SetMute").async_call.assert_called_with(
            InstanceID=0, Channel="Master", DesiredMute=True
        )

        # Test Seek
        await device.async_seek(125)  # 2 minutes and 5 seconds
        device.av_transport.action("Seek").async_call.assert_called_with(
            InstanceID=0, Unit="REL_TIME", Target="00:02:05"
        )

    @pytest.mark.asyncio
    async def test_http_actions_are_called_correctly(
        self, mock_upnp_device, mock_session
    ):
        """Test that high-level methods call the correct underlying HTTP commands."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device._http_api = AsyncMock(spec=WiimApiEndpoint)
        # Mock the internal helper that makes the actual request
        device._http_command_ok = AsyncMock()

        await device.async_set_play_mode("Line In")
        device._http_command_ok.assert_called_with(
            WiimHttpCommand.SWITCH_MODE, "line-in"
        )

    def test_update_state_from_rendering_control_event_data(
        self, mock_upnp_device, mock_session
    ):
        """Test internal state update from a parsed UPnP RenderingControl event."""
        device = WiimDevice(mock_upnp_device, mock_session)
        event_data = {
            "Volume": [{"val": "67", "channel": "Master"}],
            "Mute": [{"val": "1", "channel": "Master"}],
        }

        device._update_state_from_rendering_control_event_data(event_data)

        assert device.volume == 67
        assert device.is_muted is True
        assert device._player_properties[PlayerAttribute.VOLUME] == "67"
        assert device._player_properties[PlayerAttribute.MUTED] == MuteMode.MUTED

    def test_parse_duration(self, mock_upnp_device, mock_session):
        """Test the parsing of various duration string formats."""
        device = WiimDevice(mock_upnp_device, mock_session)
        assert device._parse_duration("01:23:45") == 5025
        assert device._parse_duration("00:02:30.123") == 150
        assert device._parse_duration(None) == 0
        assert device._parse_duration("NOT_IMPLEMENTED") == 0

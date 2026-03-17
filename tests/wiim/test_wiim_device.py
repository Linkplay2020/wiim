# test_wiim_device.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from wiim.wiim_device import WiimDevice
from wiim.endpoint import WiimApiEndpoint
from wiim.consts import (
    DeviceAttribute,
    LoopMode,
    PlayerAttribute,
    PlayingStatus,
    WiimHttpCommand,
    InputMode,
)
from wiim.models import WiimGroupRole, WiimGroupSnapshot, WiimRepeatMode


def _build_upnp_device(
    *,
    udn: str,
    name: str,
    model_name: str = "WiiM Pro",
    ip_address: str = "192.168.1.100",
):
    """Build a standalone mocked UPnP device for WiimDevice tests."""
    upnp_device = MagicMock()
    upnp_device.udn = udn
    upnp_device.friendly_name = name
    upnp_device.manufacturer = "Linkplay"
    upnp_device.model_name = model_name
    upnp_device.device_url = f"http://{ip_address}:49152/description.xml"

    def _build_service():
        service = MagicMock()
        service.has_action.return_value = True
        actions: dict[str, AsyncMock] = {}

        def action_selector(action_name: str):
            action = actions.get(action_name)
            if action is None:
                action = AsyncMock()
                actions[action_name] = action
            return action

        service.action.side_effect = action_selector
        return service

    services = {
        "urn:schemas-upnp-org:service:AVTransport:1": _build_service(),
        "urn:schemas-upnp-org:service:RenderingControl:1": _build_service(),
        "urn:wiimu-com:service:PlayQueue:1": _build_service(),
    }
    upnp_device.service.side_effect = lambda service_id: services.get(service_id)
    upnp_device.requester = MagicMock()
    return upnp_device


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

    def test_parse_duration(self, mock_upnp_device, mock_session):
        """Test the parsing of various duration string formats."""
        device = WiimDevice(mock_upnp_device, mock_session)
        assert device.parse_duration("01:23:45") == 5025
        assert device.parse_duration("00:02:30.123") == 150
        assert device.parse_duration(None) == 0
        assert device.parse_duration("NOT_IMPLEMENTED") == 0

    def test_supported_modes_from_model(self, mock_upnp_device, mock_session):
        """Test supported input/output modes are derived by the SDK."""
        device = WiimDevice(mock_upnp_device, mock_session)

        assert InputMode.LINE_IN.display_name in device.supported_input_modes  # type: ignore[attr-defined]
        assert "Optical Out" in device.supported_output_modes

    def test_current_media_uses_normalized_metadata(
        self, mock_upnp_device, mock_session
    ):
        """Test current media metadata is exposed through a typed helper."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device.current_track_info = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "uri": "https://example.com/song.mp3",
            "albumArtURI": "https://example.com/art.jpg",
        }
        device.current_track_duration = 210
        device.current_position = 15

        media = device.current_media

        assert media is not None
        assert media.title == "Test Song"
        assert media.artist == "Test Artist"
        assert media.album == "Test Album"
        assert media.uri == "https://example.com/song.mp3"
        assert media.image_url == "https://example.com/art.jpg"
        assert media.duration == 210
        assert media.position == 15
        assert device.album_art_uri == "https://example.com/art.jpg"

    def test_loop_state_helpers(self, mock_upnp_device, mock_session):
        """Test normalized loop mode helpers."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device.loop_mode = LoopMode.SHUFFLE_ENABLE_REPEAT_ONE

        assert device.loop_state.repeat == WiimRepeatMode.ONE
        assert device.loop_state.shuffle is True
        assert (
            WiimDevice.build_loop_mode(WiimRepeatMode.ALL, shuffle=False)
            == LoopMode.SHUFFLE_DISABLE_REPEAT_ALL
        )

    @pytest.mark.asyncio
    async def test_async_get_transport_capabilities(
        self, mock_upnp_device, mock_session
    ):
        """Test MEDIA_INFO is normalized into SDK transport capabilities."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device._http_api = AsyncMock(spec=WiimApiEndpoint)
        device.async_set_AVT_cmd = AsyncMock(
            return_value={
                "PlayMedium": "SONGLIST-NETWORK",
                "TrackSource": "Pandora2",
            }
        )

        capabilities = await device.async_get_transport_capabilities()

        assert capabilities.can_next is True
        assert capabilities.can_previous is False
        assert capabilities.can_repeat is True
        assert capabilities.can_shuffle is True
        assert capabilities.track_source == "Pandora2"

    @pytest.mark.asyncio
    async def test_async_get_presets(self, mock_upnp_device, mock_session):
        """Test presets are normalized for browse consumers."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device.async_get_favorites = AsyncMock(
            return_value=[
                {"uri": "1", "name": "Preset Name_#~meta", "image_url": "art.jpg"},
                {"uri": "x", "name": "Ignored"},
            ]
        )

        presets = await device.async_get_presets()

        assert len(presets) == 1
        assert presets[0].preset_id == 1
        assert presets[0].title == "Preset Name"
        assert presets[0].image_url == "art.jpg"

    @pytest.mark.asyncio
    async def test_async_get_queue_snapshot(self, mock_upnp_device, mock_session):
        """Test queue browse data is normalized for browse consumers."""
        device = WiimDevice(mock_upnp_device, mock_session)
        device.async_get_queue_items = AsyncMock(
            return_value=[
                {"SourceName": "Pandora2 Station"},
                {"uri": "1", "name": "Track One", "image_url": "art1.jpg"},
                {"uri": "2", "name": "Track Two"},
            ]
        )
        device.async_set_AVT_cmd = AsyncMock(
            return_value={
                "PlayMedium": "SONGLIST-NETWORK",
                "TrackSource": "Pandora2",
            }
        )

        snapshot = await device.async_get_queue_snapshot()

        assert snapshot.is_active is True
        assert snapshot.source_name == "Pandora2 Station"
        assert len(snapshot.items) == 2
        assert snapshot.items[0].queue_index == 1
        assert snapshot.items[0].title == "Track One"

    @pytest.mark.asyncio
    async def test_follower_reads_grouped_state_from_leader(self, mock_session):
        """Test grouped follower reads transparently resolve through the leader."""
        leader = WiimDevice(
            _build_upnp_device(
                udn="uuid:leader-1234",
                name="Leader WiiM Device",
                model_name="WiiM Pro",
                ip_address="192.168.1.101",
            ),
            mock_session,
        )
        follower = WiimDevice(
            _build_upnp_device(
                udn="uuid:follower-5678",
                name="Follower WiiM Device",
                model_name="Unknown Follower",
                ip_address="192.168.1.102",
            ),
            mock_session,
        )
        controller = MagicMock()
        controller.get_group_snapshot.side_effect = lambda udn: (
            WiimGroupSnapshot(
                role=WiimGroupRole.FOLLOWER,
                leader_udn=leader.udn,
                member_udns=(leader.udn, follower.udn),
            )
            if udn == follower.udn
            else WiimGroupSnapshot(
                role=WiimGroupRole.STANDALONE,
                leader_udn=leader.udn,
                member_udns=(leader.udn,),
            )
        )
        controller.get_device.side_effect = lambda udn: (
            leader if udn == leader.udn else follower
        )
        leader.attach_controller(controller)
        follower.attach_controller(controller)

        leader.playing_status = PlayingStatus.PLAYING
        leader.play_mode = "Spotify"
        leader.output_mode = "speaker"
        leader.loop_mode = LoopMode.SHUFFLE_ENABLE_REPEAT_ONE
        leader.current_track_info = {
            "title": "Leader Song",
            "artist": "Leader Artist",
            "album": "Leader Album",
            "uri": "https://example.com/leader.mp3",
        }
        leader.current_track_duration = 215
        leader.current_position = 42
        leader._supported_model_name = MagicMock(return_value="WiiM Pro")
        follower._supported_model_name = MagicMock(return_value=None)
        leader._http_api = AsyncMock(spec=WiimApiEndpoint)
        follower._http_api = None
        leader.async_set_AVT_cmd = AsyncMock(
            return_value={
                "PlayMedium": "SONGLIST-NETWORK",
                "TrackSource": "Pandora2",
            }
        )
        follower.async_set_AVT_cmd = AsyncMock()

        assert follower.playing_status == PlayingStatus.PLAYING
        assert follower.play_mode == "Spotify"
        assert follower.output_mode == "speaker"
        assert follower.loop_state.repeat == WiimRepeatMode.ONE
        assert follower.loop_state.shuffle is True
        assert follower.current_media is not None
        assert follower.current_media.title == "Leader Song"
        assert follower.current_media.album == "Leader Album"
        assert follower.current_media.duration == 215
        assert follower.current_media.position == 42
        assert follower.supported_input_modes == leader.supported_input_modes
        assert follower.supports_http_api is True

        capabilities = await follower.async_get_transport_capabilities()

        assert capabilities.can_previous is False
        assert capabilities.can_repeat is True
        follower.async_set_AVT_cmd.assert_not_called()
        leader.async_set_AVT_cmd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_follower_forwards_commands_except_volume_and_mute(
        self, mock_session
    ):
        """Test grouped commands route to the leader except volume and mute."""
        leader = WiimDevice(
            _build_upnp_device(
                udn="uuid:leader-1234",
                name="Leader WiiM Device",
                ip_address="192.168.1.101",
            ),
            mock_session,
        )
        follower = WiimDevice(
            _build_upnp_device(
                udn="uuid:follower-5678",
                name="Follower WiiM Device",
                ip_address="192.168.1.102",
            ),
            mock_session,
        )
        controller = MagicMock()
        controller.get_group_snapshot.side_effect = lambda udn: (
            WiimGroupSnapshot(
                role=WiimGroupRole.FOLLOWER,
                leader_udn=leader.udn,
                member_udns=(leader.udn, follower.udn),
            )
            if udn == follower.udn
            else WiimGroupSnapshot(
                role=WiimGroupRole.STANDALONE,
                leader_udn=leader.udn,
                member_udns=(leader.udn,),
            )
        )
        controller.get_device.side_effect = lambda udn: (
            leader if udn == leader.udn else follower
        )
        leader.attach_controller(controller)
        follower.attach_controller(controller)

        follower.async_play = AsyncMock(wraps=follower.async_play)
        leader.async_play = AsyncMock(wraps=leader.async_play)
        follower.async_seek = AsyncMock(wraps=follower.async_seek)
        leader.async_seek = AsyncMock(wraps=leader.async_seek)
        follower.async_set_play_mode = AsyncMock(wraps=follower.async_set_play_mode)
        leader.async_set_play_mode = AsyncMock(wraps=leader.async_set_play_mode)
        follower.async_set_loop_mode = AsyncMock(wraps=follower.async_set_loop_mode)
        leader.async_set_loop_mode = AsyncMock(wraps=leader.async_set_loop_mode)
        follower.async_set_volume = AsyncMock(wraps=follower.async_set_volume)
        leader.async_set_volume = AsyncMock(wraps=leader.async_set_volume)
        follower.async_set_mute = AsyncMock(wraps=follower.async_set_mute)
        leader.async_set_mute = AsyncMock(wraps=leader.async_set_mute)
        repeat_all_shuffle = follower.build_loop_mode(WiimRepeatMode.ALL, True)

        await follower.async_play()
        await follower.async_seek(90)
        await follower.async_set_play_mode("Line In")
        await follower.async_set_loop_mode(repeat_all_shuffle)
        await follower.async_set_volume(35)
        await follower.async_set_mute(True)

        follower.async_play.assert_awaited_once()
        leader.async_play.assert_awaited_once()
        follower.async_seek.assert_awaited_once_with(90)
        leader.async_seek.assert_awaited_once_with(90)
        follower.async_set_play_mode.assert_awaited_once_with("Line In")
        leader.async_set_play_mode.assert_awaited_once_with("Line In")
        follower.async_set_loop_mode.assert_awaited_once_with(repeat_all_shuffle)
        leader.async_set_loop_mode.assert_awaited_once_with(repeat_all_shuffle)
        follower.async_set_volume.assert_awaited_once_with(35)
        follower.async_set_mute.assert_awaited_once_with(True)
        leader.async_set_volume.assert_not_awaited()
        leader.async_set_mute.assert_not_awaited()

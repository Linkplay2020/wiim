"""Tests for device-reported input and output capabilities."""

import json
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote
from xml.sax.saxutils import quoteattr

import pytest

from wiim.consts import WiimHttpCommand
from wiim.controller import WiimController
from wiim.endpoint import WiimApiEndpoint
from wiim.exceptions import (
    WiimDeviceException,
    WiimInvalidDataException,
    WiimRequestException,
)
from wiim.wiim_device import WiimDevice


@pytest.fixture
def audio_api():
    api = AsyncMock(spec=WiimApiEndpoint)
    api.json_request.return_value = {"audioInput": [{"mode": "wifi"}, {"mode": "usb"}]}
    api.json_list_request.return_value = [
        {
            "index": 8,
            "mode": "AUDIO_OUTPUT_USB_MODE",
            "soundCard": {
                "cardId": "hw:1,0",
                "devName": "USB & DAC #1",
            },
        },
    ]
    return api


@pytest.fixture
def audio_device(mock_upnp_device, mock_session, audio_api):
    mock_upnp_device.model_name = "New WiiM Model"
    return WiimDevice(mock_upnp_device, mock_session, http_api_endpoint=audio_api)


@pytest.mark.asyncio
async def test_dynamic_capabilities_and_commands(audio_device, audio_api):
    device = audio_device
    await device.async_refresh_audio_capabilities()
    assert device.supported_input_modes == ("Network", "usb")
    assert device.supported_output_modes == ("USB & DAC #1", "Other Out")

    await device.async_set_play_mode("usb")
    audio_api.request.assert_awaited_with("setPlayerCmd:switchmode:usb")
    await device.async_set_output_mode("USB & DAC #1")
    command = audio_api.request.call_args.args[0]
    assert "&" not in command and "#" not in command
    payload = json.loads(unquote(command.split(":", 1)[1]))
    assert payload == {
        "index": 8,
        "mode": "AUDIO_OUTPUT_USB_MODE",
        "cardId": "hw:1,0",
        "devName": "USB & DAC #1",
        "devNameHex": b"USB & DAC #1".hex(),
    }
    audio_api.json_request.return_value = {
        "index": "8",
        "mode": "AUDIO_OUTPUT_USB_MODE",
        "cardId": "hw:1,0",
        "devName": "USB & DAC #1",
        "btSource": "0",
        "audioCast": "0",
    }
    assert await device.get_audio_output_hw_mode() == "USB & DAC #1"
    audio_api.json_request.assert_awaited_with(WiimHttpCommand.SOUND_CARD_ACTIVE_MODE)


@pytest.mark.parametrize("mode", ["udisk", "UDISK", "USB-in", "usb-in"])
@pytest.mark.asyncio
async def test_excluded_input_is_hidden(audio_device, audio_api, mode):
    device = audio_device
    audio_api.json_request.return_value = {
        "audioInput": [{"mode": "wifi"}, {"mode": mode}]
    }
    await device.async_refresh_audio_capabilities()
    assert device.supported_input_modes == ("Network",)
    with pytest.raises(WiimDeviceException):
        await device.async_set_play_mode(mode)
    audio_api.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_aux_input_display_name_preserves_command(audio_device, audio_api):
    audio_api.json_request.return_value = {"audioInput": [{"mode": "auxIn"}]}
    await audio_device.async_refresh_audio_capabilities()
    assert audio_device.supported_input_modes == ("Aux In",)
    await audio_device.async_set_play_mode("Aux In")
    audio_api.request.assert_awaited_once_with("setPlayerCmd:switchmode:auxIn")


@pytest.mark.asyncio
async def test_aux_input_state_from_device(audio_device, audio_api):
    device = audio_device
    device._update_state_from_av_transport_event_data(
        {"PlaybackStorageMedium": "AUXIN"}
    )
    assert device.play_mode == "Aux In"
    await device.async_set_play_mode("Network")
    audio_api.json_request.return_value = {"mode": "60"}
    await device.async_update_http_status()
    assert device.play_mode == "Aux In"
    await device.async_set_play_mode("Network")
    device.async_set_AVT_cmd = AsyncMock(
        return_value={"PlayMedium": "AUXIN", "PlayType": "60"}
    )
    capabilities = await device.async_get_transport_capabilities()
    assert not capabilities.can_next
    assert not capabilities.can_previous


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("invalid", [False, True])
@pytest.mark.asyncio
async def test_capability_failure_preserves_defaults_or_cache(
    audio_device, audio_api, cached, invalid
):
    device = audio_device
    device.upnp_device.model_name = "WiiM Pro"
    if cached:
        await device.async_refresh_audio_capabilities()
    expected = (device.supported_input_modes, device.supported_output_modes)
    assert all(expected)
    if invalid:
        audio_api.json_request.return_value = {"audioInput": [{"mode": None}]}
        audio_api.json_list_request.return_value = [{"soundCard": {}}]
    else:
        audio_api.json_request.side_effect = WiimRequestException("unsupported")
        audio_api.json_list_request.side_effect = WiimInvalidDataException("Failed")
    await device.async_refresh_audio_capabilities()
    assert (device.supported_input_modes, device.supported_output_modes) == expected
    if not cached:
        await device.async_set_output_mode("Optical Out")
        audio_api.request.assert_awaited_with("setAudioOutputHardwareMode:1")


@pytest.mark.asyncio
async def test_duplicate_output_names_are_selectable(audio_device, audio_api):
    api = audio_api
    api.json_list_request.return_value.append(
        {
            "index": 9,
            "mode": "AUDIO_OUTPUT_USB_MODE",
            "soundCard": {
                "cardId": "hw:2,0",
                "devName": "USB & DAC #1",
            },
        }
    )
    await audio_device.async_refresh_audio_capabilities()
    label = "USB & DAC #1 (hw:2,0)"
    assert audio_device.supported_output_modes == ("USB & DAC #1", label, "Other Out")
    await audio_device.async_set_output_mode(label)
    payload = json.loads(unquote(api.request.call_args.args[0].split(":", 1)[1]))
    assert payload["cardId"] == "hw:2,0"
    assert payload["devName"] == "USB & DAC #1"
    api.json_request.return_value = {
        "mode": "AUDIO_OUTPUT_USB_MODE",
        "cardId": "hw:2,0",
    }
    assert await audio_device.get_audio_output_hw_mode() == label
    api.json_request.return_value = {"mode": "AUDIO_OUTPUT_USB_MODE"}
    assert await audio_device.get_audio_output_hw_mode() == "Other Out"


@pytest.mark.asyncio
async def test_empty_capabilities_and_invalid_selection(audio_device, audio_api):
    audio_api.json_request.return_value = {"audioInput": []}
    audio_api.json_list_request.return_value = []
    await audio_device.async_refresh_audio_capabilities()
    assert audio_device.supported_input_modes == ()
    assert audio_device.supported_output_modes == ("Other Out",)
    with pytest.raises(WiimDeviceException, match="Unsupported input"):
        await audio_device.async_set_play_mode("Network")
    with pytest.raises(WiimDeviceException, match="Unsupported output"):
        await audio_device.async_set_output_mode("Line Out")
    audio_api.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_output_command_keeps_state(audio_device, audio_api):
    await audio_device.async_refresh_audio_capabilities()
    audio_api.json_request.return_value = {"mode": "UNLISTED_MODE"}
    assert await audio_device.get_audio_output_hw_mode() == "Other Out"
    previous = audio_device.output_mode
    audio_api.request.side_effect = WiimRequestException("offline")
    with pytest.raises(WiimRequestException):
        await audio_device.async_set_output_mode("USB & DAC #1")
    assert audio_device.output_mode == previous


@pytest.mark.asyncio
async def test_group_follower_uses_leader_capabilities(
    audio_device, audio_api, mock_session
):
    leader = audio_device
    await leader.async_refresh_audio_capabilities()
    follower_upnp_device = MagicMock()
    follower_upnp_device.udn = "uuid:follower"
    follower_upnp_device.friendly_name = "Follower"
    follower = WiimDevice(follower_upnp_device, mock_session)
    controller = WiimController(mock_session)
    audio_api.json_request.return_value = {"slaves": 0}
    await controller.add_device(leader)
    await controller.add_device(follower)
    controller.add_group_member(leader.udn, follower.udn)
    assert follower.supported_input_modes == leader.supported_input_modes
    assert follower.supported_output_modes == leader.supported_output_modes
    await follower.async_set_output_mode("USB & DAC #1")
    assert audio_api.request.await_count == 1
    assert follower.output_mode == "USB & DAC #1"


@pytest.mark.asyncio
async def test_new_output_current_query_falls_back_to_legacy(audio_device, audio_api):
    await audio_device.async_refresh_audio_capabilities()
    audio_api.json_request.side_effect = [
        WiimInvalidDataException("Unsupported command"),
        {"hardware": "1", "source": "0"},
    ]
    assert await audio_device.get_audio_output_hw_mode() == "Other Out"


@pytest.mark.asyncio
async def test_unknown_output_uses_other_out(audio_device, audio_api):
    device = audio_device
    await device.async_refresh_audio_capabilities()
    audio_api.json_request.return_value = {"mode": "AUDIO_OUTPUT_USB_MODE"}
    assert await device.get_audio_output_hw_mode() == "USB & DAC #1"
    audio_api.json_request.return_value = {"mode": "UNLISTED_MODE"}
    assert await device.get_audio_output_hw_mode() == "Other Out"
    audio_api.json_request.assert_awaited_with(WiimHttpCommand.SOUND_CARD_ACTIVE_MODE)
    with pytest.raises(WiimDeviceException):
        await device.async_set_output_mode("Other Out")
    audio_api.request.assert_not_awaited()

    for mode, name, expected in (
        ("AUDIO_OUTPUT_USB_MODE", "USB & DAC #1", "USB & DAC #1"),
        ("AUDIO_OUTPUT_USB_MODE", "Unlisted DAC", "Other Out"),
        ("UNLISTED_MODE", "Other device", "Other Out"),
    ):
        event = json.dumps(
            {"category": "hardware", "body": {"output_mode": mode, "dev_name": name}}
        )
        variable = MagicMock()
        variable.name = "LastChange"
        variable.value = f'<Event><InstanceID val="0"><commonevent val={quoteattr(event)}/></InstanceID></Event>'
        device._internal_handle_rendering_control_event(MagicMock(), [variable])
        assert device.output_mode == expected


@pytest.mark.parametrize("bt_source,audio_cast", [(0, 0), (1, 0), (0, 1), (1, 1)])
@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.asyncio
async def test_output_source_flags_override_hardware(
    audio_device, audio_api, bt_source, audio_cast, as_string
):
    device = audio_device
    await device.async_refresh_audio_capabilities()
    output = {
        "mode": "AUDIO_OUTPUT_USB_MODE",
        "devName": "USB & DAC #1",
        "btSource": str(bt_source) if as_string else bt_source,
        "audioCast": str(audio_cast) if as_string else audio_cast,
    }
    audio_api.json_request.return_value = output
    expected = "Other Out" if bt_source or audio_cast else "USB & DAC #1"
    assert await device.get_audio_output_hw_mode() == expected
    assert device.output_mode == expected
    audio_api.json_request.assert_awaited_with(WiimHttpCommand.SOUND_CARD_ACTIVE_MODE)


@pytest.mark.parametrize(
    "category,event_type,expected",
    [
        ("bluetooth", "a2dp_source", "Other Out"),
        ("bluetooth", "a2dp_sink", "USB & DAC #1"),
        ("audiocast", "dlna", "Other Out"),
    ],
)
@pytest.mark.parametrize("connected", [1, "1"])
@pytest.mark.asyncio
async def test_wireless_event_preserves_output_direction_before_callback(
    audio_device, audio_api, category, event_type, expected, connected
):
    device = audio_device
    await device.async_refresh_audio_capabilities()
    audio_api.json_request.return_value = {"mode": "AUDIO_OUTPUT_USB_MODE"}
    assert await device.get_audio_output_hw_mode() == "USB & DAC #1"
    audio_api.json_request.reset_mock()
    observed = []
    device.rendering_control_event_callback = lambda *_: observed.append(
        device.output_mode
    )
    event = json.dumps(
        {"category": category, "body": {"type": event_type, "connected": connected}}
    )
    variable = MagicMock()
    variable.name = "LastChange"
    variable.value = f'<Event><InstanceID val="0"><commonevent val={quoteattr(event)}/></InstanceID></Event>'
    device._internal_handle_rendering_control_event(MagicMock(), [variable])
    assert device.output_mode == expected
    assert observed == [expected]
    audio_api.json_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_endpoint_array_response(mock_session):
    api = WiimApiEndpoint(
        protocol="https", port=443, endpoint="192.168.1.2", session=mock_session
    )
    response = mock_session.get.return_value.__aenter__.return_value
    response.json.return_value = [{"mode": "AUDIO_OUTPUT_USB_MODE"}]
    assert (
        await api.json_list_request(WiimHttpCommand.SOUND_CARD_SUPPORT_LIST)
        == response.json.return_value
    )
    with pytest.raises(WiimInvalidDataException, match="object"):
        await api.json_request(WiimHttpCommand.SOUND_CARD_SUPPORT_LIST)
    response.json.return_value = {"status": "Failed"}
    with pytest.raises(WiimInvalidDataException, match="array"):
        await api.json_list_request(WiimHttpCommand.SOUND_CARD_SUPPORT_LIST)

"""Tests for device-local GEQ V2 presets."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote, unquote
from xml.sax.saxutils import quoteattr

import pytest

from wiim.consts import GEQ_PLUGIN_URI, WiimHttpCommand
from wiim.endpoint import WiimApiEndpoint
from wiim.exceptions import (
    WiimDeviceException,
    WiimInvalidDataException,
    WiimRequestException,
)
from wiim.models import WiimGroupRole, WiimGroupSnapshot
from wiim.wiim_device import WiimDevice


@pytest.fixture
def geq_api():
    api = AsyncMock(spec=WiimApiEndpoint)

    async def request(command):
        if command.startswith("EQv2GetNewList:"):
            return {
                "preset": [{"Name": "Flat"}, {"Name": "Deep"}],
                "custom": [{"Name": "My & EQ #1"}, {"Name": "Flat"}],
            }
        return {
            "status": "OK",
            "EQStat": "On",
            "source_name": "bluetooth",
            "Name": "Flat",
        }

    api.json_request.side_effect = request
    return api


@pytest.fixture
def geq_device(mock_upnp_device, mock_session, geq_api):
    return WiimDevice(mock_upnp_device, mock_session, http_api_endpoint=geq_api)


@pytest.mark.asyncio
async def test_geq_list_and_current(geq_device, geq_api):
    await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ("Flat", "Deep", "My & EQ #1")
    assert geq_device.equalizer_mode == "Flat"
    command = geq_api.json_request.await_args_list[0].args[0]
    assert json.loads(unquote(command.split(":", 1)[1])) == {
        "pluginURI": GEQ_PLUGIN_URI
    }
    assert geq_api.json_request.await_count == 2
    assert geq_api.json_request.await_args_list[1].args[0] == (
        WiimHttpCommand.EQUALIZER_STATE.format(quote(GEQ_PLUGIN_URI, safe=""))
    )


@pytest.mark.asyncio
async def test_geq_load_uses_local_device_without_querying(geq_device, geq_api):
    await geq_device.async_refresh_equalizer()
    leader = MagicMock()
    controller = MagicMock()
    controller.get_group_snapshot.return_value = WiimGroupSnapshot(
        role=WiimGroupRole.FOLLOWER,
        leader_udn="uuid:leader",
        member_udns=("uuid:leader", geq_device.udn),
    )
    controller.get_device.return_value = leader
    geq_device.attach_controller(controller)
    geq_api.reset_mock()
    geq_api.json_request.side_effect = None
    geq_api.json_request.return_value = {"status": "OK"}
    await geq_device.async_set_equalizer_mode("My & EQ #1")
    assert geq_device.equalizer_mode == "My & EQ #1"
    assert geq_api.json_request.await_count == 1
    command = geq_api.json_request.await_args.args[0]
    assert command.startswith("EQv2Load:")
    assert "&" not in command and "#" not in command
    assert json.loads(unquote(command.split(":", 1)[1])) == {
        "pluginURI": GEQ_PLUGIN_URI,
        "Name": "My & EQ #1",
    }
    leader.async_set_equalizer_mode.assert_not_called()


@pytest.mark.parametrize(
    ("name", "status", "expected"),
    [("Deep", "On", "Deep"), ("", "On", None), ("Deep", "Off", None)],
)
@pytest.mark.asyncio
async def test_geq_current_selection_sync(geq_device, geq_api, name, status, expected):
    geq_api.json_request.side_effect = None
    geq_api.json_request.return_value = {
        "status": "OK",
        "EQStat": status,
        "Name": name,
    }
    assert await geq_device.async_get_equalizer_mode() == expected
    assert geq_device.equalizer_mode == expected


@pytest.mark.parametrize(
    "response", [{"status": "failed"}, {"preset": [], "custom": [None]}]
)
@pytest.mark.asyncio
async def test_geq_unsupported_preserves_cache(geq_device, geq_api, response):
    await geq_device.async_refresh_equalizer()
    geq_api.json_request.side_effect = None
    geq_api.json_request.return_value = response
    await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ("Flat", "Deep", "My & EQ #1")
    assert geq_device.equalizer_mode == "Flat"
    assert geq_device.available


@pytest.mark.asyncio
async def test_geq_load_failure_and_invalid_selection(geq_device, geq_api):
    await geq_device.async_refresh_equalizer()
    geq_api.reset_mock()
    with pytest.raises(WiimDeviceException, match="Unsupported GEQ"):
        await geq_device.async_set_equalizer_mode("Missing")
    geq_api.json_request.assert_not_awaited()
    geq_api.json_request.side_effect = None
    geq_api.json_request.return_value = {"status": "failed"}
    with pytest.raises(WiimInvalidDataException):
        await geq_device.async_set_equalizer_mode("Deep")
    assert geq_device.equalizer_mode == "Flat"
    assert geq_api.json_request.await_count == 1
    assert geq_api.json_request.await_args.args[0].startswith("EQv2Load:")


@pytest.mark.asyncio
async def test_geq_without_http(mock_upnp_device, mock_session):
    device = WiimDevice(mock_upnp_device, mock_session)
    await device.async_refresh_equalizer()
    assert device.supported_equalizer_modes == ()
    assert device.equalizer_mode is None


@pytest.mark.asyncio
async def test_geq_unsupported_device(geq_device, geq_api):
    geq_api.json_request.side_effect = WiimInvalidDataException("unknown command")
    await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ()
    assert geq_device.equalizer_mode is None
    assert geq_device.available


@pytest.mark.asyncio
async def test_geq_network_failure_preserves_selection(geq_device, geq_api):
    await geq_device.async_refresh_equalizer()
    geq_api.json_request.side_effect = WiimRequestException("offline")
    with pytest.raises(WiimRequestException):
        await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ("Flat", "Deep", "My & EQ #1")
    assert geq_device.equalizer_mode == "Flat"
    assert geq_device.available


@pytest.mark.parametrize(
    "response", [{"status": "failed"}, WiimInvalidDataException("unknown command")]
)
@pytest.mark.asyncio
async def test_geq_current_unsupported_does_not_publish_list(
    geq_device, geq_api, response
):
    geq_api.json_request.side_effect = [
        {"preset": [{"Name": "Flat"}], "custom": []},
        response,
    ]
    await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ()
    assert geq_device.equalizer_mode is None
    assert geq_device.available


@pytest.mark.asyncio
async def test_geq_current_network_failure_can_retry(geq_device, geq_api):
    presets = {"preset": [{"Name": "Flat"}], "custom": []}
    geq_api.json_request.side_effect = [
        presets,
        WiimRequestException("timeout"),
        presets,
        {"status": "OK", "EQStat": "On", "Name": "Flat"},
    ]
    with pytest.raises(WiimRequestException):
        await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ()
    assert geq_device.equalizer_mode is None
    await geq_device.async_refresh_equalizer()
    assert geq_device.supported_equalizer_modes == ("Flat",)
    assert geq_device.equalizer_mode == "Flat"


@pytest.mark.parametrize(
    ("category", "expected_calls"), [("equaliser", 1), ("bluetooth", 0)]
)
@pytest.mark.asyncio
async def test_geq_rendering_notification(
    geq_device, geq_api, category, expected_calls
):
    await geq_device.async_refresh_equalizer()
    geq_api.reset_mock()
    geq_device.equalizer_event_callback = MagicMock()
    geq_device.rendering_control_event_callback = MagicMock()
    service = MagicMock()
    variable = MagicMock()
    variable.name = "LastChange"
    event = json.dumps({"category": category, "body": {"eq_change_type": 0}})
    variable.value = (
        '<Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/">'
        f'<InstanceID val="0"><commonevent val={quoteattr(event)}/></InstanceID></Event>'
    )
    geq_device._internal_handle_rendering_control_event(service, [variable])
    assert geq_device.equalizer_event_callback.call_count == expected_calls
    geq_device.rendering_control_event_callback.assert_called_once_with(
        service, [variable]
    )
    geq_api.json_request.assert_not_awaited()


@pytest.mark.parametrize("operation", ["read", "set"])
@pytest.mark.asyncio
async def test_geq_operations_wait_for_pending_read(geq_device, geq_api, operation):
    await geq_device.async_refresh_equalizer()
    started = asyncio.Event()
    release = asyncio.Event()

    async def old_response(command):
        started.set()
        await release.wait()
        return {"status": "OK", "EQStat": "On", "Name": "Flat"}

    geq_api.reset_mock()
    geq_api.json_request.side_effect = old_response
    first = asyncio.create_task(geq_device.async_get_equalizer_mode())
    await started.wait()
    operations = {
        "read": geq_device.async_get_equalizer_mode,
        "set": lambda: geq_device.async_set_equalizer_mode("Deep"),
    }
    second = asyncio.create_task(operations[operation]())
    try:
        await asyncio.sleep(0)
        assert geq_api.json_request.await_count == 1
        geq_api.json_request.side_effect = None
        geq_api.json_request.return_value = {
            "status": "OK",
            "EQStat": "On",
            "Name": "Deep",
        }
    finally:
        release.set()
        await asyncio.gather(first, second)
    assert geq_device.equalizer_mode == "Deep"
    assert geq_api.json_request.await_count == 2

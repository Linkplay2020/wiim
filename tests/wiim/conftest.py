# conftest.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from wiim.endpoint import WiimApiEndpoint


@pytest.fixture
def mock_session():
    """
    Fixture for a mocked aiohttp.ClientSession.
    Simulates async context management and responses.
    """
    session = MagicMock(name="mock_aiohttp_session")
    mock_get_context = AsyncMock(name="mock_session_get_context")
    mock_response = MagicMock(name="mock_response")
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="OK")
    mock_response.json = AsyncMock(return_value={"key": "value"})

    mock_get_context.__aenter__.return_value = mock_response
    session.get = MagicMock(return_value=mock_get_context)
    return session


@pytest.fixture
def mock_upnp_device():
    """
    Fixture for a mocked async_upnp_client.client.UpnpDevice.
    Provides a baseline object with essential attributes and mocked services.
    """
    device = MagicMock(name="mock_upnp_device")

    device.friendly_name = "WiiM Test Device"
    device.udn = "uuid:12345678-1234-1234-1234-1234567890ab"
    device.manufacturer = "Linkplay"
    device.model_name = "WiiM Pro"
    device.device_url = "http://192.168.1.100:49152/description.xml"

    # Mock UPnP services (AVTransport and RenderingControl)
    av_transport_service = MagicMock(name="mock_av_transport")
    av_transport_service.has_action.return_value = True
    av_transport_service.action.return_value = AsyncMock()  # Mock the action call

    rendering_control_service = MagicMock(name="mock_rendering_control")
    rendering_control_service.has_action.return_value = True
    rendering_control_service.action.return_value = AsyncMock()

    # The `service` method on the device should return the correct mocked service
    def service_selector(service_id):
        if service_id == "urn:schemas-upnp-org:service:AVTransport:1":
            return av_transport_service
        if service_id == "urn:schemas-upnp-org:service:RenderingControl:1":
            return rendering_control_service
        return None

    device.service = MagicMock(side_effect=service_selector)
    device.requester = MagicMock()
    return device


@pytest.fixture
def mock_wiim_device(mock_upnp_device):
    """
    Fixture for a generic mocked WiimDevice.
    Useful for testing the WiimController without needing a full WiimDevice instance.
    """
    device = MagicMock(name="mock_wiim_device_for_controller")
    device.udn = mock_upnp_device.udn
    device.name = mock_upnp_device.friendly_name
    device.ip_address = "192.168.1.100"
    device._http_api = AsyncMock(spec=WiimApiEndpoint)
    device._http_request = AsyncMock()
    device._http_command_ok = AsyncMock()
    device.disconnect = AsyncMock()
    return device

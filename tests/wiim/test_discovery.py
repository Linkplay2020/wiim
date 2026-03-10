# test_discovery.py
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from async_upnp_client.exceptions import UpnpConnectionError
from wiim.discovery import (
    async_create_wiim_device,
    async_probe_wiim_device,
    verify_wiim_device,
)


@pytest.mark.asyncio
class TestDiscovery:
    """Tests for device discovery and verification logic."""

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_success(self, mock_factory, mock_session):
        """Test verification of a valid WiiM device."""
        # Arrange: Mock the UpnpFactory to return a device with the correct manufacturer
        mock_device = MagicMock()
        mock_device.manufacturer = "Linkplay Technology Inc."
        mock_device.friendly_name = "WiiM Pro"
        mock_device.udn = "uuid:some-udn"
        mock_factory.return_value.async_create_device = AsyncMock(
            return_value=mock_device
        )

        device = await verify_wiim_device(
            "http://some-location/description.xml", mock_session
        )

        assert device is not None
        assert device.friendly_name == "WiiM Pro"
        mock_factory.return_value.async_create_device.assert_called_with(
            "http://some-location/description.xml"
        )

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_wrong_manufacturer(
        self, mock_factory, mock_session
    ):
        """Test that a device from a different manufacturer is not verified."""
        mock_device = MagicMock()
        mock_device.manufacturer = "Some Other Brand"
        mock_factory.return_value.async_create_device = MagicMock(
            return_value=mock_device
        )

        device = await verify_wiim_device("http://location", mock_session)

        assert device is None

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_handles_connection_error(
        self, mock_factory, mock_session
    ):
        """Test that network errors during verification are handled gracefully."""
        mock_factory.return_value.async_create_device.side_effect = UpnpConnectionError(
            "Connection failed"
        )

        device = await verify_wiim_device("http://location", mock_session)

        assert device is None

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_handles_generic_exception(
        self, mock_factory, mock_session
    ):
        """Test that unexpected errors during verification are caught."""
        mock_factory.return_value.async_create_device.side_effect = Exception(
            "A surprising error occurred"
        )

        device = await verify_wiim_device("http://location", mock_session)

        assert device is None

    @patch("wiim.discovery.ClientSession")
    @patch("wiim.discovery.WiimDevice")
    @patch("wiim.discovery.WiimApiEndpoint")
    @patch("wiim.discovery.UpnpFactory")
    async def test_async_create_wiim_device_success(
        self,
        mock_factory,
        mock_http_api_cls,
        mock_wiim_device_cls,
        mock_client_session_cls,
        mock_session,
    ):
        """Test creation of a fully initialized WiiM device from a location."""
        mock_upnp_device = MagicMock()
        mock_upnp_device.manufacturer = "Linkplay Technology Inc."
        mock_upnp_device.friendly_name = "WiiM Pro"
        mock_upnp_device.udn = "uuid:some-udn"
        mock_factory.return_value.async_create_device = AsyncMock(
            return_value=mock_upnp_device
        )

        mock_http_api = AsyncMock()
        mock_http_api.json_request = AsyncMock(return_value={"status": "ok"})
        mock_http_api_cls.return_value = mock_http_api
        http_session = MagicMock()
        mock_client_session_cls.return_value = http_session

        mock_wiim_device = MagicMock()
        mock_wiim_device.name = "WiiM Pro"
        mock_wiim_device.udn = "uuid:some-udn"
        mock_wiim_device.async_init_services_and_subscribe = AsyncMock(
            return_value=True
        )
        mock_wiim_device_cls.return_value = mock_wiim_device

        device = await async_create_wiim_device(
            "http://192.168.1.10:49152/description.xml",
            mock_session,
            ha_host_ip="192.168.1.2",
        )

        assert device is mock_wiim_device
        mock_http_api_cls.assert_called_once_with(
            protocol="https",
            port=443,
            endpoint="192.168.1.10",
            session=http_session,
            verify_ssl=False,
            owns_session=True,
        )
        mock_wiim_device_cls.assert_called_once_with(
            mock_upnp_device,
            mock_session,
            http_api_endpoint=mock_http_api,
            ha_host_ip="192.168.1.2",
            polling_interval=60,
        )

    @patch("wiim.discovery.ClientSession")
    @patch("wiim.discovery.WiimDevice")
    @patch("wiim.discovery.UpnpFactory")
    async def test_async_create_wiim_device_disconnects_failed_init(
        self,
        mock_factory,
        mock_wiim_device_cls,
        mock_client_session_cls,
        mock_session,
    ):
        """Test failed initialization disconnects the partially created device."""
        mock_upnp_device = MagicMock()
        mock_upnp_device.manufacturer = "Linkplay Technology Inc."
        mock_upnp_device.friendly_name = "WiiM Pro"
        mock_upnp_device.udn = "uuid:some-udn"
        mock_factory.return_value.async_create_device = AsyncMock(
            return_value=mock_upnp_device
        )

        mock_wiim_device = MagicMock()
        mock_wiim_device.async_init_services_and_subscribe = AsyncMock(
            return_value=False
        )
        mock_wiim_device.disconnect = AsyncMock()
        mock_wiim_device_cls.return_value = mock_wiim_device
        mock_client_session_cls.return_value = MagicMock()

        device = await async_create_wiim_device(
            "http://192.168.1.10:49152/description.xml",
            mock_session,
        )

        assert device is None
        mock_wiim_device.disconnect.assert_awaited_once()

    @patch("wiim.discovery.UpnpFactory")
    async def test_async_probe_wiim_device(
        self,
        mock_factory,
        mock_session,
    ):
        """Test probing returns normalized discovery data."""
        mock_upnp_device = MagicMock()
        mock_upnp_device.manufacturer = "Linkplay Technology Inc."
        mock_upnp_device.friendly_name = "WiiM Pro"
        mock_upnp_device.udn = "uuid:some-udn"
        mock_upnp_device.model_name = "WiiM Pro"
        mock_factory.return_value.async_create_device = AsyncMock(
            return_value=mock_upnp_device
        )

        result = await async_probe_wiim_device(
            "http://192.168.1.10:49152/description.xml",
            mock_session,
        )

        assert result is not None
        assert result.udn == "uuid:some-udn"
        assert result.name == "WiiM Pro"
        assert result.model == "WiiM Pro"
        assert result.host == "192.168.1.10"
        assert result.location == "http://192.168.1.10:49152/description.xml"

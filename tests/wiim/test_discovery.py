# test_discovery.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock 
from async_upnp_client.exceptions import UpnpConnectionError
from wiim.discovery import verify_wiim_device


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
        mock_factory.return_value.async_create_device = AsyncMock(return_value=mock_device)

        device = await verify_wiim_device("http://some-location/description.xml", mock_session)

        assert device is not None
        assert device.friendly_name == "WiiM Pro"
        mock_factory.return_value.async_create_device.assert_called_with("http://some-location/description.xml")

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_wrong_manufacturer(self, mock_factory, mock_session):
        """Test that a device from a different manufacturer is not verified."""
        mock_device = MagicMock()
        mock_device.manufacturer = "Some Other Brand"
        mock_factory.return_value.async_create_device = MagicMock(return_value=mock_device)

        device = await verify_wiim_device("http://location", mock_session)

        assert device is None

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_handles_connection_error(self, mock_factory, mock_session):
        """Test that network errors during verification are handled gracefully."""
        mock_factory.return_value.async_create_device.side_effect = UpnpConnectionError("Connection failed")
        
        device = await verify_wiim_device("http://location", mock_session)
        
        assert device is None

    @patch("wiim.discovery.UpnpFactory")
    async def test_verify_wiim_device_handles_generic_exception(self, mock_factory, mock_session):
        """Test that unexpected errors during verification are caught."""
        mock_factory.return_value.async_create_device.side_effect = Exception("A surprising error occurred")
        
        device = await verify_wiim_device("http://location", mock_session)
        
        assert device is None


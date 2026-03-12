# test_endpoint.py
import pytest
from unittest.mock import AsyncMock, ANY
from wiim.endpoint import WiimApiEndpoint
from wiim.exceptions import WiimRequestException, WiimInvalidDataException


class TestWiimApiEndpoint:
    """Tests for the WiimApiEndpoint class."""

    @pytest.mark.parametrize(
        "protocol, port, endpoint, expected_url",
        [
            ("https", 443, "192.168.1.1", "https://192.168.1.1"),  # Existing HTTPS 443
        ],
    )
    def test_init_base_url(self, protocol, port, endpoint, expected_url, mock_session):
        """Test if the base URL is constructed correctly."""
        api = WiimApiEndpoint(
            protocol=protocol, port=port, endpoint=endpoint, session=mock_session
        )
        assert api._base_url == expected_url

    @pytest.mark.asyncio
    async def test_request_ok(self, mock_session):
        """Test a successful request that expects an 'OK' response."""
        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )

        await endpoint.request("getStatusEx")

        mock_session.get.assert_called_with(
            "https://192.168.1.1/httpapi.asp?command=getStatusEx", timeout=ANY
        )

    @pytest.mark.asyncio
    async def test_request_not_ok_response_raises_exception(self, mock_session):
        """Test that a non-'OK' response raises WiimInvalidDataException."""
        mock_session.get.return_value.__aenter__.return_value.text = AsyncMock(
            return_value="FAILED"
        )
        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )

        with pytest.raises(WiimInvalidDataException):
            await endpoint.request("getStatusEx")

    @pytest.mark.asyncio
    async def test_request_http_error_raises_exception(self, mock_session):
        """Test that a non-200 HTTP status raises WiimRequestException."""
        mock_session.get.return_value.__aenter__.return_value.status = 500
        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )

        with pytest.raises(WiimRequestException):
            await endpoint.request("getStatusEx")

    @pytest.mark.asyncio
    async def test_request_with_ssl_verification_disabled(self, mock_session):
        """Test disabling SSL verification uses the shared session with ssl=False."""
        endpoint = WiimApiEndpoint(
            protocol="https",
            port=443,
            endpoint="192.168.1.1",
            session=mock_session,
            verify_ssl=False,
        )

        await endpoint.request("getStatusEx")

        mock_session.get.assert_called_with(
            "https://192.168.1.1/httpapi.asp?command=getStatusEx",
            timeout=ANY,
            ssl=False,
        )

    @pytest.mark.asyncio
    async def test_async_close_owned_session(self, mock_session):
        """Test owned sessions are closed by the endpoint."""
        mock_session.closed = False
        mock_session.close = AsyncMock()
        endpoint = WiimApiEndpoint(
            protocol="https",
            port=443,
            endpoint="192.168.1.1",
            session=mock_session,
            owns_session=True,
        )

        await endpoint.async_close()

        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_json_request_ok(self, mock_session):
        """Test a successful request that returns JSON."""
        mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(
            return_value={"status": "success"}
        )
        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )

        response = await endpoint.json_request("getStatusEx")

        assert response == {"OK": True}

    @pytest.mark.asyncio
    async def test_json_request_parses_key_value_pairs(self, mock_session):
        """Test that the endpoint can parse 'key=value' text responses."""
        mock_session.get.return_value.__aenter__.return_value.text = AsyncMock(
            return_value="key1=value1\nkey2=value2"
        )
        mock_session.get.return_value.__aenter__.return_value.json.side_effect = (
            ValueError
        )
        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )

        response = await endpoint.json_request("getPlayerStatusEx")

        assert response == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_json_request_invalid_json_raises_exception(self, mock_session):
        """
        Test that malformed JSON responses raise WiimInvalidDataException.
        Configured for HTTPS, port 443, with disabled certificate verification.
        """
        mock_session.get.return_value.__aenter__.return_value.text = AsyncMock(
            return_value="not a valid json response"
        )
        mock_session.get.return_value.__aenter__.return_value.json.side_effect = (
            ValueError
        )

        endpoint = WiimApiEndpoint(
            protocol="https", port=443, endpoint="192.168.1.1", session=mock_session
        )
        await endpoint.json_request("multiroom:getSlaveList")

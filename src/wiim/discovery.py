from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List
from urllib.parse import urlparse

from aiohttp import ClientSession, TCPConnector
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpConnectionError, UpnpError

from .consts import MANUFACTURER_WIIM, SDK_LOGGER, UPNP_DEVICE_TYPE, WiimHttpCommand
from .endpoint import WiimApiEndpoint
from .exceptions import WiimDeviceException, WiimRequestException
from .models import WiimProbeResult
from .wiim_device import DEFAULT_AVAILABILITY_POLLING_INTERVAL, WiimDevice

if TYPE_CHECKING:
    from zeroconf import Zeroconf

DISCOVERY_TIMEOUT = 10
DEVICE_VERIFICATION_TIMEOUT = 5


def _is_supported_wiim_device(device: UpnpDevice) -> bool:
    """Return True if the given UPnP device matches a supported WiiM variant."""
    return (
        bool(device.manufacturer)
        and MANUFACTURER_WIIM.lower() in device.manufacturer.lower()
    ) or (
        device.manufacturer == "Audio Pro AB"
        and bool(device.model_name)
        and device.model_name == "A10 Speaker"
    )


async def _async_create_upnp_device(
    location: str, session: ClientSession
) -> UpnpDevice:
    """Create a UPnP device using the caller-managed aiohttp session."""
    requester = AiohttpSessionRequester(
        session, with_sleep=True, timeout=DEVICE_VERIFICATION_TIMEOUT
    )
    factory = UpnpFactory(requester)
    return await factory.async_create_device(location)


async def verify_wiim_device(
    location: str, session: ClientSession
) -> UpnpDevice | None:
    """Verify if a description URL points at a supported WiiM device."""
    logger = SDK_LOGGER
    try:
        device = await _async_create_upnp_device(location, session)
        logger.debug(
            "Verifying device: %s, Manufacturer: %s, Model: %s, UDN: %s",
            device.friendly_name,
            device.manufacturer,
            device.model_name,
            device.udn,
        )

        if _is_supported_wiim_device(device):
            logger.info(
                "Verified WiiM device by manufacturer: %s (%s)",
                device.friendly_name,
                device.udn,
            )
            return device

        logger.debug(
            "Device %s at %s does not appear to be a WiiM device.",
            device.friendly_name,
            location,
        )
        return None
    except (
        UpnpConnectionError,
        UpnpError,
        asyncio.TimeoutError,
        WiimRequestException,
    ) as err:
        logger.debug("Failed to verify device at %s: %s", location, err)
        return None
    except Exception as err:  # pylint: disable=broad-except
        logger.error(
            "Unexpected error verifying device at %s: %s",
            location,
            err,
            exc_info=True,
        )
        return None


async def async_create_http_api_endpoint(
    host: str | None,
    *,
    protocol: str = "https",
    port: int = 443,
    verify_ssl: bool = False,
) -> WiimApiEndpoint | None:
    """Create and validate the WiiM HTTP API endpoint for a device host."""
    if not host:
        return None

    logger = SDK_LOGGER
    http_session = ClientSession(connector=TCPConnector(ssl=False))
    http_api = WiimApiEndpoint(
        protocol=protocol,
        port=port,
        endpoint=host,
        session=http_session,
        verify_ssl=verify_ssl,
        owns_session=True,
    )
    try:
        await http_api.json_request(WiimHttpCommand.DEVICE_STATUS)
    except Exception as err:  # pylint: disable=broad-except
        logger.warning(
            "Could not establish default HTTP API for %s, some features might be limited: %s",
            host,
            err,
        )
        await http_api.async_close()
        return None
    return http_api


async def async_probe_wiim_device(
    location: str,
    session: ClientSession,
    *,
    host: str | None = None,
) -> WiimProbeResult | None:
    """Probe a WiiM device and return normalized discovery information."""
    upnp_device = await verify_wiim_device(location, session)
    if upnp_device is None:
        return None

    resolved_host = host or urlparse(location).hostname
    if resolved_host is None:
        return None

    return WiimProbeResult(
        udn=upnp_device.udn,
        name=upnp_device.friendly_name,
        model=upnp_device.model_name or "WiiM Device",
        host=resolved_host,
        location=location or upnp_device.device_url,
    )


async def async_create_wiim_device(
    location: str,
    session: ClientSession,
    *,
    host: str | None = None,
    local_host: str | None = None,
    polling_interval: int = DEFAULT_AVAILABILITY_POLLING_INTERVAL,
    initialize: bool = True,
) -> WiimDevice:
    """Create a validated WiiM device from a UPnP location URL."""
    logger = SDK_LOGGER

    upnp_device = await verify_wiim_device(location, session)
    if upnp_device is None:
        raise WiimRequestException(f"Failed to verify WiiM device at {location}")

    http_api = await async_create_http_api_endpoint(host or urlparse(location).hostname)

    wiim_device = WiimDevice(
        upnp_device,
        session,
        http_api_endpoint=http_api,
        local_host=local_host,
        polling_interval=polling_interval,
    )

    if not initialize:
        return wiim_device

    if await wiim_device.async_init_services_and_subscribe():
        logger.info(
            "Successfully created and initialized WiimDevice: %s (%s)",
            wiim_device.name,
            wiim_device.udn,
        )
        return wiim_device

    logger.warning(
        "Failed to initialize WiimDevice after discovery: %s",
        upnp_device.friendly_name,
    )
    await wiim_device.disconnect()
    raise WiimDeviceException(
        f"Failed to initialize WiiM device from {upnp_device.friendly_name}"
    )


async def async_discover_wiim_devices_upnp(
    session: ClientSession,
    timeout: int = DISCOVERY_TIMEOUT,
    target_device_type: str = UPNP_DEVICE_TYPE,
) -> List[WiimDevice]:
    """Discover WiiM devices on the network using UPnP."""
    logger = SDK_LOGGER
    discovered_devices: dict[str, WiimDevice] = {}
    found_locations: set[str] = set()

    async def device_found_callback(udn: str, location: str, device_type: str):
        nonlocal found_locations
        if location in found_locations:
            return
        found_locations.add(location)

        logger.debug(
            "UPnP Discovery: Found %s at %s (type: %s)", udn, location, device_type
        )
        if target_device_type and target_device_type not in device_type:
            logger.debug(
                "Ignoring device %s, does not match target type %s",
                udn,
                target_device_type,
            )
            return

        try:
            wiim_device = await async_create_wiim_device(location, session)
        except (WiimDeviceException, WiimRequestException) as err:
            logger.debug("Skipping device at %s during discovery: %s", location, err)
            return

        if wiim_device.udn not in discovered_devices:
            discovered_devices[wiim_device.udn] = wiim_device

    logger.warning(
        "async_discover_wiim_devices_upnp: SSDP discovery mechanism needs to be fully implemented "
        "or integrated with HA's discovery if SDK is HA-specific."
    )

    return list(discovered_devices.values())


async def async_discover_wiim_devices_zeroconf(
    session: ClientSession,
    zeroconf_instance: "Zeroconf",
    service_type: str = "_linkplay._tcp.local.",
) -> List[WiimDevice]:
    """Discover WiiM devices using Zeroconf and then verify them via UPnP."""
    del session
    del zeroconf_instance
    del service_type

    logger = SDK_LOGGER
    discovered_wiim_devices: dict[str, WiimDevice] = {}

    logger.warning(
        "async_discover_wiim_devices_zeroconf: Relies on external Zeroconf to provide IPs. "
        "Further UPnP probing is needed to get description.xml location from just an IP."
    )

    return list(discovered_wiim_devices.values())

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List
from urllib.parse import urlparse
from aiohttp import TCPConnector, ClientSession

from async_upnp_client.client import UpnpDevice

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.exceptions import UpnpConnectionError
from async_upnp_client.client_factory import UpnpFactory

from .consts import (
    SDK_LOGGER,
    UPNP_DEVICE_TYPE,
    MANUFACTURER_WIIM,
)
from .wiim_device import WiimDevice
from .endpoint import WiimApiEndpoint
from .exceptions import WiimRequestException

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from zeroconf import Zeroconf

DISCOVERY_TIMEOUT = 10
DEVICE_VERIFICATION_TIMEOUT = 5


async def verify_wiim_device(
    location: str, session: ClientSession
) -> UpnpDevice | None:
    """
    Verifies if a device at a given location (URL to description.xml) is a WiiM device.
    Returns a UpnpDevice object if verified, otherwise None.
    """
    logger = SDK_LOGGER
    requester = AiohttpRequester(timeout=DEVICE_VERIFICATION_TIMEOUT)
    try:
        factory = UpnpFactory(requester)
        device = await factory.async_create_device(location)
        logger.debug(
            "Verifying device: %s, Manufacturer: %s, Model: %s, UDN: %s",
            device.friendly_name,
            device.manufacturer,
            device.model_name,
            device.udn,
        )

        if (
            device.manufacturer
            and MANUFACTURER_WIIM.lower() in device.manufacturer.lower()
        ):
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
    except (UpnpConnectionError, asyncio.TimeoutError, WiimRequestException) as e:
        logger.debug("Failed to verify device at %s: %s", location, e)
        return None
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "Unexpected error verifying device at %s: %s", location, e, exc_info=True
        )
        return None


async def async_discover_wiim_devices_upnp(
    session: ClientSession,
    timeout: int = DISCOVERY_TIMEOUT,
    target_device_type: str = UPNP_DEVICE_TYPE,
) -> List[WiimDevice]:
    """
    Discovers WiiM devices on the network using UPnP (SSDP).
    Creates WiimDevice instances for verified devices.
    """
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

        upnp_device = await verify_wiim_device(location, session)
        if upnp_device and upnp_device.udn not in discovered_devices:
            # Create HTTP endpoint for the WiimDevice
            host = urlparse(location).hostname
            http_api = None
            if host:
                try:
                    sessions = ClientSession(connector=TCPConnector(ssl=False))
                    http_api = WiimApiEndpoint(
                        protocol="https", port=443, endpoint=host, session=sessions
                    )
                    await http_api.json_request("getStatusEx")
                except Exception:  # pylint: disable=broad-except
                    logger.warning(
                        "Could not establish default HTTP API for %s, some features might be limited.",
                        host,
                    )
                    http_api = None

            wiim_dev = WiimDevice(upnp_device, session, http_api_endpoint=http_api)
            # Initialize services and subscribe. If it fails, device won't be added.
            if await wiim_dev.async_init_services_and_subscribe():
                discovered_devices[upnp_device.udn] = wiim_dev
                logger.info(
                    "Successfully created and initialized WiimDevice: %s (%s)",
                    wiim_dev.name,
                    wiim_dev.udn,
                )
            else:
                logger.warning(
                    "Failed to initialize WiimDevice after discovery: %s",
                    upnp_device.friendly_name,
                )

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
    """
    Discovers WiiM devices using Zeroconf (mDNS) and then verifies them via UPnP.
    This is more aligned with how Home Assistant's config flow might initiate discovery.
    `zeroconf_instance` would be `hass.data[ZEROCONF_INSTANCE]` in HA.
    """
    logger = SDK_LOGGER
    discovered_wiim_devices: dict[str, WiimDevice] = {}  # UDN: WiimDevice

    logger.warning(
        "async_discover_wiim_devices_zeroconf: Relies on external Zeroconf to provide IPs. "
        "Further UPnP probing is needed to get description.xml location from just an IP."
    )

    return list(discovered_wiim_devices.values())

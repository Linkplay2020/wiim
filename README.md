[![PyPI version](https://img.shields.io/pypi/v/wiim.svg)](https://pypi.org/project/wiim/)
[![CI](https://github.com/Linkplay2020/wiim/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/Linkplay2020/wiim/actions/workflows/test.yaml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/pypi/l/wiim.svg)](https://github.com/Linkplay2020/wiim/blob/main/LICENSE)
[![PyPI downloads](https://img.shields.io/pypi/dm/wiim.svg)](https://pypistats.org/packages/wiim)

# WiiM Python SDK

`wiim` is an asynchronous Python SDK for discovering, monitoring, and
controlling WiiM audio devices on a local network.

The SDK communicates directly with devices using UPnP eventing and the
LinkPlay HTTP API. It is intended for Home Assistant integrations, automation
platforms, and other asyncio-based applications.

## Features

- Validate and create WiiM devices from UPnP description URLs
- Discover local devices with the included Zeroconf CLI
- Control playback, volume, mute, seeking, repeat, and shuffle
- Select supported audio inputs and outputs
- Read normalized media metadata, playback state, and device information
- Subscribe to real-time UPnP state changes with HTTP polling as a fallback
- Inspect presets, the current queue, and transport capabilities
- Create, update, and disband multiroom groups
- Support IPv4 and IPv6 event listeners
- Expose typed models and exceptions for application integrations

Available features can vary by device model, active input source, and firmware
version.

## Installation

Install the latest release from PyPI:

```bash
python -m pip install wiim
```

The project is currently tested with Python 3.13.

## Quick Start

Create a device from its UPnP description URL and send playback commands:

```python
import asyncio

from aiohttp import ClientSession

from wiim import async_create_wiim_device


async def main() -> None:
    async with ClientSession() as session:
        device = await async_create_wiim_device(
            "http://192.168.1.100:49152/description.xml",
            session,
            host="192.168.1.100",
        )

        try:
            await device.async_set_volume(30)
            await device.async_play()

            print(f"Device: {device.name}")
            print(f"State: {device.playing_status}")
            print(f"Media: {device.current_media}")
        finally:
            await device.disconnect()


asyncio.run(main())
```

Replace the example address with the UPnP description URL and IP address of
your device.

## Device Discovery

Run the included CLI to discover WiiM devices advertised through Zeroconf and
print their current state:

```bash
python -m wiim
```

Applications that already receive discovery information can use
`async_create_wiim_device()` with the discovered UPnP location. This avoids
running a second discovery implementation and lets the application manage the
device lifecycle explicitly.

## Error Handling

All SDK-specific exceptions derive from `WiimException`:

- `WiimRequestException` reports HTTP and network request failures.
- `WiimDeviceException` reports device and UPnP action failures.
- `WiimInvalidDataException` reports invalid device responses.

Catch a more specific exception when the application needs different recovery
behavior for transport failures and invalid data.

```python
from wiim import WiimException

try:
    ...
except WiimException as err:
    print(f"WiiM request failed: {err}")
```

## Development

Clone the repository and install tox:

```bash
python -m pip install tox
```

Run the test suite in the isolated Python 3.13 environment:

```bash
python -m tox -e py313
```

Run all configured test and static-check environments:

```bash
python -m tox
```

## License

This project is available under the [MIT License](https://github.com/Linkplay2020/wiim/blob/main/LICENSE).

## Support

Report bugs and request features through
[GitHub Issues](https://github.com/Linkplay2020/wiim/issues). For product
support, contact `support@wiimhome.com`.

[![PyPI package](https://badge.fury.io/py/wiim.svg)](https://pypi.org/project/wiim/)


# wiim
A Python-based API interface for controlling and communicating with WiiM audio devices

## ✨ Introduction

**wiim** is a powerful and user-friendly Python library designed to significantly simplify the integration and control of [WiiM](https://wiimhome.com/) smart audio devices. WiiM devices (built on LinkPlay modules) deliver an immersive musical experience throughout your home with their excellent wireless streaming and multiroom audio capabilities. With **wiim**, you can seamlessly manage your WiiM devices directly from your Python applications.

Whether you need precise control over music playback, synchronization of multiroom groups, or real-time retrieval of playback metadata, **wiim** provides a clean and unified interface. It's the ideal choice for building smart home automations, custom music players, or any Python application requiring interaction with WiiM devices.

## 🚀 Key Features

✅ **Automatic Device Discovery**  
Smartly scans and identifies all WiiM devices on your network, making connection effortless.

✅ **Comprehensive Playback Control**  
Offers all core functionalities including play, pause, stop, skip tracks, volume adjustment, mute/unmute, shuffle, repeat modes, and input source switching.

✅ **Rich Metadata Retrieval**  
Get real-time detailed information about the currently playing track, such as title, artist, album, album art URL, and more, helping you create personalized display interfaces.

✅ **Flexible Group Management**  
Easily create, update, or disband multiroom synchronized playback groups for seamless music across your entire home.

✅ **High Availability & Stability**  
Built-in error handling and device status monitoring mechanisms ensure your control commands are reliably delivered.

## 💡 Quick Start

### Installation

Install the **wiim** library easily via pip:

```bash
pip install wiim
```

### Usage Example

Here's a quick example demonstrating how to connect to and control a WiiM device to play music:

```python
__main__.py
```

**Important Notes for the Example:**
- Starts Zeroconf discovery using AsyncZeroconf with ZeroconfListener to automatically find _linkplay._tcp.local. services broadcasted by WiiM devices on your network.
- Waits a configurable duration (e.g., 5 seconds) using asyncio.sleep() to give Zeroconf time to discover devices on the network.
- Verifies each discovered device by probing common UPnP description URLs like http://<device_ip>/description.xml with verify_wiim_device() to confirm it's a WiiM device.
- Creates a WiimDevice instance for each verified WiiM device and sets up an HTTP API endpoint using WiimApiEndpoint for controlling the device.
- Prints detailed information about each verified device including name, UDN, model, IP address, firmware version, playback status, volume, and current track metadata.
- Cleans up all resources by disconnecting from devices, canceling Zeroconf browsing, and closing aiohttp client sessions after the process completes.


## 📄 License

This project is licensed under the MIT License.

## 📞 Support & Feedback

If you encounter any issues during use, or have any suggestions and ideas, please feel free to submit them via GitHub Issues or contact our official support email at support@wiimhome.com.

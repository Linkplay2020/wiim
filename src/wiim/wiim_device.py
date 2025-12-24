# wiim/wiim_device.py
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, List, cast
from collections.abc import Sequence
from urllib.parse import urlparse, urljoin
from datetime import timedelta
import xml.etree.ElementTree as ET
from html import unescape
from contextlib import suppress

from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.exceptions import UpnpError
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.aiohttp import AiohttpNotifyServer

from .consts import (
    SDK_LOGGER,
    MANUFACTURER_WIIM,
    UPNP_AV_TRANSPORT_SERVICE_ID,
    UPNP_RENDERING_CONTROL_SERVICE_ID,
    UPNP_WIIM_PLAY_QUEUE_SERVICE_ID,
    DeviceAttribute,
    PlayerAttribute,
    PlayingStatus,
    PlayerStatus,
    _PLAYER_TO_PLAYING,
    PlayingMode,
    PLAYING_TO_INPUT_MAP,
    InputMode,
    AudioOutputHwMode,
    EqualizerMode,
    LoopMode,
    MuteMode,
    WiimHttpCommand,
    UPNP_TIMEOUT_TIME,
    AUDIO_AUX_MODE_IDS,
)
from .endpoint import WiimApiEndpoint
from .exceptions import WiimDeviceException, WiimRequestException
from .handler import parse_last_change_event
from .manufacturers import get_info_from_project

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from async_upnp_client.client import UpnpRequester

DEFAULT_AVAILABILITY_POLLING_INTERVAL = 60

GeneralEventCallback = Callable[["WiimDevice"], None]
UpnpServiceEventCallback = Callable[[UpnpService, List[UpnpStateVariable]], None]


class WiimDevice:
    """
    Represents a WiiM device, handling state and UPnP/HTTP interactions.
    """

    _device_info_properties: dict[DeviceAttribute, str]
    _player_properties: dict[PlayerAttribute, str]
    _custom_player_properties: dict[Any, Any]

    av_transport_event_callback: UpnpServiceEventCallback | None = None
    rendering_control_event_callback: UpnpServiceEventCallback | None = None
    play_queue_event_callback: UpnpServiceEventCallback | None = None
    general_event_callback: GeneralEventCallback | None = None

    def __init__(
        self,
        upnp_device: UpnpDevice,
        session: ClientSession,
        http_api_endpoint: WiimApiEndpoint | None = None,
        ha_host_ip: str | None = None,
        polling_interval: int = DEFAULT_AVAILABILITY_POLLING_INTERVAL,
    ):
        """Initialize the WiiM device."""
        self.upnp_device = upnp_device
        self._session = session
        self.logger = SDK_LOGGER

        self._device_info_properties = dict.fromkeys(
            DeviceAttribute.__members__.values(), ""
        )
        self._player_properties = dict.fromkeys(
            PlayerAttribute.__members__.values(), ""
        )
        self._custom_player_properties = {}

        self._name: str = (
            upnp_device.friendly_name
            if hasattr(upnp_device, "friendly_name")
            else "Unknown WiiM Device"
        )
        self._udn: str = (
            upnp_device.udn
            if hasattr(upnp_device, "udn")
            else f"uuid:unknown-{id(self)}"
        )
        self._model_name: str = (
            upnp_device.model_name if hasattr(upnp_device, "model_name") else None
        ) or "WiiM Device"
        self._manufacturer: str = (
            upnp_device.manufacturer if hasattr(upnp_device, "manufacturer") else None
        ) or MANUFACTURER_WIIM
        self._device_type: str = (
            upnp_device.device_type
            if hasattr(upnp_device, "device_type")
            else "UnknownType"
        )
        self._presentation_url: str | None = (
            upnp_device.presentation_url
            if hasattr(upnp_device, "presentation_url")
            else None
        )

        self.av_transport: UpnpService | None = None
        self.rendering_control: UpnpService | None = None
        self.play_queue_service: UpnpService | None = None

        self._notify_server: AiohttpNotifyServer | None = None
        self._event_handler: UpnpEventHandler | None = None

        self.requester_for_eventing: UpnpRequester | None = None
        if hasattr(self.upnp_device, "requester") and self.upnp_device.requester:
            self.requester_for_eventing = self.upnp_device.requester  # type: ignore

        self.ha_host_ip = ha_host_ip
        # if requester_for_eventing:
        #     try:
        #         loop = asyncio.get_event_loop()
        #         local_ip = ha_host_ip
        #         device_ip = self.ip_address
        #         if device_ip:
        #             last_octet = int(device_ip.split(".")[-1])
        #         else:
        #             last_octet = 0
        #         base_port = 50000
        #         assigned_port = base_port + last_octet
        #         source_ip = local_ip or "0.0.0.0"
        #         source = (source_ip, assigned_port)

        #         self._notify_server = AiohttpNotifyServer(
        #             requester=requester_for_eventing,
        #             source=source,
        #             loop=loop,
        #         )

        #         self.logger.debug(
        #             "Device %s: UpnpEventHandler and AiohttpNotifyServer initialized.",
        #             self.name,
        #         )
        #     except Exception as e:
        #         self.logger.warning(
        #             "Device %s: Failed to initialize AiohttpNotifyServer or UpnpEventHandler: %s. Eventing will be disabled.",
        #             self.name,
        #             e,
        #             exc_info=True,
        #         )
        #         self._notify_server = None
        #         self._event_handler = None
        # else:
        #     self.logger.warning(
        #         "Device %s: UpnpDevice has no valid requester. Eventing will not be available.",
        #         self.name,
        #     )

        self.volume: int = 0
        self.is_muted: bool = False
        self.playing_status: PlayingStatus = PlayingStatus.STOPPED
        self.current_track_info: dict[str, Any] = {}
        self.play_mode: str
        self.input_source: str
        self.loop_mode: LoopMode = LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
        self.equalizer_mode: EqualizerMode = EqualizerMode.NONE
        self.current_position: int = 0
        self.current_track_duration: int = 0
        self.next_track_uri: str | None = None

        self._http_api: WiimApiEndpoint | None = http_api_endpoint

        self._available: bool = True
        self._cancel_event_renewal: asyncio.TimerHandle | None = None
        self._event_handler_started: bool = False

        self._polling_interval = polling_interval
        self._polling_task: asyncio.Task | None = None

    async def async_init_services_and_subscribe(self) -> bool:
        """
        Initialize UPnP services and subscribe to events.
        Also fetches initial HTTP status as a baseline.
        Returns True if successful, False otherwise.
        """
        if self.requester_for_eventing:
            try:
                loop = asyncio.get_event_loop()
                local_ip = self.ha_host_ip
                device_ip = self.ip_address
                if device_ip:
                    last_octet = int(device_ip.split(".")[-1])
                else:
                    last_octet = 0
                base_port = 50000
                assigned_port = base_port + last_octet
                source_ip = local_ip or "0.0.0.0"
                source = (source_ip, assigned_port)

                if self.av_transport:
                    self.av_transport = None
                if self.rendering_control:
                    self.rendering_control = None
                if self.play_queue_service:
                    self.play_queue_service = None

                if self._notify_server:
                    try:
                        await self._notify_server.async_stop_server()
                    except Exception as e:
                        self.logger.warning(
                            "Failed to stop previous notify server: %s", e
                        )
                    self._notify_server = None

                self._notify_server = AiohttpNotifyServer(
                    requester=self.upnp_device.requester,
                    source=source,
                    loop=loop,
                )

                if self._event_handler:
                    self._event_handler = None

                self.logger.debug(
                    "Device %s: UpnpEventHandler and AiohttpNotifyServer initialized.",
                    self.name,
                )
            except Exception as e:
                self.logger.warning(
                    "Device %s: Failed to initialize AiohttpNotifyServer or UpnpEventHandler: %s. Eventing will be disabled.",
                    self.name,
                    e,
                    exc_info=True,
                )
                self._notify_server = None
                self._event_handler = None
        else:
            self.logger.warning(
                "Device %s: UpnpDevice has no valid requester. Eventing will not be available.",
                self.name,
            )

        try:
            if hasattr(self.upnp_device, "service"):
                self.av_transport = self.upnp_device.service(
                    UPNP_AV_TRANSPORT_SERVICE_ID
                )
                self.rendering_control = self.upnp_device.service(
                    UPNP_RENDERING_CONTROL_SERVICE_ID
                )
                self.play_queue_service = self.upnp_device.service(
                    UPNP_WIIM_PLAY_QUEUE_SERVICE_ID
                )
            else:
                self.logger.warning(
                    "Device %s: upnp_device object does not have 'service' method. UPnP services not loaded.",
                    self.name,
                )
                self.av_transport = None
                self.rendering_control = None
                self.play_queue_service = None

            if not self.play_queue_service:
                self.logger.debug(
                    "Device %s: Custom PlayQueue service (%s) not found.",
                    self.name,
                    UPNP_WIIM_PLAY_QUEUE_SERVICE_ID,
                )

            if not self.av_transport or not self.rendering_control:
                self.logger.warning(
                    "Device %s: Missing required UPnP services (AVTransport or RenderingControl). Event subscription will be skipped for these.",
                    self.name,
                )

            if self._notify_server is not None:
                self._event_handler = self._notify_server.event_handler
                self._event_handler._notify_server = self._notify_server

            if self._event_handler and self._notify_server:
                if not self._event_handler_started:
                    try:
                        await self._notify_server.async_start_server()
                        self.logger.info(
                            "Notify server started at %s (override for device: %s)",
                            self._notify_server.callback_url,
                            self._event_handler.callback_url,
                        )
                        self._event_handler_started = True
                        self.logger.info(
                            "Device %s: AiohttpNotifyServer for UPnP events started at: %s",
                            self.name,
                            self._notify_server.callback_url,
                        )
                    except Exception as e:
                        self.logger.warning(
                            "Device %s: Failed to start AiohttpNotifyServer: %s",
                            self.name,
                            e,
                            exc_info=True,
                        )
                        self._event_handler_started = False

                if self._event_handler_started:
                    if self.av_transport:
                        self.av_transport.on_event = (
                            self._internal_handle_av_transport_event
                        )
                        await self._event_handler.async_subscribe(
                            self.av_transport,
                            timeout=timedelta(seconds=UPNP_TIMEOUT_TIME),
                        )
                        self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
                    if self.rendering_control:
                        self.rendering_control.on_event = (
                            self._internal_handle_rendering_control_event
                        )
                        await self._event_handler.async_subscribe(
                            self.rendering_control,
                            timeout=timedelta(seconds=UPNP_TIMEOUT_TIME),
                        )
                        self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
                    if self.play_queue_service:
                        self.play_queue_service.on_event = (
                            self._internal_handle_play_queue_event
                        )
                        await self._event_handler.async_subscribe(
                            self.play_queue_service,
                            timeout=timedelta(seconds=UPNP_TIMEOUT_TIME),
                        )
                        self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
                    self.logger.info(
                        "Device %s: Subscribed to available UPnP service events.",
                        self.name,
                    )

                    self._start_polling()

                else:
                    self.logger.warning(
                        "Device %s: Notify server not started, cannot subscribe to service events.",
                        self.name,
                    )
            elif not self._event_handler:
                self.logger.warning(
                    "Device %s: No event handler (init failed), cannot subscribe to service events.",
                    self.name,
                )

            await self.async_update_http_status()
            if self._event_handler_started:
                await self._fetch_initial_upnp_states()

            self._available = True
            self.logger.info("Device %s: Finished service initialization.", self.name)
            return True

        except UpnpError as err:
            self.logger.warning(
                "Device %s: Error initializing UPnP aspects: %s", self.name, err
            )
            try:
                await self.async_update_http_status()
                self._available = False
                return False
            except WiimRequestException:
                self._available = False
                return False
        except WiimRequestException as err:
            self.logger.warning(
                "Device %s: Error fetching initial HTTP status: %s", self.name, err
            )
            self._available = False
            return False
        except Exception as err:
            self.logger.warning(
                "Device %s: Unexpected error during async_init_services_and_subscribe: %s",
                self.name,
                err,
                exc_info=True,
            )
            self._available = False
            return False

    async def _fetch_initial_upnp_states(self):
        """Fetch initial state from UPnP LastChange variables if possible."""
        # if the device supports GetStateVariable on LastChange.
        if self.rendering_control and self.rendering_control.has_state_variable(
            "LastChange"
        ):
            try:
                self.logger.debug(
                    "Device %s: RenderingControl has LastChange. Initial state will come via NOTIFY or HTTP.",
                    self.name,
                )
            except UpnpError as e:
                self.logger.debug(
                    "Device %s: Could not query initial RenderingControl LastChange: %s",
                    self.name,
                    e,
                )

        if self.av_transport and self.av_transport.has_state_variable("LastChange"):
            try:
                self.logger.debug(
                    "Device %s: AVTransport has LastChange. Initial state will come via NOTIFY or HTTP.",
                    self.name,
                )
            except UpnpError as e:
                self.logger.debug(
                    "Device %s: Could not query initial AVTransport LastChange: %s",
                    self.name,
                    e,
                )

    async def _renew_subscriptions(self) -> bool:
        """Renew UPnP event subscriptions."""
        if not self._event_handler or not self._event_handler_started:
            self.logger.warning(
                "Device %s: Event handler not available or not started, cannot renew subscriptions.",
                self.name,
            )
            self._available = False
            return False

        self.logger.debug("Device %s: Renewing UPnP subscriptions.", self.name)
        success_all = True
        try:
            if self.av_transport:
                await self._event_handler.async_resubscribe(self.av_transport)
                self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
        except UpnpError as err_av:
            self.logger.warning(
                "Device %s: Failed to renew AVTransport subscription: %s",
                self.name,
                err_av,
            )
            success_all = False

        try:
            if self.rendering_control:
                await self._event_handler.async_resubscribe(self.rendering_control)
                self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
        except UpnpError as err_rc:
            self.logger.warning(
                "Device %s: Failed to renew RenderingControl subscription: %s",
                self.name,
                err_rc,
            )
            success_all = False

        try:
            if self.play_queue_service:
                await self._event_handler.async_resubscribe(self.play_queue_service)
                self._schedule_subscription_renewal(UPNP_TIMEOUT_TIME)
        except UpnpError as err_pq:
            self.logger.warning(
                "Device %s: Failed to renew PlayQueue subscription: %s",
                self.name,
                err_pq,
            )
            success_all = False

        if success_all:
            self.logger.info(
                "Device %s: Successfully renewed UPnP subscriptions.", self.name
            )
            return True
        else:
            self.logger.warning(
                "Device %s: One or more UPnP subscriptions failed to renew.", self.name
            )
            if not (self.av_transport and self.av_transport.service_id) or not (
                self.rendering_control and self.rendering_control.service_id
            ):
                self.logger.warning(
                    "Device %s: Core AVT/RC subscriptions lost. Marking as unavailable.",
                    self.name,
                )

            if self._notify_server:
                try:
                    await self._notify_server.async_stop_server()
                    self._notify_server = None
                    self.logger.info(
                        "Device %s: AiohttpNotifyServer stopped.", self.name
                    )
                except Exception as err:
                    self.logger.warning(
                        "Device %s: Error stopping AiohttpNotifyServer: %s",
                        self.name,
                        err,
                        exc_info=True,
                    )
            self._available = False
            self._event_handler_started = False
            return False

    def _schedule_subscription_renewal(self, timeout: int) -> None:
        """Schedule the next subscription renewal."""
        renew_in = max(30, timeout - 60)
        self.logger.debug(
            "Device %s: Scheduling next subscription renewal in %s seconds.",
            self.name,
            renew_in,
        )
        if self._cancel_event_renewal:
            self._cancel_event_renewal.cancel()
        loop = asyncio.get_event_loop()
        self._cancel_event_renewal = loop.call_later(
            renew_in, lambda: asyncio.create_task(self._renew_subscriptions())
        )

    def _internal_handle_av_transport_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """Internal handler for AVTransport events, calls external callback."""
        self.logger.debug(
            "Device %s: Internal AVTransport event: %s", self.name, state_variables
        )
        if self.av_transport_event_callback:
            try:
                self.av_transport_event_callback(service, list(state_variables))
            except Exception as e:
                self.logger.warning(
                    "Device %s: Error in HA-provided av_transport_event_callback: %s",
                    self.name,
                    e,
                    exc_info=True,
                )

        temp_parsed_data = (
            parse_last_change_event(str(state_variables[0].value), self.logger)
            if state_variables and state_variables[0].name == "LastChange"
            else {}
        )
        if "TransportState" in temp_parsed_data:
            state_map = {
                "PLAYING": PlayingStatus.PLAYING,
                "PAUSED_PLAYBACK": PlayingStatus.PAUSED,
                "STOPPED": PlayingStatus.STOPPED,
                "TRANSITIONING": PlayingStatus.LOADING,
                "NO_MEDIA_PRESENT": PlayingStatus.STOPPED,
            }
            self.playing_status = state_map.get(
                temp_parsed_data["TransportState"], self.playing_status
            )

    def _internal_handle_rendering_control_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """Internal handler for RenderingControl events, calls external callback."""
        self.logger.debug(
            "Device %s: Internal RenderingControl event: %s", self.name, state_variables
        )
        if self.rendering_control_event_callback:
            try:
                self.rendering_control_event_callback(service, list(state_variables))
            except Exception as e:
                self.logger.warning(
                    "Device %s: Error in HA-provided rendering_control_event_callback: %s",
                    self.name,
                    e,
                    exc_info=True,
                )

        temp_parsed_data = (
            parse_last_change_event(str(state_variables[0].value), self.logger)
            if state_variables and state_variables[0].name == "LastChange"
            else {}
        )
        if "Volume" in temp_parsed_data:
            vol_data = temp_parsed_data["Volume"]
            if isinstance(vol_data, list) and vol_data:
                master_vol = next(
                    (
                        ch_vol
                        for ch_vol in vol_data
                        if ch_vol.get("channel") == "Master"
                    ),
                    None,
                )
                if master_vol and master_vol.get("val") is not None:
                    self.volume = int(master_vol.get("val"))
            elif isinstance(vol_data, dict) and vol_data.get("val") is not None:
                # self.volume = int(vol_data.get("val"))
                val = vol_data.get("val")
                self.volume = int(val) if val is not None else 0
        if "Mute" in temp_parsed_data:
            mute_data = temp_parsed_data["Mute"]
            if isinstance(mute_data, list) and mute_data:
                master_mute = next(
                    (
                        ch_mute
                        for ch_mute in mute_data
                        if ch_mute.get("channel") == "Master"
                    ),
                    None,
                )
                if master_mute and master_mute.get("val") is not None:
                    self.is_muted = master_mute.get("val") == "1"
            elif isinstance(mute_data, dict) and mute_data.get("val") is not None:
                self.is_muted = mute_data.get("val") == "1"

    def _internal_handle_play_queue_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """Internal handler for PlayQueue events, calls external callback."""
        self.logger.debug(
            "Device %s: Internal PlayQueue event: %s", self.name, state_variables
        )
        if self.play_queue_event_callback:
            try:
                self.play_queue_event_callback(service, list(state_variables))
            except Exception as e:
                self.logger.warning(
                    "Device %s: Error in HA-provided play_queue_event_callback: %s",
                    self.name,
                    e,
                    exc_info=True,
                )

    def _update_state_from_av_transport_event_data(self, event_data: Dict[str, Any]):
        """(Primarily for HTTP cache) Update device state based on parsed AVTransport event data."""
        # This method is now mostly for populating _player_properties from LastChange,
        if "TransportState" in event_data:
            state_map = {
                "PLAYING": PlayingStatus.PLAYING,
                "PAUSED_PLAYBACK": PlayingStatus.PAUSED,
                "STOPPED": PlayingStatus.STOPPED,
                "TRANSITIONING": PlayingStatus.LOADING,
                "NO_MEDIA_PRESENT": PlayingStatus.STOPPED,
            }
            self.playing_status = state_map.get(
                event_data["TransportState"], self.playing_status
            )
            self._player_properties[PlayerAttribute.PLAYING_STATUS] = (
                self.playing_status.value
            )

        if "CurrentTrackMetaData" in event_data:
            meta = event_data["CurrentTrackMetaData"]
            if isinstance(meta, dict):
                self.current_track_info["title"] = meta.get("title", "Unknown Title")
                self.current_track_info["artist"] = meta.get("artist", "Unknown Artist")
                self.current_track_info["album"] = meta.get("album", "Unknown Album")
                self.current_track_info["album_art_uri"] = self.make_absolute_url(
                    meta.get("albumArtURI")
                )
                self.current_track_info["uri"] = meta.get("res")

        if "CurrentTrackDuration" in event_data:
            self.current_track_duration = self.parse_duration(
                event_data["CurrentTrackDuration"]
            )
        if "RelativeTimePosition" in event_data:
            self.current_position = self.parse_duration(
                event_data["RelativeTimePosition"]
            )

        if "NextAVTransportURI" in event_data and event_data[
            "NextAVTransportURI"
        ] not in [None, "NOT_IMPLEMENTED", ""]:
            self.next_track_uri = event_data["NextAVTransportURI"]
        else:
            self.next_track_uri = None

        self._player_properties[PlayerAttribute.PLAYING_STATUS] = (
            self.playing_status.value
        )
        self._player_properties[PlayerAttribute.TITLE] = self.current_track_info.get(
            "title", ""
        )
        self._player_properties[PlayerAttribute.ARTIST] = self.current_track_info.get(
            "artist", ""
        )
        self._player_properties[PlayerAttribute.ALBUM] = self.current_track_info.get(
            "album", ""
        )
        self._player_properties[PlayerAttribute.TOTAL_LENGTH] = str(
            self.current_track_duration * 1000
        )
        self._player_properties[PlayerAttribute.CURRENT_POSITION] = str(
            self.current_position * 1000
        )

        self.logger.debug(
            "Device %s: Updated AVTransport state: Status=%s, Track=%s",
            self.name,
            self.playing_status,
            self.current_track_info.get("title"),
        )

    def _handle_rendering_control_event(
        self, service: UpnpService, state_variables: List[UpnpStateVariable]
    ) -> None:
        """Handle state variable changes for RenderingControl."""
        self.logger.debug(
            "Device %s: RenderingControl event: %s", self.name, state_variables
        )
        changed_vars = {
            sv.name: sv.value for sv in state_variables if sv.name == "LastChange"
        }
        if "LastChange" in changed_vars and changed_vars["LastChange"] is not None:
            event_data = parse_last_change_event(
                str(changed_vars["LastChange"]), self.logger
            )
            self._update_state_from_rendering_control_event_data(event_data)

    def _update_state_from_rendering_control_event_data(
        self, event_data: Dict[str, Any]
    ):
        """Update device state based on parsed RenderingControl event data."""
        if "Volume" in event_data:
            vol_data = event_data["Volume"]
            if isinstance(vol_data, list) and vol_data:
                master_vol = next(
                    (
                        ch_vol
                        for ch_vol in vol_data
                        if ch_vol.get("channel") == "Master"
                    ),
                    None,
                )
                if master_vol and master_vol.get("val") is not None:
                    try:
                        self.volume = int(master_vol.get("val"))
                    except ValueError:
                        self.logger.warning(
                            "Invalid volume value from event: %s", master_vol.get("val")
                        )
                elif vol_data[0].get("val") is not None:
                    try:
                        self.volume = int(vol_data[0].get("val"))
                    except ValueError:
                        self.logger.warning(
                            "Invalid volume value from event: %s",
                            vol_data[0].get("val"),
                        )
            elif isinstance(vol_data, dict) and vol_data.get("val") is not None:
                try:
                    # self.volume = int(vol_data.get("val"))
                    val = vol_data.get("val")
                    self.volume = int(val) if val is not None else 0
                except ValueError:
                    self.logger.warning(
                        "Invalid volume value from event: %s", vol_data.get("val")
                    )

        if "Mute" in event_data:
            mute_data = event_data["Mute"]
            if isinstance(mute_data, list) and mute_data:
                master_mute = next(
                    (
                        ch_mute
                        for ch_mute in mute_data
                        if ch_mute.get("channel") == "Master"
                    ),
                    None,
                )
                if master_mute and master_mute.get("val") is not None:
                    self.is_muted = master_mute.get("val") == "1" or master_mute.get(
                        "val"
                    )
                elif mute_data[0].get("val") is not None:
                    self.is_muted = mute_data[0].get("val") == "1" or mute_data[0].get(
                        "val"
                    )
            elif isinstance(mute_data, dict) and mute_data.get("val") is not None:
                # self.is_muted = mute_data.get("val") == "1" or mute_data.get("val")
                self.is_muted = mute_data.get("val") == "1"

        self._player_properties[PlayerAttribute.VOLUME] = str(self.volume)
        self._player_properties[PlayerAttribute.MUTED] = (
            MuteMode.MUTED if self.is_muted else MuteMode.UNMUTED
        )

        self.logger.debug(
            "Device %s: Updated RenderingControl state: Volume=%s, Muted=%s",
            self.name,
            self.volume,
            self.is_muted,
        )

    def _handle_play_queue_event(
        self, service: UpnpService, state_variables: List[UpnpStateVariable]
    ) -> None:
        """Handle state variable changes for the custom PlayQueue service."""
        self.logger.debug("Device %s: PlayQueue event: %s", self.name, state_variables)

    async def _http_request(
        self, command: WiimHttpCommand | str, params: str | None = None
    ) -> dict[str, Any]:
        """Make an HTTP request to the device."""
        if not self._http_api:
            raise WiimDeviceException(
                f"Device {self.name}: HTTP API endpoint not configured."
            )

        cmd_str = command.value if isinstance(command, WiimHttpCommand) else command
        full_command = cmd_str.format(params) if params else cmd_str

        try:
            return await self._http_api.json_request(full_command)
        except WiimRequestException as err:
            self.logger.warning(
                "Device %s: HTTP request failed for command %s: %s",
                self.name,
                full_command,
                err,
            )
            raise

    async def _http_command_ok(
        self, command: WiimHttpCommand | str, params: str | None = None
    ) -> None:
        """Make an HTTP request and expect 'OK'."""
        if not self._http_api:
            raise WiimDeviceException(
                f"Device {self.name}: HTTP API endpoint not configured."
            )

        cmd_str = command.value if isinstance(command, WiimHttpCommand) else command
        full_command = cmd_str.format(params) if params else cmd_str
        try:
            await self._http_api.request(full_command)
        except WiimRequestException as err:
            self.logger.warning(
                "Device %s: HTTP command_ok failed for %s: %s",
                self.name,
                full_command,
                err,
            )
            raise

    async def async_update_http_status(self) -> None:
        """Fetch device and player status via HTTP API."""
        if not self._http_api:
            self.logger.debug(
                "Device %s: No HTTP API, skipping HTTP status update.", self.name
            )
            return

        try:
            device_data = await self._http_request(WiimHttpCommand.DEVICE_STATUS)
            self._device_info_properties.update(
                cast(Dict[DeviceAttribute, str], device_data)
            )

            player_data = await self._http_request(WiimHttpCommand.PLAYER_STATUS)
            self._player_properties.update(
                cast(Dict[PlayerAttribute, str], player_data)
            )

            if PlayerAttribute.VOLUME in self._player_properties:
                try:
                    self.volume = int(self._player_properties[PlayerAttribute.VOLUME])
                except ValueError:
                    self.logger.warning(
                        "Invalid volume in HTTP status: %s",
                        self._player_properties[PlayerAttribute.VOLUME],
                    )

            if PlayerAttribute.MUTED in self._player_properties:
                self.is_muted = (
                    self._player_properties[PlayerAttribute.MUTED] == MuteMode.MUTED
                )

            http_playing_status_str = self._player_properties.get(
                PlayerAttribute.PLAYING_STATUS
            )
            if http_playing_status_str:
                try:
                    ps = PlayerStatus(http_playing_status_str)
                    http_playing_status = _PLAYER_TO_PLAYING.get(
                        ps, PlayingStatus.UNKNOWN
                    )
                    # http_playing_status = PlayingStatus(http_playing_status_str)
                    # if self.playing_status in [
                    #     PlayingStatus.STOPPED,
                    #     PlayingStatus.LOADING,
                    #     None,
                    # ] or (
                    #     http_playing_status == PlayingStatus.STOPPED
                    #     and self.playing_status != PlayingStatus.STOPPED
                    # ):
                    #     self.playing_status = http_playing_status
                    if self.playing_status != http_playing_status:
                        self.playing_status = http_playing_status
                except ValueError:
                    self.logger.warning(
                        "Invalid playing_status in HTTP status: %s",
                        http_playing_status_str,
                    )

            def get_input_mode_from_playing_mode(value: str) -> InputMode:
                try:
                    playing_mode = PlayingMode(value)
                except ValueError:
                    return InputMode.WIFI

                return PLAYING_TO_INPUT_MAP.get(playing_mode, InputMode.WIFI)

            http_play_mode_str = self._player_properties.get(
                PlayerAttribute.PLAYBACK_MODE
            )
            if http_play_mode_str:
                try:
                    self.play_mode = get_input_mode_from_playing_mode(
                        http_play_mode_str
                    ).display_name  # type: ignore[attr-defined]
                except ValueError:
                    self.logger.warning(
                        "Invalid playback_mode in HTTP status: %s", http_play_mode_str
                    )

            http_loop_mode_str = self._player_properties.get(
                PlayerAttribute.PLAYLIST_MODE
            )
            if http_loop_mode_str:
                try:
                    self.loop_mode = LoopMode(int(http_loop_mode_str))
                except ValueError:
                    self.logger.warning(
                        "Invalid playback_mode in HTTP status: %s", http_play_mode_str
                    )

            http_name = self._device_info_properties.get(DeviceAttribute.DEVICE_NAME)
            if http_name and http_name != self._name:
                self.logger.info(
                    "Device %s: Name updated via HTTP from '%s' to '%s'",
                    self._udn,
                    self._name,
                    http_name,
                )
                self._name = http_name

            project_id = self._device_info_properties.get(DeviceAttribute.PROJECT)
            if project_id:
                manufacturer, model = get_info_from_project(project_id)
                self._manufacturer = manufacturer
                self._model_name = model

        except WiimRequestException as err:
            self.logger.warning(
                "Device %s: Failed to update status via HTTP: %s", self.name, err
            )
            raise
        except ValueError as err:
            self.logger.warning(
                "Device %s: Error parsing HTTP status data: %s. Player Data: %s, Device Data: %s",
                self.name,
                err,
                self._player_properties,
                self._device_info_properties,
            )

    async def _invoke_upnp_action(
        self, service_name: str, action_name: str, **kwargs
    ) -> dict:
        """Helper to invoke a UPnP action."""
        service: UpnpService | None = None
        if service_name == "AVTransport" and self.av_transport:
            service = self.av_transport
        elif service_name == "RenderingControl" and self.rendering_control:
            service = self.rendering_control
        elif service_name == "PlayQueue" and self.play_queue_service:
            service = self.play_queue_service

        if not service:
            raise WiimDeviceException(
                f"Device {self.name}: Service {service_name} is not available or not initialized."
            )

        if not hasattr(service, "has_action") or not service.has_action(action_name):
            raise WiimDeviceException(
                f"Device {self.name}: Service {service_name} has no action {action_name}"
            )

        action = service.action(action_name)
        try:
            self.logger.debug(
                "Device %s: Invoking UPnP Action %s.%s with %s",
                self.name,
                service_name,
                action_name,
                kwargs,
            )
            if "InstanceID" not in kwargs:
                kwargs["InstanceID"] = 0
            result = await action.async_call(**kwargs)
            self.logger.debug(
                "Device %s: UPnP Action %s.%s result: %s",
                self.name,
                service_name,
                action_name,
                result,
            )
            return result  # type: ignore
        except UpnpError as err:
            self.logger.warning(
                "Device %s: UPnP action %s.%s failed: %s",
                self.name,
                service_name,
                action_name,
                err,
            )
            raise WiimDeviceException(
                f"UPnP action {action_name} failed: {err}"
            ) from err

    async def async_play(
        self, uri: str | None = None, metadata: str | None = None
    ) -> None:
        """
        Start playback. If URI is provided, plays that URI. Otherwise, resumes.
        Metadata is typically DIDL-Lite XML string.
        """
        if uri:
            didl_metadata = (
                metadata
                or '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="1"><dc:title>Unknown</dc:title><upnp:class>object.item.audioItem.musicTrack</upnp:class></item></DIDL-Lite>'
            )
            await self._invoke_upnp_action(
                "AVTransport",
                "SetAVTransportURI",
                CurrentURI=uri,
                CurrentURIMetaData=didl_metadata,
            )
        await self._invoke_upnp_action("AVTransport", "Play", Speed="1")
        self.playing_status = PlayingStatus.PLAYING

    async def async_pause(self) -> None:
        """Pause playback."""
        await self._invoke_upnp_action("AVTransport", "Pause")
        self.playing_status = PlayingStatus.PAUSED

    async def async_stop(self) -> None:
        """Stop playback."""
        await self._invoke_upnp_action("AVTransport", "Stop")
        self.playing_status = PlayingStatus.STOPPED

    async def async_next(self) -> None:
        """Play next track."""
        await self._invoke_upnp_action("AVTransport", "Next")

    async def async_previous(self) -> None:
        """Play previous track."""
        await self._invoke_upnp_action("AVTransport", "Previous")

    async def async_seek(self, position_seconds: int) -> None:
        """Seek to a position in the current track (in seconds)."""
        time_str = self._format_duration(position_seconds)
        await self._invoke_upnp_action(
            "AVTransport", "Seek", Unit="REL_TIME", Target=time_str
        )

    async def async_set_volume(self, volume_percent: int) -> None:
        """Set volume (0-100)."""
        if not 0 <= volume_percent <= 100:
            self.logger.warning(
                "Attempted to set volume outside 0-100 range: %s", volume_percent
            )
            volume_percent = max(0, min(100, volume_percent))
        await self._invoke_upnp_action(
            "RenderingControl",
            "SetVolume",
            Channel="Master",
            DesiredVolume=volume_percent,
        )
        self.volume = volume_percent

    async def async_set_mute(self, mute: bool) -> None:
        """Set mute state."""
        await self._invoke_upnp_action(
            "RenderingControl",
            "SetMute",
            Channel="Master",
            DesiredMute=mute,
        )
        self.is_muted = mute

    async def async_set_AVT_cmd(self, cmd: str) -> dict[str, Any]:
        """Set common AVT cmd."""
        result = await self._invoke_upnp_action("AVTransport", cmd)
        return result

    async def async_set_play_mode(self, input_mode: str) -> None:
        """Set the playback source/mode using HTTP API."""
        DISPLAY_TO_COMMAND = {
            mode.display_name: mode.command_name  # type: ignore[attr-defined]
            for mode in InputMode  # type: ignore[attr-defined]
        }

        http_mode_val = DISPLAY_TO_COMMAND[input_mode]
        if http_mode_val and self._http_api:
            try:
                await self._http_command_ok(WiimHttpCommand.SWITCH_MODE, http_mode_val)
                self.play_mode = input_mode
            except WiimRequestException as e:
                self.logger.warning(
                    "Device %s: Failed to set play mode to %s via HTTP: %s",
                    self.name,
                    input_mode,
                    e,
                )
                raise
        elif not self._http_api:
            self.logger.warning(
                "Device %s: HTTP API unavailable, cannot set play mode %s.",
                self.name,
                input_mode,
            )
            raise WiimDeviceException(
                f"HTTP API unavailable to set play mode {input_mode}"
            )
        else:
            self.logger.warning(
                "Device %s: No HTTP command mapping for play mode %s.",
                self.name,
                input_mode,
            )
            raise WiimDeviceException(
                f"Cannot set play mode {input_mode} without HTTP mapping."
            )

    async def async_set_output_mode(self, output_mode: str) -> None:
        DISPLAY_TO_COMMAND = {mode.display_name: mode.cmd for mode in AudioOutputHwMode}  # type: ignore[attr-defined]

        http_mode_val = DISPLAY_TO_COMMAND[output_mode]
        if any(key in self._udn for key in AUDIO_AUX_MODE_IDS) and http_mode_val == 7:
            http_mode_val = 2
        if http_mode_val > 0 and http_mode_val != 64 and self._http_api:
            try:
                await self._http_command_ok(
                    WiimHttpCommand.AUDIO_OUTPUT_HW_MODE_SET, http_mode_val
                )
            except WiimRequestException as e:
                self.logger.warning(
                    "Device %s: Failed to set output mode to %s via HTTP: %s",
                    self.name,
                    output_mode,
                    e,
                )
                raise
        elif http_mode_val == 64:
            self.logger.debug("other mode no action.")
        elif not self._http_api:
            self.logger.warning(
                "Device %s: HTTP API unavailable, cannot set output mode %s.",
                self.name,
                output_mode,
            )
            raise WiimDeviceException(
                f"HTTP API unavailable to set output mode {output_mode}"
            )
        else:
            self.logger.warning(
                "Device %s: No HTTP command mapping for output mode %s.",
                self.name,
                output_mode,
            )
            raise WiimDeviceException(
                f"Cannot set output mode {output_mode} without HTTP mapping."
            )

    async def async_set_loop_mode(self, loop: LoopMode) -> None:
        """Set loop/repeat mode using UPnP."""
        await self._invoke_upnp_action(
            "PlayQueue", "SetQueueLoopMode", LoopMode=int(loop)
        )
        self.loop_mode = loop

    async def async_play_queue_with_index(self, index: int) -> None:
        """Set loop/repeat mode using UPnP."""
        await self._invoke_upnp_action(
            "PlayQueue", "PlayQueueWithIndex", QueueName="CurrentQueue", Index=index
        )

    async def async_set_equalizer_mode(self, eq_mode: EqualizerMode) -> None:
        """Set equalizer mode using HTTP API."""
        if self._manufacturer == MANUFACTURER_WIIM and self._http_api:
            try:
                # if eq_mode == EqualizerMode.NONE:
                #     await self._http_command_ok(WiimHttpCommand.WIIM_EQUALIZER_OFF)
                # else:
                #     await self._http_command_ok(
                #         WiimHttpCommand.WIIM_EQ_LOAD, eq_mode.value
                #     )
                self.equalizer_mode = eq_mode
                self._custom_player_properties[PlayerAttribute.EQUALIZER_MODE] = (
                    eq_mode.value
                )
                return
            except WiimRequestException as e:
                self.logger.warning(
                    "Device %s: Failed to set WiiM EQ mode to %s via HTTP: %s",
                    self.name,
                    eq_mode.value,
                    e,
                )
                raise

        self.logger.warning(
            "Device %s: Set equalizer mode %s not supported or HTTP API unavailable.",
            self.name,
            eq_mode.value,
        )
        raise WiimDeviceException(
            f"Set equalizer mode {eq_mode.value} not supported or HTTP API unavailable."
        )

    async def async_get_favorites(self) -> list:
        """Get Presets from the PlayQueue service (speculative)."""
        if not self.play_queue_service:
            self.logger.warning(
                "Device %s: PlayQueue service not available.", self.name
            )
            return []
        try:
            result = await self._invoke_upnp_action("PlayQueue", "GetKeyMapping")
            return self._parse_preset_data(result.get("QueueContext", ""))
        except WiimDeviceException:
            return []

    def _parse_preset_data(self, xml_str: str) -> list:
        """Parse queue data from PlayQueue service (needs actual format)."""
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            self.logger.warning("Failed to parse KeyList XML: %s", e)
            return []

        results = []
        for key_elem in root:
            tag = key_elem.tag
            if not tag.startswith("Key"):
                continue

            try:
                idx = int(tag[3:])
            except ValueError:
                continue

            name = key_elem.findtext("Name", default="")
            url = key_elem.findtext("PicUrl", default="")

            if not name and not url:
                continue

            results.append({"uri": str(idx), "name": name, "image_url": url})

        return results

    async def async_get_queue_items(self) -> list:
        """Get items from the PlayQueue service (speculative)."""
        if not self.play_queue_service:
            self.logger.warning(
                "Device %s: PlayQueue service not available.", self.name
            )
            return []
        try:
            result = await self._invoke_upnp_action(
                "PlayQueue", "BrowseQueue", QueueName="CurrentQueue"
            )
            return self._parse_queue_data(result.get("QueueContext", ""))
        except WiimDeviceException:
            return []

    def _parse_queue_data(self, xml_str: str) -> list:
        """Parse queue data from PlayQueue service (needs actual format)."""
        self.logger.debug("Device %s: Parsing queue data.", self.name)
        try:
            root = ET.fromstring(xml_str)
            tracks_elem = root.find("Tracks")
            if tracks_elem is None:
                self.logger.debug("tracks is null")
                return []

            results = []
            didl_ns = {
                "didl": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
                "dc": "http://purl.org/dc/elements/1.1/",
                "upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/",
            }

            list_info_element = root.find("ListInfo")
            # Find the <SourceName> element within <ListInfo>
            if list_info_element is not None:
                source_name_element = list_info_element.find("SourceName")
                if source_name_element is not None:
                    results.append({"SourceName": source_name_element.text})

            for idx, track_elem in enumerate(tracks_elem, start=1):
                metadata_raw = track_elem.findtext("Metadata")
                if not metadata_raw:
                    self.logger.debug("metadata_raw is null")
                    continue

                metadata_xml = unescape(metadata_raw)
                self.logger.debug("metadata_xml is %s", metadata_xml)

                try:
                    didl_root = ET.fromstring(metadata_xml)
                except ET.ParseError:
                    self.logger.warning("Failed to parse DIDL-Lite for track #%d", idx)
                    continue

                item_elem = didl_root.find("didl:item", namespaces=didl_ns)
                if item_elem is None:
                    self.logger.debug("item_elem is null")
                    continue

                title = item_elem.findtext("dc:title", default="", namespaces=didl_ns)
                album_art = item_elem.findtext(
                    "upnp:albumArtURI", default="", namespaces=didl_ns
                )

                results.append({"uri": str(idx), "name": title, "image_url": album_art})

            return results

        except ET.ParseError as e:
            self.logger.warning("Failed to parse queue XML: %s", e)
            return []

    @property
    def name(self) -> str:
        """Return the name of the device."""
        # Ensure _device_info_properties is initialized before accessing
        if hasattr(self, "_device_info_properties") and self._device_info_properties:
            http_name = self._device_info_properties.get(DeviceAttribute.DEVICE_NAME)
            if http_name:
                return http_name
        return self._name

    @property
    def udn(self) -> str:
        """Return the UDN (Unique Device Name) of the device."""
        return self._udn

    @property
    def model_name(self) -> str:
        """Return the model name of the device."""
        if hasattr(self, "_device_info_properties") and self._device_info_properties:
            project_id = self._device_info_properties.get(DeviceAttribute.PROJECT)
            if project_id:
                _, model = get_info_from_project(project_id)
                if model != "WiiM":
                    return model
        return (
            self.upnp_device.model_name
            if hasattr(self.upnp_device, "model_name") and self.upnp_device.model_name
            else "WiiM Device"
        )

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version from HTTP API."""
        if hasattr(self, "_device_info_properties") and self._device_info_properties:
            return self._device_info_properties.get(DeviceAttribute.FIRMWARE)
        return None

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if (
            self.upnp_device
            and hasattr(self.upnp_device, "device_url")
            and self.upnp_device.device_url
        ):
            try:
                return urlparse(self.upnp_device.device_url).hostname
            except ValueError:
                pass
        if self._http_api:
            try:
                return urlparse(str(self._http_api)).hostname
            except ValueError:
                pass
        return None

    @property
    def http_api_url(self) -> str | None:
        """Return the base URL for the HTTP API if configured."""
        return str(self._http_api) if self._http_api else None

    @property
    def available(self) -> bool:
        """Return True if the device is considered available."""
        upnp_dev_available = True
        if hasattr(self.upnp_device, "available"):
            upnp_dev_available = self.upnp_device.available
        self.logger.debug(
            "Device self available = %s, upnp avaliable = %s.",
            self._available,
            upnp_dev_available,
        )
        return self._available and upnp_dev_available

    @property
    def album_art_uri(self) -> str | None:
        """Return the current track's album art URI."""
        return self.current_track_info.get("album_art_uri")

    @property
    def manufacturer(self) -> str | None:
        return self._manufacturer

    @property
    def model(self) -> str | None:
        return self._model_name

    @property
    def presentation_url(self) -> str | None:
        return self._presentation_url

    @property
    def supports_http_api(self) -> bool:
        return self._http_api is not None

    @property
    def available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    async def get_audio_output_hw_mode(self) -> str | None:
        return await self._http_request(WiimHttpCommand.AUDIO_OUTPUT_HW_MODE)

    async def play_preset(self, preset: int) -> None:
        if not self.supports_http_api:
            raise RuntimeError("HTTP API not supported")
        await self._http_command_ok(WiimHttpCommand.PLAY_PRESET, str(preset))

    async def ensure_subscriptions(self) -> None:
        ok = await self._renew_subscriptions()
        if not ok:
            self._available = True
            await self.async_init_services_and_subscribe()
            await self._renew_subscriptions()

    async def play_preset(self, preset: int) -> None:
        if not self.supports_http_api:
            raise RuntimeError("HTTP API not supported")
        await self._http_command_ok(
            WiimHttpCommand.PLAY_PRESET, str(preset)
        )

    async def play_url(self, url: str) -> None:
        if not self.supports_http_api:
            raise RuntimeError("HTTP API not supported")
        await self._http_command_ok(
            WiimHttpCommand.PLAY, url
        )

    @property
    def album_art_url(self) -> str | None:
        return self._album_art_url

    def parse_duration(self, time_str: str | None) -> int:
        """Parse HH:MM:SS or HH:MM:SS.mmm duration string to seconds."""
        if not time_str:
            return 0
        if time_str.upper() == "NOT_IMPLEMENTED" or not time_str.strip():
            return 0

        parts = time_str.split(".")[0].split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 1:
                return int(parts[0])
        except ValueError:
            self.logger.warning("Could not parse duration string: '%s'", time_str)
            return 0
        self.logger.warning("Unhandled duration string format: '%s'", time_str)
        return 0

    def _format_duration(self, seconds: int) -> str:
        """Format seconds into HH:MM:SS string."""
        if not isinstance(seconds, (int, float)) or seconds < 0:
            seconds = 0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}"

    def make_absolute_url(self, relative_url: str | None) -> str | None:
        """Convert a relative URL from UPnP metadata to an absolute one."""
        if not relative_url:
            return None

        base_for_url_join = None
        if (
            self.upnp_device
            and hasattr(self.upnp_device, "device_url")
            and self.upnp_device.device_url
        ):
            base_for_url_join = self.upnp_device.device_url
        elif (
            self.upnp_device
            and hasattr(self.upnp_device, "presentation_url")
            and self.upnp_device.presentation_url
        ):
            base_for_url_join = self.upnp_device.presentation_url
        elif self.http_api_url:
            base_for_url_join = self.http_api_url

        if base_for_url_join:
            try:
                return urljoin(base_for_url_join, relative_url)
            except ValueError as e:
                self.logger.warning(
                    "Could not join URL '%s' with base '%s': %s",
                    relative_url,
                    base_for_url_join,
                    e,
                )
                return relative_url

        self.logger.debug(
            "Cannot make URL absolute: No base URL available for relative path %s",
            relative_url,
        )
        if urlparse(relative_url).scheme and urlparse(relative_url).netloc:
            return relative_url
        return None

    async def disconnect(self) -> None:
        """Clean up resources, unsubscribe from events."""
        self.logger.info(
            "Device %s: Disconnecting...", self.name
        )  # self.name is safe here
        if self._cancel_event_renewal:
            self._cancel_event_renewal.cancel()
            self._cancel_event_renewal = None

        await self.async_stop_polling()

        if self._event_handler and self._event_handler_started:
            try:
                if (
                    self.av_transport
                    and hasattr(self.av_transport, "event_subscription_sid")
                    and self.av_transport.event_subscription_sid
                ):
                    await self._event_handler.async_unsubscribe(self.av_transport)
                if (
                    self.rendering_control
                    and hasattr(self.rendering_control, "event_subscription_sid")
                    and self.rendering_control.event_subscription_sid
                ):
                    await self._event_handler.async_unsubscribe(self.rendering_control)
                if (
                    self.play_queue_service
                    and hasattr(self.play_queue_service, "event_subscription_sid")
                    and self.play_queue_service.event_subscription_sid
                ):
                    await self._event_handler.async_unsubscribe(self.play_queue_service)
            except UpnpError as err:
                self.logger.warning(
                    "Device %s: Error during UPnP unsubscribe: %s", self.name, err
                )
            except Exception as err:
                self.logger.warning(
                    "Device %s: Unexpected error during UPnP unsubscribe: %s",
                    self.name,
                    err,
                    exc_info=True,
                )

        if self._notify_server:
            try:
                await self._notify_server.async_stop_server()
                self._notify_server = None
                self.logger.info("Device %s: AiohttpNotifyServer stopped.", self.name)
            except Exception as err:
                self.logger.warning(
                    "Device %s: Error stopping AiohttpNotifyServer: %s",
                    self.name,
                    err,
                    exc_info=True,
                )

        self._event_handler_started = False
        self._available = False

    def _format_time_for_sync(self) -> str:
        """Helper to format current time for TIMESYNC HTTP command."""
        import time

        return time.strftime("%Y%m%d%H%M%S")

    async def _async_polling_loop(self) -> None:
        """
        Background task to periodically poll the device's status for availability.
        If the device is configured for HTTP API, it will use DEVICE_STATUS command.
        """
        self.logger.debug(
            "Device %s: Starting availability polling loop with interval %s seconds.",
            self.name,
            self._polling_interval,
        )
        while True:
            try:
                await asyncio.sleep(self._polling_interval)

                if not self._http_api:
                    self.logger.debug(
                        "Device %s: HTTP API not available for polling. Marking as unavailable.",
                        self.name,
                    )
                    if self._available:
                        self._available = False
                    continue

                await self._http_request(WiimHttpCommand.DEVICE_STATUS)

                if not self._available:
                    self.logger.info(
                        "Device %s: Polling successful, marking as available = %s.",
                        self.name,
                        self._available,
                    )
                    if self.general_event_callback:
                        self.general_event_callback(self)

            except WiimRequestException as e:
                if self._available:
                    self.logger.warning(
                        "Device %s: Polling failed (HTTP error: %s). Marking as unavailable and disconnecting.",
                        self.name,
                        e,
                    )

                    # await self.disconnect()

                    if self.general_event_callback:
                        # asyncio.create_task(self.general_event_callback(self))
                        self.general_event_callback(self)
                    # self._available = False

                else:
                    self.logger.debug(
                        "Device %s: Polling failed again while already unavailable: %s",
                        self.name,
                        e,
                    )
            except asyncio.CancelledError:
                self.logger.debug("Polling loop for %s cancelled.", self.name)
                break
            except Exception as e:
                self.logger.warning(
                    "Device %s: Unexpected error in polling loop: %s",
                    self.name,
                    e,
                    exc_info=True,
                )
                if self._available:
                    self.logger.warning(
                        "Device %s: Unexpected error during polling. Marking as unavailable and disconnecting.",
                        self.name,
                    )

                    # await self.disconnect()

                    if self.general_event_callback:
                        self.general_event_callback(self)
                    # self._available = False

    def _start_polling(self) -> None:
        """Ensure the polling task is running; if not, start it and attach restart callback."""
        if self._polling_task is None or self._polling_task.done():
            self.logger.debug(
                "Device %s: Starting availability polling task.", self.name
            )
            self._polling_task = asyncio.create_task(self._async_polling_loop())
            self._polling_task.add_done_callback(self._on_polling_done)

    def _on_polling_done(self, fut: asyncio.Task) -> None:
        """Called whenever the polling task finishes."""
        # try:
        #     exc = fut.exception()
        #     if exc:
        #         self.logger.warning(
        #             "Device %s: Polling task terminated with exception: %s",
        #             self.name,
        #             exc,
        #         )
        # except asyncio.CancelledError:
        #     self.logger.debug("Device %s: Polling task was cancelled.", self.name)
        self.logger.info("Device %s: Restarting polling task.", self.name)
        # asyncio.get_running_loop().call_later(1, self._start_polling)

    async def async_stop_polling(self) -> None:
        """Clean up on unloading the integration."""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._polling_task

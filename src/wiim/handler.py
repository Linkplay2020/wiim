import xml.etree.ElementTree as ET
from typing import Any, Dict
import logging


def parse_last_change_event(xml_text: str, logger: logging.Logger) -> Dict[str, Any]:
    """
    Parses the LastChange event XML from UPnP services.
    AVTransport and RenderingControl typically use this.
    The XML structure is <Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/">
                         <InstanceID val="0">
                           <Volume channel="Master" val="50"/>
                           <Mute channel="Master" val="0"/>
                         </InstanceID>
                       </Event>
    or for AVTransport:
                       <Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
                         <InstanceID val="0">
                           <TransportState val="PLAYING"/>
                           <CurrentTrackMetaData val="&lt;DIDL-Lite ...&gt;"/>
                         </InstanceID>
                       </Event>
    """
    changed_variables: Dict[str, Any] = {}
    try:
        # Remove default namespace for easier parsing if present
        xml_text = xml_text.replace(
            ' xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/"', ""
        )
        xml_text = xml_text.replace(
            ' xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"', ""
        )
        xml_text = xml_text.replace(
            ' xmlns="urn:schemas-wiimu-com:metadata-1-0/PlayQueue/"', ""
        )

        root = ET.fromstring(xml_text)
        instance_id_node = root.find("InstanceID") or root.find("QueueID")
        if instance_id_node is None:
            logger.warning(
                "No InstanceID found in LastChange event XML: %s", xml_text[:200]
            )
            return changed_variables

        for child in instance_id_node:
            variable_name = child.tag
            value = child.get("val")
            channel = child.get("channel")

            if variable_name == "Volume" or variable_name == "Mute":
                if variable_name not in changed_variables:
                    changed_variables[variable_name] = []
                channel_data = {"val": value}
                if channel:
                    channel_data["channel"] = channel
                changed_variables[variable_name].append(channel_data)
            elif (
                variable_name == "CurrentTrackMetaData"
                or variable_name == "AVTransportURIMetaData"
                or variable_name == "NextAVTransportURIMetaData"
            ):
                # These are often DIDL-Lite XML strings themselves.
                # Basic parsing here, more complex parsing might be needed.
                try:
                    if value is None:
                        continue
                    didl_root = ET.fromstring(value)
                    item_node = didl_root.find(
                        ".//{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item"
                    )
                    if item_node is not None:
                        meta: Dict[str, Any] = {}
                        title_node = item_node.find(
                            "{http://purl.org/dc/elements/1.1/}title"
                        )
                        if title_node is not None:
                            meta["title"] = title_node.text
                        artist_node = item_node.find(
                            "{urn:schemas-upnp-org:metadata-1-0/upnp/}artist"
                        )
                        if artist_node is not None:
                            meta["artist"] = artist_node.text
                        album_node = item_node.find(
                            "{urn:schemas-upnp-org:metadata-1-0/upnp/}album"
                        )
                        if album_node is not None:
                            meta["album"] = album_node.text
                        art_node = item_node.find(
                            "{urn:schemas-upnp-org:metadata-1-0/upnp/}albumArtURI"
                        )
                        if art_node is not None:
                            meta["albumArtURI"] = art_node.text
                        res_node = item_node.find(
                            ".//{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res"
                        )
                        if res_node is not None:
                            meta["res"] = res_node.text
                            meta["duration"] = res_node.get("duration")
                        changed_variables[variable_name] = meta
                    else:
                        changed_variables[variable_name] = (
                            value  # Store raw if not parsable as DIDL
                        )
                except ET.ParseError:
                    if value:
                        logger.debug(
                            "Failed to parse metadata XML for %s: %s",
                            variable_name,
                            value[:100],
                        )
                    changed_variables[variable_name] = value  # Store raw XML
            elif variable_name == "LoopMpde" or variable_name == "LoopMode":
                # interpret as integer if possible
                try:
                    changed_variables[variable_name] = (
                        int(value) if value is not None else 4
                    )
                except ValueError:
                    changed_variables[variable_name] = 4
            else:
                changed_variables[variable_name] = value
        logger.debug("Parsed LastChange event: %s", changed_variables)
    except ET.ParseError as e:
        logger.error(
            "Error parsing LastChange event XML: %s\nXML: %s", e, xml_text[:500]
        )  # Log more XML on error
    return changed_variables

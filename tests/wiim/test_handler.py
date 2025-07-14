# test_handler.py
import logging
from wiim.handler import parse_last_change_event


class TestHandler:
    """Tests for UPnP event parsing functions."""

    DUMMY_LOGGER = logging.getLogger("dummy_test_logger")

    def test_parse_last_change_volume_mute(self):
        """Test parsing of a RenderingControl event for Volume and Mute."""
        xml_text = """
        <Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/">
            <InstanceID val="0">
                <Volume channel="Master" val="42"/>
                <Mute channel="Master" val="0"/>
            </InstanceID>
        </Event>
        """
        expected = {
            "Volume": [{"val": "42", "channel": "Master"}],
            "Mute": [{"val": "0", "channel": "Master"}],
        }
        assert parse_last_change_event(xml_text, self.DUMMY_LOGGER) == expected

    def test_parse_last_change_transport_state(self):
        """Test parsing of an AVTransport event for TransportState."""
        xml_text = """
        <Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
            <InstanceID val="0">
                <TransportState val="PLAYING"/>
            </InstanceID>
        </Event>
        """
        expected = {"TransportState": "PLAYING"}
        assert parse_last_change_event(xml_text, self.DUMMY_LOGGER) == expected

    def test_parse_last_change_metadata(self):
        """Test parsing of an AVTransport event containing DIDL-Lite metadata."""
        didl_lite_xml = "&lt;DIDL-Lite xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot; xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot;&gt;&lt;item id=&quot;0&quot;&gt;&lt;dc:title&gt;My Song&lt;/dc:title&gt;&lt;upnp:artist&gt;My Artist&lt;/upnp:artist&gt;&lt;upnp:album&gt;My Album&lt;/upnp:album&gt;&lt;upnp:albumArtURI&gt;/art.jpg&lt;/upnp:albumArtURI&gt;&lt;res duration=&quot;0:04:20&quot;&gt;http://server/song.mp3&lt;/res&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;"
        xml_text = f"""
        <Event>
            <InstanceID val="0">
                <CurrentTrackMetaData val="{didl_lite_xml}"/>
            </InstanceID>
        </Event>
        """
        parsed = parse_last_change_event(xml_text, self.DUMMY_LOGGER)

        assert "CurrentTrackMetaData" in parsed
        metadata = parsed["CurrentTrackMetaData"]
        assert metadata["title"] == "My Song"
        assert metadata["artist"] == "My Artist"
        assert metadata["album"] == "My Album"
        assert metadata["albumArtURI"] == "/art.jpg"
        assert metadata["res"] == "http://server/song.mp3"
        assert metadata["duration"] == "0:04:20"

    def test_parse_invalid_xml_returns_empty_dict(self):
        """Test that malformed XML does not crash the parser."""
        xml_text = "<Event><InvalidXML"
        assert parse_last_change_event(xml_text, self.DUMMY_LOGGER) == {}

    def test_parse_no_instance_id_returns_empty_dict(self):
        """Test that XML without an <InstanceID> tag is handled gracefully."""
        xml_text = '<Event><SomeOtherTag val="1"/></Event>'
        assert parse_last_change_event(xml_text, self.DUMMY_LOGGER) == {}

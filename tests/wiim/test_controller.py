# test_controller.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from wiim.controller import WiimController
from wiim.wiim_device import WiimDevice
from wiim.consts import WiimHttpCommand, MultiroomAttribute


class TestWiimController:
    """Tests for the WiimController class."""

    @pytest.mark.asyncio
    async def test_add_and_remove_device(self, mock_session, mock_wiim_device):
        """Test basic device management."""
        controller = WiimController(mock_session)

        # Add device
        await controller.add_device(mock_wiim_device)
        assert len(controller.devices) == 1
        assert controller.get_device(mock_wiim_device.udn) == mock_wiim_device

        # Remove device
        await controller.remove_device(mock_wiim_device.udn)
        assert len(controller.devices) == 0
        mock_wiim_device.disconnect.assert_called_once()

    def test_restore_full_udn(self, mock_session):
        """Test the helper function that reconstructs a full UDN from a short UUID."""
        controller = WiimController(mock_session)
        short_uuid = "1234567890abcdef1234567890abcdef"
        expected_udn = "uuid:12345678-90ab-cdef-1234-567890abcdef12345678"

        restored_udn = controller._restore_full_udn(short_uuid, "any_leader_udn")
        assert restored_udn == expected_udn

    @pytest.mark.asyncio
    async def test_async_update_multiroom_status(self, mock_session, mock_wiim_device):
        """Test parsing of multiroom group status from a leader's HTTP response."""
        controller = WiimController(mock_session)

        # Arrange: Create mock leader and follower devices
        leader = mock_wiim_device
        leader.udn = "uuid:11111111-2222-3333-4444-555555555555"
        leader.name = "Leader"
        # leader._http_request = AsyncMock()

        follower = MagicMock(spec=WiimDevice)
        follower.udn = "uuid:66666666-7777-8888-9999-aaaaaaaa66666666"
        follower.name = "Follower"
        follower._http_api = AsyncMock()
        follower._http_request = AsyncMock()

        await controller.add_device(leader)
        await controller.add_device(follower)

        # Mock the HTTP response from the leader device
        multiroom_response = {
            MultiroomAttribute.NUM_FOLLOWERS: "1",
            MultiroomAttribute.FOLLOWER_LIST: [
                {
                    MultiroomAttribute.UUID: "66666666777788889999aaaaaaaa"  # The short UUID
                }
            ],
        }
        leader._http_request.return_value = multiroom_response

        # Act
        await controller.async_update_multiroom_status(leader)

        # Assert: Check if the internal group map was updated correctly
        assert leader.udn in controller._multiroom_groups
        assert controller._multiroom_groups[leader.udn] == [follower.udn]

    def test_get_device_group_info(self, mock_session):
        """Test the function that determines a device's role in a group."""
        controller = WiimController(mock_session)
        controller._multiroom_groups = {"leader_udn": ["follower_udn"]}
        controller._devices = {
            "leader_udn": MagicMock(),
            "follower_udn": MagicMock(),
            "standalone_udn": MagicMock(),
        }

        assert controller.get_device_group_info("leader_udn") == {
            "role": "leader",
            "leader_udn": "leader_udn",
        }
        assert controller.get_device_group_info("follower_udn") == {
            "role": "follower",
            "leader_udn": "leader_udn",
        }
        assert controller.get_device_group_info("standalone_udn") == {
            "role": "standalone",
            "leader_udn": "standalone_udn",
        }
        assert controller.get_device_group_info("unknown_udn") is None

    @pytest.mark.asyncio
    async def test_async_join_group(self, mock_session, mock_wiim_device):
        """Test that the join group command is sent to the correct device (the follower)."""
        controller = WiimController(mock_session)

        leader = mock_wiim_device
        leader.udn = "uuid:leader-udn-full-1111-1111-111111111111"
        leader.ip_address = "192.168.1.100"

        follower = MagicMock(spec=WiimDevice)
        follower.udn = "uuid:follower-udn"
        follower.ip_address = "192.168.1.101"
        follower._http_command_ok = AsyncMock()
        follower._http_api = AsyncMock()

        await controller.add_device(leader)
        await controller.add_device(follower)

        formatted_udn = "leaderudnfull111111111111"
        with patch.object(controller, "_restore_full_udn", return_value=leader.udn):
            await controller.async_join_group(leader.udn, follower.udn)

            expected_command = WiimHttpCommand.MULTIROOM_JOIN.format(
                leader.ip_address, formatted_udn
            )
            follower._http_command_ok.assert_called_with(expected_command)

    @pytest.mark.asyncio
    async def test_async_ungroup_device_as_leader(self, mock_session, mock_wiim_device):
        """Test that ungrouping a leader disbands the whole group."""
        controller = WiimController(mock_session)
        leader = mock_wiim_device
        leader.udn = "leader_udn"

        await controller.add_device(leader)
        controller._multiroom_groups = {"leader_udn": ["follower_udn"]}

        await controller.async_ungroup_device("leader_udn")

        # Assert: The leader sends the UNGROUP command
        leader._http_command_ok.assert_called_with(WiimHttpCommand.MULTIROOM_UNGROUP)
        # Assert: The group is removed from controller's internal state
        assert "leader_udn" not in controller._multiroom_groups

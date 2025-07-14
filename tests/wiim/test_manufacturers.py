# test_manufacturers.py

from wiim.manufacturers import (
    get_info_from_project,
    MANUFACTURER_WIIM,
    MODELS_WIIM_PRO,
    MODELS_GENERIC,
)


class TestManufacturers:
    """Tests for the manufacturer and model lookup functions."""

    def test_get_info_from_known_project(self):
        """
        Test that a known project ID returns the correct manufacturer and model.
        """
        project_id = "WiiM_Pro_with_gc4a"
        manufacturer, model = get_info_from_project(project_id)
        assert manufacturer == MANUFACTURER_WIIM
        assert model == MODELS_WIIM_PRO

    def test_get_info_from_unknown_project(self):
        """
        Test that an unknown project ID returns the default manufacturer and a generic model.
        """
        project_id = "An_Unknown_Project_ID_12345"
        manufacturer, model = get_info_from_project(project_id)
        assert manufacturer == MANUFACTURER_WIIM
        assert model == MODELS_GENERIC

    def test_get_info_from_empty_project(self):
        """
        Test that an empty project string returns the default/generic info.
        """
        project_id = ""
        manufacturer, model = get_info_from_project(project_id)
        assert manufacturer == MANUFACTURER_WIIM
        assert model == MODELS_GENERIC

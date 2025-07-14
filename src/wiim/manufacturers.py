"""Manufacturers and their devices for the WiiM component."""

from typing import Final


MANUFACTURER_WIIM: Final[str] = "Linkplay"
MODELS_WIIM_AMP: Final[str] = "WiiM Amp"
MODELS_WIIM_MINI: Final[str] = "WiiM Mini"
MODELS_WIIM_PRO: Final[str] = "WiiM Pro"
MODELS_WIIM_PRO_PLUS: Final[str] = "WiiM Pro Plus"
MODELS_WIIM_AMP_PRO: Final[str] = "WiiM Amp Pro"
MODELS_WIIM_ULTRA: Final[str] = "WiiM Ultra"
MODELS_WIIM_AMP_ULTRA: Final[str] = "WiiM Amp Ultra"
MODELS_WIIM_CI_MOD_S: Final[str] = "WiiM CI MOD S"
MODELS_WIIM_CI_MOD_A80: Final[str] = "WiiM CI MOD A80"
MODELS_GENERIC: Final[str] = "WiiM"

PROJECTID_LOOKUP: Final[dict[str, tuple[str, str]]] = {
    "WiiM_Amp_4layer": (MANUFACTURER_WIIM, MODELS_WIIM_AMP),
    "WiiM_Pro_with_gc4a": (MANUFACTURER_WIIM, MODELS_WIIM_PRO),
    "Muzo_Mini": (MANUFACTURER_WIIM, MODELS_WIIM_MINI),
    "WiiM_Pro_Plus": (MANUFACTURER_WIIM, MODELS_WIIM_PRO_PLUS),
    "WiiM_Amp_Pro": (MANUFACTURER_WIIM, MODELS_WIIM_AMP_PRO),
    "WiiM_Ultra": (MANUFACTURER_WIIM, MODELS_WIIM_ULTRA),
    "WiiM_Amp_Ultra": (MANUFACTURER_WIIM, MODELS_WIIM_AMP_ULTRA),
    "WiiM_CI_MOD_S": (MANUFACTURER_WIIM, MODELS_WIIM_CI_MOD_S),
    "WiiM_CI_MOD_A80": (MANUFACTURER_WIIM, MODELS_WIIM_CI_MOD_A80),
}


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    return PROJECTID_LOOKUP.get(project, (MANUFACTURER_WIIM, MODELS_GENERIC))

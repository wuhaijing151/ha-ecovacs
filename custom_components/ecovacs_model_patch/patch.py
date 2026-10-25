"""Alias device classes that deebot_client does not know to supported ones.

``deebot_client`` resolves a device class by importing
``deebot_client.hardware.<device_class>`` (see ``deebot_client.hardware``).
When that module does not exist the device is reported as unsupported and the
official ``ecovacs`` integration creates no entities at all.

This module registers an in-memory module under that name so the lookup
succeeds.  ``StaticDeviceInfo`` only carries a data type plus the device
capabilities, therefore reusing a sibling's ``get_device_info()`` is complete --
no other state depends on the module name.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import pkgutil
import sys
import types

_LOGGER = logging.getLogger(__name__)

HARDWARE_PACKAGE = "deebot_client.hardware"


def supported_classes() -> set[str]:
    """Return every device class the installed deebot_client ships."""
    try:
        from deebot_client import hardware
    except ImportError:  # pragma: no cover - ecovacs integration missing
        return set()

    return {
        name
        for _, name, _ in pkgutil.iter_modules(hardware.__path__)
        if not name.startswith("_")
    }


def module_available(device_class: str) -> bool:
    """Return True when deebot_client already handles this device class."""
    try:
        return importlib.util.find_spec(f"{HARDWARE_PACKAGE}.{device_class}") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def install_alias(device_class: str, sibling: str) -> bool:
    """Make ``deebot_client.hardware.<device_class>`` resolve to ``sibling``.

    Returns True when the alias is in place.
    """
    full_name = f"{HARDWARE_PACKAGE}.{device_class}"
    if full_name in sys.modules:
        return True

    try:
        source = importlib.import_module(f"{HARDWARE_PACKAGE}.{sibling}")
    except (ImportError, ModuleNotFoundError) as err:
        _LOGGER.error(
            "Sibling device class %s is not available in deebot_client: %s",
            sibling,
            err,
        )
        return False

    shim = types.ModuleType(full_name)
    shim.__doc__ = (
        f"Alias of {HARDWARE_PACKAGE}.{sibling}. Created at runtime because "
        "upstream deebot_client does not support this device class yet."
    )
    shim.get_device_info = source.get_device_info  # type: ignore[attr-defined]
    sys.modules[full_name] = shim

    # The lookup caches negative results, drop ours so a retry will succeed.
    try:
        from deebot_client import hardware

        hardware._NOT_FOUND.discard(device_class)  # noqa: SLF001
    except (ImportError, AttributeError):  # pragma: no cover - defensive
        pass

    _LOGGER.warning(
        "Device class %s is unknown to deebot_client and is now handled like %s",
        device_class,
        sibling,
    )
    return True


def remove_alias(device_class: str) -> None:
    """Drop a runtime alias (used when deebot_client catches up upstream)."""
    sys.modules.pop(f"{HARDWARE_PACKAGE}.{device_class}", None)
    try:
        from deebot_client import hardware

        hardware._NOT_FOUND.add(device_class)  # noqa: SLF001
    except (ImportError, AttributeError):  # pragma: no cover - defensive
        pass
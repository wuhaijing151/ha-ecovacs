"""Patch the official Ecovacs integration for models unknown to deebot_client.

The official ``ecovacs`` integration asks ``deebot_client`` for the static
capabilities of every device found in the Ecovacs cloud.  That lookup is an
import of ``deebot_client.hardware.<device_class>``; when the module is missing
the device is dropped as *not supported*, no entities are created and
previously registered entities stay behind as unavailable ghosts.

Newer models (for example the DEEBOT T30 MAX, class ``wc8lnp``) are missing
upstream and upstream only accepts manual contributions.  This integration
bridges the gap at runtime, without touching any installed file:

1. it detects the device classes that deebot_client cannot handle -- taken from
   the running Ecovacs controller and from the devices of the account;
2. it reads the Ecovacs product IoT map and scores every *supported* class
   against the unsupported one (same ``name``/``UILogicId`` first, exactly like
   upstream ``scripts/check_for_similar_models.py``, then the model family such
   as ``t30`` and ``smartType``);
3. it registers an in-memory alias module for the unsupported class reusing the
   sibling's ``get_device_info()`` -- ``StaticDeviceInfo`` only carries the data
   type plus capabilities, so the alias is complete;
4. it reloads the Ecovacs config entry so the vacuum shows up immediately.

Detection results are cached in ``<config>/ecovacs_model_patch_cache.json`` and
a full diagnostics report is written to
``<config>/ecovacs_model_patch_report.json``.

中文说明见 https://gitee.com/wuhaijing151/ha-ecovacs
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .cloud import async_get_unsupported_classes
from .const import (
    CACHE_FILE,
    CONF_ENABLED,
    CONF_HARDWARE_OVERRIDE,
    CONF_REDISCOVER,
    CONF_WATCH,
    DEFAULT_WATCH,
    DOMAIN,
    ECOVACS_DOMAIN,
    ISSUE_NO_SIBLING,
    REPORT_FILE,
    SERVICE_REFRESH,
)
from .discovery import async_discover
from .patch import install_alias, module_available, supported_classes

_LOGGER = logging.getLogger(__name__)

LEARN_MORE_URL = "https://gitee.com/wuhaijing151/ha-ecovacs"

#: ``ecovacs_model_patch:`` without a value is the documented "just add one
#: line" configuration, so None must be accepted next to a full mapping.
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Any(
            None,
            vol.Schema(
                {
                    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
                    vol.Optional(CONF_WATCH): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(CONF_HARDWARE_OVERRIDE): {cv.string: cv.string},
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _async_read_cache(hass: HomeAssistant) -> dict[str, str]:
    """Read the cache file without blocking the event loop."""

    def _read() -> dict[str, str]:
        try:
            with open(hass.config.path(CACHE_FILE), encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as err:
            _LOGGER.warning("Cannot read %s: %s", CACHE_FILE, err)
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    return await hass.async_add_executor_job(_read)


async def _async_write_json(
    hass: HomeAssistant, name: str, payload: Any
) -> None:
    """Write a diagnostics file without blocking the event loop."""

    def _write() -> None:
        with open(hass.config.path(name), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)

    try:
        await hass.async_add_executor_job(_write)
    except OSError as err:  # pragma: no cover - best effort diagnostics
        _LOGGER.warning("Cannot write %s: %s", name, err)


async def _async_detect_targets(hass: HomeAssistant) -> dict[str, str]:
    """Return {device class: where it was found} for unsupported devices."""
    targets: dict[str, str] = {}

    for entry in hass.config_entries.async_entries(ECOVACS_DOMAIN):
        # ``runtime_data`` is the Ecovacs controller and its ``devices``
        # attribute holds deebot_client's Devices dataclass.
        runtime = getattr(entry, "runtime_data", None)
        devices = getattr(runtime, "devices", runtime)
        for device in getattr(devices, "not_supported", None) or []:
            data = getattr(device, "api", device)
            if isinstance(data, dict) and (device_class := data.get("class")):
                targets.setdefault(str(device_class), "ecovacs controller")

    for device_class, name in (await async_get_unsupported_classes(hass)).items():
        targets.setdefault(device_class, f"ecovacs cloud ({name})")

    return targets


async def _async_reload_ecovacs(hass: HomeAssistant) -> None:
    """Reload the Ecovacs config entries so entities are created."""
    await asyncio.sleep(2)
    for entry in list(hass.config_entries.async_entries(ECOVACS_DOMAIN)):
        try:
            await hass.config_entries.async_reload(entry.entry_id)
            _LOGGER.warning("Reloaded Ecovacs config entry %s", entry.entry_id)
        except Exception as err:  # noqa: BLE001 - never break start up
            _LOGGER.error(
                "Could not reload Ecovacs config entry %s: %s", entry.entry_id, err
            )


async def _async_apply(
    hass: HomeAssistant, *, rediscover: bool, reload_entry: bool
) -> dict[str, Any]:
    """Detect, patch and (optionally) reload the Ecovacs integration."""
    options: dict[str, Any] = hass.data.get(DOMAIN, {}).get("options", {})
    watch = [str(item) for item in options.get(CONF_WATCH) or DEFAULT_WATCH]
    overrides = {
        str(key): str(value)
        for key, value in (options.get(CONF_HARDWARE_OVERRIDE) or {}).items()
    }

    detected = await _async_detect_targets(hass)
    targets = list(dict.fromkeys([*watch, *detected]))

    cache = await _async_read_cache(hass)
    mapping: dict[str, str] = {}
    sources: dict[str, str] = {}
    pending: list[str] = []

    for device_class in targets:
        if device_class in overrides:
            mapping[device_class] = overrides[device_class]
            sources[device_class] = "configuration"
        elif not rediscover and device_class in cache:
            mapping[device_class] = cache[device_class]
            sources[device_class] = "cache"
        else:
            pending.append(device_class)

    report: dict[str, Any] = {}
    if pending:
        found, report = await async_discover(hass, pending)
        mapping.update(found)
        for device_class in found:
            sources[device_class] = "detected"
        if found:
            cache.update(found)
            await _async_write_json(hass, CACHE_FILE, cache)

    installed: list[str] = []
    for device_class, sibling in mapping.items():
        if device_class not in overrides and module_available(device_class):
            _LOGGER.warning(
                "deebot_client now supports %s - the runtime patch is not needed",
                device_class,
            )
            continue
        if install_alias(device_class, sibling):
            installed.append(device_class)
            ir.async_delete_issue(
                hass, DOMAIN, ISSUE_NO_SIBLING.format(device_class=device_class)
            )

    unresolved = [device_class for device_class in targets if device_class not in mapping]
    for device_class in unresolved:
        product = (
            report.get("devices", {}).get(device_class, {}).get("product") or {}
        )
        try:
            ir.async_create_issue(
                hass,
                DOMAIN,
                ISSUE_NO_SIBLING.format(device_class=device_class),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="no_sibling_found",
                translation_placeholders={
                    "device_class": device_class,
                    "product": str(
                        product.get("name") or product.get("model") or device_class
                    ),
                },
                learn_more_url=LEARN_MORE_URL,
            )
        except Exception as err:  # noqa: BLE001 - a repair issue is nice to have
            _LOGGER.debug("Could not create a repair issue for %s: %s", device_class, err)

    result: dict[str, Any] = {
        "generated": dt_util.utcnow().isoformat(),
        "ecovacs_entries": len(hass.config_entries.async_entries(ECOVACS_DOMAIN)),
        "deebot_client_class_count": len(supported_classes()),
        "targets": sources,
        "mapping": mapping,
        "unresolved": unresolved,
        "installed": installed,
    }
    if report:
        result["discovery"] = report
    await _async_write_json(hass, REPORT_FILE, result)

    if installed:
        if reload_entry:
            await _async_reload_ecovacs(hass)
        _LOGGER.warning(
            "Runtime patch active: %s",
            ", ".join(f"{item} -> {mapping[item]}" for item in installed),
        )

    return result


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from configuration.yaml."""
    conf = config.get(DOMAIN) or {}
    if not conf.get(CONF_ENABLED, True):
        _LOGGER.warning("Disabled in configuration.yaml - nothing to do")
        return True

    if not supported_classes():
        _LOGGER.error(
            "deebot_client was not found. Please install/enable the official "
            "'Ecovacs' integration first."
        )
        return True

    hass.data.setdefault(DOMAIN, {})["options"] = {
        CONF_WATCH: list(conf.get(CONF_WATCH) or DEFAULT_WATCH),
        CONF_HARDWARE_OVERRIDE: dict(conf.get(CONF_HARDWARE_OVERRIDE) or {}),
    }

    async def _handle_refresh(call: ServiceCall) -> None:
        """Re-run detection and reload the Ecovacs integration."""
        result = await _async_apply(
            hass,
            rediscover=bool(call.data.get(CONF_REDISCOVER)),
            reload_entry=True,
        )
        _LOGGER.info(
            "Refresh finished: installed=%s unresolved=%s",
            result["installed"] or "none",
            result["unresolved"] or "none",
        )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)

    async def _async_started(_event: Any) -> None:
        await _async_apply(hass, rediscover=False, reload_entry=True)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_started)
    return True
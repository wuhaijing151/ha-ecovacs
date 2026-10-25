"""Access to the Ecovacs cloud through deebot_client.

The official integration already holds an authenticated ``ApiClient``; reusing
it avoids parsing credentials a second time.  When the integration is not
loaded (for example because its setup failed) an own client is created from the
config entry data and torn down afterwards.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from homeassistant.const import CONF_COUNTRY, CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import ECOVACS_DOMAIN

_LOGGER = logging.getLogger(__name__)


def _live_client(hass: HomeAssistant) -> Any | None:
    """Return the authenticated client of a running Ecovacs config entry."""
    for entry in hass.config_entries.async_entries(ECOVACS_DOMAIN):
        client = getattr(getattr(entry, "runtime_data", None), "_api_client", None)
        if client is not None:
            return client
    return None


@contextlib.asynccontextmanager
async def async_api_client(hass: HomeAssistant) -> AsyncIterator[Any | None]:
    """Yield an authenticated deebot_client ApiClient (or None)."""
    if (client := _live_client(hass)) is not None:
        yield client
        return

    try:
        from deebot_client.api_client import ApiClient
        from deebot_client.authentication import Authenticator, create_rest_config
        from deebot_client.util import md5
        from homeassistant.components.ecovacs.const import CONF_OVERRIDE_REST_URL
        from homeassistant.helpers import aiohttp_client
    except ImportError as err:  # pragma: no cover - ecovacs integration missing
        _LOGGER.error("deebot_client is unavailable: %s", err)
        yield None
        return

    for entry in hass.config_entries.async_entries(ECOVACS_DOMAIN):
        data = dict(entry.data)
        try:
            rest = create_rest_config(
                aiohttp_client.async_get_clientsession(hass),
                device_id=data[CONF_DEVICE_ID],
                alpha_2_country=data[CONF_COUNTRY],
                override_rest_url=data.get(CONF_OVERRIDE_REST_URL),
            )
            authenticator = Authenticator(
                rest, data[CONF_USERNAME], md5(data[CONF_PASSWORD])
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Cannot build an Ecovacs client: %s", err)
            continue

        try:
            yield ApiClient(authenticator)
        finally:
            await authenticator.teardown()
        return

    yield None


async def async_get_iot_map(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the Ecovacs product IoT map (device class -> product)."""
    async with async_api_client(hass) as client:
        if client is None:
            return {}
        try:
            return await client.get_product_iot_map() or {}
        except Exception as err:  # noqa: BLE001 - cloud errors must not break setup
            _LOGGER.warning("Could not fetch the Ecovacs product list: %s", err)
            return {}


async def async_get_device_classes(hass: HomeAssistant) -> set[str]:
    """Return the device classes bound to the account."""
    async with async_api_client(hass) as client:
        if client is None:
            return set()
        try:
            devices = await client.get_devices() or []
        except Exception as err:  # noqa: BLE001 - cloud errors must not break setup
            _LOGGER.warning("Could not fetch the Ecovacs device list: %s", err)
            return set()

    classes: set[str] = set()
    for device in devices:
        if isinstance(device, dict) and (device_class := device.get("class")):
            classes.add(str(device_class))
    return classes
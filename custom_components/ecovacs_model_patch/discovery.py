"""Find the supported device class that is closest to an unsupported one.

Upstream deebot_client groups hardware-identical models by the ``name`` and
``UILogicId`` fields of the Ecovacs product IoT map, which is exactly what
``scripts/check_for_similar_models.py`` does in the upstream repository.

Unsupported models usually have no such twin yet (that is why they are
unsupported), so this module adds weaker criteria -- the model family
(``t30max_cn_h_t30h5`` -> ``t30``) and ``smartType`` -- and scores every
candidate to pick the most plausible supported model.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant

from .cloud import async_get_iot_map
from .const import MIN_SCORE
from .patch import async_supported_classes

_LOGGER = logging.getLogger(__name__)

_FAMILY_RE = re.compile(r"^([a-z]{1,4}\d{1,4})")

#: Similarity weights.  A candidate needs MIN_SCORE points to be accepted.
_WEIGHT_NAME = 1000
_WEIGHT_UILOGIC = 900
_WEIGHT_FAMILY = 400
_WEIGHT_MODEL = 300
_WEIGHT_SMART_TYPE = 100


def _family(product: dict[str, Any]) -> str:
    """Model family token, e.g. ``T30_MAX_AUTO`` / ``t30max_cn_h_t30h5`` -> t30."""
    for key in ("model", "UILogicId", "name"):
        value = str(product.get(key) or "").lower()
        if match := _FAMILY_RE.match(value):
            return match.group(1)
    return ""


def _summarise(device_class: str, product: dict[str, Any] | None) -> dict[str, Any]:
    """Return the interesting fields of a product entry."""
    if not product:
        return {"class": device_class}
    return {
        "class": device_class,
        "name": product.get("name"),
        "model": product.get("model"),
        "UILogicId": product.get("UILogicId"),
        "smartType": product.get("smartType"),
        "materialNo": product.get("materialNo"),
    }


def _score(wanted: dict[str, Any], other: dict[str, Any]) -> tuple[int, list[str]]:
    """Score how similar two products are."""
    score = 0
    reasons: list[str] = []

    if wanted.get("name") and wanted.get("name") == other.get("name"):
        score += _WEIGHT_NAME
        reasons.append("same name")
    if wanted.get("UILogicId") and wanted.get("UILogicId") == other.get("UILogicId"):
        score += _WEIGHT_UILOGIC
        reasons.append("same UILogicId")
    if family := _family(wanted):
        if family == _family(other):
            score += _WEIGHT_FAMILY
            reasons.append(f"same family {family}")
    if wanted.get("model") and wanted.get("model") == other.get("model"):
        score += _WEIGHT_MODEL
        reasons.append("same model")
    if wanted.get("smartType") and wanted.get("smartType") == other.get("smartType"):
        score += _WEIGHT_SMART_TYPE
        reasons.append("same smartType")

    return score, reasons


async def async_discover(
    hass: HomeAssistant, wanted: Iterable[str]
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return {unsupported class: supported sibling} plus a diagnostics report."""
    wanted = [str(item) for item in wanted]
    known = await async_supported_classes(hass)
    report: dict[str, Any] = {
        "supported_class_count": len(known),
        "devices": {},
    }
    mapping: dict[str, str] = {}

    iot_map = await async_get_iot_map(hass)
    report["iot_map_available"] = bool(iot_map)
    if not iot_map:
        return mapping, report

    for device_class in wanted:
        product = iot_map.get(device_class)
        entry: dict[str, Any] = {
            "product": _summarise(device_class, product),
            "family": _family(product) if product else "",
            "same_product": [],
            "ranked": [],
            "picked": None,
            "picked_reason": [],
        }
        report["devices"][device_class] = entry
        if not product:
            _LOGGER.warning(
                "Device class %s is not listed in the Ecovacs product list", device_class
            )
            continue

        ranked: list[dict[str, Any]] = []
        same_product: list[str] = []
        for other, other_product in iot_map.items():
            if other == device_class or not isinstance(other_product, dict):
                continue
            score, reasons = _score(product, other_product)
            if other_product.get("name") == product.get("name") or other_product.get(
                "UILogicId"
            ) == product.get("UILogicId"):
                same_product.append(other)
            if score:
                ranked.append(
                    {
                        "score": score,
                        "why": reasons,
                        "supported": other in known,
                        **_summarise(other, other_product),
                    }
                )

        ranked.sort(key=lambda item: (-item["score"], not item["supported"], item["class"]))
        entry["same_product"] = sorted(same_product)
        entry["ranked"] = ranked[:20]

        best = next(
            (item for item in ranked if item["supported"] and item["score"] >= MIN_SCORE),
            None,
        )
        if best is None:
            _LOGGER.warning(
                "No supported model is similar enough to %s (%s). Candidates: %s",
                device_class,
                entry["product"].get("name") or "unknown name",
                ", ".join(
                    f"{item['class']}({item.get('model') or item.get('name')})"
                    for item in ranked[:5]
                )
                or "none",
            )
            continue

        entry["picked"] = best["class"]
        entry["picked_reason"] = best["why"]
        mapping[device_class] = best["class"]
        _LOGGER.debug(
            "Matched %s with %s (%s)", device_class, best["class"], ", ".join(best["why"])
        )

    return mapping, report
"""Constants for the Ecovacs model patch integration.

Author: 吴海晶 <https://gitee.com/wuhaijing151>
Repository: https://gitee.com/wuhaijing151/ha-ecovacs
"""

from __future__ import annotations

DOMAIN = "ecovacs_model_patch"

#: Domain of the official Ecovacs integration this component patches.
ECOVACS_DOMAIN = "ecovacs"

#: configuration.yaml options
CONF_ENABLED = "enabled"
CONF_WATCH = "watch"
CONF_HARDWARE_OVERRIDE = "hardware_override"
CONF_REDISCOVER = "rediscover"

#: Services
SERVICE_REFRESH = "refresh"

#: Diagnostics written into the Home Assistant configuration directory.
CACHE_FILE = f"{DOMAIN}_cache.json"
REPORT_FILE = f"{DOMAIN}_report.json"

#: A sibling model is only accepted when it reaches this similarity score.
#: "same family" alone scores 400, "same smartType" alone only 100, so a
#: candidate from another model family is never picked by accident.
MIN_SCORE = 400

#: Device classes patched in addition to the automatically detected ones.
DEFAULT_WATCH: tuple[str, ...] = ()

ISSUE_NO_SIBLING = "no_sibling_found_{device_class}"
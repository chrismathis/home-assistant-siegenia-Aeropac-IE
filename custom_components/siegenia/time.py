from __future__ import annotations

import datetime
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DATA_CLIENT, DATA_COORDINATOR
from .device import build_device_info

def _combined(data: dict | None) -> dict:
    data = data or {}
    merged = {}
    for key in ("state", "params", "info"):
        v = data.get(key) or {}
        if isinstance(v, dict):
            merged.update(v)
    return merged

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    d = _combined(coord.data)
    entities: list[TimeEntity] = []

    timer = d.get("timer")
    if isinstance(timer, dict):
        if "poweron_time" in timer:
            entities.append(SiegeniaTimeEntity(coord, entry, "poweron_time", "start_time"))
        if "duration" in timer:
            entities.append(SiegeniaTimeEntity(coord, entry, "duration", "timer_duration"))

    if entities:
        async_add_entities(entities, True)

class SiegeniaTimeEntity(CoordinatorEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, key: str, translation_key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        self._attr_translation_key = translation_key
        slug = key.lower().replace("_", "-").replace(".", "-")
        self._attr_unique_id = f"{entry.entry_id}-{slug}"
        if key == "duration":
            self._attr_icon = "mdi:timer-sand"
        else:
            self._attr_icon = "mdi:clock-start"

    def _get_system_name(self) -> str | None:
        """Get the system name from device info."""
        if custom_name := self._entry.data.get("name"):
            return custom_name
        data = self.coordinator.data or {}
        for part in ("state", "params", "info"):
            d = data.get(part) or {}
            if isinstance(d, dict):
                system_name = d.get("systemname") or d.get("device_name")
                if system_name:
                    return system_name
        return None

    @property
    def device_info(self):
        return build_device_info(
            self.coordinator.data, 
            self._entry.entry_id, 
            self._entry.data.get("host"),
            self._entry.data.get("name")
        )

    def _d(self) -> dict:
        return _combined(self.coordinator.data)

    @property
    def native_value(self) -> datetime.time | None:
        d = self._d()
        timer = d.get("timer")
        if not isinstance(timer, dict):
            return None
        time_obj = timer.get(self._key)
        if not isinstance(time_obj, dict):
            return None
        try:
            h = int(time_obj.get("hour", 0))
            m = int(time_obj.get("minute", 0))
            return datetime.time(hour=h, minute=m)
        except Exception:
            return None

    async def async_set_value(self, value: datetime.time) -> None:
        # Construct the partial timer payload
        payload = {
            "timer": {
                self._key: {
                    "hour": value.hour,
                    "minute": value.minute
                }
            }
        }
        await self._client.set_device_params(payload)
        await self.coordinator.async_request_refresh()

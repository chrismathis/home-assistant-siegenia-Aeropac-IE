from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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
    entities: list[SwitchEntity] = []

    if "ecomode" in d:
        entities.append(SiegeniaSilentSwitch(hass, entry))
    if "ecotimer" in d:
        entities.append(SiegeniaSilentTimerSwitch(hass, entry))

    timer = d.get("timer")
    if isinstance(timer, dict):
        if "enabled" in timer:
            entities.append(SiegeniaTimerSwitch(hass, entry, "enabled", "Timer Enabled", "mdi:timer"))
        if "repeat" in timer:
            entities.append(SiegeniaTimerSwitch(hass, entry, "repeat", "Timer Repeat", "mdi:timer-sync"))

    if entities:
        async_add_entities(entities, True)


class SiegeniaSilentSwitch(CoordinatorEntity, SwitchEntity):
    _attr_icon = "mdi:volume-mute"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        super().__init__(coord)
        self._client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        self._entry = entry
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Silent Mode" if system_name else "Siegenia Silent Mode"
        self._attr_unique_id = f"{entry.entry_id}-ecomode"

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
    def is_on(self) -> bool:
        return bool(self._d().get("ecomode", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"ecomode": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"ecomode": False})
        await self.coordinator.async_request_refresh()


class SiegeniaSilentTimerSwitch(CoordinatorEntity, SwitchEntity):
    _attr_icon = "mdi:clock-mute"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        super().__init__(coord)
        self._client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        self._entry = entry
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Silent Timer" if system_name else "Siegenia Silent Timer"
        self._attr_unique_id = f"{entry.entry_id}-ecotimer"

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
    def is_on(self) -> bool:
        return bool(self._d().get("ecotimer", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"ecotimer": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"ecotimer": False})
        await self.coordinator.async_request_refresh()


class SiegeniaTimerSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, key: str, name_suffix: str, icon: str) -> None:
        coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        super().__init__(coord)
        self._client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        self._entry = entry
        self._key = key
        self._attr_icon = icon
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} {name_suffix}" if system_name else f"Siegenia {name_suffix}"
        slug = key.lower().replace("_", "-").replace(".", "-")
        self._attr_unique_id = f"{entry.entry_id}-timer-{slug}"

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
    def is_on(self) -> bool:
        timer = self._d().get("timer")
        if isinstance(timer, dict):
            return bool(timer.get(self._key, False))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"timer": {self._key: True}})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._client.set_device_params({"timer": {self._key: False}})
        await self.coordinator.async_request_refresh()
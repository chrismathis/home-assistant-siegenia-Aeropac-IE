from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
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
    entities: list[SelectEntity] = []

    if "fanmode" in d:
        entities.append(SiegeniaFanModeSelect(coord, entry))

    if "fanmirror" in d:
        entities.append(SiegeniaFanMirrorSelect(coord, entry))

    if "slave_fandirection" in d:
        entities.append(SiegeniaSlaveFanDirectionSelect(coord, entry))

    if "bathcontrolmodeactive" in d:
        entities.append(SiegeniaBathControlActiveSelect(coord, entry))

    if "bathcontrolmodepassive" in d:
        entities.append(SiegeniaBathControlPassiveSelect(coord, entry))

    if "ecomode_start" in d:
        entities.append(SiegeniaSilentTimerTimeSelect(coord, entry, "ecomode_start", "Silent Timer ON"))

    if "ecomode_end" in d:
        entities.append(SiegeniaSilentTimerTimeSelect(coord, entry, "ecomode_end", "Silent Timer OFF"))

    if entities:
        async_add_entities(entities, True)


class SiegeniaFanModeSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:fan-clock"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Fan Mode" if system_name else "Siegenia Fan Mode"
        self._attr_unique_id = f"{entry.entry_id}-fanmode"

        # Determine options based on device type:
        # Type 8: Aerotube: ["IN", "OUT", "IN_OUT", "AUTO"]
        # Type 14: Aeroplus: ["IN", "OUT", "IN_OUT", "IN_OUT_WRG", "AUTO"]
        d = _combined(coordinator.data)
        dev_type = d.get("type")
        if dev_type == 8:
            self._attr_options = ["IN", "OUT", "IN_OUT", "AUTO"]
        elif dev_type == 14:
            self._attr_options = ["IN", "OUT", "IN_OUT", "IN_OUT_WRG", "AUTO"]
        else:
            self._attr_options = ["IN", "OUT", "IN_OUT", "AUTO"]

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get("fanmode")
        if val in self._attr_options:
            return val
        return None

    async def async_select_option(self, option: str) -> None:
        await self._client.set_device_params({"fanmode": option})
        await self.coordinator.async_request_refresh()


class SiegeniaFanMirrorSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:reflect-horizontal"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Fan Mirror Mode" if system_name else "Siegenia Fan Mirror Mode"
        self._attr_unique_id = f"{entry.entry_id}-fanmirror"
        self._attr_options = ["Slave mode", "Slave must mirror", "Slave must copy"]
        self._mapping = {
            "Slave mode": 0,
            "Slave must mirror": 1,
            "Slave must copy": 2,
        }
        self._reverse_mapping = {v: k for k, v in self._mapping.items()}

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get("fanmirror")
        if val is not None:
            try:
                return self._reverse_mapping.get(int(val))
            except Exception:
                pass
        return None

    async def async_select_option(self, option: str) -> None:
        if (val := self._mapping.get(option)) is not None:
            await self._client.set_device_params({"fanmirror": val})
            await self.coordinator.async_request_refresh()


class SiegeniaSlaveFanDirectionSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:arrow-split-vertical"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Slave Fan Direction" if system_name else "Siegenia Slave Fan Direction"
        self._attr_unique_id = f"{entry.entry_id}-slave-fandirection"
        self._attr_options = ["Slave supply air", "Slave exhaust air"]
        self._mapping = {
            "Slave supply air": 1,
            "Slave exhaust air": 2,
        }
        self._reverse_mapping = {v: k for k, v in self._mapping.items()}

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get("slave_fandirection")
        if val is not None:
            try:
                return self._reverse_mapping.get(int(val))
            except Exception:
                pass
        return None

    async def async_select_option(self, option: str) -> None:
        if (val := self._mapping.get(option)) is not None:
            await self._client.set_device_params({"slave_fandirection": val})
            await self.coordinator.async_request_refresh()


class SiegeniaBathControlActiveSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:water"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Bath Control Active Mode" if system_name else "Siegenia Bath Control Active Mode"
        self._attr_unique_id = f"{entry.entry_id}-bathcontrolmodeactive"
        self._attr_options = ["IN", "OUT", "IGNORE"]

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get("bathcontrolmodeactive")
        if val in self._attr_options:
            return val
        return None

    async def async_select_option(self, option: str) -> None:
        await self._client.set_device_params({"bathcontrolmodeactive": option})
        await self.coordinator.async_request_refresh()


class SiegeniaBathControlPassiveSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:water-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Bath Control Passive Mode" if system_name else "Siegenia Bath Control Passive Mode"
        self._attr_unique_id = f"{entry.entry_id}-bathcontrolmodepassive"
        self._attr_options = ["IN", "OUT", "IN_OUT", "AUTO"]

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get("bathcontrolmodepassive")
        if val in self._attr_options:
            return val
        return None

    async def async_select_option(self, option: str) -> None:
        await self._client.set_device_params({"bathcontrolmodepassive": option})
        await self.coordinator.async_request_refresh()


class SiegeniaSilentTimerTimeSelect(CoordinatorEntity, SelectEntity):
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry, key: str, name_suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._client = coordinator.hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} {name_suffix}" if system_name else f"Siegenia {name_suffix}"
        slug = key.lower().replace("_", "-").replace(".", "-")
        self._attr_unique_id = f"{entry.entry_id}-{slug}"
        self._attr_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]

    def _get_system_name(self) -> str | None:
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
    def current_option(self) -> str | None:
        val = self._d().get(self._key)
        if val is not None:
            try:
                idx = int(val)
                if 0 <= idx < 96:
                    return self._attr_options[idx]
            except Exception:
                pass
        return None

    async def async_select_option(self, option: str) -> None:
        if option in self._attr_options:
            val = self._attr_options.index(option)
            await self._client.set_device_params({self._key: val})
            await self.coordinator.async_request_refresh()

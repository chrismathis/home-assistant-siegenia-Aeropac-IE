from __future__ import annotations

from typing import Optional

from homeassistant.components.number import NumberEntity
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

def _raw_max_m3h(d: dict) -> int:
    for k in ("maxfanpower", "max_fan_power"):
        if k in d and d.get(k):
            try:
                v = int(d.get(k))
                if v > 0:
                    return v
            except Exception:
                continue
    return 60

def _manual_cap_m3h(d: dict, raw_max: int) -> Optional[int]:
    for k in ("maxfanpowermanual", "manual_maxfanpower"):
        if k in d and d.get(k) is not None:
            try:
                val = int(d.get(k))
                if val <= 0:
                    continue
                if val <= 100:
                    return max(1, int(round(raw_max * val / 100)))
                return val
            except Exception:
                continue
    return None

def _effective_max_m3h(d: dict) -> int:
    raw_max = _raw_max_m3h(d)
    cap = _manual_cap_m3h(d, raw_max)
    if cap is not None:
        return min(raw_max, cap)
    return raw_max

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    d = _combined(coord.data)
    entities: list[NumberEntity] = []
    
    if any(k in d for k in ("fanpower", "maxfanpower", "maxfanpowermanual", "max_fan_power", "manual_maxfanpower")):
        entities.append(SiegeniaFanPowerNumber(hass, entry))
        
    percent_configs = [
        ("automode_maxairflow", "Max Airflow"),
        ("automode_co2sensity", "CO2 Sensitivity"),
        ("ecomode_maxairflow", "Silent Max Airflow"),
        ("bathcontrolfanpower", "Bath Control Fan Power"),
        ("slave_fanpower", "Slave Fan Power"),
    ]
    for key, name_suffix in percent_configs:
        if key in d:
            entities.append(SiegeniaPercentNumber(coord, entry, key, name_suffix))
            
    if entities:
        async_add_entities(entities, True)


class SiegeniaFanPowerNumber(CoordinatorEntity, NumberEntity):
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "m³/h"
    _attr_mode = "auto"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        super().__init__(coord)
        self._client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
        self._entry = entry
        # Get system name from device info
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Fan Power" if system_name else "Siegenia Fan Power"
        self._attr_unique_id = f"{entry.entry_id}-fanpower"
        
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
    def native_min_value(self) -> float:
        return 0.0

    @property
    def native_max_value(self) -> float:
        return float(_effective_max_m3h(self._d()))

    @property
    def native_step(self) -> float:
        return 1.0

    @property
    def native_value(self) -> float | None:
        d = self._d()
        try:
            raw_power = int(d.get("fanpower", 0) or 0)
            pct = int(round(raw_power * 100 / 7))
        except Exception:
            pct = 0
        eff_max = _effective_max_m3h(d)
        return round(eff_max * pct / 100, 0)

    async def async_set_native_value(self, value: float) -> None:
        d = self._d()
        eff_max = _effective_max_m3h(d)
        value = max(0.0, min(float(value), float(eff_max)))
        pct = int(round((value * 100) / max(1.0, float(eff_max))))
        raw_power = int(round(pct * 7 / 100))
        await self._client.set_device_params({"automode": False, "auto_mode": False, "fanpower": raw_power})
        await self.coordinator.async_request_refresh()


class SiegeniaPercentNumber(CoordinatorEntity, NumberEntity):
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%"
    _attr_mode = "auto"
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
        if key in ("bathcontrolfanpower", "slave_fanpower"):
            self._attr_entity_registry_enabled_default = False

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
    def native_value(self) -> float | None:
        d = self._d()
        val = d.get(self._key)
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            return None

    async def async_set_native_value(self, value: float) -> None:
        await self._client.set_device_params({self._key: int(round(value))})
        await self.coordinator.async_request_refresh()
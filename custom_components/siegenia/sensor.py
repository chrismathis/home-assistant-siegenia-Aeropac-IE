from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DATA_COORDINATOR
from .device import build_device_info

UNIT_MAP = {
    "airbase.humidity.indoor": "%",
    "airbase.humidity.outdoor": "%",
    "airbase.temperature.indoor": "°C",
    "airbase.temperature.outdoor": "°C",
    "airquality.co2content": "ppm",
    "humidity.indoor": "%",
    "humidity.outdoor": "%",
    "temperature.indoor": "°C",
    "temperature.outdoor": "°C",
    "co2_value": "ppm",
    "fanmode": None,
    "maxfanpower": None,
    "systemname": None,
    "connection": None,
    "airquality": None,
    "maxfanpowermanual": None,
    "airquality.voc": None,
    "timer.remainingtime": "min",
}

def _flatten(data: Dict[str, Any], parent: str = "", out: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if out is None:
        out = {}
    for k, v in (data or {}).items():
        key = f"{parent}.{k}" if parent else str(k)
        if isinstance(v, dict):
            _flatten(v, key, out)
        else:
            out[key] = v
    return out

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]

    combined = {}
    for part in ("state", "params", "info"):
        d = (coordinator.data or {}).get(part) or {}
        if isinstance(d, dict):
            combined.update(d)
    flat = _flatten(combined)
    flat.update(combined)

    entities: list[SensorEntity] = []
    for key, unit in UNIT_MAP.items():
        if key in flat:
            entities.append(SiegeniaKeySensor(coordinator, entry, key, unit))

    entities.append(SiegeniaRawStateSensor(coordinator, entry))

    if "externaldevices" in combined:
        entities.append(SiegeniaPairedDeviceSensor(coordinator, entry))

    async_add_entities(entities)

class SiegeniaKeySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, key: str, unit: str | None) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        # Get system name from device info
        system_name = self._get_system_name()
        name = key.replace("_", " ").replace(".", " ").title()
        self._attr_name = f"{system_name} {name}" if system_name else f"Siegenia {name}"
        slug = key.lower().replace(" ", "-").replace(".", "-").replace("_", "-")
        self._attr_unique_id = f"{entry.entry_id}-{slug}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        return build_device_info(
            self.coordinator.data, 
            self._entry.entry_id, 
            self._entry.data.get("host"),
            self._entry.data.get("name")
        )
            
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
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        combined = {}
        for part in ("state", "params", "info"):
            d = data.get(part) or {}
            if isinstance(d, dict):
                combined.update(d)
        flat = combined.copy()
        def _flatten_in(x: dict, parent: str = "", out: dict | None = None):
            if out is None:
                out = {}
            for k, v in (x or {}).items():
                kk = f"{parent}.{k}" if parent else str(k)
                if isinstance(v, dict):
                    _flatten_in(v, kk, out)
                else:
                    out[kk] = v
            return out
        flat.update(_flatten_in(combined))
        return flat.get(self._key)

class SiegeniaRawStateSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-json"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Raw State" if system_name else "Siegenia Raw State"
        self._attr_unique_id = f"{entry.entry_id}-raw-state"
        
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

    @property
    def native_value(self) -> str:
        # Keep the main state safely under the 255-character limit
        return "Data Available" if self.coordinator.data else "Waiting for data"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        # Put the massive JSON payload here, where Home Assistant allows unlimited size
        data = self.coordinator.data or {}
        combined = {}
        for part in ("state", "params", "info"):
            d = data.get(part) or {}
            if isinstance(d, dict):
                combined.update(d)
        return {"raw_data": combined}


class SiegeniaPairedDeviceSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:link-variant"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        system_name = self._get_system_name()
        self._attr_name = f"{system_name} Paired Device" if system_name else "Siegenia Paired Device"
        self._attr_unique_id = f"{entry.entry_id}-paired-device"

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
        data = self.coordinator.data or {}
        merged = {}
        for key in ("state", "params", "info"):
            v = data.get(key) or {}
            if isinstance(v, dict):
                merged.update(v)
        return merged

    @property
    def native_value(self) -> str | None:
        d = self._d()
        external_devices = d.get("externaldevices") or {}
        devices_list = external_devices.get("devices") or []
        if not devices_list:
            return "None"
        dev = devices_list[0]
        name = dev.get("name") or "AEROTUBE"
        serial = dev.get("serialnr") or ""
        return f"{name} ({serial})".strip()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._d()
        external_devices = d.get("externaldevices") or {}
        devices_list = external_devices.get("devices") or []
        
        # Mirror mode description
        mirror_val = d.get("fanmirror")
        mirror_mode = "Unknown"
        if mirror_val is not None:
            try:
                mirror_mode = {
                    0: "Slave mode",
                    1: "Slave must mirror",
                    2: "Slave must copy"
                }.get(int(mirror_val), "Unknown")
            except Exception:
                pass

        if not devices_list:
            return {
                "paired": False,
                "mirror_mode": mirror_mode,
            }

        dev = devices_list[0]
        return {
            "paired": True,
            "slave_id": dev.get("id"),
            "slave_name": dev.get("name"),
            "slave_serial": dev.get("serialnr"),
            "slave_online": dev.get("online", False),
            "slave_type": dev.get("type"),
            "mirror_mode": mirror_mode,
            "slave_direction": {
                1: "Slave supply air",
                2: "Slave exhaust air"
            }.get(d.get("slave_fandirection"), "Unknown"),
            "slave_power_percent": d.get("slave_fanpower"),
        }
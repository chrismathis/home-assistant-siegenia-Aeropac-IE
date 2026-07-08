from __future__ import annotations

from .const import DOMAIN

DEVICE_TYPE_MAP = {
    1: "Aeropac",
    2: "Aeromat VT",
    3: "Aeromat UP",
    4: "Aerovital",
    5: "Aerovital",
    8: "Aerotube",
    10: "Universal Module",
    11: "Drive Axxent DK",
    12: "VT Upgrade",
    13: "Drive CL",
    14: "Aeroplus",
    15: "Senso Secure",
}


def _info_from_data(data: dict | None) -> dict:
    info = (data or {}).get("info") or {}
    return info if isinstance(info, dict) else {}


def _coerce_str(value) -> str | None:
    if value is None:
        return None
    return str(value)


def build_device_info(data: dict | None, entry_id: str, host: str | None = None, custom_name: str | None = None) -> dict:
    info = _info_from_data(data)
    serial_raw = info.get("serialnr") or info.get("serial_number")
    identifiers = {(DOMAIN, str(serial_raw))} if serial_raw else {(DOMAIN, entry_id)}

    device_info = {
        "identifiers": identifiers,
        "manufacturer": "Siegenia",
    }

    name = (
        custom_name
        or info.get("systemname")
        or info.get("devicename")
        or info.get("device_name")
        or info.get("name")
    )
    if not name and host:
        name = f"Siegenia {host}"
    if name:
        device_info["name"] = name

    # Resolve human-readable model from type map, fallback to other fields
    model = None
    dev_type = info.get("type")
    if dev_type is not None:
        try:
            model = DEVICE_TYPE_MAP.get(int(dev_type))
        except Exception:
            pass

    if not model:
        model = _coerce_str(info.get("model") or info.get("type") or info.get("hardwareversion"))

    if model:
        device_info["model"] = model

    sw_version = _coerce_str(info.get("softwareversion"))
    if sw_version:
        device_info["sw_version"] = sw_version

    hw_version = _coerce_str(info.get("hardwareversion"))
    if hw_version:
        device_info["hw_version"] = hw_version

    serial = _coerce_str(serial_raw)
    if serial:
        device_info["serial_number"] = serial

    return device_info
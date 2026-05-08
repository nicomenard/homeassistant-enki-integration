"""Enki light entities.

Two kinds of light node exist:
  - ESDK ceiling fan light kit  → controlled via api-enki-power-prod (endpoint 2)
  - Standard light node         → controlled via api-enki-lighting-prod
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EnkiDevice
from .base import EnkiBaseEntity
from .const import DEVICE_TYPE_FANS, DEVICE_TYPE_LIGHTS, DOMAIN, LOGGER
from .coordinator import EnkiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnkiCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[LightEntity] = []
    for device in coordinator.data:
        if device.device_type == DEVICE_TYPE_FANS:
            entities.append(EnkiFanLight(coordinator, device))
        elif device.device_type == DEVICE_TYPE_LIGHTS:
            entities.append(EnkiStandardLight(coordinator, device))
    async_add_entities(entities)


class EnkiFanLight(EnkiBaseEntity, LightEntity):
    """Light kit on an Enki ESDK ceiling fan (power-only via api-enki-power-prod)."""

    _attr_name = "Light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: EnkiCoordinator, device: EnkiDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}-{device.node_id}-light"

    @property
    def is_on(self) -> bool:
        return self._device.last_reported_value.get("light_power") == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_light_power(
            self._device.home_id, self._device.node_id, True
        )
        self.coordinator.update_cached_value(self._device.node_id, "light_power", "ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_light_power(
            self._device.home_id, self._device.node_id, False
        )
        self.coordinator.update_cached_value(self._device.node_id, "light_power", "OFF")


class EnkiStandardLight(EnkiBaseEntity, LightEntity):
    """Standard Enki light node (api-enki-lighting-prod, brightness + color temp)."""

    _attr_name = "Light"
    _attr_supported_color_modes: set[ColorMode]
    _attr_color_mode: ColorMode
    _brightness_max: int = 100

    def __init__(self, coordinator: EnkiCoordinator, device: EnkiDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}-{device.node_id}-light"
        self._color_temp_values: list[int] = []
        modes: set[ColorMode] = set()
        pv   = device.possible_values
        caps = device.capabilities

        if "change_color_temperature" in caps:
            modes.add(ColorMode.COLOR_TEMP)
            raw = pv.get("change_color_temperature", {}).get("values", [])
            if raw:
                self._color_temp_values = [int(v.strip("TK")) for v in raw]
                self._attr_min_color_temp_kelvin = min(self._color_temp_values)
                self._attr_max_color_temp_kelvin = max(self._color_temp_values)

        if "change_brightness" in caps:
            modes.add(ColorMode.BRIGHTNESS)
            r = pv.get("change_brightness", {}).get("range", {})
            self._brightness_max = r.get("max", 100)

        if not modes and "switch_electrical_power" in caps:
            modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = modes or {ColorMode.ONOFF}
        if ColorMode.COLOR_TEMP in modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ColorMode.BRIGHTNESS in modes:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        return self._device.last_reported_value.get("power") == "ON"

    @property
    def brightness(self) -> int | None:
        raw = self._device.last_reported_value.get("brightness")
        return round(raw * 255 / self._brightness_max) if raw is not None else None

    @property
    def color_temp_kelvin(self) -> int | None:
        raw = self._device.last_reported_value.get("colorTemperature")
        return int(raw.strip("TK")) if raw else None

    def _closest_color_temp(self, target: int) -> str:
        best = min(self._color_temp_values, key=lambda v: abs(v - target))
        return f"T{best}K"

    async def async_turn_on(self, **kwargs: Any) -> None:
        home_id, node_id = self._device.home_id, self._device.node_id
        if ATTR_BRIGHTNESS in kwargs:
            value = round(kwargs[ATTR_BRIGHTNESS] * self._brightness_max / 255, 2)
            await self.coordinator.api.async_change_light_state(home_id, node_id, "brightness", value)
            self.coordinator.update_cached_value(node_id, "brightness", value)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            value = self._closest_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN])
            await self.coordinator.api.async_change_light_state(home_id, node_id, "colorTemperature", value)
            self.coordinator.update_cached_value(node_id, "colorTemperature", value)
        else:
            await self.coordinator.api.async_change_light_state(home_id, node_id, "power", "ON")
            self.coordinator.update_cached_value(node_id, "power", "ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_change_light_state(
            self._device.home_id, self._device.node_id, "power", "OFF"
        )
        self.coordinator.update_cached_value(self._device.node_id, "power", "OFF")

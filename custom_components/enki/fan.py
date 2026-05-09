"""Enki ceiling fan entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from .api import EnkiDevice
from .base import EnkiBaseEntity
from .const import AIRFLOW_MODE_BREEZE, DEVICE_TYPE_FANS, DOMAIN
from .coordinator import EnkiCoordinator

SPEED_RANGE = (1, 6)  # Siroco+ has 6 speed levels; 0 = off


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnkiCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        EnkiFan(coordinator, device)
        for device in coordinator.data
        if device.device_type == DEVICE_TYPE_FANS
    )


class EnkiFan(EnkiBaseEntity, FanEntity):
    """Enki ceiling fan (ESDK node, api-enki-power-prod + api-enki-airflow-prod)."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: EnkiCoordinator, device: EnkiDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}-{device.node_id}-fan"

    @property
    def is_on(self) -> bool:
        return self._device.last_reported_value.get("fan_speed", 0) > 0

    @property
    def percentage(self) -> int | None:
        speed = self._device.last_reported_value.get("fan_speed", 0)
        if speed == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    @property
    def speed_count(self) -> int:
        return SPEED_RANGE[1]

    @property
    def preset_mode(self) -> str | None:
        mode = self._device.last_reported_value.get("airflow_mode")
        return "breeze" if mode == AIRFLOW_MODE_BREEZE else None

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        home_id, node_id = self._device.home_id, self._device.node_id
        if percentage is not None and percentage > 0:
            speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
        else:
            # Restore last speed or default to 1
            speed = max(1, self._device.last_reported_value.get("fan_speed", 0) or 1)
        await self.coordinator.api.async_set_fan_speed(home_id, node_id, speed)
        self.coordinator.update_cached_value(node_id, "fan_speed", speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_fan_speed(
            self._device.home_id, self._device.node_id, 0
        )
        self.coordinator.update_cached_value(self._device.node_id, "fan_speed", 0)

    async def async_set_percentage(self, percentage: int) -> None:
        home_id, node_id = self._device.home_id, self._device.node_id
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.coordinator.api.async_set_fan_speed(home_id, node_id, speed)
        self.coordinator.update_cached_value(node_id, "fan_speed", speed)

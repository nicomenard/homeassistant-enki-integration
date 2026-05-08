"""Base entity for all Enki entities."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EnkiDevice
from .const import DOMAIN
from .coordinator import EnkiCoordinator


class EnkiBaseEntity(CoordinatorEntity[EnkiCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnkiCoordinator, device: EnkiDevice) -> None:
        super().__init__(coordinator)
        self._device = device
        self.node_id = device.node_id

    @property
    def available(self) -> bool:
        d = self._device
        return d.is_enabled and d.state != "DEACTIVATED"

    @callback
    def _handle_coordinator_update(self) -> None:
        updated = self.coordinator.get_device_by_node(self.node_id)
        if updated:
            self._device = updated
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        lrv = self._device.last_reported_value
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.node_id)},
            name=self._device.device_name,
            manufacturer=lrv.get("manufacturerId", "Enki"),
            model=str(lrv.get("modelNumber", self._device.device_id)).replace("_", " ").title(),
            sw_version=lrv.get("version"),
        )

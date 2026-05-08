"""DataUpdateCoordinator for the Enki integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnkiAPI, EnkiAuthError, EnkiConnectionError, EnkiDevice
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class EnkiCoordinator(DataUpdateCoordinator[list[EnkiDevice]]):
    """Fetches all Enki devices on a fixed interval."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.api = EnkiAPI(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[EnkiDevice]:
        try:
            return await self.api.async_get_devices()
        except EnkiAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except EnkiConnectionError as err:
            raise UpdateFailed(f"Cannot reach Enki cloud: {err}") from err

    def get_device_by_node(self, node_id: str) -> EnkiDevice | None:
        if not self.data:
            return None
        return next((d for d in self.data if d.node_id == node_id), None)

    def update_cached_value(self, node_id: str, key: str, value: Any) -> None:
        """Optimistically update cached state so UI reflects changes immediately."""
        device = self.get_device_by_node(node_id)
        if device:
            device.last_reported_value[key] = value
            self.async_set_updated_data(self.data)

"""DataUpdateCoordinator for the Enki integration."""
from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnkiAPI, EnkiAuthError, EnkiConnectionError, EnkiDevice
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, OPTIMISTIC_GRACE


class EnkiCoordinator(DataUpdateCoordinator[list[EnkiDevice]]):
    """Fetches all Enki devices on a fixed interval."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.api = EnkiAPI(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
        )
        # (node_id, key) -> (optimistic value, monotonic expiry). Keeps a just-
        # issued command from being reverted by a poll before the cloud catches up.
        self._pending: dict[tuple[str, str], tuple[Any, float]] = {}
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[EnkiDevice]:
        try:
            devices = await self.api.async_get_devices()
        except EnkiAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except EnkiConnectionError as err:
            raise UpdateFailed(f"Cannot reach Enki cloud: {err}") from err
        self._reapply_pending(devices)
        return devices

    def _reapply_pending(self, devices: list[EnkiDevice]) -> None:
        """Keep freshly-commanded values until the cloud confirms them.

        The Enki cloud accepts commands asynchronously (202) and only reflects
        the new state a few seconds later. Without this, a poll landing in that
        window reads the old value and makes on/off toggles flap.
        """
        if not self._pending:
            return
        now = time.monotonic()
        by_node = {d.node_id: d for d in devices}
        for (node_id, key), (value, expiry) in list(self._pending.items()):
            device = by_node.get(node_id)
            if device is None or now >= expiry:
                self._pending.pop((node_id, key), None)  # gone or expired
            elif device.last_reported_value.get(key) == value:
                self._pending.pop((node_id, key), None)  # cloud caught up
            else:
                device.last_reported_value[key] = value  # hold the optimistic value

    def get_device_by_node(self, node_id: str) -> EnkiDevice | None:
        if not self.data:
            return None
        return next((d for d in self.data if d.node_id == node_id), None)

    def update_cached_value(self, node_id: str, key: str, value: Any) -> None:
        """Optimistically update cached state so UI reflects changes immediately."""
        device = self.get_device_by_node(node_id)
        if device:
            device.last_reported_value[key] = value
            self._pending[(node_id, key)] = (value, time.monotonic() + OPTIMISTIC_GRACE)
            self.async_set_updated_data(self.data)

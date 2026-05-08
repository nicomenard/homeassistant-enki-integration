"""The Enki ceiling fan integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import EnkiAuthError, EnkiConnectionError
from .const import DOMAIN
from .coordinator import EnkiCoordinator

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = EnkiCoordinator(hass, entry)

    try:
        await coordinator.api.async_connect()
    except EnkiAuthError as err:
        raise ConfigEntryNotReady(f"Invalid credentials: {err}") from err
    except EnkiConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot reach Enki cloud: {err}") from err

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

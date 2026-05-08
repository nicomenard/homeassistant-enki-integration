"""Enki cloud API client."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    DEVICE_TYPE_FANS,
    DEVICE_TYPE_LIGHTS,
    ENKI_AIRFLOW_API_KEY,
    ENKI_BASE_URL,
    ENKI_BFF_API_KEY,
    ENKI_ESDK_API_KEY,
    ENKI_HOME_API_KEY,
    ENKI_LIGHTS_API_KEY,
    ENKI_NODE_API_KEY,
    ENKI_OIDC_URL,
    ENKI_POWER_API_KEY,
    ENKI_REFERENTIEL_API_KEY,
    FAN_ENDPOINT,
    LIGHT_ENDPOINT,
    LOGGER,
    REFERENTIEL_VERSION,
)


class EnkiAuthError(Exception):
    pass


class EnkiConnectionError(Exception):
    pass


@dataclass
class EnkiDevice:
    home_id: str
    device_id: str
    node_id: str
    device_name: str
    device_type: str
    is_enabled: bool
    state: str
    # Capabilities/possible values (standard light nodes only)
    capabilities: list[str] = field(default_factory=list)
    possible_values: dict[str, Any] = field(default_factory=dict)
    # Flat state dict populated per device type
    last_reported_value: dict[str, Any] = field(default_factory=dict)


class EnkiAPI:
    """Client for the Enki cloud API (Leroy Merlin / Adeo)."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._token_type: str = "Bearer"
        self._token_expires_at: float = 0.0

    async def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._token_expires_at - 30:
            return
        await self.async_connect()

    async def async_connect(self) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ENKI_OIDC_URL,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "password",
                        "client_id": "enki-front",
                        "username": self._username,
                        "password": self._password,
                    },
                ) as resp:
                    if resp.status == 401:
                        raise EnkiAuthError("Invalid username or password")
                    if resp.status != 200:
                        raise EnkiConnectionError(f"Auth failed: {resp.status}")
                    data = await resp.json()
                    self._access_token = data["access_token"]
                    self._token_type = data["token_type"]
                    self._token_expires_at = time.time() + data["expires_in"]
        except aiohttp.ClientError as err:
            raise EnkiConnectionError(f"Cannot reach Enki auth: {err}") from err

    def _auth_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {"Authorization": f"{self._token_type} {self._access_token}"}
        if extra:
            h.update(extra)
        return h

    # -------------------------------------------------------------------------
    # Device discovery
    # -------------------------------------------------------------------------

    async def async_get_devices(self) -> list[EnkiDevice]:
        await self._ensure_token()
        homes = await self._get_homes()
        devices: list[EnkiDevice] = []
        for home_id in homes:
            devices.extend(await self._get_devices_for_home(home_id))
        return devices

    async def _get_homes(self) -> list[str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-home-prod/v1/homes",
                headers=self._auth_headers({"X-Gateway-APIKey": ENKI_HOME_API_KEY}),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"get_homes failed: {resp.status}")
                return [h["id"] for h in (await resp.json())["items"]]

    async def _get_devices_for_home(self, home_id: str) -> list[EnkiDevice]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-mobile-bff-prod/v1/dashboard/homes/{home_id}?hasGroups=true",
                headers=self._auth_headers({"X-Gateway-APIKey": ENKI_BFF_API_KEY}),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"get_devices failed: {resp.status}")
                data = await resp.json()

        devices = []
        for section in data["sections"]:
            for item in section["items"]:
                meta = item.get("metadata", {})
                if "nodeId" not in meta:
                    continue

                node_id   = meta["nodeId"]
                device_id = meta["deviceId"]
                bff_type  = meta.get("deviceType", "")

                node_info   = await self._get_node(home_id, node_id)
                device_info = await self._get_device_info_safe(device_id)
                device_type = device_info.get("type") or bff_type

                last_reported: dict[str, Any] = {}
                if device_type == DEVICE_TYPE_FANS and item["isEnabled"]:
                    last_reported = await self._get_fan_full_state(home_id, node_id)
                elif device_type == DEVICE_TYPE_LIGHTS and item["isEnabled"]:
                    last_reported = await self._get_light_state(home_id, node_id)

                devices.append(EnkiDevice(
                    home_id=home_id,
                    device_id=device_id,
                    node_id=node_id,
                    device_name=item["title"]["label"],
                    device_type=device_type,
                    is_enabled=item["isEnabled"],
                    state=item["state"],
                    capabilities=device_info.get("capabilities", []),
                    possible_values=device_info.get("possibleValues", {}),
                    last_reported_value={**node_info, **last_reported},
                ))
        return devices

    async def _get_node(self, home_id: str, node_id: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-node-agg-prod/v1/nodes/{node_id}",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_NODE_API_KEY,
                    "homeId": home_id,
                }),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"get_node failed: {resp.status}")
                return await resp.json()

    async def _get_device_info_safe(self, device_id: str) -> dict[str, Any]:
        """Fetch referentiel info; ESDK nodes return 404 — return empty dict."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-referentiel-agg-prod/v1/devices/{device_id}?version={REFERENTIEL_VERSION}",
                headers=self._auth_headers({"X-Gateway-APIKey": ENKI_REFERENTIEL_API_KEY}),
            ) as resp:
                if resp.status == 404:
                    return {}
                if resp.status != 200:
                    raise EnkiConnectionError(f"get_device_info failed: {resp.status}")
                return await resp.json()

    # -------------------------------------------------------------------------
    # Ceiling fan state  (api-enki-power-prod + api-enki-airflow-prod)
    #
    # State is spread across three endpoints; we flatten into one dict:
    #   fan_power    : "ON" | "OFF"    (power endpoint 1)
    #   light_power  : "ON" | "OFF"    (power endpoint 2)
    #   fan_speed    : int  0-6        (airflow check-fan-speed)
    #   airflow_mode : "MANUAL"|"BREEZE" (airflow check-airflow-mode)
    # -------------------------------------------------------------------------

    async def _get_fan_full_state(self, home_id: str, node_id: str) -> dict[str, Any]:
        fan_power   = await self._get_power_state(home_id, node_id, FAN_ENDPOINT)
        light_power = await self._get_power_state(home_id, node_id, LIGHT_ENDPOINT)
        speed       = await self._get_fan_speed(home_id, node_id)
        mode        = await self._get_airflow_mode(home_id, node_id)
        return {
            "fan_power":    fan_power,
            "light_power":  light_power,
            "fan_speed":    speed,
            "airflow_mode": mode,
        }

    async def _get_power_state(self, home_id: str, node_id: str, endpoint: int) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-power-prod/v1/power/{node_id}/check-electrical-power?endpoints={endpoint}",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_POWER_API_KEY,
                    "homeId": home_id,
                }),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"check-electrical-power failed: {resp.status}")
                data = await resp.json()
                return data["lastReportedValue"]

    async def _get_fan_speed(self, home_id: str, node_id: str) -> int:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-airflow-prod/v1/airflow/{node_id}/check-fan-speed",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_AIRFLOW_API_KEY,
                    "homeId": home_id,
                }),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"check-fan-speed failed: {resp.status}")
                return (await resp.json())["lastReportedValue"]

    async def _get_airflow_mode(self, home_id: str, node_id: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-airflow-prod/v1/airflow/{node_id}/check-airflow-mode",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_AIRFLOW_API_KEY,
                    "homeId": home_id,
                }),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"check-airflow-mode failed: {resp.status}")
                return (await resp.json())["lastReportedValue"]

    # -------------------------------------------------------------------------
    # Fan commands
    # -------------------------------------------------------------------------

    async def async_set_fan_power(self, home_id: str, node_id: str, on: bool) -> None:
        await self._ensure_token()
        await self._switch_power(home_id, node_id, FAN_ENDPOINT, "ON" if on else "OFF")

    async def async_set_fan_speed(self, home_id: str, node_id: str, speed: int) -> None:
        """Set fan speed (0–6). Setting > 0 also turns the fan on."""
        await self._ensure_token()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ENKI_BASE_URL}/api-enki-airflow-prod/v1/airflow/{node_id}/change-fan-speed",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_AIRFLOW_API_KEY,
                    "homeId": home_id,
                }),
                json={"value": speed},
            ) as resp:
                if resp.status != 202:
                    raise EnkiConnectionError(f"change-fan-speed failed: {resp.status}")

    # -------------------------------------------------------------------------
    # Light commands (power only — light kit on ESDK fan)
    # -------------------------------------------------------------------------

    async def async_set_light_power(self, home_id: str, node_id: str, on: bool) -> None:
        await self._ensure_token()
        await self._switch_power(home_id, node_id, LIGHT_ENDPOINT, "ON" if on else "OFF")

    async def _switch_power(
        self, home_id: str, node_id: str, endpoint: int, value: str
    ) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ENKI_BASE_URL}/api-enki-power-prod/v1/power/{node_id}/switch-electrical-power?endpoints={endpoint}",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_POWER_API_KEY,
                    "homeId": home_id,
                }),
                json={"value": value},
            ) as resp:
                if resp.status != 202:
                    raise EnkiConnectionError(
                        f"switch-electrical-power (endpoint {endpoint}) failed: {resp.status}"
                    )

    # -------------------------------------------------------------------------
    # Standard light node commands (non-ESDK, lights type)
    # -------------------------------------------------------------------------

    async def _get_light_state(self, home_id: str, node_id: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ENKI_BASE_URL}/api-enki-lighting-prod/v1/lighting/{node_id}/check-light-state",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_LIGHTS_API_KEY,
                    "homeId": home_id,
                }),
            ) as resp:
                if resp.status != 200:
                    raise EnkiConnectionError(f"check-light-state failed: {resp.status}")
                return await resp.json()

    async def async_change_light_state(
        self, home_id: str, node_id: str, parameter: str, value: Any
    ) -> None:
        await self._ensure_token()
        current = await self._get_light_state(home_id, node_id)
        payload = current.get("lastReportedValue", {})
        payload[parameter] = value
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ENKI_BASE_URL}/api-enki-lighting-prod/v1/lighting/{node_id}/change-light-state",
                headers=self._auth_headers({
                    "X-Gateway-APIKey": ENKI_LIGHTS_API_KEY,
                    "homeId": home_id,
                }),
                json=payload,
            ) as resp:
                if resp.status != 202:
                    raise EnkiConnectionError(f"change-light-state failed: {resp.status}")

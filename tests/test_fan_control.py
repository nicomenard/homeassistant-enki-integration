"""Integration tests for Enki ceiling fan + light control.

These tests hit the real Enki cloud API.
Set credentials and device IDs via environment variables or a .env file:

    ENKI_USERNAME   your Enki app email
    ENKI_PASSWORD   your Enki app password
    ENKI_HOME_ID    home ID (from the API)
    ENKI_NODE_ID    ceiling fan node ID

All four variables are required; tests are skipped if any is missing.
The tests leave the device in its original state (fan off, light off).
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from custom_components.enki.api import EnkiAPI, EnkiAuthError, EnkiConnectionError

USERNAME = os.getenv("ENKI_USERNAME", "")
PASSWORD = os.getenv("ENKI_PASSWORD", "")
HOME_ID  = os.getenv("ENKI_HOME_ID", "")
NODE_ID  = os.getenv("ENKI_NODE_ID", "")

if not all([USERNAME, PASSWORD, HOME_ID, NODE_ID]):
    pytest.skip(
        "Set ENKI_USERNAME, ENKI_PASSWORD, ENKI_HOME_ID, ENKI_NODE_ID to run integration tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
async def api():
    """Authenticated EnkiAPI client."""
    client = EnkiAPI(USERNAME, PASSWORD)
    await client.async_connect()
    return client


@pytest.fixture()
async def clean_state(api):
    """Ensure fan and light are OFF before and after each test."""
    await api.async_set_fan_speed(HOME_ID, NODE_ID, 0)
    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "OFF")
    await asyncio.sleep(1)
    yield api
    # teardown — restore off state
    await api.async_set_fan_speed(HOME_ID, NODE_ID, 0)
    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "OFF")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def test_connect():
    """Token is obtained without error."""
    client = EnkiAPI(USERNAME, PASSWORD)
    await client.async_connect()
    assert client._access_token is not None


async def test_connect_bad_password():
    client = EnkiAPI(USERNAME, "wrongpassword")
    with pytest.raises(EnkiAuthError):
        await client.async_connect()


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

async def test_get_devices(api):
    devices = await api.async_get_devices()
    assert len(devices) > 0
    fan = next((d for d in devices if d.node_id == NODE_ID), None)
    assert fan is not None, "Ceiling fan node not found"
    assert fan.device_type == "ceiling_fans"
    assert fan.device_name == "Ventilateur plafond"


# ---------------------------------------------------------------------------
# Fan control
# ---------------------------------------------------------------------------

async def test_fan_turn_on(clean_state):
    api = clean_state
    await api.async_set_fan_speed(HOME_ID, NODE_ID, 1)
    await asyncio.sleep(2)
    speed = await api._get_fan_speed(HOME_ID, NODE_ID)
    assert speed > 0


async def test_fan_turn_off(clean_state):
    api = clean_state
    await api.async_set_fan_speed(HOME_ID, NODE_ID, 1)
    await asyncio.sleep(1)
    await api.async_set_fan_speed(HOME_ID, NODE_ID, 0)
    await asyncio.sleep(2)
    speed = await api._get_fan_speed(HOME_ID, NODE_ID)
    assert speed == 0


async def test_fan_set_speed(clean_state):
    api = clean_state
    await api.async_set_fan_power(HOME_ID, NODE_ID, True)
    await asyncio.sleep(1)

    for speed in (1, 3, 6):
        await api.async_set_fan_speed(HOME_ID, NODE_ID, speed)
        await asyncio.sleep(2)
        reported = await api._get_fan_speed(HOME_ID, NODE_ID)
        assert reported == speed, f"Expected speed {speed}, got {reported}"


async def test_fan_speed_zero_when_off(clean_state):
    api = clean_state
    speed = await api._get_fan_speed(HOME_ID, NODE_ID)
    assert speed == 0


# ---------------------------------------------------------------------------
# Light control
# ---------------------------------------------------------------------------

async def test_light_turn_on(clean_state):
    api = clean_state
    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "ON")
    await asyncio.sleep(2)
    state = await api._get_light_state(HOME_ID, NODE_ID)
    assert state["lastReportedValue"]["power"] == "ON"


async def test_light_turn_off(clean_state):
    api = clean_state
    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "ON")
    await asyncio.sleep(1)
    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "OFF")
    await asyncio.sleep(2)
    state = await api._get_light_state(HOME_ID, NODE_ID)
    assert state["lastReportedValue"]["power"] == "OFF"


async def test_light_brightness(clean_state):
    api = clean_state
    await api.async_set_light_power(HOME_ID, NODE_ID, True)
    await asyncio.sleep(1)

    for value in (0.2, 0.6, 1.0):
        await api.async_change_light_state(HOME_ID, NODE_ID, "brightness", value)
        await asyncio.sleep(2)
        state = await api._get_light_state(HOME_ID, NODE_ID)
        reported = state["lastReportedValue"]["brightness"]
        assert abs(reported - value) < 0.05, f"Expected brightness {value}, got {reported}"


async def test_light_color_temperature(clean_state):
    api = clean_state
    await api.async_set_light_power(HOME_ID, NODE_ID, True)
    await asyncio.sleep(1)

    for kelvin in (3500, 5000, 6500):
        await api.async_change_light_state(HOME_ID, NODE_ID, "colorTemperature", f"T{kelvin}K")
        await asyncio.sleep(2)
        state = await api._get_light_state(HOME_ID, NODE_ID)
        reported = state["lastReportedValue"]["colorTemperature"]
        assert reported == f"T{kelvin}K", f"Expected T{kelvin}K, got {reported}"


# ---------------------------------------------------------------------------
# Fan + light independence
# ---------------------------------------------------------------------------

async def test_fan_and_light_independent(clean_state):
    """Turning the fan on must not affect the light, and vice versa."""
    api = clean_state

    await api.async_set_fan_speed(HOME_ID, NODE_ID, 1)
    await asyncio.sleep(2)
    light = await api._get_light_state(HOME_ID, NODE_ID)
    assert light["lastReportedValue"]["power"] == "OFF", "Turning fan on should not affect the light"

    await api.async_change_light_state(HOME_ID, NODE_ID, "power", "ON")
    await asyncio.sleep(2)
    speed = await api._get_fan_speed(HOME_ID, NODE_ID)
    assert speed > 0, "Turning light on should not turn off the fan"

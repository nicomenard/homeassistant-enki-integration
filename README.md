# Enki Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for **Enki** smart ceiling fans (Leroy Merlin / Adeo ecosystem), specifically supporting ESDK-based models such as the **INSPIRE Siroco+**.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Supported devices

| Model | Type | Fan | Light |
|---|---|---|---|
| INSPIRE Siroco + (AD_TCFL_1) | ESDK ceiling fan | ✅ on/off, 6 speeds | ✅ on/off |

Other Enki ceiling fan models with ESDK firmware should also work.

Standard Enki light nodes (non-ESDK) are supported as well, with brightness and colour temperature where the device supports it.

## Features

- **Fan**: turn on/off, set speed (6 levels)
- **Light kit**: turn on/off
- Cloud polling via the Enki API (Leroy Merlin / Adeo)
- Config flow UI — set up from the Home Assistant integrations page
- HACS compatible

## Installation

### HACS (recommended)

1. In HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/clamoriniere/homeassistant-enki-integration` as an **Integration**
3. Install **Enki** and restart Home Assistant

### Manual

Copy `custom_components/enki/` into your HA `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Enki**
3. Enter your Enki app email and password (the same credentials used in the Leroy Merlin / Enki mobile app)

## Development

### Prerequisites

```bash
pip install pytest pytest-asyncio aiohttp
```

### Running the integration tests

The tests call the real Enki cloud API. Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

```ini
ENKI_USERNAME=your@email.com
ENKI_PASSWORD=yourpassword
ENKI_HOME_ID=your_home_id
ENKI_NODE_ID=your_ceiling_fan_node_id
```

Then run:

```bash
export $(cat .env | xargs)
python3 -m pytest tests/ -v
```

### How it works

The Enki platform (Adeo / Leroy Merlin) exposes a set of REST microservices behind an API gateway. Each service requires a per-service `X-Gateway-APIKey` header in addition to a Bearer token obtained via OIDC.

For ESDK ceiling fan nodes the relevant services are:

| Service | Purpose |
|---|---|
| `api-enki-power-prod` | Fan power (endpoint 1) and light power (endpoint 2) |
| `api-enki-airflow-prod` | Fan speed (0–6) and airflow mode (MANUAL / BREEZE) |
| `api-enki-esdk-prod` | Device connectivity state |
| `api-enki-mobile-bff-prod` | Device discovery |

## License

[MIT](LICENSE)

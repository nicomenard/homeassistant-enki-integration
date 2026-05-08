#!/usr/bin/env python3
"""
Authenticate with the Enki API and dump all devices with their types,
capabilities, and state. Also probes the airflow endpoint with the live token.

Usage:
    python3 scripts/discover_devices.py <email> <password>
"""
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request

OIDC_URL = "https://keycloak-prod.iot.leroymerlin.fr/realms/enki/protocol/openid-connect/token"
BASE_URL = "https://enki.api.devportal.adeo.cloud"

HOME_KEY         = "FULsxyI3x1f7MtLVOsP6V1DeAPmBQJCB"
BFF_KEY          = "Bco7qBHRHOQiSVcEHdgS0rijpebMBwkB"
NODE_KEY         = "UBb0Kv6xXpG6bOvD8VZ9A63uxqQ4G1A3"
REFERENTIEL_KEY  = "3uk9rlaIUgBsz1tEPV7GQMhhGfRwPFJY"
LIGHTS_KEY       = "3OVsNulRsUXfr7Hze54OHx8l6qDu2UcE"


def post(url, data: dict, headers: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(url, headers: dict):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read(500).decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def auth_headers(token_type, access_token, extra: dict = None) -> dict:
    h = {
        "Authorization": f"{token_type} {access_token}",
        "User-Agent": "enki-discover/0.1",
    }
    if extra:
        h.update(extra)
    return h


import urllib.parse


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <email> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]

    # ── 1. Authenticate ──────────────────────────────────────────────────────
    print("Authenticating...")
    try:
        resp = post(
            OIDC_URL,
            data={
                "grant_type": "password",
                "client_id": "enki-front",
                "username": username,
                "password": password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except urllib.error.HTTPError as e:
        print(f"Auth failed: {e.code} {e.read(200).decode()}")
        sys.exit(1)

    token_type = resp["token_type"]
    access_token = resp["access_token"]
    print(f"  OK — token valid for {resp['expires_in']}s\n")

    def h(key, extra=None):
        headers = auth_headers(token_type, access_token, {"X-Gateway-APIKey": key})
        if extra:
            headers.update(extra)
        return headers

    # ── 2. List homes ────────────────────────────────────────────────────────
    status, data = get(f"{BASE_URL}/api-enki-home-prod/v1/homes", h(HOME_KEY))
    if status != 200:
        print(f"get_homes failed: {status} {data}")
        sys.exit(1)
    homes = [item["id"] for item in data["items"]]
    print(f"Homes found: {homes}\n")

    # ── 3. Dump all devices ──────────────────────────────────────────────────
    for home_id in homes:
        print(f"{'='*60}")
        print(f"Home: {home_id}")
        print(f"{'='*60}")
        status, data = get(
            f"{BASE_URL}/api-enki-mobile-bff-prod/v1/dashboard/homes/{home_id}?hasGroups=true",
            h(BFF_KEY),
        )
        if status != 200:
            print(f"  get_devices failed: {status}")
            continue

        for section in data.get("sections", []):
            for item in section.get("items", []):
                meta = item.get("metadata", {})
                if "nodeId" not in meta:
                    continue

                node_id = meta["nodeId"]
                device_id = meta["deviceId"]
                name = item["title"]["label"]
                state = item.get("state")
                enabled = item.get("isEnabled")

                # Get device type from referentiel
                _, dev_info = get(
                    f"{BASE_URL}/api-enki-referentiel-agg-prod/v1/devices/{device_id}?version=2.15.0",
                    h(REFERENTIEL_KEY),
                )
                device_type = dev_info.get("type", "?") if isinstance(dev_info, dict) else "?"
                capabilities = dev_info.get("capabilities", []) if isinstance(dev_info, dict) else []

                print(f"\n  Device : {name}")
                print(f"    type        : {device_type}")
                print(f"    nodeId      : {node_id}")
                print(f"    deviceId    : {device_id}")
                print(f"    state       : {state}  enabled={enabled}")
                print(f"    capabilities: {capabilities}")

                # If it's a light, show state
                if device_type == "lights" and enabled:
                    status2, light_state = get(
                        f"{BASE_URL}/api-enki-lighting-prod/v1/lighting/{node_id}/check-light-state",
                        h(LIGHTS_KEY, {"homeId": home_id}),
                    )
                    print(f"    light state : [{status2}] {json.dumps(light_state)[:200]}")

        # ── 4. Probe airflow endpoint for any node ───────────────────────────
        print(f"\n{'─'*60}")
        print("Probing airflow endpoint (no API key — will show token accepted):")
        # Try with just the auth token and no API key — different error than unauthenticated
        status3, resp3 = get(
            f"{BASE_URL}/api-enki-airflow-prod/v1/airflow/{node_id}/check-airflow-state",
            auth_headers(token_type, access_token),  # no gateway key
        )
        print(f"  No key   → {status3}: {json.dumps(resp3)[:120]}")

        # Try with the lights key (wrong key, but authenticated)
        status4, resp4 = get(
            f"{BASE_URL}/api-enki-airflow-prod/v1/airflow/{node_id}/check-airflow-state",
            h(LIGHTS_KEY, {"homeId": home_id}),
        )
        print(f"  LIGHTS key → {status4}: {json.dumps(resp4)[:120]}")


if __name__ == "__main__":
    main()

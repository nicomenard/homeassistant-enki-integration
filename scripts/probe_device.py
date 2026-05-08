#!/usr/bin/env python3
"""
Probe an Enki fan for open ports and HTTP API endpoints.

Usage:
    python scripts/probe_device.py <ip>
    python scripts/probe_device.py 192.168.1.42
"""
import asyncio
import json
import socket
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

PORTS_TO_SCAN = [80, 443, 1883, 4455, 6668, 7000, 8080, 8081, 8443, 9000, 9999, 10000]

# Common paths found on IoT/smart home devices
HTTP_PATHS = [
    "/",
    "/api",
    "/api/v1",
    "/api/v1/status",
    "/api/v1/device",
    "/api/v1/fan",
    "/api/v1/light",
    "/api/status",
    "/api/device",
    "/api/info",
    "/status",
    "/state",
    "/device",
    "/info",
    "/fan",
    "/light",
    "/config",
    "/cgi-bin/status",
    "/cgi-bin/info",
    "/v1/info",
    "/v1/status",
    "/local",
    "/json",
    "/report",
]


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str, dict]:
    req = Request(url, headers={"User-Agent": "enki-probe/0.1", "Accept": "*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096).decode(errors="replace")
            headers = dict(resp.headers)
            return resp.status, body, headers
    except HTTPError as e:
        return e.code, "", {}
    except URLError:
        return 0, "", {}


def try_parse_json(text: str) -> str:
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, ValueError):
        return text[:300]


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <ip-address>")
        sys.exit(1)

    host = sys.argv[1]
    print(f"\n=== Probing {host} ===\n")

    # 1. Port scan
    print("[ Port scan ]")
    open_ports = []
    for port in PORTS_TO_SCAN:
        if check_port(host, port):
            open_ports.append(port)
            print(f"  OPEN  {port}")
        else:
            print(f"  closed {port}")

    if not open_ports:
        print("\nNo open ports found. Check the IP address or that the device is on.")
        sys.exit(1)

    # 2. HTTP probe on open HTTP-ish ports
    http_ports = [p for p in open_ports if p in (80, 443, 8080, 8081, 8443, 9000, 9999, 10000)]
    if not http_ports:
        print("\nNo HTTP ports open. Device may use a non-HTTP protocol.")
        print(f"Open ports: {open_ports}")
        sys.exit(0)

    print(f"\n[ HTTP probe on ports {http_ports} ]\n")
    for port in http_ports:
        scheme = "https" if port in (443, 8443) else "http"
        print(f"--- {scheme}://{host}:{port} ---")
        for path in HTTP_PATHS:
            url = f"{scheme}://{host}:{port}{path}"
            status, body, headers = http_get(url)
            if status and status not in (404, 405):
                ct = headers.get("Content-Type", "")
                indicator = "  <<< JSON!" if "json" in ct or (body.strip().startswith("{") or body.strip().startswith("[")) else ""
                print(f"  [{status}] {path}  ({ct.split(';')[0]}){indicator}")
                if body.strip():
                    print("    " + try_parse_json(body).replace("\n", "\n    "))
        print()


if __name__ == "__main__":
    main()

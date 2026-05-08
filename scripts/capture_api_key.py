"""
mitmproxy addon: intercept Enki app traffic and print the airflow API key.

Usage:
    pip install mitmproxy
    mitmproxy -s scripts/capture_api_key.py --listen-port 8888

Then on your phone:
    1. Set HTTP proxy to <your-mac-ip>:8888
    2. Install the mitmproxy CA cert (visit http://mitm.it on the phone)
    3. Open the Enki app and control the ceiling fan (change speed, turn on/off)

This script will print any X-Gateway-APIKey values it sees going to
enki.api.devportal.adeo.cloud, grouped by API service.
"""

from mitmproxy import http

ENKI_HOST = "enki.api.devportal.adeo.cloud"
seen: dict[str, str] = {}


def request(flow: http.HTTPFlow) -> None:
    if ENKI_HOST not in flow.request.pretty_host:
        return

    path = flow.request.path
    key = flow.request.headers.get("X-Gateway-APIKey", "")
    auth = flow.request.headers.get("Authorization", "")[:60]
    method = flow.request.method

    # Extract the service name from the path prefix
    parts = path.lstrip("/").split("/")
    service = parts[0] if parts else "unknown"

    if key and service not in seen:
        seen[service] = key
        print(f"\n{'='*60}")
        print(f"NEW SERVICE KEY FOUND")
        print(f"  Service : {service}")
        print(f"  Key     : {key}")
        print(f"  Path    : {path}")
        print(f"  Method  : {method}")
        print(f"{'='*60}\n")
    elif key:
        print(f"[{method}] {service}  {path.split('/')[-1]}")

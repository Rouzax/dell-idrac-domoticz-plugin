"""Dev-only: capture Redfish payloads from a live iDRAC and sanitize them.

Usage: python3 tools/capture_fixtures.py <host> <user> <password> <out_dir>

Never commit raw output. The sanitizer below is the only thing standing between
a live capture and a public repository.
"""

import base64
import json
import ssl
import sys
import urllib.request
from pathlib import Path

PATHS = {
    "system": "/redfish/v1/Systems/System.Embedded.1",
    "chassis": "/redfish/v1/Chassis/System.Embedded.1",
    "thermal": "/redfish/v1/Chassis/System.Embedded.1/Thermal",
    "power": "/redfish/v1/Chassis/System.Embedded.1/Power",
    "sensors_expanded": "/redfish/v1/Chassis/System.Embedded.1/Sensors?$expand=*($levels=1)",
    "ethernet": "/redfish/v1/Systems/System.Embedded.1/EthernetInterfaces?$expand=*($levels=1)",
    "dell_attributes": (
        "/redfish/v1/Managers/iDRAC.Embedded.1/Oem/Dell/DellAttributes/System.Embedded.1"
    ),
}

# Replacement map: real value pattern -> placeholder. Applied to the serialized
# JSON so it catches identifiers wherever they are nested.
SCRUB_KEYS = (
    "SerialNumber",
    "PartNumber",
    "UUID",
    "SKU",
    "ServiceTag",
    "MACAddress",
    "PermanentMACAddress",
    "HostName",
    "AssetTag",
    "SASAddress",
    "WWN",
    "PPID",
    "ManagerMACAddress",
    "PlatformGUID",
    "smbiosGUID",
)
PLACEHOLDERS = {
    "SerialNumber": "SERIAL0000000",
    "PartNumber": "0PARTNO00000",
    "UUID": "00000000-0000-0000-0000-000000000000",
    "SKU": "SVCTAG0",
    "ServiceTag": "SVCTAG0",
    "MACAddress": "00:11:22:33:44:55",
    "PermanentMACAddress": "00:11:22:33:44:55",
    "HostName": "server.example.invalid",
    "AssetTag": "",
    "SASAddress": "0000000000000000",
    "WWN": "0000000000000000",
    "PPID": "PPID000000000",
    "ManagerMACAddress": "00:11:22:33:44:55",
    "PlatformGUID": "00000000-0000-0000-0000-000000000000",
    "smbiosGUID": "00000000-0000-0000-0000-000000000000",
}


def scrub(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in SCRUB_KEYS and isinstance(value, str):
                out[key] = PLACEHOLDERS[key]
            else:
                out[key] = scrub(value)
        return out
    if isinstance(node, list):
        return [scrub(item) for item in node]
    return node


def fetch(host, user, password, path):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(f"https://{host}{path}")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        return json.load(resp)


def main():
    host, user, password, out_dir = sys.argv[1:5]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = dict(PATHS)
    storage_col = fetch(host, user, password, "/redfish/v1/Systems/System.Embedded.1/Storage")
    for member in storage_col.get("Members", []):
        ctrl = member["@odata.id"]
        paths["storage_expanded"] = f"{ctrl}?$expand=*($levels=1)"
        paths["volumes"] = f"{ctrl}/Volumes?$expand=*($levels=1)"
        break
    for name, path in paths.items():
        payload = scrub(fetch(host, user, password, path))
        text = json.dumps(payload, indent=1, sort_keys=True)
        (out / f"{name}.json").write_text(text + "\n", encoding="utf-8")
        print(f"wrote {name}.json ({len(text)} b)")


if __name__ == "__main__":
    main()

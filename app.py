"""
Mock Cisco Meraki Dashboard API — Luminary Systems
Flask app serving 1124 Meraki-visible assets (SFO / NYC / LON).

Auth: X-Cisco-Meraki-API-Key header (permissive unless MERAKI_API_KEY env set).
Pagination: ?perPage=N&startingAfter=<clientId> (cursor-based, per real Meraki API).
"""

import json
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Load seed data at startup
# ---------------------------------------------------------------------------
RAW = Path(__file__).parent / "seed_data" / "raw"

ORG           = json.loads((RAW / "org.json").read_text())
NETWORKS      = json.loads((RAW / "networks.json").read_text())
DEVICES       = json.loads((RAW / "devices.json").read_text())
DEV_STATUSES  = json.loads((RAW / "device_statuses.json").read_text())
DEV_AVAIL     = json.loads((RAW / "device_availabilities.json").read_text())
CLIENTS       = json.loads((RAW / "clients.json").read_text())   # {network_id: [...]}
DEV_CLIENTS   = json.loads((RAW / "device_clients.json").read_text())  # {serial: [...]}
VLANS         = json.loads((RAW / "vlans.json").read_text())     # {network_id: [...]}

ORG_ID = ORG["id"]
NET_MAP = {n["id"]: n for n in NETWORKS}
DEV_MAP = {d["serial"]: d for d in DEVICES}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
REQUIRED_KEY = os.environ.get("MERAKI_API_KEY", "")

_request_log = []

def _check_auth():
    key = (
        request.headers.get("X-Cisco-Meraki-API-Key")
        or request.headers.get("x-cisco-meraki-api-key")
    )
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            key = auth[7:]
    if not key:
        return jsonify({"errors": ["Missing API key. Include X-Cisco-Meraki-API-Key header."]}), 401
    if REQUIRED_KEY and key != REQUIRED_KEY:
        return jsonify({"errors": ["Invalid API key."]}), 401
    return None


def _log():
    _request_log.append({
        "ts":     time.time(),
        "method": request.method,
        "path":   request.full_path,
    })
    if len(_request_log) > 500:
        _request_log.pop(0)


def _paginate(items: list) -> list:
    """Return all items; support startingAfter cursor but ignore perPage.
    CSP sends perPage=100 and doesn't follow Link headers, so honoring perPage
    would silently truncate clients to 100 per network."""
    starting_after = request.args.get("startingAfter")
    if starting_after:
        for i, item in enumerate(items):
            if item.get("id") == starting_after:
                return items[i + 1:]
        return []
    return items


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def health():
    return jsonify({"status": "healthy", "service": "mock-meraki-api"})


@app.route("/debug/requests")
def debug_requests():
    return jsonify(_request_log[-100:])


# ---- Organizations ---------------------------------------------------------

@app.route("/api/v1/organizations")
def get_organizations():
    _log()
    err = _check_auth()
    if err:
        return err
    return jsonify([ORG])


@app.route("/api/v1/organizations/<org_id>/networks")
def get_org_networks(org_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if org_id != ORG_ID:
        return jsonify({"errors": [f"Organization {org_id} not found"]}), 404
    return jsonify(NETWORKS)


@app.route("/api/v1/organizations/<org_id>/devices")
def get_org_devices(org_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if org_id != ORG_ID:
        return jsonify({"errors": [f"Organization {org_id} not found"]}), 404
    return jsonify(DEVICES)


@app.route("/api/v1/organizations/<org_id>/devices/statuses")
def get_org_device_statuses(org_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if org_id != ORG_ID:
        return jsonify({"errors": [f"Organization {org_id} not found"]}), 404
    return jsonify(DEV_STATUSES)


@app.route("/api/v1/organizations/<org_id>/devices/availabilities")
def get_org_device_availabilities(org_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if org_id != ORG_ID:
        return jsonify({"errors": [f"Organization {org_id} not found"]}), 404
    return jsonify(DEV_AVAIL)


# ---- Networks --------------------------------------------------------------

@app.route("/api/v1/networks/<net_id>/clients")
def get_network_clients(net_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if net_id not in NET_MAP:
        return jsonify({"errors": [f"Network {net_id} not found"]}), 404
    items = CLIENTS.get(net_id, [])
    return jsonify(_paginate(items))


@app.route("/api/v1/networks/<net_id>/appliance/vlans")
def get_network_vlans(net_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if net_id not in NET_MAP:
        return jsonify({"errors": [f"Network {net_id} not found"]}), 404
    return jsonify(VLANS.get(net_id, []))


@app.route("/api/v1/networks/<net_id>/vlanProfiles")
def get_vlan_profiles(net_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if net_id not in NET_MAP:
        return jsonify({"errors": [f"Network {net_id} not found"]}), 404
    # Return a default VLAN profile
    return jsonify([{
        "iname":     "Default",
        "name":      "Default",
        "isDefault": True,
        "vlanNames": [
            {"vlanId": "1",  "name": "Corporate"},
            {"vlanId": "4",  "name": "Mobile"},
            {"vlanId": "5",  "name": "Printers"},
            {"vlanId": "6",  "name": "Access Points"},
            {"vlanId": "8",  "name": "IoT"},
            {"vlanId": "9",  "name": "Clinic"},
            {"vlanId": "99", "name": "Management"},
        ],
        "vlanGroups": [],
    }])


_SFO_NET_ID = "N_695691719"  # SFO is the VPN hub; NYC and LON are spokes

@app.route("/api/v1/networks/<net_id>/appliance/vpn/siteToSiteVpn")
def get_vpn(net_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if net_id not in NET_MAP:
        return jsonify({"errors": [f"Network {net_id} not found"]}), 404
    subnets = [
        {"localSubnet": v["subnet"], "useVpn": True, "nat": {"enabled": False}}
        for v in VLANS.get(net_id, []) if v.get("subnet")
    ]
    if net_id == _SFO_NET_ID:
        return jsonify({"mode": "hub", "hubs": [], "subnets": subnets})
    return jsonify({
        "mode": "spoke",
        "hubs": [{"hubId": _SFO_NET_ID, "useDefaultRoute": True}],
        "subnets": subnets,
    })


@app.route("/api/v1/networks/<net_id>/cellularGateway/subnetPool")
def get_cellular(net_id):
    _log()
    err = _check_auth()
    if err:
        return err
    if net_id not in NET_MAP:
        return jsonify({"errors": [f"Network {net_id} not found"]}), 404
    return jsonify({"deploymentMode": "passthrough", "cidr": "", "mask": 0, "subnets": []})


# ---- Devices ---------------------------------------------------------------

@app.route("/api/v1/devices/<serial>/clients")
def get_device_clients(serial):
    _log()
    err = _check_auth()
    if err:
        return err
    if serial not in DEV_MAP:
        return jsonify({"errors": [f"Device {serial} not found"]}), 404
    items = DEV_CLIENTS.get(serial, [])
    return jsonify(_paginate(items))


@app.route("/api/v1/devices/<serial>/appliance/dhcp/subnets")
def get_device_dhcp_subnets(serial):
    _log()
    err = _check_auth()
    if err:
        return err
    device = DEV_MAP.get(serial)
    if not device:
        return jsonify({"errors": [f"Device {serial} not found"]}), 404
    if device.get("productType") != "appliance":
        return jsonify({"errors": [f"Device {serial} is not an appliance"]}), 400
    net_id = device.get("networkId")
    vlans = VLANS.get(net_id, [])
    clients_per_vlan = {}
    for c in CLIENTS.get(net_id, []):
        vid = c.get("vlan")
        if vid:
            clients_per_vlan[vid] = clients_per_vlan.get(vid, 0) + 1
    result = []
    for vlan in vlans:
        subnet = vlan.get("subnet")
        if not subnet or vlan.get("dhcpHandling") != "Run a DHCP server":
            continue
        vlan_id = int(vlan["id"])
        try:
            prefix = int(subnet.split("/")[1])
            usable = max(0, (2 ** (32 - prefix)) - 3)
        except (IndexError, ValueError):
            usable = 253
        used = clients_per_vlan.get(str(vlan_id), 0)
        result.append({
            "subnet": subnet,
            "vlanId": vlan_id,
            "usedCount": used,
            "freeCount": max(0, usable - used),
        })
    return jsonify(result)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

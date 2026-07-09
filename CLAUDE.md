# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What this is

A mock **Cisco Meraki Dashboard API** (Flask) serving 1124 Luminary Systems assets across
3 Meraki-managed sites (San Francisco, New York, London), so the **Infoblox Universal
Asset Insights** Meraki connector can be pointed at a live HTTPS endpoint without a real
Meraki cloud subscription. Sibling project to the mock Mist / CrowdStrike / Intune /
Jamf / Ordr APIs; same Flask-on-App-Runner pattern.

Cisco Meraki is a cloud-managed networking platform. It reports two asset classes:
**network devices** (APs, switches, appliances) and **clients** (endpoints connected
through the Meraki-managed network).

Meraki sites are SFO / NYC / LON only — AMS / SGP / BLR are Mist sites.

## Architecture

Single Flask app (`app.py`) loads JSON files at startup:
- `seed_data/raw/org.json`                  — 1 org object
- `seed_data/raw/networks.json`             — 3 networks (SFO / NYC / LON)
- `seed_data/raw/devices.json`              — 155 devices (96 APs + 53 switches + 6 appliances)
- `seed_data/raw/device_statuses.json`      — device statuses (one per device)
- `seed_data/raw/device_availabilities.json`— device availabilities (one per device)
- `seed_data/raw/clients.json`              — 969 clients keyed by network_id
- `seed_data/raw/device_clients.json`       — per-device clients keyed by serial
- `seed_data/raw/vlans.json`                — 7 VLANs per network, keyed by network_id

Deployed via `Dockerfile` (gunicorn).

## The API contract

Based on the Cisco Meraki Dashboard REST API v1:
- `GET /api/v1/organizations`                                  → [org]
- `GET /api/v1/organizations/{orgId}/networks`                 → [network]
- `GET /api/v1/organizations/{orgId}/devices`                  → [device]
- `GET /api/v1/organizations/{orgId}/devices/statuses`         → [device_status]
- `GET /api/v1/organizations/{orgId}/devices/availabilities`   → [device_availability]
- `GET /api/v1/networks/{networkId}/clients`                   → [client] (paginated)
- `GET /api/v1/networks/{networkId}/appliance/vlans`           → [vlan]
- `GET /api/v1/networks/{networkId}/vlanProfiles`              → [vlan_profile]
- `GET /api/v1/networks/{networkId}/appliance/vpn/siteToSiteVpn` → vpn_config
- `GET /api/v1/networks/{networkId}/cellularGateway/subnetPool`  → stub
- `GET /api/v1/devices/{serial}/clients`                       → [device_client] (simplified)

**Auth:** `X-Cisco-Meraki-API-Key` header. Permissive by default unless `MERAKI_API_KEY` env var set.

**Pagination (clients):** `?perPage=N&startingAfter=<clientId>` cursor-based (real Meraki style).

## Data generation

`python seed_data/generate_meraki_data.py` rebuilds all JSON files from
`assets_luminary.xlsx` — all rows where `seen_by` includes `meraki` (1124 rows, v7 dataset).

Category mapping:
- `wap` → device (productType: wireless, model: MR57)
- `switch` → device (productType: switch, model: MS225-48)
- `router` → device (productType: appliance, model: MX450)
- `win_laptop`, `mac_laptop`, `mobile_ios`, `mobile_droid` → wireless clients
- `iot` → wireless clients (IoT SSID)
- `linux_ws`, `printer`, `clinic` → wired clients (switchport)

Central/local fallback:
```python
_CENTRAL = ROOT.parent / "luminary-demo-docs" / "master-sheet" / "assets_luminary.xlsx"
_LOCAL   = ROOT / "seed_data" / "source" / "assets_luminary.xlsx"
XLSX     = _CENTRAL if _CENTRAL.exists() else _LOCAL
```

`seed_data/raw/*.json` IS committed — the deployed app serves data immediately.
xlsx files are gitignored.

## Key schema details

- **MAC format:** `aa:bb:cc:dd:ee:ff` (colon-separated lowercase)
- **Timestamps:** `firstSeen`/`lastSeen` = Unix timestamp as STRING (e.g., `"1751327000"`).
  `configurationUpdatedAt`/`lastReportedAt` = ISO 8601 string.
- **Client usage:** bytes (int) at `/networks/{id}/clients`; KB (int) at `/devices/{serial}/clients`.
- **Client id:** 12-char hex string (md5 slice of hostname seed).
- **Device serial:** `Q2KD-XXXX-XXXX` (APs), `Q2QN-XXXX-XXXX` (switches/appliances).

## VLAN structure

| VLAN | Segment | Name       | IP scheme (SFO)  | Asset types         |
|------|---------|------------|------------------|---------------------|
| 1    | .1      | Corporate  | 10.11.1.0/24     | win_laptop, mac_laptop, linux_ws |
| 4    | .4      | Mobile     | 10.11.4.0/24     | mobile_ios, mobile_droid |
| 5    | .5      | Printers   | 10.11.5.0/24     | printer             |
| 6    | .6      | Access Points | 10.11.6.0/24  | wap                 |
| 8    | .8      | IoT        | 10.11.8.0/24     | iot                 |
| 9    | .9      | Clinic     | 10.11.9.0/24     | clinic              |
| 99   | .0      | Management | 10.11.0.0/24     | switches, routers   |

## AWS / Docker deploy

ECR repo: `mock-meraki-api` (account `905418046272`, region `us-east-1`).
App Runner service ARN: `arn:aws:apprunner:us-east-1:905418046272:service/mock-meraki-api/1dbf5b2a738044ca9b5f403254674b0a`
Live endpoint: `https://4ndm7ee4pz.us-east-1.awsapprunner.com`

Deploy via docker build + push. App Runner runs in **permissive auth mode** — no
`MERAKI_API_KEY` env var is set, so any non-empty key is accepted. In UAI, enter any
placeholder key (e.g. `mock_meraki_key`) as the API key.

```bash
docker build --no-cache --platform linux/amd64 -t mock-meraki-build .
docker tag mock-meraki-build 905418046272.dkr.ecr.us-east-1.amazonaws.com/mock-meraki-api:latest
docker push 905418046272.dkr.ecr.us-east-1.amazonaws.com/mock-meraki-api:latest
```

# Mock Cisco Meraki API

A mock implementation of the **Cisco Meraki Dashboard API**, designed for **Infoblox
Universal Asset Insights** integration testing and demos. Points the Infoblox Meraki
connector at a live HTTPS endpoint without a real Meraki cloud subscription.

## Overview

Cisco Meraki is a cloud-managed **Wi-Fi / switching / SD-WAN** platform. It discovers
and manages two classes of assets:

- **Network devices** — APs (MR series), switches (MS series), and appliances (MX series)
- **Clients** — endpoints (laptops, mobiles, printers, IoT) connected through
  Meraki-managed networks

This mock serves **1124 assets** across 3 Luminary Systems sites (San Francisco, New York,
London) drawn from the Luminary Systems UAI Demo Dataset v7.

## API surface

| Method & path | Purpose |
|---|---|
| `GET /api/v1/organizations` | Single Luminary Systems org |
| `GET /api/v1/organizations/{orgId}/networks` | 3 networks (SFO / NYC / LON) |
| `GET /api/v1/organizations/{orgId}/devices` | All APs + switches + appliances |
| `GET /api/v1/organizations/{orgId}/devices/statuses` | Per-device online status |
| `GET /api/v1/organizations/{orgId}/devices/availabilities` | Per-device availability |
| `GET /api/v1/networks/{networkId}/clients` | Clients at network (paginated) |
| `GET /api/v1/networks/{networkId}/appliance/vlans` | VLAN config |
| `GET /api/v1/networks/{networkId}/vlanProfiles` | VLAN profiles |
| `GET /api/v1/networks/{networkId}/appliance/vpn/siteToSiteVpn` | VPN config |
| `GET /api/v1/devices/{serial}/clients` | Clients on a specific device |

Extras: `GET /` health check, `GET /debug/requests` (request log).

### Authentication

Meraki uses the `X-Cisco-Meraki-API-Key` header. The mock is permissive by default —
any non-empty key is accepted unless `MERAKI_API_KEY` env var is set.

```bash
curl -H "X-Cisco-Meraki-API-Key: mock_meraki_key_luminary" \
  "$BASE/api/v1/organizations"
```

### Pagination

`GET /networks/{id}/clients` supports Meraki cursor pagination:
`?perPage=1000&startingAfter=<clientId>`

## Data

**1124 total assets** — 969 clients + 155 network devices — across 3 Meraki-managed
sites (SFO / NYC / LON only; AMS / SGP / BLR are Mist sites in this dataset).

### Fleet breakdown

| Category | Meraki type | Count |
|----------|-------------|-------|
| Windows laptops | wireless client | 322 |
| macOS laptops | wireless client | 191 |
| iOS mobile | wireless client | 148 |
| Android mobile | wireless client | 126 |
| IoT / cameras | wireless client | 130 |
| Access Points (Cisco Meraki MR57) | network device | 96 |
| Switches (Cisco Meraki MS225-48) | network device | 53 |
| Printers | wired client | 25 |
| Linux workstations | wired client | 18 |
| Clinic / medical devices | wired client | 9 |
| Routers (Cisco MX450 appliance) | network device | 6 |
| **Total** | | **1124** |

### Site breakdown

| Site | Clients | Devices | Total |
|------|---------|---------|-------|
| San Francisco (SFO) | 495 | 80 | 575 |
| New York (NYC) | 220 | 39 | 259 |
| London (LON) | 254 | 36 | 290 |

### Key IDs

| Resource | ID |
|----------|----|
| Org | `51336d5d-3abf-6a4a-c4a3-c1d8beeb44ef` |
| SFO network | `6fec2fb6-45dc-d2de-a94c-25498f93f8c7` |
| NYC network | `d7495cf1-9fd6-e48a-fdd8-c63dedeb069a` |
| LON network | `4ec98c15-f3a3-c9b7-1393-d4dea0efe855` |

### Cross-system matching

Hostnames / IPs / MACs come verbatim from the master sheet — Asset Insights
correlates the same physical device across Meraki, CrowdStrike, Intune, Jamf, and
ServiceNow automatically.

Source of truth: [`luminary-demo-docs/master-sheet/assets_luminary.xlsx`](https://github.com/repswalp-cmd/luminary-demo-docs)
(Luminary Systems UAI Demo Dataset v7, ~2,295 total assets).

Regenerate deterministically:

```bash
python seed_data/generate_meraki_data.py
# writes seed_data/raw/{org,networks,devices,clients,vlans,...}.json
```

## Run locally

```bash
pip install -r requirements.txt
python app.py                 # serves on :5000
# or:
gunicorn app:app --bind 0.0.0.0:8080
```

## Deploy (AWS App Runner)

```bash
# Authenticate
aws sso login --profile okta-sso
aws ecr get-login-password --profile okta-sso --region us-east-1 \
  | docker login --username AWS --password-stdin \
    905418046272.dkr.ecr.us-east-1.amazonaws.com

# Build AMD64
docker build --no-cache --platform linux/amd64 -t mock-meraki-build .
docker tag mock-meraki-build 905418046272.dkr.ecr.us-east-1.amazonaws.com/mock-meraki-api:latest
docker push 905418046272.dkr.ecr.us-east-1.amazonaws.com/mock-meraki-api:latest
```

App Runner picks up the new image automatically (`AutoDeploymentsEnabled=True`).

## Reference

`docs/meraki_responses/` holds representative request/response pairs.

## Contact

Built for Infoblox Universal Asset Insights testing.
Contact: **TME — Rajkumar Repswal**

---
*Mock API for testing purposes. Not affiliated with or endorsed by Cisco Systems or Infoblox.*

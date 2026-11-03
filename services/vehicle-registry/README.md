# Vehicle Registry Service

Owns the list of fleet vehicles and which wallet each one is charged to. Toll Transaction asks it whether a vehicle may be charged.

## API (base: /api/v1/vehicles)
| Method | Path | Result |
|---|---|---|
| POST | `/` body `{vehicle_id, fleet_id, wallet_id}` | 201 vehicle, 409 VEHICLE_EXISTS, 422 VALIDATION_ERROR |
| GET | `/?fleet_id=` | 200 list |
| GET | `/{vehicle_id}` | 200 `{vehicle_id, fleet_id, wallet_id, active}`, 404 VEHICLE_NOT_FOUND |
| PATCH | `/{vehicle_id}` body `{active}` | 200 vehicle, 404 |
| GET | `/{vehicle_id}/chargeable` | 200 `{..., chargeable: true}`, 404 VEHICLE_NOT_FOUND, 409 VEHICLE_INACTIVE |
| GET | `/health` | 200 |

## Business rule
| ID | Rule | Enforced in | Tests |
|---|---|---|---|
| BR5 | Only a registered, active vehicle can be charged a toll | `service.assert_chargeable`; Toll Transaction also checks `active` before deducting | `test_br5_*` |

## Run
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
mysql -u registry_user -p registry_db < schema.sql
uvicorn app.main:app --port 8003
```

## Test
`python -m pytest -v` (needs the database from `.env`)

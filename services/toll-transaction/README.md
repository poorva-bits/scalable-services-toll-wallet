# Toll Transaction Service

Receives toll gate crossings and runs the flow: check vehicle, deduct from wallet, notify.

## Run
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
mysql -u toll_user -p toll_db < schema.sql
uvicorn app.main:app --port 8002
```
Set USE_STUBS=false and the registry/notification URLs once those services run. Wallet must always be running.

## Test
`python -m pytest -v`
# Wallet Service

Holds fleet wallet balances and a ledger of every top-up and deduction.

## Run
```bash
python -m venv .venv 
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL
mysql -u wallet_user -p wallet_db < schema.sql
uvicorn app.main:app --port 8001
```
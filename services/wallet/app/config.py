import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
BANK_URL = os.getenv("BANK_URL", "")  # empty = stubbed bank (always succeeds)
BANK_TIMEOUT = float(os.getenv("BANK_TIMEOUT", "2"))  # seconds per attempt
BANK_MAX_ATTEMPTS = int(os.getenv("BANK_MAX_ATTEMPTS", "4"))  # first try + retries
BANK_BACKOFF_BASE = float(os.getenv("BANK_BACKOFF_BASE", "0.5"))  # seconds, doubled each retry
BANK_BACKOFF_MAX = float(os.getenv("BANK_BACKOFF_MAX", "4"))  # cap on a single wait

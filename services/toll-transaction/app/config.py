import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]  # required, no hard-coded default
WALLET_URL = os.environ["WALLET_URL"]  # wallet service base url
REGISTRY_URL = os.getenv("REGISTRY_URL", "")  # only needed when USE_STUBS is false
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "")  # only needed when USE_STUBS is false
USE_STUBS = os.getenv("USE_STUBS", "true").lower() == "true"  # fake registry/notification until real ones exist
STUB_WALLET_ID = int(os.getenv("STUB_WALLET_ID", "1"))  # wallet id the stub registry returns
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "3"))  # seconds to wait on other services
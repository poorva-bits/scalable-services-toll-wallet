import os

from dotenv import load_dotenv

load_dotenv()

MODES = ("ok", "slow", "fail", "flaky")
MODE = os.getenv("MODE", "ok").lower()  # starting behaviour; switchable at runtime
SLOW_SECONDS = float(os.getenv("SLOW_SECONDS", "5"))  # delay in slow mode
FLAKY_FAILURES = int(os.getenv("FLAKY_FAILURES", "2"))  # failed attempts per reference before success in flaky mode

"""Integration check for the Notification Service; start Docker Compose first. Usage: python notification_test.py"""
import os
import random

import requests

BASE_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")
wallet_id = random.randint(10**6, 10**9)

print("HEALTH:", requests.get(f"{BASE_URL}/health", timeout=5).json())

first = requests.post(f"{BASE_URL}/api/v1/notifications", json={"wallet_id": wallet_id, "type": "LOW_BALANCE", "message": "Balance too low"},
                      headers={"X-Request-ID": "notification-test-001"}, timeout=5)
assert first.status_code == 201, (first.status_code, first.text)
repeat = requests.post(f"{BASE_URL}/api/v1/notifications", json={"wallet_id": wallet_id, "type": "LOW_BALANCE", "message": "Balance too low"}, timeout=5)
assert repeat.status_code == 200 and repeat.json()["suppressed"] is True, repeat.text
print("LOW_BALANCE first:", first.status_code, "repeat suppressed:", repeat.json()["suppressed"])

charged = requests.post(f"{BASE_URL}/api/v1/notifications", json={"wallet_id": wallet_id, "type": "TOLL_CHARGED", "message": "Toll charged"}, timeout=5)
assert charged.status_code == 201, charged.text
again = requests.post(f"{BASE_URL}/api/v1/notifications", json={"wallet_id": wallet_id, "type": "LOW_BALANCE", "message": "Balance too low"}, timeout=5)
assert again.status_code == 201, again.text
print("after TOLL_CHARGED, LOW_BALANCE reported again:", again.status_code)

listed = requests.get(f"{BASE_URL}/api/v1/notifications", params={"wallet_id": wallet_id}, timeout=5).json()
print("LISTED:", [n["type"] for n in listed])

"""Integration checks for Notification Service; start Docker Compose first."""
import os
import uuid
import requests

BASE_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")
booking_id = f"notification-test-{uuid.uuid4()}"
payload = {
    "booking_id": booking_id,
    "message": "Your appointment is confirmed",
    "recipient": "patient-test",
    "channel": "mock",
}

health = requests.get(f"{BASE_URL}/health", timeout=5)
health.raise_for_status()
print("HEALTH:", health.json())

first = requests.post(f"{BASE_URL}/api/v1/notifications", json=payload, headers={"X-Request-ID": "notification-test-001"}, timeout=5)
assert first.status_code == 201, (first.status_code, first.text)
first_body = first.json()
print("FIRST:", first.status_code, {"id": first_body["id"], "booking_id": first_body["booking_id"], "status": first_body["status"]})

replay = requests.post(f"{BASE_URL}/api/v1/notifications", json=payload, headers={"X-Request-ID": "notification-test-002"}, timeout=5)
assert replay.status_code == 200, (replay.status_code, replay.text)
assert replay.json()["id"] == first_body["id"]
print("REPLAY:", replay.status_code, "same notification id:", replay.json()["id"] == first_body["id"])

changed = dict(payload, message="Different message for same booking")
conflict = requests.post(f"{BASE_URL}/api/v1/notifications", json=changed, timeout=5)
assert conflict.status_code == 409, (conflict.status_code, conflict.text)
print("PAYLOAD CONFLICT:", conflict.status_code, conflict.json())

records = requests.get(f"{BASE_URL}/api/v1/notifications?limit=500", timeout=5)
records.raise_for_status()
matching = [item for item in records.json() if item["booking_id"] == booking_id]
assert len(matching) == 1, f"Expected one notification record, got {len(matching)}"
print("DATABASE/API STATE: exactly one notification record for test booking")
print("Notification Service checks passed.")

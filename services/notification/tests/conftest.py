import os
import sys
import tempfile

# Use a throwaway SQLite file for tests and make app.py importable
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_notification.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""Run tests against a throw-away copy of the ingested DB so dev data is never touched."""
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not os.environ.get("TEST_DATABASE_URL"):
    _tmp = Path(tempfile.mkdtemp()) / "test.db"
    shutil.copy(ROOT / "data" / "bruinbuddy.db", _tmp)
    os.environ["BB_DB_PATH"] = str(_tmp)
    os.environ.pop("DATABASE_URL", None)
else:  # run the same suite against a throw-away Postgres that already has the course ingested
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["BB_MOCK_LLM"] = "1"

import os
import tempfile

# Keep tests off the real database and off the network
os.environ["FIELDDX_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["FIELDDX_LLM"] = "off"
os.environ.pop("GEMINI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app import db
    from app.main import app
    db.reset()
    return TestClient(app)

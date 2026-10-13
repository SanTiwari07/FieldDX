import os
import tempfile

# Keep tests off the real database and off the network
os.environ["FIELDDX_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["FIELDDX_LLM"] = "off"
os.environ.pop("GEMINI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient


def signed_in(area: str) -> TestClient:
    """A browser session for a fresh officer who works in `area`."""
    import secrets
    from app.main import app
    c = TestClient(app)
    user = f"t{secrets.token_hex(4)}"
    assert c.post("/api/auth/register", json={"name": "Test Officer", "username": user, "pin": "4321"}).status_code == 200
    assert c.post("/api/me/area", json={"area_id": area}).status_code == 200
    return c


@pytest.fixture()
def client():
    from app import db
    db.reset()
    return signed_in("niphad")

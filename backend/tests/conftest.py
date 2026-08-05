import os
import tempfile
from pathlib import Path

TEST_DATABASE_PATH=Path(tempfile.gettempdir())/f"letter_test_{os.getpid()}.db"
TEST_DATABASE_PATH.unlink(missing_ok=True)
os.environ["LETTER_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH}"
os.environ["LETTER_SECRET_KEY"] = "test-secret-key-with-more-than-thirty-two-chars"
os.environ["LETTER_LOGIN_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["LETTER_PUBLIC_RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.seed import seed


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(engine); seed(); yield; Base.metadata.drop_all(engine);engine.dispose();TEST_DATABASE_PATH.unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as value: yield value


@pytest.fixture
def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@letter.com.br", "password": "Letter@123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

"""
Shared fixtures for backend tests.
Uses an in-memory SQLite DB so no real PostgreSQL is needed.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.models import Base
from app.main import app

SQLITE_URL = "sqlite:///./test_token_monitor.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client():
    """Fresh DB + TestClient for each test function."""
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

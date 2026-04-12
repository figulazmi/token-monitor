"""
Root conftest — runs before any test collection.
Set DATABASE_URL to SQLite so no PostgreSQL is needed for tests.
Must stay at the top before any app imports.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_token_monitor.db"

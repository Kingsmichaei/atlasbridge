"""Shared test environment.

Settings are read once, when app.config is first imported, so every test module must see the
same environment no matter which one pytest collects first. These match test_gateway.py.
"""
import os

os.environ["MOCK_UPSTREAM"] = "1"
os.environ["ADMIN_TOKEN"] = "admin-test"
os.environ["SIGNUP_CODE"] = "beta"
os.environ["DATABASE_URL"] = "sqlite:///./test_atlasbridge.db"
os.environ["LOG_CONTENT"] = "1"
os.environ["SESSION_SECRET"] = "test-session-secret"

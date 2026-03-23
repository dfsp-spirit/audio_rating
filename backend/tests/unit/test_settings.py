import pytest

from audiorating_backend.settings import ARBackendSettings


def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv("AR_DATABASE_URL", "sqlite:///tmp.db")
    cfg = ARBackendSettings()
    assert cfg.database_url == "sqlite:///tmp.db"


def test_database_url_missing_raises(monkeypatch):
    monkeypatch.delenv("AR_DATABASE_URL", raising=False)
    cfg = ARBackendSettings()
    with pytest.raises(ValueError, match="AR_DATABASE_URL"):
        _ = cfg.database_url


def test_allowed_origins_parsing(monkeypatch):
    monkeypatch.setenv("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    cfg = ARBackendSettings()
    assert cfg.allowed_origins == ["http://localhost:3000"]


def test_allowed_origins_missing_raises(monkeypatch):
    monkeypatch.setenv("AR_ALLOWED_ORIGINS", "[]")
    cfg = ARBackendSettings()
    with pytest.raises(ValueError, match="AR_ALLOWED_ORIGINS"):
        _ = cfg.allowed_origins


def test_frontend_url_ensures_trailing_slash(monkeypatch):
    monkeypatch.setenv("AR_FRONTEND_URL", "https://example.org/rate")
    cfg = ARBackendSettings()
    assert cfg.frontend_url == "https://example.org/rate/"


def test_rootpath_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("AR_ROOTPATH", "/ar_backend/")
    cfg = ARBackendSettings()
    assert cfg.rootpath == "/ar_backend"


def test_admin_credentials_from_env(monkeypatch):
    monkeypatch.setenv("AR_API_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("AR_API_ADMIN_PASSWORD", "secret")
    cfg = ARBackendSettings()
    assert cfg.admin_username == "admin"
    assert cfg.admin_password == "secret"

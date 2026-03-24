import pytest

from app.config.cors import (
    DEV_CORS_ORIGINS,
    get_cors_allow_credentials,
    get_cors_allowed_origins,
)


def test_get_cors_allowed_origins_uses_dev_defaults_when_env_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    origins = get_cors_allowed_origins()

    assert origins == DEV_CORS_ORIGINS


def test_get_cors_allowed_origins_uses_dev_defaults_when_env_blank(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "   ")

    origins = get_cors_allowed_origins()

    assert origins == DEV_CORS_ORIGINS


def test_get_cors_allowed_origins_parses_explicit_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " https://app.example.com , http://192.168.1.50:5173 ",
    )

    origins = get_cors_allowed_origins()

    assert origins == ["https://app.example.com", "http://192.168.1.50:5173"]


def test_get_cors_allowed_origins_supports_explicit_allow_all(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    origins = get_cors_allowed_origins()

    assert origins == ["*"]


def test_get_cors_allowed_origins_rejects_mixed_wildcard_and_specific(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*,https://app.example.com")

    with pytest.raises(ValueError, match="cannot be combined"):
        get_cors_allowed_origins()


def test_get_cors_allow_credentials_is_false_for_wildcard():
    assert get_cors_allow_credentials(["*"]) is False


def test_get_cors_allow_credentials_is_true_for_specific_origins():
    assert get_cors_allow_credentials(["https://app.example.com"]) is True

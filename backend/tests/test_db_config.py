import importlib
import sys
from pathlib import Path

import sqlalchemy
import sqlalchemy.orm as sa_orm


MODULE_NAME = "app.db.db"


def _load_db_module(monkeypatch, database_url):
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    calls = {"create_engine": [], "sessionmaker": [], "declarative_base": 0}

    def fake_create_engine(url, **kwargs):
        engine_obj = {"url": url, "kwargs": kwargs}
        calls["create_engine"].append((url, kwargs, engine_obj))
        return engine_obj

    def fake_sessionmaker(**kwargs):
        session_factory = {"sessionmaker_kwargs": kwargs}
        calls["sessionmaker"].append((kwargs, session_factory))
        return session_factory

    def fake_declarative_base():
        calls["declarative_base"] += 1
        return "BASE_SENTINEL"

    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)
    monkeypatch.setattr(sa_orm, "sessionmaker", fake_sessionmaker)
    monkeypatch.setattr(sa_orm, "declarative_base", fake_declarative_base)

    sys.modules.pop(MODULE_NAME, None)
    module = importlib.import_module(MODULE_NAME)
    return module, calls


def test_db_config_default_sqlite_path_and_sqlite_engine_args(monkeypatch):
    module, calls = _load_db_module(monkeypatch, database_url=None)

    expected_path = (Path(module.__file__).resolve().parents[2] / "app.db").as_posix()
    expected_url = f"sqlite:///{expected_path}"

    assert module.DEFAULT_SQLITE_PATH == expected_path
    assert module.DATABASE_URL == expected_url

    assert len(calls["create_engine"]) == 1
    create_url, create_kwargs, create_engine_obj = calls["create_engine"][0]
    assert create_url == expected_url
    assert create_kwargs == {"connect_args": {"check_same_thread": False}}
    assert module.engine == create_engine_obj

    assert len(calls["sessionmaker"]) == 1
    session_kwargs, session_obj = calls["sessionmaker"][0]
    assert session_kwargs == {"autocommit": False, "autoflush": False, "bind": module.engine}
    assert module.SessionLocal == session_obj

    assert calls["declarative_base"] == 1
    assert module.Base == "BASE_SENTINEL"


def test_db_config_sqlite_database_url_uses_sqlite_connect_args(monkeypatch):
    module, calls = _load_db_module(monkeypatch, database_url="sqlite:///custom.db")

    assert module.DATABASE_URL == "sqlite:///custom.db"
    create_url, create_kwargs, _ = calls["create_engine"][0]
    assert create_url == "sqlite:///custom.db"
    assert create_kwargs == {"connect_args": {"check_same_thread": False}}


def test_db_config_non_sqlite_database_url_omits_sqlite_connect_args(monkeypatch):
    module, calls = _load_db_module(
        monkeypatch,
        database_url="postgresql://user:pass@localhost:5432/testdb",
    )

    assert module.DATABASE_URL == "postgresql://user:pass@localhost:5432/testdb"
    create_url, create_kwargs, _ = calls["create_engine"][0]
    assert create_url == "postgresql://user:pass@localhost:5432/testdb"
    assert create_kwargs == {}
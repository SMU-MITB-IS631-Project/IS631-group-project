import importlib
from unittest.mock import Mock


def test_get_db_yields_session_and_closes_on_normal_teardown(monkeypatch):
    db_module = importlib.import_module("app.dependencies.db")
    fake_session = Mock()
    session_factory = Mock(return_value=fake_session)
    monkeypatch.setattr(db_module, "SessionLocal", session_factory)

    gen = db_module.get_db()
    yielded = next(gen)

    assert yielded is fake_session
    session_factory.assert_called_once_with()

    # Finish dependency lifecycle as FastAPI would after request handling.
    try:
        next(gen)
    except StopIteration:
        pass

    fake_session.close.assert_called_once_with()


def test_get_db_closes_session_when_generator_is_closed_early(monkeypatch):
    db_module = importlib.import_module("app.dependencies.db")
    fake_session = Mock()
    session_factory = Mock(return_value=fake_session)
    monkeypatch.setattr(db_module, "SessionLocal", session_factory)

    gen = db_module.get_db()
    yielded = next(gen)
    assert yielded is fake_session

    # Simulate request abort/exception path where generator is closed.
    gen.close()

    fake_session.close.assert_called_once_with()
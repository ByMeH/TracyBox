import sqlite3
from pathlib import Path

import pytest

import main
from database import connect_database as open_sqlite_database


class FakeApplication:
    exit_code = 7

    def __init__(self, argv):
        self.argv = argv
        self.icon = None

    def setWindowIcon(self, icon):
        self.icon = icon

    def exec(self):
        return self.exit_code


class FakeMessageBox:
    def __init__(self):
        self.calls = []

    def critical(self, parent, title, text):
        self.calls.append((title, text))


class FakeWindow:
    def __init__(self, connection):
        self.connection = connection
        self.was_shown = False

    def show(self):
        self.was_shown = True


class TrackingConnection:
    def __init__(self, connection):
        self._connection = connection
        self.close_calls = 0

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        self.close_calls += 1
        self._connection.close()


@pytest.fixture
def lifecycle(monkeypatch, tmp_path):
    opened_connections = []
    windows = []
    message_box = FakeMessageBox()

    def connect_database(db_path):
        connection = TrackingConnection(open_sqlite_database(db_path))
        opened_connections.append(connection)
        return connection

    class RecordingWindow(FakeWindow):
        def __init__(self, connection):
            super().__init__(connection)
            windows.append(self)

    monkeypatch.setattr(main, "QApplication", FakeApplication)
    monkeypatch.setattr(main, "QMessageBox", message_box)
    monkeypatch.setattr(main, "resource_path", lambda relative_path: tmp_path / relative_path)
    monkeypatch.setattr(main, "connect_database", connect_database)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(main, "MainWindow", RecordingWindow)

    return opened_connections, message_box, windows


def test_main_closes_connection_after_normal_shutdown(lifecycle):
    opened_connections, _, windows = lifecycle

    assert main.main() == 7
    assert len(opened_connections) == 1
    assert opened_connections[0].close_calls == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened_connections[0].execute("SELECT 1")
    assert len(windows) == 1
    assert windows[0].was_shown is True


def test_main_closes_connection_when_initialize_database_fails(lifecycle, monkeypatch):
    opened_connections, message_box, _ = lifecycle

    def fail_initialization(connection):
        raise sqlite3.OperationalError("schema failure")

    monkeypatch.setattr(main, "initialize_database", fail_initialization)

    assert main.main() == 1
    assert len(opened_connections) == 1
    assert opened_connections[0].close_calls == 1
    assert message_box.calls == [
        ("Ошибка базы данных", "Не удалось открыть базу данных: schema failure")
    ]


def test_main_closes_connection_when_window_creation_fails(lifecycle, monkeypatch):
    opened_connections, _, _ = lifecycle

    def fail_window_creation(connection):
        raise RuntimeError("window failure")

    monkeypatch.setattr(main, "MainWindow", fail_window_creation)

    with pytest.raises(RuntimeError, match="window failure"):
        main.main()
    assert len(opened_connections) == 1
    assert opened_connections[0].close_calls == 1


def test_main_closes_connection_when_application_run_fails(lifecycle, monkeypatch):
    opened_connections, _, _ = lifecycle

    class FailingApplication(FakeApplication):
        def exec(self):
            raise RuntimeError("event loop failure")

    monkeypatch.setattr(main, "QApplication", FailingApplication)

    with pytest.raises(RuntimeError, match="event loop failure"):
        main.main()
    assert len(opened_connections) == 1
    assert opened_connections[0].close_calls == 1


def test_close_error_does_not_mask_initialization_error(lifecycle, monkeypatch):
    _, message_box, _ = lifecycle

    class FailingCloseConnection:
        def __init__(self):
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            raise sqlite3.OperationalError("close failure")

    connection = FailingCloseConnection()

    def fail_initialization(connection):
        raise sqlite3.OperationalError("schema failure")

    monkeypatch.setattr(main, "connect_database", lambda db_path: connection)
    monkeypatch.setattr(main, "initialize_database", fail_initialization)

    assert main.main() == 1
    assert connection.close_calls == 1
    assert message_box.calls == [
        ("Ошибка базы данных", "Не удалось открыть базу данных: schema failure")
    ]


def test_close_error_after_normal_shutdown_is_reported(lifecycle, monkeypatch, capsys):
    _, _, windows = lifecycle

    class FailingCloseConnection:
        def __init__(self):
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            raise sqlite3.OperationalError("close failure")

    connection = FailingCloseConnection()

    monkeypatch.setattr(main, "connect_database", lambda db_path: connection)
    monkeypatch.setattr(main, "initialize_database", lambda connection: None)

    assert main.main() == 1
    assert connection.close_calls == 1
    assert len(windows) == 1
    assert windows[0].was_shown is True
    assert "Не удалось закрыть базу данных: close failure" in capsys.readouterr().err

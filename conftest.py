import pytest

from database import connect_database, initialize_database


@pytest.fixture
def connection(tmp_path):
    connection = connect_database(tmp_path / "tracebox.db")
    initialize_database(connection)
    yield connection
    connection.close()

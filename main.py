import sqlite3
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from database import connect_database, initialize_database
from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent / "assets" / "tracebox.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    try:
        database_directory = Path.home() / ".tracebox"
        database_directory.mkdir(parents=True, exist_ok=True)
        connection = connect_database(database_directory / "tracebox.db")
        initialize_database(connection)
    except OSError as error:
        QMessageBox.critical(None, "Ошибка каталога данных", f"Не удалось создать каталог данных: {error}")
        return 1
    except sqlite3.Error as error:
        QMessageBox.critical(None, "Ошибка базы данных", f"Не удалось открыть базу данных: {error}")
        return 1

    try:
        window = MainWindow(connection)
        window.show()
        exit_code = app.exec()
    finally:
        connection.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

import sqlite3
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from database import connect_database, initialize_database
from main_window import MainWindow


def resource_path(relative_path: str) -> Path:
    # В сборке PyInstaller ресурсы распаковываются во временный каталог sys._MEIPASS
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / relative_path
    return Path(__file__).resolve().parent / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = resource_path("assets/tracebox.svg")
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

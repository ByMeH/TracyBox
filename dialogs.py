import sqlite3
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import repositories
import tools
from constants import DEFAULT_DIFFICULTY, DEFAULT_STATUS, DIFFICULTIES, STATUSES


class CompetitionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, competition: sqlite3.Row | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новое соревнование" if competition is None else "Изменение соревнования")
        self.setMinimumWidth(420)

        self.name_edit = QLineEdit()
        self.platform_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.has_date_check = QCheckBox("Указать")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setEnabled(False)
        self.has_date_check.toggled.connect(self.date_edit.setEnabled)
        self.description_edit = QTextEdit()

        date_row = QHBoxLayout()
        date_row.addWidget(self.has_date_check)
        date_row.addWidget(self.date_edit)
        date_row.addStretch()
        date_widget = QWidget()
        date_widget.setLayout(date_row)

        form = QFormLayout()
        form.addRow("Название*", self.name_edit)
        form.addRow("Организатор", self.platform_edit)
        form.addRow("Ссылка", self.url_edit)
        form.addRow("Дата начала", date_widget)
        form.addRow("Описание", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if competition is not None:
            self.name_edit.setText(competition["name"])
            self.platform_edit.setText(competition["platform"])
            self.url_edit.setText(competition["url"])
            start_date = QDate.fromString(competition["start_date"], "yyyy-MM-dd")
            if start_date.isValid():
                self.has_date_check.setChecked(True)
                self.date_edit.setDate(start_date)
            self.description_edit.setPlainText(competition["description"])

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Проверка ввода", "Укажите название соревнования.")
            return
        self.accept()

    def values(self) -> dict[str, str]:
        if self.has_date_check.isChecked():
            start_date = self.date_edit.date().toString("yyyy-MM-dd")
        else:
            start_date = ""
        return {
            "name": self.name_edit.text(),
            "platform": self.platform_edit.text().strip(),
            "url": self.url_edit.text().strip(),
            "start_date": start_date,
            "description": self.description_edit.toPlainText().strip(),
        }


class ChallengeDialog(QDialog):
    def __init__(
        self,
        competitions: list[sqlite3.Row],
        parent: QWidget | None = None,
        challenge: sqlite3.Row | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новое задание" if challenge is None else "Изменение задания")
        self.setMinimumWidth(420)

        self.competition_combo = QComboBox()
        for competition in competitions:
            self.competition_combo.addItem(competition["name"], competition["id"])
        self.title_edit = QLineEdit()
        self.category_edit = QLineEdit()
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTIES)
        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.points_spin = QSpinBox()
        self.points_spin.setRange(0, 1_000_000)
        self.description_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Соревнование*", self.competition_combo)
        form.addRow("Название*", self.title_edit)
        form.addRow("Категория", self.category_edit)
        form.addRow("Сложность", self.difficulty_combo)
        form.addRow("Статус", self.status_combo)
        form.addRow("Баллы", self.points_spin)
        form.addRow("Описание", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if challenge is None:
            self.difficulty_combo.setCurrentText(DEFAULT_DIFFICULTY)
            self.status_combo.setCurrentText(DEFAULT_STATUS)
        else:
            self.competition_combo.setCurrentIndex(self.competition_combo.findData(challenge["competition_id"]))
            self.title_edit.setText(challenge["title"])
            self.category_edit.setText(challenge["category"])
            self.difficulty_combo.setCurrentText(challenge["difficulty"])
            self.status_combo.setCurrentText(challenge["status"])
            self.points_spin.setValue(challenge["points"])
            self.description_edit.setPlainText(challenge["description"])

    def _accept(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Проверка ввода", "Укажите название задания.")
            return
        self.accept()

    def values(self) -> dict[str, str | int]:
        return {
            "competition_id": self.competition_combo.currentData(),
            "title": self.title_edit.text(),
            "category": self.category_edit.text().strip(),
            "difficulty": self.difficulty_combo.currentText(),
            "status": self.status_combo.currentText(),
            "points": self.points_spin.value(),
            "description": self.description_edit.toPlainText().strip(),
        }


class NoteDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, note: sqlite3.Row | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новая заметка" if note is None else "Изменение заметки")
        self.setMinimumWidth(380)

        self.title_edit = QLineEdit()
        self.content_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Заголовок*", self.title_edit)
        form.addRow("Текст*", self.content_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if note is not None:
            self.title_edit.setText(note["title"])
            self.content_edit.setPlainText(note["content"])

    def _accept(self) -> None:
        if not self.title_edit.text().strip() or not self.content_edit.toPlainText().strip():
            QMessageBox.warning(self, "Проверка ввода", "Укажите заголовок и текст заметки.")
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {"title": self.title_edit.text(), "content": self.content_edit.toPlainText()}


class ChallengeDetailsDialog(QDialog):
    def __init__(
        self,
        connection: sqlite3.Connection,
        challenge: sqlite3.Row,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection = connection
        self.challenge_id = challenge["id"]
        self._notes_by_id: dict[int, sqlite3.Row] = {}
        self._artifacts_by_id: dict[int, sqlite3.Row] = {}

        self.setWindowTitle(f"Задание: {challenge['title']}")
        self.resize(680, 480)

        tabs = QTabWidget()
        tabs.addTab(self._build_description_tab(challenge), "Описание")
        tabs.addTab(self._build_notes_tab(), "Заметки")
        tabs.addTab(self._build_files_tab(), "Файлы")

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(self.button_box)

        self.refresh_notes()
        self.refresh_files()

    def _build_description_tab(self, challenge: sqlite3.Row) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.description_view = QTextEdit()
        self.description_view.setReadOnly(True)
        self.description_view.setPlainText(challenge["description"] or "Описание отсутствует.")
        layout.addWidget(self.description_view)
        return page

    def _build_notes_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.notes_list = QListWidget()
        self.notes_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.notes_list.itemDoubleClicked.connect(self._open_note_editor)
        layout.addWidget(self.notes_list)

        buttons = QHBoxLayout()
        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self._add_note)
        edit_button = QPushButton("Изменить")
        edit_button.clicked.connect(self._edit_note)
        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self._delete_note)
        buttons.addWidget(add_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _build_files_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.files_table = QTableWidget(0, 5)
        self.files_table.setHorizontalHeaderLabels(["Имя файла", "Размер (байт)", "SHA-256", "Путь", "Доступен"])
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.files_table)

        buttons = QHBoxLayout()
        add_button = QPushButton("Добавить файл")
        add_button.clicked.connect(self._add_file)
        delete_button = QPushButton("Удалить запись")
        delete_button.clicked.connect(self._delete_file)
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def refresh_notes(self) -> None:
        try:
            notes = repositories.get_notes(self.connection, self.challenge_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self._notes_by_id = {row["id"]: row for row in notes}
        self.notes_list.clear()
        for row in notes:
            item = QListWidgetItem(row["title"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.notes_list.addItem(item)

    def refresh_files(self) -> None:
        try:
            artifacts = repositories.get_artifacts(self.connection, self.challenge_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self._artifacts_by_id = {row["id"]: row for row in artifacts}
        self.files_table.setRowCount(len(artifacts))
        for position, row in enumerate(artifacts):
            available = Path(row["path"]).exists()
            values = (
                row["file_name"],
                str(row["file_size"]),
                row["sha256"],
                row["path"],
                "Да" if available else "Нет",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.files_table.setItem(position, column, item)

    def _add_note(self) -> None:
        dialog = NoteDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            repositories.add_note(self.connection, self.challenge_id, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self.refresh_notes()

    def _edit_note(self) -> None:
        self._run_note_editor(self._selected_note_id())

    def _open_note_editor(self, item: QListWidgetItem) -> None:
        self._run_note_editor(item.data(Qt.ItemDataRole.UserRole))

    def _run_note_editor(self, note_id: int | None) -> None:
        if note_id is None:
            QMessageBox.information(self, "Нет выбранной записи", "Выберите заметку в списке.")
            return
        dialog = NoteDialog(parent=self, note=self._notes_by_id[note_id])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = repositories.update_note(self.connection, note_id, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if not updated:
            QMessageBox.information(self, "Запись не найдена", "Заметка уже была удалена.")
        self.refresh_notes()

    def _delete_note(self) -> None:
        note_id = self._selected_note_id()
        if note_id is None:
            QMessageBox.information(self, "Нет выбранной записи", "Выберите заметку в списке.")
            return
        title = self._notes_by_id[note_id]["title"]
        answer = QMessageBox.question(self, "Удаление заметки", f"Удалить заметку «{title}»?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repositories.delete_note(self.connection, note_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if not deleted:
            QMessageBox.information(self, "Запись не найдена", "Заметка уже была удалена.")
        self.refresh_notes()

    def _add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if not path:
            return
        try:
            hashes = tools.calculate_file_hashes(path)
            file_size = Path(path).stat().st_size
        except OSError as error:
            QMessageBox.critical(self, "Ошибка чтения файла", f"Не удалось прочитать файл: {error}")
            return
        try:
            repositories.add_artifact(
                self.connection, self.challenge_id, path, Path(path).name, file_size, hashes["sha256"]
            )
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self.refresh_files()

    def _delete_file(self) -> None:
        artifact_id = self._selected_file_id()
        if artifact_id is None:
            QMessageBox.information(self, "Нет выбранной записи", "Выберите файл в таблице.")
            return
        file_name = self._artifacts_by_id[artifact_id]["file_name"]
        answer = QMessageBox.question(
            self,
            "Удаление записи",
            f"Удалить запись о файле «{file_name}»?\n\nСам файл останется на диске.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repositories.delete_artifact(self.connection, artifact_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if not deleted:
            QMessageBox.information(self, "Запись не найдена", "Запись уже была удалена.")
        self.refresh_files()

    def _selected_note_id(self) -> int | None:
        item = self.notes_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _selected_file_id(self) -> int | None:
        item = self.files_table.item(self.files_table.currentRow(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _show_database_error(self, error: sqlite3.Error) -> None:
        QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось выполнить операцию: {error}")

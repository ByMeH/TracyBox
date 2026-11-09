import sqlite3
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import repositories
from constants import STATUSES
from dialogs import ChallengeDialog, ChallengeDetailsDialog, CompetitionDialog


class MainWindow(QMainWindow):
    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__()
        self.connection = connection
        self._competitions_by_id: dict[int, sqlite3.Row] = {}
        self._challenges_by_id: dict[int, sqlite3.Row] = {}

        self.setWindowTitle("TraceBox")
        self.resize(1000, 640)

        tabs = QTabWidget()
        tabs.addTab(self._build_dashboard_tab(), "Обзор")
        tabs.addTab(self._build_competitions_tab(), "Соревнования")
        tabs.addTab(self._build_challenges_tab(), "Задания")
        tabs.addTab(self._build_tools_tab(), "Инструменты")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage("Готово")
        self.refresh_all()

    def _build_dashboard_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.dashboard_hint = QLabel(
            "В базе пока нет данных. Создайте первое соревнование на вкладке «Соревнования»."
        )
        self.dashboard_hint.setWordWrap(True)
        self.dashboard_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dashboard_hint)

        self.stats_group = QGroupBox("Общая статистика")
        stats_form = QFormLayout(self.stats_group)
        self.total_competitions_label = QLabel()
        self.total_challenges_label = QLabel()
        self.solved_label = QLabel()
        stats_form.addRow("Соревнований", self.total_competitions_label)
        stats_form.addRow("Заданий", self.total_challenges_label)
        stats_form.addRow("Решено заданий", self.solved_label)
        layout.addWidget(self.stats_group)

        self.status_group = QGroupBox("Задания по статусам")
        status_form = QFormLayout(self.status_group)
        self.status_labels: dict[str, QLabel] = {}
        for status in STATUSES:
            label = QLabel()
            self.status_labels[status] = label
            status_form.addRow(status, label)
        layout.addWidget(self.status_group)

        self.recent_group = QGroupBox("Последние задания")
        recent_layout = QVBoxLayout(self.recent_group)
        self.recent_table = self._make_table(["Название", "Соревнование", "Статус", "Изменено"])
        recent_layout.addWidget(self.recent_table)
        layout.addWidget(self.recent_group)

        layout.addStretch()
        return page

    def _build_competitions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.competitions_table = self._make_table(
            ["Название", "Организатор", "Ссылка", "Дата начала", "Описание"]
        )
        layout.addWidget(self.competitions_table)
        layout.addLayout(
            self._make_button_row([
                ("Добавить", self._add_competition),
                ("Изменить", self._edit_competition),
                ("Удалить", self._delete_competition),
            ])
        )
        return page

    def _build_challenges_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Соревнование:"))
        self.competition_filter = QComboBox()
        filters.addWidget(self.competition_filter)
        filters.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все статусы", None)
        for status in STATUSES:
            self.status_filter.addItem(status, status)
        filters.addWidget(self.status_filter)
        filters.addStretch()
        layout.addLayout(filters)

        self.competition_filter.currentIndexChanged.connect(self.refresh_challenges)
        self.status_filter.currentIndexChanged.connect(self.refresh_challenges)

        self.challenges_table = self._make_table(
            ["Соревнование", "Название", "Категория", "Сложность", "Статус", "Баллы"]
        )
        self.challenges_table.itemDoubleClicked.connect(self._show_challenge_details)
        layout.addWidget(self.challenges_table)
        layout.addLayout(
            self._make_button_row([
                ("Добавить", self._add_challenge),
                ("Изменить", self._edit_challenge),
                ("Удалить", self._delete_challenge),
                ("Подробнее", self._show_challenge_details),
            ])
        )
        return page

    def _build_tools_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("Хеширование файлов и кодировщики Base64/Hex/URL будут подключены на следующем этапе.")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _make_button_row(self, actions: list[tuple[str, Callable[[], None]]]) -> QHBoxLayout:
        buttons = QHBoxLayout()
        for label, slot in actions:
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        return buttons

    def refresh_all(self) -> None:
        self.refresh_competitions()
        self.refresh_challenges()
        self.refresh_dashboard()

    def refresh_competitions(self) -> None:
        try:
            competitions = repositories.get_competitions(self.connection)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self._competitions_by_id = {row["id"]: row for row in competitions}

        columns = ("name", "platform", "url", "start_date", "description")
        self.competitions_table.setRowCount(len(competitions))
        for position, row in enumerate(competitions):
            for column, key in enumerate(columns):
                item = QTableWidgetItem(str(row[key]))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.competitions_table.setItem(position, column, item)

        self._refresh_competition_filter(competitions)

    def _refresh_competition_filter(self, competitions: list[sqlite3.Row]) -> None:
        combo = self.competition_filter
        selected = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Все соревнования", None)
        for row in competitions:
            combo.addItem(row["name"], row["id"])
        if selected is not None:
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def refresh_challenges(self) -> None:
        try:
            challenges = repositories.get_challenges(
                self.connection,
                competition_id=self.competition_filter.currentData(),
                status=self.status_filter.currentData(),
            )
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self._challenges_by_id = {row["id"]: row for row in challenges}

        columns = ("competition_name", "title", "category", "difficulty", "status", "points")
        self.challenges_table.setRowCount(len(challenges))
        for position, row in enumerate(challenges):
            for column, key in enumerate(columns):
                item = QTableWidgetItem(str(row[key]))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.challenges_table.setItem(position, column, item)

    def refresh_dashboard(self) -> None:
        try:
            stats = repositories.get_dashboard_stats(self.connection)
            recent = repositories.get_recent_challenges(self.connection)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return

        is_empty = stats["total_competitions"] == 0 and stats["total_challenges"] == 0
        self.dashboard_hint.setVisible(is_empty)
        self.stats_group.setVisible(not is_empty)
        self.status_group.setVisible(not is_empty)
        self.recent_group.setVisible(not is_empty)

        self.total_competitions_label.setText(str(stats["total_competitions"]))
        self.total_challenges_label.setText(str(stats["total_challenges"]))
        self.solved_label.setText(f"{stats['solved_challenges']} ({stats['solved_percentage']}%)")
        for status, count in stats["status_counts"].items():
            self.status_labels[status].setText(str(count))

        columns = ("title", "competition_name", "status", "updated_at")
        self.recent_table.setRowCount(len(recent))
        for position, row in enumerate(recent):
            for column, key in enumerate(columns):
                self.recent_table.setItem(position, column, QTableWidgetItem(str(row[key])))

    def _add_competition(self) -> None:
        dialog = CompetitionDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            repositories.add_competition(self.connection, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self.statusBar().showMessage("Соревнование добавлено")
        self.refresh_all()

    def _edit_competition(self) -> None:
        competition_id = self._selected_id(self.competitions_table)
        if competition_id is None:
            self._inform_no_selection("соревнование")
            return
        dialog = CompetitionDialog(parent=self, competition=self._competitions_by_id[competition_id])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = repositories.update_competition(self.connection, competition_id, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if updated:
            self.statusBar().showMessage("Соревнование сохранено")
        else:
            QMessageBox.information(self, "Запись не найдена", "Соревнование уже было удалено.")
        self.refresh_all()

    def _delete_competition(self) -> None:
        competition_id = self._selected_id(self.competitions_table)
        if competition_id is None:
            self._inform_no_selection("соревнование")
            return
        name = self._competitions_by_id[competition_id]["name"]
        answer = QMessageBox.question(
            self,
            "Удаление соревнования",
            f"Удалить соревнование «{name}»?\n\n"
            "Вместе с ним будут удалены все его задания, заметки и записи о файлах.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repositories.delete_competition(self.connection, competition_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if deleted:
            self.statusBar().showMessage("Соревнование удалено")
        else:
            QMessageBox.information(self, "Запись не найдена", "Соревнование уже было удалено.")
        self.refresh_all()

    def _add_challenge(self) -> None:
        try:
            competitions = repositories.get_competitions(self.connection)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if not competitions:
            QMessageBox.information(
                self,
                "Нет соревнований",
                "Сначала создайте соревнование на вкладке «Соревнования».",
            )
            return
        dialog = ChallengeDialog(competitions, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            repositories.add_challenge(self.connection, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        self.statusBar().showMessage("Задание добавлено")
        self.refresh_all()

    def _edit_challenge(self) -> None:
        challenge_id = self._selected_id(self.challenges_table)
        if challenge_id is None:
            self._inform_no_selection("задание")
            return
        try:
            competitions = repositories.get_competitions(self.connection)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        dialog = ChallengeDialog(
            competitions, parent=self, challenge=self._challenges_by_id[challenge_id]
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = repositories.update_challenge(self.connection, challenge_id, **dialog.values())
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if updated:
            self.statusBar().showMessage("Задание сохранено")
        else:
            QMessageBox.information(self, "Запись не найдена", "Задание уже было удалено.")
        self.refresh_all()

    def _delete_challenge(self) -> None:
        challenge_id = self._selected_id(self.challenges_table)
        if challenge_id is None:
            self._inform_no_selection("задание")
            return
        title = self._challenges_by_id[challenge_id]["title"]
        answer = QMessageBox.question(
            self,
            "Удаление задания",
            f"Удалить задание «{title}»?\n\n"
            "Вместе с ним будут удалены его заметки и записи о файлах.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repositories.delete_challenge(self.connection, challenge_id)
        except sqlite3.Error as error:
            self._show_database_error(error)
            return
        if deleted:
            self.statusBar().showMessage("Задание удалено")
        else:
            QMessageBox.information(self, "Запись не найдена", "Задание уже было удалено.")
        self.refresh_all()

    def _show_challenge_details(self) -> None:
        challenge_id = self._selected_id(self.challenges_table)
        if challenge_id is None:
            self._inform_no_selection("задание")
            return
        dialog = ChallengeDetailsDialog(
            self.connection, self._challenges_by_id[challenge_id], parent=self
        )
        dialog.exec()

    def _selected_id(self, table: QTableWidget) -> int | None:
        item = table.item(table.currentRow(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _inform_no_selection(self, noun: str) -> None:
        QMessageBox.information(self, "Нет выбранной записи", f"Выберите {noun} в таблице.")

    def _show_database_error(self, error: sqlite3.Error) -> None:
        QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось выполнить операцию: {error}")

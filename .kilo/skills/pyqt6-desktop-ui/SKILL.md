---
name: pyqt6-desktop-ui
description: Use when implementing or changing TraceBox windows, dialogs, widgets, layouts, Qt signals and slots, or user-facing validation in PyQt6.
---

# PyQt6 desktop UI

- Use PyQt6 APIs and imports consistently; do not mix PyQt5 and PyQt6.
- Build layouts with Qt layout classes. Avoid hard-coded widget coordinates.
- Give dialogs a parent, a clear title, and explicit accept/cancel behavior.
- Use signals and slots for communication. Keep button handlers short and delegate data operations to the appropriate module.
- Keep SQL and file-processing logic out of widget classes.
- Use QFileDialog for choosing files and QMessageBox for actionable user-facing errors or confirmations.
- Validate user input before saving and show concise Russian messages that explain how to fix it.
- Use standard widgets where they fit: QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QCheckBox, QListWidget, QTableWidget/QTableView, QTabWidget and QProgressBar.
- Do not add widgets just to claim that they are used. Each control must serve a real workflow.
- Do not block the event loop with long work. Hash files in chunks; only introduce QThread/QtConcurrent if a measured operation visibly freezes the UI.
- Keep UI code readable. Extract a widget or dialog when it has a distinct responsibility, not merely to reduce a line count.
- Test user-visible flows manually and test non-UI logic with pytest.

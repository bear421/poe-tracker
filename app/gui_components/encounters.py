from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QToolButton, QLabel, QDialog, QVBoxLayout, QPushButton
)
from PySide6.QtCore import Qt, Signal, QMetaObject, QSize
from PySide6.QtGui import QPixmap
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from poe_bridge import Encounter, get_recent_encounters, events
from encounter_detect import debug_encounters
import time

class EncounterPreviewDialog(QDialog):
    def __init__(self, encounter, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screenshot")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        encounters = debug_encounters(encounter.screenshot_path)
        encounters = [e for e in encounters if e[0]]
        layout.addWidget(QLabel(f"{"\n".join([f"{e[0]}: {e[1]}" for e in encounters])}"))

        self.pixmap = QPixmap(encounter.screenshot_path)
        self.update_image()

        self.resizeEvent = self._on_resize

    def _on_resize(self, event):
        # self.update_image()
        super().resizeEvent(event)

    def update_image(self):
        if not self.pixmap.isNull():
            available_size = self.size()
            scaled_pixmap = self.pixmap.scaled(
                available_size.width(), available_size.height() - 100, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)



class EncountersWidget(QWidget):
    _encounter_detected_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Timestamp", "Data", "Screenshot"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.table)
        self._encounter_detected_signal.connect(self.update_table)
        events.on("encounter_detected", lambda _: self._encounter_detected_signal.emit())
        self.update_table()

    def _on_encounter(self):
        QMetaObject.invokeMethod(self, "update_table", Qt.QueuedConnection)

    def update_table(self):
        self.table.setRowCount(0)
        for encounter in get_recent_encounters():
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            self.table.setItem(row_position, 0, QTableWidgetItem(encounter.name))
            self.table.setItem(row_position, 1, QTableWidgetItem(encounter.ts.strftime("%Y-%m-%d %H:%M:%S")))
            self.table.setItem(row_position, 2, QTableWidgetItem(str(encounter.data)))

            if encounter.screenshot_path:
                thumbnail_label = QLabel()
                pixmap = QPixmap(encounter.screenshot_path)
                pixmap = pixmap.scaledToHeight(100, Qt.SmoothTransformation)
                thumbnail_label.setPixmap(pixmap)
                thumbnail_label.setAlignment(Qt.AlignCenter)
                thumbnail_label.mousePressEvent = lambda _, encounter=encounter: self.show_screenshot_preview(encounter)
                self.table.setCellWidget(row_position, 3, thumbnail_label)
            else:
                self.table.setItem(row_position, 3, QTableWidgetItem("No Screenshot"))

        self.table.resizeRowsToContents()

    def show_screenshot_preview(self, encounter):
        dialog = EncounterPreviewDialog(encounter, self)
        dialog.exec()
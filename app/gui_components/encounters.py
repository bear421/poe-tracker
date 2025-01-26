from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QDialog, QVBoxLayout, QPushButton, QTabWidget, QTextEdit, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QMetaObject
from PySide6.QtGui import QPixmap, QImage
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from poe_bridge import Encounter, get_recent_encounters, events
from encounter_detect import debug_encounters
import cv2
import numpy as np
import time

class EncounterPreviewDialog(QDialog):
    def __init__(self, encounter, parent=None):
        super().__init__(parent)
        print(f"constructing encounter preview dialog for {encounter.name}")
        self.setWindowTitle(f"Encounter: {encounter.name}")
        self.resize(800, 600)

        self.tabs = QTabWidget(self)
        self.image_tab = QWidget()
        self.debug_tab = QWidget()

        image_layout = QVBoxLayout(self.image_tab)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.image_label)

        debug_layout = QVBoxLayout(self.debug_tab)
        self.debug_tabs = QTabWidget()
        debug_layout.addWidget(self.debug_tabs)

        self.tabs.addTab(self.image_tab, "Image")
        self.tabs.addTab(self.debug_tab, "Debug")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(close_button)

        encounters = debug_encounters(encounter.screenshot_path)
        encounters = [e for e in encounters if e[0]]
        self.populate_debug_tab(encounters)

        self.pixmap = QPixmap(encounter.screenshot_path)
        self.update_image()

    def update_image(self):
        if not self.pixmap.isNull():
            available_size = self.image_tab.size()
            scaled_pixmap = self.pixmap.scaled(
                available_size.width(), available_size.height() - 100, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

    def populate_debug_tab(self, encounters):
        for name, data in encounters:
            encounter_tab = QWidget()
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)

            title_label = QLabel(f"<b>{name}</b>")
            scroll_layout.addWidget(title_label)

            if "_debug_info" in data:
                for debug_entry in data["_debug_info"]:
                    for key, value in debug_entry.items():
                        if key in ["image", "anchors"]:
                            continue
                        if key in ["visualization", "template"]:
                            qimage = self._convert_np_to_qpixmap(value)
                            if qimage:
                                image_label = QLabel()
                                image_label.setPixmap(qimage)
                                scroll_layout.addWidget(image_label)
                        else:
                            text_label = QLabel(f"{key}: {value}")
                            scroll_layout.addWidget(text_label)

            scroll_area.setWidget(scroll_content)
            encounter_tab_layout = QVBoxLayout(encounter_tab)
            encounter_tab_layout.addWidget(scroll_area)
            self.debug_tabs.addTab(encounter_tab, name)

    def _convert_np_to_qpixmap(self, np_image):
        if np_image is not None and isinstance(np_image, np.ndarray):
            height, width = np_image.shape[:2]
            if height > 4000 or width > 4000:
                raise Exception(f"deny generation of massive pixmap: {width}x{height}")
            bytes_per_line = 3 * width if np_image.ndim == 3 else width
            qimage_format = QImage.Format_RGB888 if np_image.ndim == 3 else QImage.Format_Grayscale8
            qimage = QImage(np_image.data, width, height, bytes_per_line, qimage_format)
            return QPixmap.fromImage(qimage)
        return None

class TagSelectionWidget(QWidget):
    def __init__(self, tags: List[str], selected_tags: List[str], parent=None):
        super().__init__(parent)
        self.selected_tags = set(selected_tags)
        layout = QVBoxLayout(self)

        # Add checkboxes for each tag
        self.checkboxes = {}
        for tag in tags:
            checkbox = QCheckBox(tag)
            checkbox.setChecked(tag in self.selected_tags)
            checkbox.stateChanged.connect(self._on_tag_changed)
            layout.addWidget(checkbox)
            self.checkboxes[tag] = checkbox

    def _on_tag_changed(self, state):
        sender = self.sender()
        tag = sender.text()
        if state == Qt.Checked:
            self.selected_tags.add(tag)
        else:
            self.selected_tags.discard(tag)

    def get_selected_tags(self):
        return list(self.selected_tags)

class EncountersWidget(QWidget):
    _encounter_detected_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Timestamp", "Data", "Screenshot", "Tags"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.table)
        self._encounter_detected_signal.connect(self.update_table)
        events.on("encounter_detected", lambda _: self._encounter_detected_signal.emit())
        self.available_tags = ["ocr_inaccurate", "ocr_fp_bait"]
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
                thumbnail_label.mousePressEvent = lambda _, e=encounter: self.show_screenshot_preview(e)

                self.table.setCellWidget(row_position, 3, thumbnail_label)
            else:
                self.table.setItem(row_position, 3, QTableWidgetItem("No Screenshot"))

            tag_widget = TagSelectionWidget(self.available_tags, encounter.tags if hasattr(encounter, 'tags') else [])
            self.table.setCellWidget(row_position, 4, tag_widget)

        self.table.resizeRowsToContents()

    def show_screenshot_preview(self, encounter):
        dialog = EncounterPreviewDialog(encounter, self)
        dialog.exec()

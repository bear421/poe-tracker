from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QWidget, QPushButton, QToolButton, QStyle
)
from PySide6.QtCore import Qt, QTimer, QMetaObject, Signal
from datetime import timedelta
from poe_bridge import get_recent_maps, events, delete_map
from util.format import format_number

class MapsWidget(QWidget):
    _map_completed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        self.map_table = QTableWidget()
        self.map_table.setColumnCount(6)
        self.map_table.setHorizontalHeaderLabels([
            "Map Name", "XP Gained", "XP/H", "Area Level", "Duration", ""
        ])

        header = self.map_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Map Name
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.map_table.setSelectionMode(QTableWidget.NoSelection)
        self.map_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.map_table)
        self._map_completed_signal.connect(self.update_table)
        events.on("map_completed", lambda _: self._map_completed_signal.emit())
        self.update_table()

    def _on_map_completed(self):
        QMetaObject.invokeMethod(self, "update_table", Qt.QueuedConnection)

    def update_table(self):
        self.map_table.setRowCount(0)
        for map_data in reversed(get_recent_maps()):
            duration_seconds = map_data.span.map_time().total_seconds()
            duration_str = str(timedelta(seconds=int(duration_seconds)))

            row_position = self.map_table.rowCount()
            self.map_table.insertRow(row_position)

            self.map_table.setItem(row_position, 0, QTableWidgetItem(map_data.map_label))
            self.map_table.setItem(row_position, 1, QTableWidgetItem(format_number(map_data.xp_gained)))
            self.map_table.setItem(row_position, 2, QTableWidgetItem(format_number(int(map_data.xph))))
            self.map_table.setItem(row_position, 3, QTableWidgetItem(str(map_data.area_level)))
            self.map_table.setItem(row_position, 4, QTableWidgetItem(duration_str))
            delete_button = QToolButton()
            delete_icon = self.style().standardIcon(QStyle.SP_TrashIcon)
            delete_button.setIcon(delete_icon)
            delete_button.setToolTip("Delete map")
            delete_button.clicked.connect(lambda _, map=map_data, row=row_position: self.delete_row(map, row))
            self.map_table.setCellWidget(row_position, 5, delete_button)
        self.map_table.resizeRowsToContents()

    def delete_row(self, map, row):
        delete_map(map)
        self.map_table.removeRow(row)
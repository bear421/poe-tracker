from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QWidget
)
from PySide6.QtCore import Qt, QTimer
from datetime import timedelta
from poe_bridge import get_recent_maps, events

class MapsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up the layout
        layout = QVBoxLayout(self)

        # Create the table widget
        self.map_table = QTableWidget()
        self.map_table.setColumnCount(5)
        self.map_table.setHorizontalHeaderLabels([
            "Map Name", "XP Gained", "XP/H", "Area Level", "Duration"
        ])

        # Set column stretch and alignment
        header = self.map_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Map Name
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.map_table.setSelectionMode(QTableWidget.NoSelection)
        self.map_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.map_table)

        # Connect to map_completed event
        events.on("map_completed", lambda _: self.update_table())

        # Initial update
        self.update_table()

    def update_table(self):
        # Clear the table
        self.map_table.setRowCount(0)

        # Populate the table with data
        for map_data in get_recent_maps():
            duration_seconds = map_data.span.map_time().total_seconds()
            duration_str = str(timedelta(seconds=int(duration_seconds)))

            row_position = self.map_table.rowCount()
            self.map_table.insertRow(row_position)

            self.map_table.setItem(row_position, 0, QTableWidgetItem(map_data.map_name))
            self.map_table.setItem(row_position, 1, QTableWidgetItem(f"{map_data.xp_gained:,}"))
            self.map_table.setItem(row_position, 2, QTableWidgetItem(f"{int(map_data.xph):,}"))
            self.map_table.setItem(row_position, 3, QTableWidgetItem(str(map_data.area_level)))
            self.map_table.setItem(row_position, 4, QTableWidgetItem(duration_str))

        # Resize rows to content
        self.map_table.resizeRowsToContents()
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QLabel, QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QDialog, QTextEdit
)
from PySide6.QtCore import Qt
from datetime import datetime, timedelta
import math
import random
from db import conn
from poe_bridge import _tracker, get_recent_xp_snapshots
from gui_components.logs import LogViewer
from gui_components.instance_loader import InstanceLoader
from util.format import format_number

class DebugWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        # XP Snapshot Group
        xp_group = QGroupBox("Debug apply_xp_snapshot")
        xp_layout = QFormLayout()
        
        self.xp_entry = QLineEdit("3939232944")
        self.timestamp_entry = QLineEdit(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        xp_layout.addRow("XP Value:", self.xp_entry)
        xp_layout.addRow("Timestamp (YYYY-MM-DD HH:MM:SS):", self.timestamp_entry)
        
        button_layout = QHBoxLayout()
        xp_button = QPushButton("XP Snapshot")
        xp_button.clicked.connect(self.test_xp_snapshot)
        random_button = QPushButton("Random XP Snapshot")
        random_button.clicked.connect(self.random_xp_snapshot)
        
        button_layout.addWidget(xp_button)
        button_layout.addWidget(random_button)
        xp_layout.addRow(button_layout)
        
        xp_group.setLayout(xp_layout)
        layout.addWidget(xp_group)
        
        area_group = QGroupBox("Debug enter_area")
        area_layout = QFormLayout()

        self.area_entry = QLineEdit("Augury")
        self.level_entry = QLineEdit("80")
        self.area_timestamp_entry = QLineEdit(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        area_layout.addRow("Area Name:", self.area_entry)
        area_layout.addRow("Area Level:", self.level_entry)
        area_layout.addRow("Timestamp (YYYY-MM-DD HH:MM:SS):", self.area_timestamp_entry)
        
        area_button = QPushButton("Test Enter Area")
        area_button.clicked.connect(self.test_enter_area)
        area_layout.addRow(area_button)
        
        area_group.setLayout(area_layout)
        layout.addWidget(area_group)
        
        # Advanced Group
        advanced_group = QGroupBox("Advanced")
        advanced_layout = QHBoxLayout()
        
        log_button = QPushButton("Open Log Viewer")
        log_button.clicked.connect(self.open_log_viewer)
        snapshot_button = QPushButton("Show XP Snapshots")
        snapshot_button.clicked.connect(self.show_snapshots_data)
        import_button = QPushButton("Import Instance Data")
        import_button.clicked.connect(self.load_instance_data_from_log)
        
        advanced_layout.addWidget(log_button)
        advanced_layout.addWidget(snapshot_button)
        advanced_layout.addWidget(import_button)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        log_group = QGroupBox("Log Line Simulator")
        log_layout = QFormLayout()
        
        self.log_entry = QTextEdit()
        self.log_entry.setMinimumHeight(100)
        log_layout.addRow("Log Lines:", self.log_entry)
        
        log_button = QPushButton("Simulate Log Lines")
        log_button.clicked.connect(self.simulate_log_line)
        log_layout.addRow(log_button)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        self.setLayout(layout)

    def test_xp_snapshot(self):
        try:
            xp = int(self.xp_entry.text())
            timestamp = datetime.strptime(self.timestamp_entry.text(), "%Y-%m-%d %H:%M:%S")
            _tracker.apply_xp_snapshot(xp, timestamp)
        except ValueError as e:
            print(f"[Debug Error] Invalid input: {e}")

    def random_xp_snapshot(self):
        xp = random.randint(1000000000, 1000000000000000000)
        timestamp = datetime.now() - timedelta(days=random.randint(0, 30))
        _tracker.apply_xp_snapshot(xp, timestamp)

    def test_enter_area(self):
        try:
            area_name = self.area_entry.text()
            area_level = int(self.level_entry.text()) if self.level_entry.text() else None
            timestamp = datetime.strptime(self.area_timestamp_entry.text(), "%Y-%m-%d %H:%M:%S")
            seed = int(math.floor(random.random() * 10000000))
            _tracker.enter_area(timestamp, area_level, area_name, seed)
        except ValueError as e:
            print(f"[Debug Error] Invalid input: {e}")

    def show_snapshots_data(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("XP Snapshots Data")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["#", "Timestamp", "XP", "Encounter Type"])
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        snapshots = get_recent_xp_snapshots()
        table.setRowCount(len(snapshots))
        
        for idx, snapshot in enumerate(snapshots):
            table.setItem(idx, 0, QTableWidgetItem(str(idx)))
            table.setItem(idx, 1, QTableWidgetItem(str(snapshot.ts)))
            table.setItem(idx, 2, QTableWidgetItem(f"{snapshot.xp:,}"))
            table.setItem(idx, 3, QTableWidgetItem(str(snapshot.encounter_type)))
        
        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec()

    def load_instance_data_from_log(self):
        loader = InstanceLoader()
        loader.show_modal(self)

    def open_log_viewer(self):
        viewer = LogViewer(self.window())
        viewer.show()

    def simulate_log_line(self):
        try:
            log_text = self.log_entry.toPlainText()
            if log_text:
                log_lines = [line.strip() for line in log_text.split('\n') if line.strip()]
                _tracker.process_log_lines(log_lines)
        except Exception as e:
            print(f"[Debug Error] Failed to process log lines: {e}")
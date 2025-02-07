from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QCheckBox, QScrollBar
)
from PySide6.QtCore import QTimer, Qt
from poe_bridge import find_poe_logfile

class LogViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Path of Exile Log Viewer")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        
        control_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.show_log_tail)
        control_layout.addWidget(refresh_button)
        
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh (5s)")
        self.auto_refresh_checkbox.stateChanged.connect(self.toggle_auto_refresh)
        control_layout.addWidget(self.auto_refresh_checkbox)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        layout.addWidget(self.log_text)
        
        self.setLayout(layout)
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.show_log_tail)
        self.refresh_timer.setInterval(5000)
        

        self.show_log_tail()

    def show_log_tail(self):
        try:
            log_path = find_poe_logfile()
            if not log_path:
                self.log_text.clear()
                self.log_text.insertPlainText("Could not locate Path of Exile log file.")
                return

            with open(log_path, 'r', encoding='utf-8') as f:
                # Read last 1000 lines
                lines = f.readlines()[-1000:]
                self.log_text.clear()
                self.log_text.insertPlainText(''.join(lines))
                
                # Scroll to bottom
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
        except Exception as e:
            self.log_text.clear()
            self.log_text.insertPlainText(f"Error reading log file: {str(e)}")

    def toggle_auto_refresh(self, state):
        if state == Qt.Checked:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()
import sys
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt
import pandas as pd
from db import conn
from poe_bridge import events
from util.format import format_number

class QTableWidgetItem_C(QTableWidgetItem):
    def __init__(self, text, comparator=None):
        super().__init__(text)
        self.comparator = comparator

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            if self.comparator:
                return self.comparator(self.text(), other.text())
            else:
                try:
                    def parse_formatted_number(text):
                        text = text.replace(",", "")
                        multipliers = {"K": 1E3, "M": 1E6, "B": 1E9}
                        if text[-1] in multipliers:
                            return float(text[:-1]) * multipliers[text[-1]]
                        return float(text)
                    
                    self_value = parse_formatted_number(self.text())
                    other_value = parse_formatted_number(other.text())
                    return self_value < other_value
                except ValueError:
                    return self.text() < other.text()
        return super().__lt__(other)

class StatsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.stats_table = QTableWidget()
        self.stats_table.setSortingEnabled(True)
        self.layout.addWidget(self.stats_table)
        self.sort_states = {}
        self.update_table()

        events.on("map_completed", lambda _: self.update_table())

    def update_table(self):
        query = """
            SELECT 
                data->>'map_name' AS 'Map Name', 
                COUNT(*) AS 'Count', 
                SUM(CAST(data->>'xp_gained' AS INTEGER)) AS 'Total XP', 
                CAST(MEDIAN(CAST(data->>'xph' AS INTEGER)) AS INTEGER) AS 'Median XP/H',
                CAST(MEDIAN(CAST(data->>'span'->>'map_time' AS INTEGER)) AS INTEGER) AS 'Median Map Duration',
                CAST(MEDIAN(CAST(data->>'span'->>'load_time' AS INTEGER)) AS INTEGER) AS 'Median Load Duration'
            FROM maps 
            WHERE CAST(data->>'xp_gained' AS INTEGER) > 0
            GROUP BY data->>'map_name' 
            ORDER BY data->>'map_name'
        """
        self.stats_df = stats_df = pd.read_sql(query, conn)
        self.populate_table(stats_df)

    def populate_table(self, dataframe):
        self.stats_table.clearContents()
        self.stats_table.setRowCount(len(dataframe))
        self.stats_table.setColumnCount(len(dataframe.columns))
        self.stats_table.setHorizontalHeaderLabels(dataframe.columns.tolist())
        for row_idx, row in dataframe.iterrows():
            for col_idx, value in enumerate(row):
                # Format numbers for numeric columns (skip Map Name column)
                if col_idx > 0:
                    item = QTableWidgetItem_C(format_number(value))
                    item.setTextAlignment(Qt.AlignRight)
                else:
                    item = QTableWidgetItem_C(str(value))
                self.stats_table.setItem(row_idx, col_idx, item)
        self.stats_table.resizeRowsToContents()
from PySide6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QHBoxLayout, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QTabWidget, QSizePolicy, QFormLayout
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from datetime import datetime, timedelta
import traceback
import statistics
from poe_bridge import get_current_map, get_recent_xp_snapshots, get_recent_maps, events, get_recent_xph, get_next_waystone
from ladder_api import LadderEntry
from db import conn
from xp_table import get_level_from_xp, get_xp_range_for_level
from area_tla import get_threat_indicator
from util.format import format_number


def mk_label(text, font = QFont("Helvetica", 12, QFont.Normal)):
    label = QLabel(text)
    label.setFont(font)
    return label

class OverviewWidget(QWidget):

    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()

        self.map_group = QGroupBox("No current map data")
        self.map_group.setFont(QFont("Helvetica", 12, QFont.Bold))
        map_layout = QVBoxLayout()
        
        self.xp_label = mk_label("?")
        self.xph_label = mk_label("?")
        self.duration_label = mk_label("?")
        
        map_stats_layout = QFormLayout()
        map_layout.addLayout(map_stats_layout, 0)
        map_stats_layout.addRow("XP Gained", self.xp_label)
        map_stats_layout.addRow("XP/H", self.xph_label)
        map_stats_layout.addRow("Duration", self.duration_label)

        self.mods_layout = QVBoxLayout()
        map_layout.addLayout(self.mods_layout, 0)
        map_layout.addStretch()
        self.map_group.setLayout(map_layout)

        self.encounters_group = QGroupBox("Encounters")
        self.encounters_group.setFont(QFont("Helvetica", 12, QFont.Bold))
        self.encounters_layout = QVBoxLayout()
        self.encounters_group.setLayout(self.encounters_layout)

        self.ladder_group = QGroupBox("Ladder")
        self.ladder_group.setFont(QFont("Helvetica", 12, QFont.Bold))
        self.ladder_layout = QFormLayout()
        self.ladder_group.setLayout(self.ladder_layout)

        top_section = QWidget()
        top_section.setLayout(QHBoxLayout())
        top_section.layout().addWidget(self.map_group)
        top_section.layout().addWidget(self.ladder_group)
        self.layout.addWidget(top_section)
        self.layout.addWidget(self.encounters_group)
        self.layout.addStretch()
        self.setLayout(self.layout)

        self.current_ladder_entry = None
        for field, data in conn.execute("SELECT field, data FROM gui_state").fetchall():
            if field == "current_ladder_entry":
                self.current_ladder_entry = LadderEntry.from_row(data)

        events.on("ladder_data", self.update_ladder_entry)
        self.update()
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(500)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                del item

    def update(self):
        try:
            current_map = get_current_map()
            map_label = f"{current_map.map_label} - {current_map.area_level}" if current_map else "No current map data"
            self.map_group.setTitle(map_label)

            if current_map:
                xp_gained = current_map.xp_gained
                now_or_ho = current_map.hideout_start_time if current_map.hideout_start_time else datetime.now()
                total_duration = (
                    now_or_ho - current_map.span.start
                ) if current_map.span.end is None else current_map.span.map_time()
                xph = int(xp_gained / total_duration.total_seconds() * 3600) if total_duration.total_seconds() > 0 else 0
                total_duration = timedelta(seconds=int(total_duration.total_seconds()))
                if current_map.in_hideout() and xp_gained > 0:
                    self.xp_label.setText(f"{format_number(xp_gained)}")
                    self.xph_label.setText(f"{format_number(xph)}")
                else:
                    self.xp_label.setText(f"?")
                    self.xph_label.setText(f"?")
                self.duration_label.setText(f"{str(total_duration)}")

                self.clear_layout(self.mods_layout)
                waystone = get_next_waystone() or current_map.waystone
                if waystone:
                    for mod in waystone.affixes:
                        ti = get_threat_indicator(mod)
                        mod_label = mk_label(mod.text)
                        bg_color = "rgba(200, 0, 0, 0.2)" if ti and ti.multi > 0 else "rgba(0, 200, 0, 0.2)"
                        mod_label.setStyleSheet(f"background-color: {bg_color}; border-radius: 3px; padding: 2px;")
                        self.mods_layout.addWidget(mod_label)

            encounters = []
            if get_recent_xp_snapshots() and current_map:
                map_start_time = current_map.span.start
                xp_snapshots = list(get_recent_xp_snapshots())
                for i in range(len(xp_snapshots), 0, -1):
                    snapshot = xp_snapshots[i - 1]
                    if i == len(xp_snapshots):
                        # incomplete head snapshot, has no next
                        next_snapshot = None
                    else:
                        next_snapshot = get_recent_xp_snapshots()[i]
                    if snapshot.ts < map_start_time:
                        break
                    if snapshot.encounter_type == "hideout" or snapshot.source == "ladder":
                        continue

                    if next_snapshot:
                        duration = (next_snapshot.ts - snapshot.ts).total_seconds()
                        xp_gained = next_snapshot.delta
                    else:
                        duration = (now_or_ho - snapshot.ts).total_seconds()
                        xp_gained = 0

                    if duration < 0:
                        continue

                    xph = (xp_gained / duration) * 3600 if duration > 0 else 0
                    encounters.append({
                        "Encounter Type": snapshot.encounter_type,
                        "XP": xp_gained,
                        "XP/H": int(xph),
                        "Duration": str(timedelta(seconds=int(duration))),
                    })
                encounters.reverse()

            if encounters:
                self.clear_layout(self.encounters_layout)
                table = QTableWidget(len(encounters), 5)
                table.setHorizontalHeaderLabels(["#", "Encounter Type", "XP", "XP/H", "Duration"])
                table.horizontalHeader().setStretchLastSection(True)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                table.verticalHeader().setVisible(False)
                table.setEditTriggers(QTableWidget.NoEditTriggers)  #read-only

                for i, row in enumerate(encounters):
                    table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                    table.setItem(i, 1, QTableWidgetItem(row["Encounter Type"]))
                    table.setItem(i, 2, QTableWidgetItem(f"{format_number(row['XP'])}"))
                    table.setItem(i, 3, QTableWidgetItem(f"{format_number(row['XP/H'])}"))
                    table.setItem(i, 4, QTableWidgetItem(row["Duration"]))

                # Add the table to the layout
                self.encounters_layout.addWidget(table)
                self.encounters_group.show()
            else:
                self.encounters_group.hide()

            if self.current_ladder_entry:
                self.clear_layout(self.ladder_layout)
                ladder_entry = self.current_ladder_entry
                character_name = ladder_entry.character.name
                rank = ladder_entry.rank
                xpp = "?"
                eta = "?"
                idle_p = "?"
                if get_recent_xp_snapshots():
                    xp = get_recent_xp_snapshots()[-1].xp
                    level = get_level_from_xp(xp)
                    (xp_lo, xp_hi) = get_xp_range_for_level(level)
                    xp_delta = xp - xp_lo
                    xpp = xp_delta / (xp_hi - xp_lo) * 100
                    valid_maps = list(filter(lambda m: m.xph, get_recent_maps()))
                    recent_xph = get_recent_xph()
                    idle_p_list = []
                    idle_load = []
                    idle_pause = []
                    idle_hideout = []
                    for m in valid_maps:
                        idle_p_list.append(m.span.idle_time() / (m.span.map_time() + m.span.idle_time()))
                        idle_load.append(m.span.load_time)
                        idle_pause.append(m.span.pause_time)
                        idle_hideout.append(m.span.hideout_time)
                    idle_p = statistics.median(idle_p_list)
                    idle_load = statistics.median(idle_load)
                    idle_pause = statistics.median(idle_pause)
                    idle_hideout = statistics.median(idle_hideout)
                    if recent_xph > 0:
                        eta = f"{(xp_hi - xp) / recent_xph / (1 - idle_p):.1f}h"

                self.ladder_layout.addRow("Character", mk_label(f"{character_name}"))
                self.ladder_layout.addRow("Rank", mk_label(f"{rank}"))
                if ladder_entry.prev:
                    xp_delta = ladder_entry.prev.character.experience - ladder_entry.character.experience
                    self.ladder_layout.addRow("Ahead", mk_label(f"{ladder_entry.prev.character.name} (+{format_number(xp_delta)})"))
                if ladder_entry.next:
                    xp_delta = ladder_entry.character.experience - ladder_entry.next.character.experience
                    self.ladder_layout.addRow("Behind", mk_label(f"{ladder_entry.next.character.name} (-{format_number(xp_delta)})"))
                self.ladder_layout.addRow("XP", mk_label(f"{xpp:.3f}%"))
                self.ladder_layout.addRow("Recent XP/H", mk_label(f"{format_number(recent_xph)}"))
                self.ladder_layout.addRow("Idle", mk_label(f"{int(idle_p * 100)}%"))
                self.ladder_layout.addRow("ETA", mk_label(f"{eta}"))

        except Exception as e:
            print(f"[Error in update_overview]: {str(e)}\n{traceback.format_exc()}")

    def update_ladder_entry(self, event):
        self.current_ladder_entry = event.get("ladder_data")
        conn.execute("INSERT INTO gui_state (field, data) VALUES (?, ?)", ["current_ladder_entry", self.current_ladder_entry.to_dict()])
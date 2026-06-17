"""
ICE Measurement Procedures - Main Entry Point

This module provides the GUI launcher for ICE measurement procedures.
All procedure classes are now organized in the 'procedures' package.
"""

import logging
import sys

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import time, math
import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtWidgets, QtGui, QtCore
from pymeasure.display.windows.managed_dock_window import ManagedDockWindow

import pyqtgraph as pg
pg.setConfigOption("useOpenGL", True)

# Import from the procedures package
from procedures import (
    # Utilities
    _as_cat_list, _proc_matches, _rebind_instruments_from_configuration,
    # Procedure classes
    Resistance_time_measurement,
    Resistance_gate_sweep_measurement,
    Resistance_magnet_sweep_measurement,
    Resistance_two_gate_scan_sweep_measurement,
    Resistance_two_gate_mapping_measurement,
    Resistance_magnet_and_gate_mapping_measurement,
    Resistance_magnet_and_2gate_mapping_measurement,
    Differential_conductance_SRS860,
    Differential_conductance_Zurich,
    Differential_Resistance_Zurich,
    Differential_Resistance_Zurich_AUX_map,
    Rt_RV_RH_sequencer_measurement,
    RV_dV_dI_sequencer_measurement,
    # Registration dicts
    proc_resistance_time,
    proc_resistance_gate,
    proc_resistance_magnet,
    proc_resistance_two_gate_sweep,
    proc_resistance_two_gate_map,
    proc_resistance_magnet_gate_map,
    proc_resistance_magnet_2gate_map,
    proc_differential_conductance_SRS860,
    proc_differential_conductance_Zurich,
    proc_differential_resistance_Zurich,
    proc_differential_resistance_Zurich_AUX_map,
    proc_Rt_RV_RH_sequencer,
    proc_RV_dV_dI_sequencer,
    # Aggregates
    CATAGORIES,
    PROCEDURES,
)

save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav"


class GenericWindow(ManagedDockWindow):
    """A ManagedWindow configured from a spec in PROCEDURES."""
    
    def __init__(self, spec_name: str):
        spec = PROCEDURES[spec_name]

        # 1. Define the base arguments that every window needs
        kwargs = {
            "procedure_class": spec['cls'],
            "inputs": spec['inputs'],
            "displays": spec['displays'],
            "x_axis": spec.get('x'),
            "y_axis": spec.get('y'),
            "linewidth": 1.5,
            "inputs_in_scrollarea": True
        }

        # 2. Add sequencer arguments ONLY if they are defined in the procedure spec
        if spec.get('sequencer'):
            kwargs['sequencer'] = spec['sequencer']
            kwargs['sequencer_inputs'] = spec['sequencer_inputs']

        # 3. Pass all arguments to the parent class
        super().__init__(**kwargs)

        self.setWindowTitle(f"{spec_name} (ManagedWindow)")
        self.filename = f"{spec_name}"
        self.directory = save_dir

        try:
            self.plot_widget.plot.showGrid(x=True, y=True)
        except Exception:
            pass


class Launcher(QtWidgets.QMainWindow):
    """Tiny picker that opens per-procedure ManagedWindows with multicategory filter."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Procedure Launcher")
        self.resize(800, 400)
        self.setMinimumSize(400, 350)
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        self.CAT = CATAGORIES

        layout = QtWidgets.QVBoxLayout(central)

        # General description section
        general_desc = QtWidgets.QLabel(
            "Select a measurement procedure below to open its dedicated window.\n"
            "You can filter by one or more categories; only matching procedures will be shown.\n"
        )
        general_desc.setStyleSheet("""
            QLabel {
                border: 1px solid #b0c4de;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        general_desc.setWordWrap(True)
        layout.addWidget(general_desc)

        layout.addSpacing(8)

        # Multi-category filter row
        filter_row = QtWidgets.QHBoxLayout()
        filter_container = QtWidgets.QWidget()
        filter_h = QtWidgets.QHBoxLayout(filter_container)

        self.category_checks = {}
        for name, color in self.CAT.items():
            cb = QtWidgets.QCheckBox(name)
            cb.setTristate(False)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    background-color: {color};
                    border: 1px solid #ccc;
                    border-radius: 6px;
                    padding: 2px 6px;
                    margin-right: 6px;
                }}
            """)
            cb.stateChanged.connect(self._apply_category_filter)
            self.category_checks[name] = cb
            filter_h.addWidget(cb)

        filter_h.addStretch()
        filter_row.addWidget(filter_container)

        clear_btn = QtWidgets.QPushButton("Show All")
        clear_btn.clicked.connect(self._clear_category_filter)
        filter_row.addWidget(clear_btn)

        layout.addLayout(filter_row)
        layout.addSpacing(6)

        # Procedure selection row
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        row.addWidget(QtWidgets.QLabel("Procedure:"))
        self.combo = QtWidgets.QComboBox()
        self.combo.currentTextChanged.connect(self.update_description)
        row.addWidget(self.combo)

        self.btn = QtWidgets.QPushButton("Open window")
        self.btn.clicked.connect(self.open_window)
        row.addWidget(self.btn)

        # Category label
        self.category_label = QtWidgets.QLabel()
        self.category_label.setTextFormat(QtCore.Qt.RichText)
        self.category_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 4px 0px;
                margin-top: 5px;
                margin-bottom: 5px;
                font-size: 15px;
            }
        """)
        layout.addWidget(self.category_label)

        # Description section
        desc_label = QtWidgets.QLabel("Description:")
        desc_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(desc_label)

        self.description_text = QtWidgets.QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        self.description_text.setStyleSheet("""
            QTextEdit {
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.description_text)

        layout.addStretch()

        # Keep references so windows are not GC'ed
        self._windows = []
        console_log(log)

        # Populate procedures
        self._populate_combo()
        self.update_description()

        # Toolbar Exit action
        tb = self.addToolBar("App")
        exit_action = QtGui.QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._on_exit_clicked)
        tb.addAction(exit_action)

    def _selected_categories(self):
        return [name for name, cb in self.category_checks.items() if cb.isChecked()]

    def _populate_combo(self):
        current = self.combo.currentText()
        self.combo.blockSignals(True)
        self.combo.clear()
        selected = self._selected_categories()

        names = []
        for name, spec in PROCEDURES.items():
            if _proc_matches(spec, selected):
                names.append(name)

        self.combo.addItems(names)
        self.combo.blockSignals(False)

        if current in names:
            idx = self.combo.findText(current)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        elif names:
            self.combo.setCurrentIndex(0)

    def _apply_category_filter(self):
        self._populate_combo()
        self.update_description()

    def _clear_category_filter(self):
        for cb in self.category_checks.values():
            cb.setChecked(False)
        self._populate_combo()
        self.update_description()

    def update_description(self):
        """Update the description text and category chips when procedure selection changes."""
        name = self.combo.currentText()
        if name in PROCEDURES:
            proc = PROCEDURES[name]

            description = proc.get('description', 'No description available.')
            self.description_text.setPlainText(description)

            cat_list = _as_cat_list(proc.get('category', 'Unknown'))

            chips = []
            for c in cat_list:
                color = self.CAT.get(c, '#f0f0f0')
                chips.append(
                    f'<span style="background-color:{color};'
                    f' border:1px solid #ccc; border-radius:6px;'
                    f' padding:2px 8px; margin-right:6px;">{c}</span>'
                )
            html = "Category: " + (" ".join(chips) if chips else "Unknown")
            self.category_label.setText(html)
        else:
            self.description_text.setPlainText('No description available.')
            self.category_label.setText('Category: Unknown')

    def open_window(self):
        name = self.combo.currentText()
        if not name:
            return
        w = GenericWindow(name)
        w.show()
        self._windows.append(w)

    def _on_exit_clicked(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Exit",
            "Stop any running measurement and exit?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.stop()
        except Exception:
            pass
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        try:
            self.stop()
        except Exception:
            pass

        try:
            import configuration as cfg
            instrument_list = [
                cfg.magnet,
                cfg.Gate_1, cfg.Gate_2, cfg.Dual_gate,
                cfg.MFLI_1, cfg.MFLI_2, cfg.MFLI_3,
                cfg.SRS860_1, cfg.SRS860_2,
                cfg.SRS830_1, cfg.SRS830_2, cfg.SRS830_3
            ]

            for inst in instrument_list:
                if inst != 0 and hasattr(inst, 'adapter'):
                    try:
                        inst.adapter.close()
                    except Exception:
                        pass
        except Exception:
            pass

        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from importlib import reload
    from config_prelaunch import run_and_optionally_launch
    import configuration as _cfg

    def _start_launcher():
        reload(_cfg)
        _rebind_instruments_from_configuration()

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        win = Launcher()
        win.show()
        sys.exit(app.exec_())

    run_and_optionally_launch(_start_launcher)
"""
Pre-Launcher Instrument Configuration Dialog (PyQt5)
-----------------------------------------------------------------
What this provides
- A small GUI that opens **before** your Launcher.
- Lets the user choose which instruments to use and set their addresses.
- Enumerates: VISA resources (for K2450/K2604B/SRS860/SRS830),
- If a field is left empty or the instrument is unticked, your `configuration.py`
  will set that instrument variable to 0 so your existing Procedures keep working.

How to integrate (minimal changes)
1) Put this file next to your existing `configuration.py`.
2) Add the small patch at the *top* of your `configuration.py` (shown below) so it
   reads the JSON produced by this dialog and constructs the instrument objects accordingly.
3) Run `python config_prelaunch.py` to open the dialog; press **Save & Launch** to
   store the JSON and (optionally) boot your Launcher.

"""
from __future__ import annotations
import re
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# Ensure the repo root (which holds the Instruments package) is importable,
# e.g. for Instruments.MFLI in _test_mfli_connection.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- Qt ---
from PyQt5 import QtCore, QtWidgets

# --- Enumerations for ports/resources ---
# VISA (PyVISA)
try:
    import pyvisa
except Exception:
    pyvisa = None

# Location for the JSON overrides (same folder as configuration.py)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OVERRIDES_JSON = os.path.join(THIS_DIR, "instrument_overrides.json")


@dataclass
class InstrumentConfig:
    use_gate1: bool = False
    gate1_visa: str = ""

    use_gate2: bool = False
    gate2_visa: str = ""

    use_dual_gate: bool = False
    dual_gate_visa: str = ""
    dual_gate_visa_library: str = 'C:\\Windows\\System32\\visa64.dll'

    use_k6221: bool = False
    k6221_visa: str = ""

    use_yoko_gs200_1: bool = False
    yoko_gs200_1_visa: str = ""

    use_yoko_gs200_2: bool = False
    yoko_gs200_2_visa: str = ""

    use_yoko7651_1: bool = False
    yoko7651_1_visa: str = ""

    use_yoko7651_2: bool = False
    yoko7651_2_visa: str = ""

    use_srs860_1: bool = False
    srs860_1_visa: str = ""

    use_srs860_2: bool = False
    srs860_2_visa: str = ""

    use_srs860_3: bool = False
    srs860_3_visa: str = ""

    use_srs860_4: bool = False
    srs860_4_visa: str = ""

    use_srs830_1: bool = False
    srs830_1_visa: str = ""

    use_srs830_2: bool = False
    srs830_2_visa: str = ""

    use_srs830_3: bool = False
    srs830_3_visa: str = ""

    use_mfli_1: bool = False
    mfli_1_host: str = ""  # e.g. "192.168.93.134" or "localhost"
    mfli_1_port: int = 8004
    mfli_1_dev: str = ""   # e.g. "dev5985"

    use_mfli_2: bool = False
    mfli_2_host: str = ""  # e.g. "192.168.93.134" or "localhost"
    mfli_2_port: int = 8004
    mfli_2_dev: str = ""   #e.g. "dev32114"

    use_mfli_3: bool = False
    mfli_3_host: str = ""  # e.g. "192.168.93.134" or "localhost"
    mfli_3_port: int = 8004
    mfli_3_dev: str = ""

    def to_json(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: Dict) -> "InstrumentConfig":
        base = cls()
        base.__dict__.update(data or {})
        return base


class ConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Instrument Configuration")
        self.setModal(True)
        self.setMinimumWidth(720)

        # Load existing file if present
        self._cfg = self._load_existing()

        # Widgets
        self.tabs = QtWidgets.QTabWidget(self)
        self._keithley_tab = self._build_keithley_tab()
        self._yokogawa_tab = self._build_yokogawa_tab()
        self._lockins_tab = self._build_lockins_tab()
        self._mfli_tab = self._build_mfli_tab()

        self.tabs.addTab(self._keithley_tab, "Keithley SMUs")
        self.tabs.addTab(self._yokogawa_tab, "Yokogawa Sources")
        self.tabs.addTab(self._lockins_tab, "Lock-ins")
        self.tabs.addTab(self._mfli_tab, "Zurich MFLI")


        # Buttons
        self.btn_autoscan = QtWidgets.QPushButton("Auto-Search (VISA *IDN?)")
        self.btn_refresh = QtWidgets.QPushButton("Refresh lists")
        self.btn_save = QtWidgets.QPushButton("Save & Launch")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")

        self.btn_autoscan.clicked.connect(self._auto_search)
        self.btn_refresh.clicked.connect(self._refresh_all)
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_autoscan)
        btns.addWidget(self.btn_refresh)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addLayout(btns)

        # First fill
        self._refresh_all()
        self._apply_cfg_to_widgets()

    # ---------- Utility ----------
    def _load_existing(self) -> InstrumentConfig:
        if os.path.isfile(OVERRIDES_JSON):
            try:
                with open(OVERRIDES_JSON, "r", encoding="utf-8") as f:
                    return InstrumentConfig.from_json(json.load(f))
            except Exception:
                pass
        return InstrumentConfig()

    def _visa_list(self) -> List[str]:
        resources: List[str] = []
        if pyvisa is None:
            return resources
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
        except Exception:
            resources = []
        return resources

    def _apply_cfg_to_widgets(self) -> None:
        # Gate 1/2 and Dual
        self.chk_gate1.setChecked(self._cfg.use_gate1)
        self.cmb_gate1.setEditText(self._cfg.gate1_visa)
        self.chk_gate2.setChecked(self._cfg.use_gate2)
        self.cmb_gate2.setEditText(self._cfg.gate2_visa)
        self.chk_dual.setChecked(self._cfg.use_dual_gate)
        self.cmb_dual.setEditText(self._cfg.dual_gate_visa)

        self.chk_k6221.setChecked(self._cfg.use_k6221)
        self.cmb_k6221.setEditText(self._cfg.k6221_visa)

        # Yokogawa sources
        self.chk_yoko_gs200_1.setChecked(self._cfg.use_yoko_gs200_1)
        self.cmb_yoko_gs200_1.setEditText(self._cfg.yoko_gs200_1_visa)
        self.chk_yoko_gs200_2.setChecked(self._cfg.use_yoko_gs200_2)
        self.cmb_yoko_gs200_2.setEditText(self._cfg.yoko_gs200_2_visa)
        self.chk_yoko7651_1.setChecked(self._cfg.use_yoko7651_1)
        self.cmb_yoko7651_1.setEditText(self._cfg.yoko7651_1_visa)
        self.chk_yoko7651_2.setChecked(self._cfg.use_yoko7651_2)
        self.cmb_yoko7651_2.setEditText(self._cfg.yoko7651_2_visa)

        # Lock-ins
        self.chk_srs860_1.setChecked(self._cfg.use_srs860_1)
        self.cmb_srs860_1.setEditText(self._cfg.srs860_1_visa)
        self.chk_srs860_2.setChecked(self._cfg.use_srs860_2)
        self.cmb_srs860_2.setEditText(self._cfg.srs860_2_visa)
        self.chk_srs860_3.setChecked(self._cfg.use_srs860_3)
        self.cmb_srs860_3.setEditText(self._cfg.srs860_3_visa)
        self.chk_srs860_4.setChecked(self._cfg.use_srs860_4)
        self.cmb_srs860_4.setEditText(self._cfg.srs860_4_visa)

        self.chk_srs830_1.setChecked(self._cfg.use_srs830_1)
        self.cmb_srs830_1.setEditText(self._cfg.srs830_1_visa)
        self.chk_srs830_2.setChecked(self._cfg.use_srs830_2)
        self.cmb_srs830_2.setEditText(self._cfg.srs830_2_visa)
        self.chk_srs830_3.setChecked(self._cfg.use_srs830_3)
        self.cmb_srs830_3.setEditText(self._cfg.srs830_3_visa)

        self.chk_mfli_1.setChecked(self._cfg.use_mfli_1)
        self.edt_mfli_1_host.setText(self._cfg.mfli_1_host or "")
        self.spn_mfli_1_port.setValue(int(self._cfg.mfli_1_port or 8004))
        self.cmb_mfli_1_dev.setEditText(self._cfg.mfli_1_dev or "")

        self.chk_mfli_2.setChecked(self._cfg.use_mfli_2)
        self.edt_mfli_2_host.setText(self._cfg.mfli_2_host or "")
        self.spn_mfli_2_port.setValue(int(self._cfg.mfli_2_port or 8004))
        self.cmb_mfli_2_dev.setEditText(self._cfg.mfli_2_dev or "")

        self.chk_mfli_3.setChecked(self._cfg.use_mfli_3)
        self.edt_mfli_3_host.setText(self._cfg.mfli_3_host or "")
        self.spn_mfli_3_port.setValue(int(self._cfg.mfli_3_port or 8004))
        self.cmb_mfli_3_dev.setEditText(self._cfg.mfli_3_dev or "")

    def _refresh_all(self):
        self._fill_visa_comboboxes(self._visa_list())


    # ---------- Tabs ----------
    def _build_keithley_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(w)

        self.chk_gate1 = QtWidgets.QCheckBox("Use Gate_1 (Keithley 2450)")
        self.cmb_gate1 = QtWidgets.QComboBox(); self.cmb_gate1.setEditable(True)
        self.chk_gate2 = QtWidgets.QCheckBox("Use Gate_2 (Keithley 2450)")
        self.cmb_gate2 = QtWidgets.QComboBox(); self.cmb_gate2.setEditable(True)
        self.chk_dual = QtWidgets.QCheckBox("Use Dual_gate (Keithley 2604B)")
        self.cmb_dual = QtWidgets.QComboBox(); self.cmb_dual.setEditable(True)
        self.chk_k6221 = QtWidgets.QCheckBox("Use K6221 (Keithley 6221 AC/DC current source)")
        self.cmb_k6221 = QtWidgets.QComboBox(); self.cmb_k6221.setEditable(True)

        grid.addWidget(self.chk_gate1, 0, 0); grid.addWidget(self.cmb_gate1, 0, 1)
        grid.addWidget(self.chk_gate2, 1, 0); grid.addWidget(self.cmb_gate2, 1, 1)
        grid.addWidget(self.chk_dual, 2, 0); grid.addWidget(self.cmb_dual, 2, 1)
        grid.addWidget(self.chk_k6221, 3, 0); grid.addWidget(self.cmb_k6221, 3, 1)
        grid.setColumnStretch(1, 1)
        return w

    def _build_yokogawa_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(w)

        self.chk_yoko_gs200_1 = QtWidgets.QCheckBox("Use YokoGS200_1 (Yokogawa GS200)")
        self.cmb_yoko_gs200_1 = QtWidgets.QComboBox(); self.cmb_yoko_gs200_1.setEditable(True)
        self.chk_yoko_gs200_2 = QtWidgets.QCheckBox("Use YokoGS200_2 (Yokogawa GS200)")
        self.cmb_yoko_gs200_2 = QtWidgets.QComboBox(); self.cmb_yoko_gs200_2.setEditable(True)
        self.chk_yoko7651_1 = QtWidgets.QCheckBox("Use Yoko7651_1 (Yokogawa 7651)")
        self.cmb_yoko7651_1 = QtWidgets.QComboBox(); self.cmb_yoko7651_1.setEditable(True)
        self.chk_yoko7651_2 = QtWidgets.QCheckBox("Use Yoko7651_2 (Yokogawa 7651)")
        self.cmb_yoko7651_2 = QtWidgets.QComboBox(); self.cmb_yoko7651_2.setEditable(True)

        grid.addWidget(self.chk_yoko_gs200_1, 0, 0); grid.addWidget(self.cmb_yoko_gs200_1, 0, 1)
        grid.addWidget(self.chk_yoko_gs200_2, 1, 0); grid.addWidget(self.cmb_yoko_gs200_2, 1, 1)
        grid.addWidget(self.chk_yoko7651_1, 2, 0); grid.addWidget(self.cmb_yoko7651_1, 2, 1)
        grid.addWidget(self.chk_yoko7651_2, 3, 0); grid.addWidget(self.cmb_yoko7651_2, 3, 1)
        grid.setColumnStretch(1, 1)
        return w

    # def _build_keithley_tab(self) -> QtWidgets.QWidget:
    #     w = QtWidgets.QWidget(self)
    #     grid = QtWidgets.QGridLayout(w)
    #
    #     self.chk_gate1 = QtWidgets.QCheckBox("Use Gate_1 (Keithley 2450)")
    #     self.cmb_gate1 = QtWidgets.QComboBox();
    #     self.cmb_gate1.setEditable(True)
    #
    #     self.chk_gate2 = QtWidgets.QCheckBox("Use Gate_2 (Keithley 2450)")
    #     self.cmb_gate2 = QtWidgets.QComboBox();
    #     self.cmb_gate2.setEditable(True)
    #
    #     self.chk_dual = QtWidgets.QCheckBox("Use Dual_gate (Keithley 2600)")
    #     self.cmb_dual = QtWidgets.QComboBox();
    #     self.cmb_dual.setEditable(True)
    #
    #     # VISA library for Dual_gate (optional)
    #     self.edt_dual_visalib = QtWidgets.QLineEdit()
    #     self.edt_dual_visalib.setPlaceholderText(r"C:\Windows\System32\visa64.dll")
    #     self.btn_dual_visalib_browse = QtWidgets.QPushButton("Browse…")
    #
    #     def _pick_visalib():
    #         path, _ = QtWidgets.QFileDialog.getOpenFileName(
    #             w, "Select visa64.dll", "", "DLL (*.dll);;All files (*.*)"
    #         )
    #         if path:
    #             self.edt_dual_visalib.setText(path)
    #
    #     self.btn_dual_visalib_browse.clicked.connect(_pick_visalib)
    #
    #     grid.addWidget(self.chk_gate1, 0, 0);
    #     grid.addWidget(self.cmb_gate1, 0, 1)
    #     grid.addWidget(self.chk_gate2, 1, 0);
    #     grid.addWidget(self.cmb_gate2, 1, 1)
    #     grid.addWidget(self.chk_dual, 2, 0);
    #     grid.addWidget(self.cmb_dual, 2, 1)
    #
    #     grid.addWidget(QtWidgets.QLabel("Dual VISA library:"), 3, 0)
    #     row = QtWidgets.QHBoxLayout()
    #     row.addWidget(self.edt_dual_visalib, 1)
    #     row.addWidget(self.btn_dual_visalib_browse)
    #     grid.addLayout(row, 3, 1)
    #
    #     grid.setColumnStretch(1, 1)
    #     return w

    def _build_lockins_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(w)
        self.chk_srs860_1 = QtWidgets.QCheckBox("Use SRS860_1")
        self.cmb_srs860_1 = QtWidgets.QComboBox(); self.cmb_srs860_1.setEditable(True)
        self.chk_srs860_2 = QtWidgets.QCheckBox("Use SRS860_2")
        self.cmb_srs860_2 = QtWidgets.QComboBox(); self.cmb_srs860_2.setEditable(True)
        self.chk_srs860_3 = QtWidgets.QCheckBox("Use SRS860_3")
        self.cmb_srs860_3 = QtWidgets.QComboBox(); self.cmb_srs860_3.setEditable(True)
        self.chk_srs860_4 = QtWidgets.QCheckBox("Use SRS860_4")
        self.cmb_srs860_4 = QtWidgets.QComboBox(); self.cmb_srs860_4.setEditable(True)
        self.chk_srs830_1 = QtWidgets.QCheckBox("Use SRS830_1")
        self.cmb_srs830_1 = QtWidgets.QComboBox(); self.cmb_srs830_1.setEditable(True)
        self.chk_srs830_2 = QtWidgets.QCheckBox("Use SRS830_2")
        self.cmb_srs830_2 = QtWidgets.QComboBox(); self.cmb_srs830_2.setEditable(True)
        self.chk_srs830_3 = QtWidgets.QCheckBox("Use SRS830_3")
        self.cmb_srs830_3 = QtWidgets.QComboBox(); self.cmb_srs830_3.setEditable(True)

        grid.addWidget(self.chk_srs830_1, 0, 0); grid.addWidget(self.cmb_srs830_1, 0, 1)
        grid.addWidget(self.chk_srs830_2, 1, 0); grid.addWidget(self.cmb_srs830_2, 1, 1)
        grid.addWidget(self.chk_srs830_3, 2, 0); grid.addWidget(self.cmb_srs830_3, 2, 1)
        grid.addWidget(self.chk_srs860_1, 3, 0); grid.addWidget(self.cmb_srs860_1, 3, 1)
        grid.addWidget(self.chk_srs860_2, 4, 0); grid.addWidget(self.cmb_srs860_2, 4, 1)
        grid.addWidget(self.chk_srs860_3, 5, 0); grid.addWidget(self.cmb_srs860_3, 5, 1)
        grid.addWidget(self.chk_srs860_4, 6, 0); grid.addWidget(self.cmb_srs860_4, 6, 1)
        grid.setColumnStretch(1, 1)
        return w

    def _build_mfli_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)

        self.chk_mfli_1 = QtWidgets.QCheckBox("Use MFLI _1")
        self.edt_mfli_1_host = QtWidgets.QLineEdit()
        self.edt_mfli_1_host.setPlaceholderText("e.g. 192.168.93.134 or localhost")
        self.spn_mfli_1_port = QtWidgets.QSpinBox()
        self.spn_mfli_1_port.setRange(1, 65535);
        self.spn_mfli_1_port.setValue(8004)

        # Device selector (editable); “Find” is best-effort
        self.cmb_mfli_1_dev = QtWidgets.QComboBox();
        self.cmb_mfli_1_dev.setEditable(True)
        self.btn_mfli_1_find = QtWidgets.QPushButton("Find on server")
        self.btn_mfli_1_test = QtWidgets.QPushButton("Test connection")

        self.btn_mfli_1_find.clicked.connect(self._scan_mfli_devices)
        self.btn_mfli_1_test.clicked.connect(lambda: self._test_mfli_connection(1))

        form.addRow(self.chk_mfli_1)
        form.addRow("Host/IP:", self.edt_mfli_1_host)
        form.addRow("Port:", self.spn_mfli_1_port)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.cmb_mfli_1_dev, 1)
        row.addWidget(self.btn_mfli_1_find)
        row.addWidget(self.btn_mfli_1_test)
        form.addRow("Device:", row)

        self.chk_mfli_2 = QtWidgets.QCheckBox("Use MFLI _2")
        self.edt_mfli_2_host = QtWidgets.QLineEdit()
        self.edt_mfli_2_host.setPlaceholderText("e.g. 192.168.93.134 or localhost")
        self.spn_mfli_2_port = QtWidgets.QSpinBox()
        self.spn_mfli_2_port.setRange(1, 65535);
        self.spn_mfli_2_port.setValue(8004)

        # Device selector (editable); “Find” is best-effort
        self.cmb_mfli_2_dev = QtWidgets.QComboBox();
        self.cmb_mfli_2_dev.setEditable(True)
        self.btn_mfli_2_find = QtWidgets.QPushButton("Find on server")
        self.btn_mfli_2_test = QtWidgets.QPushButton("Test connection")

        self.btn_mfli_2_find.clicked.connect(self._scan_mfli_devices)
        self.btn_mfli_2_test.clicked.connect(lambda: self._test_mfli_connection(2))

        form.addRow(self.chk_mfli_2)
        form.addRow("Host/IP:", self.edt_mfli_2_host)
        form.addRow("Port:", self.spn_mfli_2_port)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.cmb_mfli_2_dev, 1)
        row.addWidget(self.btn_mfli_2_find)
        row.addWidget(self.btn_mfli_2_test)
        form.addRow("Device:", row)

        self.chk_mfli_3 = QtWidgets.QCheckBox("Use MFLI _3")
        self.edt_mfli_3_host = QtWidgets.QLineEdit()
        self.edt_mfli_3_host.setPlaceholderText("e.g. 192.168.93.134 or localhost")
        self.spn_mfli_3_port = QtWidgets.QSpinBox()
        self.spn_mfli_3_port.setRange(1, 65535);
        self.spn_mfli_3_port.setValue(8004)

        # Device selector (editable); “Find” is best-effort
        self.cmb_mfli_3_dev = QtWidgets.QComboBox();
        self.cmb_mfli_3_dev.setEditable(True)
        self.btn_mfli_3_find = QtWidgets.QPushButton("Find on server")
        self.btn_mfli_3_test = QtWidgets.QPushButton("Test connection")

        self.btn_mfli_3_find.clicked.connect(self._scan_mfli_devices)
        self.btn_mfli_3_test.clicked.connect(lambda: self._test_mfli_connection(3))

        form.addRow(self.chk_mfli_3)
        form.addRow("Host/IP:", self.edt_mfli_3_host)
        form.addRow("Port:", self.spn_mfli_3_port)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.cmb_mfli_3_dev, 1)
        row.addWidget(self.btn_mfli_3_find)
        row.addWidget(self.btn_mfli_3_test)
        form.addRow("Device:", row)
        return w

    # ---------- Fillers ----------
    def _fill_visa_comboboxes(self, resources: List[str]):
        for cmb in (self.cmb_gate1, self.cmb_gate2, self.cmb_dual, self.cmb_k6221,
                    self.cmb_yoko_gs200_1, self.cmb_yoko_gs200_2,
                    self.cmb_yoko7651_1, self.cmb_yoko7651_2,
                    self.cmb_srs860_1, self.cmb_srs860_2,
                    self.cmb_srs860_3, self.cmb_srs860_4,
                      self.cmb_srs830_1, self.cmb_srs830_2, self.cmb_srs830_3):
            cmb.clear(); cmb.addItems(resources); cmb.setEditable(True)


    def accept(self) -> None:
        # Gather -> save JSON
        cfg = InstrumentConfig(
            use_gate1=self.chk_gate1.isChecked(),
            gate1_visa=self.cmb_gate1.currentText().strip(),

            use_gate2=self.chk_gate2.isChecked(),
            gate2_visa=self.cmb_gate2.currentText().strip(),

            use_dual_gate=self.chk_dual.isChecked(),
            dual_gate_visa=self.cmb_dual.currentText().strip(),

            use_k6221=self.chk_k6221.isChecked(),
            k6221_visa=self.cmb_k6221.currentText().strip(),

            use_yoko_gs200_1=self.chk_yoko_gs200_1.isChecked(),
            yoko_gs200_1_visa=self.cmb_yoko_gs200_1.currentText().strip(),

            use_yoko_gs200_2=self.chk_yoko_gs200_2.isChecked(),
            yoko_gs200_2_visa=self.cmb_yoko_gs200_2.currentText().strip(),

            use_yoko7651_1=self.chk_yoko7651_1.isChecked(),
            yoko7651_1_visa=self.cmb_yoko7651_1.currentText().strip(),

            use_yoko7651_2=self.chk_yoko7651_2.isChecked(),
            yoko7651_2_visa=self.cmb_yoko7651_2.currentText().strip(),

            use_srs860_1=self.chk_srs860_1.isChecked(),
            srs860_1_visa=self.cmb_srs860_1.currentText().strip(),

            use_srs860_2=self.chk_srs860_2.isChecked(),
            srs860_2_visa=self.cmb_srs860_2.currentText().strip(),

            use_srs860_3=self.chk_srs860_3.isChecked(),
            srs860_3_visa=self.cmb_srs860_3.currentText().strip(),

            use_srs860_4=self.chk_srs860_4.isChecked(),
            srs860_4_visa=self.cmb_srs860_4.currentText().strip(),

            use_srs830_1=self.chk_srs830_1.isChecked(),
            srs830_1_visa=self.cmb_srs830_1.currentText().strip(),

            use_srs830_2=self.chk_srs830_2.isChecked(),
            srs830_2_visa=self.cmb_srs830_2.currentText().strip(),

            use_srs830_3=self.chk_srs830_3.isChecked(),
            srs830_3_visa=self.cmb_srs830_3.currentText().strip(),

            use_mfli_1=self.chk_mfli_1.isChecked(),
            mfli_1_host=self.edt_mfli_1_host.text().strip(),
            mfli_1_port=int(self.spn_mfli_1_port.value()),
            mfli_1_dev=self.cmb_mfli_1_dev.currentText().strip(),

            use_mfli_2=self.chk_mfli_2.isChecked(),
            mfli_2_host=self.edt_mfli_2_host.text().strip(),
            mfli_2_port=int(self.spn_mfli_2_port.value()),
            mfli_2_dev=self.cmb_mfli_2_dev.currentText().strip(),

            use_mfli_3=self.chk_mfli_3.isChecked(),
            mfli_3_host=self.edt_mfli_3_host.text().strip(),
            mfli_3_port=int(self.spn_mfli_3_port.value()),
            mfli_3_dev=self.cmb_mfli_3_dev.currentText().strip(),

        )
        # empty fields are fine; configuration.py will turn those into 0
        try:
            with open(OVERRIDES_JSON, "w", encoding="utf-8") as f:
                json.dump(cfg.to_json(), f, indent=2)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))
            return
        super().accept()

    # def _scan_mfli_devices(self):
    #     host = self.edt_mfli_1_host.text().strip() or "localhost" or self.edt_mfli_2_host.text().strip()
    #     port = int(self.spn_mfli_1_port.value()) or int(self.spn_mfli_2_port.value())
    #     found = []
    #     # Try zhinst.toolkit first
    #     try:
    #         from zhinst.toolkit import Session
    #         sess = Session(host=host, port=port)
    #         sess.connect()
    #         # toolkit exposes .devices with .serial and .dev_type (varies by version)
    #         for d in getattr(sess, "devices", []):
    #             did = getattr(d, "serial", "") or getattr(d, "device_id", "")
    #             dtype = getattr(d, "dev_type", "") or getattr(d, "device_type", "")
    #             if str(dtype).upper().startswith("MFLI") and did:
    #                 found.append(did)
    #         try:
    #             sess.disconnect()
    #         except Exception:
    #             pass
    #     except Exception:
    #         pass
    #     # Fallback: old discovery API
    #     if not found:
    #         try:
    #             from zhinst.core import ziDiscovery
    #             disc = ziDiscovery()
    #             # returns list of dicts on some versions
    #             for info in disc.findAll():
    #                 did = info.get("deviceid") or info.get("serial") or info.get("id")
    #                 dtype = (info.get("devicetype") or info.get("type") or "").upper()
    #                 addr = info.get("serveraddress") or info.get("ip", "")
    #                 prt = int(info.get("serverport") or info.get("port") or 0)
    #                 if did and dtype.startswith("MFLI") and (not host or addr == host) and (not port or prt == port):
    #                     found.append(did)
    #         except Exception:
    #             pass
    #
    #     if not found:
    #         QtWidgets.QMessageBox.information(self, "MFLI Finder",
    #                                           "No MFLI devices found (or Zurich drivers not installed).\n"
    #                                           "Enter host/port/device manually.")
    #         return
    #     self.cmb_mfli_1_dev.clear()
    #     self.cmb_mfli_1_dev.addItems(sorted(set(found)))
    #     if found:
    #         self.cmb_mfli_1_dev.setCurrentIndex(0)
    #
    # def _test_mfli_1_connection(self):
    #     host = self.edt_mfli_1_host.text().strip()
    #     port = int(self.spn_mfli_1_port.value())
    #     dev = self.cmb_mfli_1_dev.currentText().strip()
    #     if not (host and port and dev):
    #         QtWidgets.QMessageBox.warning(self, "Test MFLI", "Fill host, port, and device first.")
    #         return
    #     ok = False
    #     err = ""
    #     # Lightweight “can I talk to it?” test, using your controller if available.
    #     try:
    #         from MFLI import MFLIController
    #         probe = MFLIController(host, port, 6, dev)
    #         try:
    #             # Minimal call that should succeed quickly if reachable
    #             _ = probe.get_auxout(0)
    #             ok = True
    #         except Exception as e:
    #             err = str(e)
    #     except Exception as e:
    #         err = f"Controller not importable or test failed: {e}"
    #     if ok:
    #         QtWidgets.QMessageBox.information(self, "Test MFLI", f"Connected to {dev} on {host}:{port}.")
    #     else:
    #         QtWidgets.QMessageBox.critical(self, "Test MFLI",
    #                                        f"Failed to connect.\n{err}\nYou can still Save and run without MFLI.")
    #
    def _discover_mfli(self):
        """Discover MFLI devices via LabOne. Returns [(device_id, host, port)].

        Tries zhinst.toolkit Session against the configured/localhost data
        server, falls back to zhinst.core ziDiscovery. No UI, no dialogs —
        shared by _scan_mfli_devices and _auto_search.
        """
        hosts = [
            self.edt_mfli_1_host.text().strip(),
            getattr(self, "edt_mfli_2_host", None) and self.edt_mfli_2_host.text().strip(),
            getattr(self, "edt_mfli_3_host", None) and self.edt_mfli_3_host.text().strip(),
        ]
        ports = [
            int(self.spn_mfli_1_port.value()),
            getattr(self, "spn_mfli_2_port", None) and int(self.spn_mfli_2_port.value()),
            getattr(self, "spn_mfli_3_port", None) and int(self.spn_mfli_3_port.value()),
        ]

        hosts = [h or "localhost" for h in hosts if h]
        ports = [p for p in ports if p]

        found = []

        # --- First: try zhinst.toolkit discovery ---
        try:
            from zhinst.toolkit import Session

            for host, port in zip(hosts, ports):
                sess = Session(host=host, port=port)
                sess.connect()

                for d in getattr(sess, "devices", []):
                    did = getattr(d, "serial", "") or getattr(d, "device_id", "")
                    dtype = getattr(d, "dev_type", "") or getattr(d, "device_type", "")
                    if str(dtype).upper().startswith("MFLI") and did:
                        found.append((did, host, port))
                sess.disconnect()

        except Exception:
            pass

        # --- Fallback: zhinst.core discovery ---
        if not found:
            try:
                from zhinst.core import ziDiscovery
                disc = ziDiscovery()

                for info in disc.findAll():
                    did = info.get("deviceid") or info.get("serial") or info.get("id")
                    dtype = (info.get("devicetype") or info.get("type") or "").upper()
                    addr = info.get("serveraddress") or info.get("ip", "")
                    prt = int(info.get("serverport") or info.get("port") or 0)
                    if did and dtype.startswith("MFLI"):
                        found.append((did, addr, prt))
            except Exception:
                pass

        # dedupe by device id, keep first sighting
        seen, unique = set(), []
        for did, host, port in found:
            if did not in seen:
                seen.add(did)
                unique.append((did, host, port))
        return unique

    def _scan_mfli_devices(self):
        """Scan for all available MFLI devices and populate all device dropdowns."""
        found = self._discover_mfli()

        if not found:
            QtWidgets.QMessageBox.information(
                self, "MFLI Finder",
                "No MFLI devices found (or Zurich drivers not installed).\n"
                "Enter host/port/device manually."
            )
            return

        # --- Populate UI elements dynamically ---
        unique_devices = sorted(set(did for did, _, _ in found))
        for idx in range(1, 4):  # Adjust range if you have more MFLI slots
            cmb = getattr(self, f"cmb_mfli_{idx}_dev", None)
            if cmb:
                cmb.clear()
                cmb.addItems(unique_devices)
                if unique_devices:
                    cmb.setCurrentIndex(0)

    # ---------- Auto-search ----------
    def _auto_search(self) -> None:
        """Scan VISA resources, query *IDN?, reassign family slots.

        Every run re-detects from scratch: for each instrument family with
        at least one detection, its slots are cleared and refilled in
        resource order — running twice never duplicates an instrument and
        picks up address changes. Families with no detections are left
        untouched (manual entries survive). Yokogawa 7651 never answers
        *IDN? — set it manually.
        """
        if pyvisa is None:
            QtWidgets.QMessageBox.warning(self, "Auto-Search", "pyvisa not available.")
            return

        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Auto-Search", f"VISA scan failed:\n{e}")
            return

        # model key -> ordered (checkbox, combobox) slots
        slots = {
            '2450':  [(self.chk_gate1, self.cmb_gate1), (self.chk_gate2, self.cmb_gate2)],
            '2600':  [(self.chk_dual, self.cmb_dual)],
            '6221':  [(self.chk_k6221, self.cmb_k6221)],
            'gs200': [(self.chk_yoko_gs200_1, self.cmb_yoko_gs200_1),
                      (self.chk_yoko_gs200_2, self.cmb_yoko_gs200_2)],
            'sr860': [(self.chk_srs860_1, self.cmb_srs860_1),
                      (self.chk_srs860_2, self.cmb_srs860_2),
                      (self.chk_srs860_3, self.cmb_srs860_3),
                      (self.chk_srs860_4, self.cmb_srs860_4)],
            'sr830': [(self.chk_srs830_1, self.cmb_srs830_1),
                      (self.chk_srs830_2, self.cmb_srs830_2),
                      (self.chk_srs830_3, self.cmb_srs830_3)],
        }

        def _query_idn(addr):
            """*IDN? with a terminator retry — GS200 USB-TMC often needs
            read_termination='\\n' to answer. Returns (idn_or_None, err_or_'')."""
            try:
                res = rm.open_resource(addr, open_timeout=2000)
            except Exception as e:
                return None, f"open failed: {e}"
            try:
                res.timeout = 2500
                try:
                    return res.query('*IDN?').strip(), ''
                except Exception as e1:
                    try:
                        res.read_termination = '\n'
                        res.write_termination = '\n'
                        return res.query('*IDN?').strip(), ''
                    except Exception as e2:
                        return None, f"no answer ({type(e1).__name__} / {type(e2).__name__})"
            finally:
                try:
                    res.close()
                except Exception:
                    pass

        per_family, silent, unknown = {}, [], []
        for addr in resources:
            idn, err = _query_idn(addr)
            if not idn:
                silent.append(f"{addr}  {err}".rstrip())
                continue
            key = classify_prelaunch(idn)
            if key is None:
                continue
            if key == 'unknown':
                unknown.append(f"{addr}: {idn}")
                continue
            per_family.setdefault(key, []).append((addr, idn))

        found = []
        for key, key_slots in slots.items():
            detections = per_family.get(key, [])
            if not detections:
                continue  # nothing found: leave manual settings alone
            # full reassignment for this family (fixes duplicates + stale addresses)
            for chk, cmb in key_slots:
                chk.setChecked(False)
                cmb.clearEditText()
            for (chk, cmb), (addr, idn) in zip(key_slots, detections):
                cmb.setEditText(addr)
                chk.setChecked(True)
                found.append(f"{key.upper()} @ {addr}\n    {idn}")
            if len(detections) > len(key_slots):
                extra = ", ".join(a for a, _ in detections[len(key_slots):])
                found.append(f"WARNING: more {key.upper()} units than slots "
                             f"(ignored: {extra})")

        # --- MFLI (LabOne discovery, not VISA) ---
        try:
            mfli_devices = self._discover_mfli()
        except Exception:
            mfli_devices = []
        if mfli_devices:
            mfli_slots = []
            for idx in (1, 2, 3):
                chk = getattr(self, f"chk_mfli_{idx}", None)
                edt = getattr(self, f"edt_mfli_{idx}_host", None)
                spn = getattr(self, f"spn_mfli_{idx}_port", None)
                cmb = getattr(self, f"cmb_mfli_{idx}_dev", None)
                if None not in (chk, edt, spn, cmb):
                    mfli_slots.append((chk, edt, spn, cmb))
            # same full-reassignment semantics as the VISA families
            for chk, edt, spn, cmb in mfli_slots:
                chk.setChecked(False)
            for (chk, edt, spn, cmb), (did, host, port) in zip(mfli_slots, mfli_devices):
                if host:
                    edt.setText(str(host))
                if port:
                    spn.setValue(int(port))
                cmb.setCurrentText(str(did))  # combos are editable
                chk.setChecked(True)
                found.append(f"MFLI @ {host}:{port}\n    {did}")
            if len(mfli_devices) > len(mfli_slots):
                extra = ", ".join(d for d, _, _ in mfli_devices[len(mfli_slots):])
                found.append(f"WARNING: more MFLI units than slots (ignored: {extra})")

        msg = "Auto-Search results:\n\n" + ("\n".join(found) if found else "nothing detected")
        if silent:
            msg += ("\n\nNo *IDN? answer (set manually if connected):\n"
                    + "\n".join(silent))
        if unknown:
            msg += "\n\nUnrecognized *IDN? (set manually):\n" + "\n".join(unknown)
        msg += "\n\nNote: Yokogawa 7651 never auto-detects — fill it manually."
        QtWidgets.QMessageBox.information(self, "Auto-Search", msg)

    def _test_mfli_connection(self, index: int):
        """Test connection for an arbitrary MFLI (1, 2, 3, etc.)"""
        try:
            host = getattr(self, f"edt_mfli_{index}_host").text().strip()
            port = int(getattr(self, f"spn_mfli_{index}_port").value())
            dev = getattr(self, f"cmb_mfli_{index}_dev").currentText().strip()
        except AttributeError:
            QtWidgets.QMessageBox.warning(self, "Test MFLI", f"MFLI #{index} widgets not found.")
            return

        if not (host and port and dev):
            QtWidgets.QMessageBox.warning(self, "Test MFLI", "Fill host, port, and device first.")
            return

        ok = False
        err = ""
        try:
            from Instruments.MFLI import MFLIController
            probe = MFLIController(host, port, 6, dev)
            try:
                _ = probe.get_auxout(0)  # simple quick check
                ok = True
            except Exception as e:
                err = str(e)
        except Exception as e:
            err = f"Controller not importable or test failed: {e}"

        if ok:
            QtWidgets.QMessageBox.information(self, "Test MFLI", f"Connected to {dev} on {host}:{port}.")
        else:
            QtWidgets.QMessageBox.critical(self, "Test MFLI",
                                           f"Failed to connect.\n{err}\nYou can still Save and run without MFLI.")


# ---------------- VISA auto-search classification ----------------

_KEITHLEY_2600_FAMILY = ('2600', '2601', '2602', '2603', '2604', '2605', '2606')
_KEITHLEY_2450_FAMILY = ('2450', '2460', '2461', '2470')


def classify_prelaunch(idn):
    """Return a model key for an *IDN? string, else None (not ours).

    'unknown' means: recognized vendor but unsupported model.
    """
    if not idn:
        return None
    parts = [p.strip() for p in idn.split(',')]
    vendor = parts[0].upper() if parts else ''
    model = parts[1].upper() if len(parts) > 1 else ''

    if 'KEITHLEY' in vendor:
        m = re.search(r'MODEL\s*([0-9]+[A-Z]*)', idn, re.IGNORECASE)
        digits = re.sub(r'\D', '', m.group(1)) if m else ''
        if digits in _KEITHLEY_2600_FAMILY:
            return '2600'
        if digits in _KEITHLEY_2450_FAMILY:
            return '2450'
        if digits in ('6221',):
            return '6221'
        return 'unknown'
    if 'STANFORD' in vendor or 'SRS' in vendor:
        if 'SR830' in model:
            return 'sr830'
        if 'SR860' in model:
            return 'sr860'
        return 'unknown'
    if 'YOKOGAWA' in vendor:
        # GS210 = newer firmware/revision of the GS200, same driver
        if 'GS200' in model or 'GS210' in model:
            return 'gs200'
        return 'unknown'
    return None


def run_and_optionally_launch(launch_fn=None):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dlg = ConfigDialog()
    if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        if callable(launch_fn):
            launch_fn()




if __name__ == "__main__":
    # Example: wire this into your Launcher bootstrap
    def _dummy_launch():
        # Import late so it reads the freshly saved JSON in configuration.py
        # Replace this with your real Launcher import & start
        print("Launching your app… (replace _dummy_launch with your real launcher)")

    run_and_optionally_launch(_dummy_launch)

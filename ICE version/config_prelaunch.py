"""
Pre-Launcher Instrument Configuration Dialog (PyQt6)
-----------------------------------------------------------------
What this provides
- A small GUI that opens **before** your Launcher.
- Lets the user choose which instruments to use and set their addresses.
- Enumerates: COM ports (for magnet), VISA resources (for K2450/K2604B/SRS860/SRS830),
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
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# --- Qt ---
from PyQt5 import QtCore, QtWidgets

# --- Enumerations for ports/resources ---
# VISA (PyVISA)
try:
    import pyvisa
except Exception:
    pyvisa = None

# Serial ports (pyserial)
try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

# Location for the JSON overrides (same folder as configuration.py)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OVERRIDES_JSON = os.path.join(THIS_DIR, "instrument_overrides.json")


@dataclass
class InstrumentConfig:
    use_magnet: bool = False
    magnet_com: str = ""
    magnet_baud: int = 9600
    magnet_timeout_s: float = 0.3

    use_gate1: bool = False
    gate1_visa: str = ""

    use_gate2: bool = False
    gate2_visa: str = ""

    use_dual_gate: bool = False
    dual_gate_visa: str = ""
    dual_gate_visa_library: str = 'C:\\Windows\\System32\\visa64.dll'

    use_srs860_1: bool = False
    srs860_1_visa: str = ""

    use_srs860_2: bool = False
    srs860_2_visa: str = ""

    use_srs830_1: bool = False
    srs830_1_visa: str = ""

    use_srs830_2: bool = False
    srs830_2_visa: str = ""

    use_srs830_3: bool = False
    srs830_3_visa: str = ""

    use_mfli_1: bool = False
    mfli_1_host: str = ""  # e.g. "192.168.93.134" or "localhost"
    mfli_1_port: int = 8004
    mfli_1_dev: str = ""

    use_mfli_2: bool = False
    mfli_2_host: str = ""  # e.g. "192.168.93.134" or "localhost"
    mfli_2_port: int = 8004
    mfli_2_dev: str = ""

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
        self._magnet_tab = self._build_magnet_tab()
        self._keithley_tab = self._build_keithley_tab()
        self._lockins_tab = self._build_lockins_tab()
        self._mfli_tab = self._build_mfli_tab()

        self.tabs.addTab(self._magnet_tab, "Magnet")
        self.tabs.addTab(self._keithley_tab, "Keithley SMUs")
        self.tabs.addTab(self._lockins_tab, "Lock-ins")
        self.tabs.addTab(self._mfli_tab, "Zurich MFLI")


        # Buttons
        self.btn_refresh = QtWidgets.QPushButton("Refresh lists")
        self.btn_save = QtWidgets.QPushButton("Save & Launch")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")

        self.btn_refresh.clicked.connect(self._refresh_all)
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
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

    def _com_list(self) -> List[str]:
        if list_ports is None:
            return []
        try:
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    def _apply_cfg_to_widgets(self) -> None:
        # Magnet
        self.chk_magnet.setChecked(self._cfg.use_magnet)
        self.cmb_magnet_port.setEditText(self._cfg.magnet_com)
        self.spn_magnet_baud.setValue(int(self._cfg.magnet_baud))
        self.dsb_magnet_timeout.setValue(float(self._cfg.magnet_timeout_s))
        # Gate 1/2 and Dual
        self.chk_gate1.setChecked(self._cfg.use_gate1)
        self.cmb_gate1.setEditText(self._cfg.gate1_visa)
        self.chk_gate2.setChecked(self._cfg.use_gate2)
        self.cmb_gate2.setEditText(self._cfg.gate2_visa)
        self.chk_dual.setChecked(self._cfg.use_dual_gate)
        self.cmb_dual.setEditText(self._cfg.dual_gate_visa)

        # Lock-ins
        self.chk_srs860_1.setChecked(self._cfg.use_srs860_1)
        self.cmb_srs860_1.setEditText(self._cfg.srs860_1_visa)
        self.chk_srs860_2.setChecked(self._cfg.use_srs860_2)
        self.cmb_srs860_2.setEditText(self._cfg.srs860_2_visa)

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
        self._fill_com_ports(self._com_list())


    # ---------- Tabs ----------
    def _build_magnet_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)

        self.chk_magnet = QtWidgets.QCheckBox("Use Cryomagnetics MPS4G")
        self.cmb_magnet_port = QtWidgets.QComboBox()
        self.cmb_magnet_port.setEditable(True)
        self.spn_magnet_baud = QtWidgets.QSpinBox()
        self.spn_magnet_baud.setRange(1200, 921600)
        self.spn_magnet_baud.setValue(9600)
        self.dsb_magnet_timeout = QtWidgets.QDoubleSpinBox()
        self.dsb_magnet_timeout.setRange(0.01, 10.0)
        self.dsb_magnet_timeout.setDecimals(2)
        self.dsb_magnet_timeout.setValue(0.30)

        form.addRow(self.chk_magnet)
        form.addRow("COM Port:", self.cmb_magnet_port)
        form.addRow("Baud:", self.spn_magnet_baud)
        form.addRow("Timeout (s):", self.dsb_magnet_timeout)
        return w

    def _build_keithley_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(w)

        self.chk_gate1 = QtWidgets.QCheckBox("Use Gate_1 (Keithley 2450)")
        self.cmb_gate1 = QtWidgets.QComboBox(); self.cmb_gate1.setEditable(True)
        self.chk_gate2 = QtWidgets.QCheckBox("Use Gate_2 (Keithley 2450)")
        self.cmb_gate2 = QtWidgets.QComboBox(); self.cmb_gate2.setEditable(True)
        self.chk_dual = QtWidgets.QCheckBox("Use Dual_gate (Keithley 2604B)")
        self.cmb_dual = QtWidgets.QComboBox(); self.cmb_dual.setEditable(True)

        grid.addWidget(self.chk_gate1, 0, 0); grid.addWidget(self.cmb_gate1, 0, 1)
        grid.addWidget(self.chk_gate2, 1, 0); grid.addWidget(self.cmb_gate2, 1, 1)
        grid.addWidget(self.chk_dual, 2, 0); grid.addWidget(self.cmb_dual, 2, 1)
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
        self.chk_srs830_1 = QtWidgets.QCheckBox("Use SRS830_1")
        self.cmb_srs830_1 = QtWidgets.QComboBox(); self.cmb_srs830_1.setEditable(True)
        self.chk_srs830_2 = QtWidgets.QCheckBox("Use SRS830_2")
        self.cmb_srs830_2 = QtWidgets.QComboBox(); self.cmb_srs830_2.setEditable(True)
        self.chk_srs830_3 = QtWidgets.QCheckBox("Use SRS830_3")
        self.cmb_srs830_3 = QtWidgets.QComboBox(); self.cmb_srs830_3.setEditable(True)

        grid.addWidget(self.chk_srs860_1, 0, 0); grid.addWidget(self.cmb_srs860_1, 0, 1)
        grid.addWidget(self.chk_srs860_2, 1, 0); grid.addWidget(self.cmb_srs860_2, 1, 1)
        grid.addWidget(self.chk_srs830_1, 2, 0); grid.addWidget(self.cmb_srs830_1, 2, 1)
        grid.addWidget(self.chk_srs830_2, 3, 0); grid.addWidget(self.cmb_srs830_2, 3, 1)
        grid.addWidget(self.chk_srs830_3, 4, 0); grid.addWidget(self.cmb_srs830_3, 4, 1)
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
    def _fill_com_ports(self, ports: List[str]):
        self.cmb_magnet_port.clear()
        self.cmb_magnet_port.addItems(ports)
        self.cmb_magnet_port.setEditable(True)

    def _fill_visa_comboboxes(self, resources: List[str]):
        for cmb in (self.cmb_gate1, self.cmb_gate2, self.cmb_dual,
                     self.cmb_srs860_1, self.cmb_srs860_2,
                       self.cmb_srs830_1, self.cmb_srs830_2, self.cmb_srs830_3):
            cmb.clear(); cmb.addItems(resources); cmb.setEditable(True)


    def accept(self) -> None:
        # Gather -> save JSON
        cfg = InstrumentConfig(
            use_magnet=self.chk_magnet.isChecked(),
            magnet_com=self.cmb_magnet_port.currentText().strip(),
            magnet_baud=int(self.spn_magnet_baud.value()),
            magnet_timeout_s=float(self.dsb_magnet_timeout.value()),

            use_gate1=self.chk_gate1.isChecked(),
            gate1_visa=self.cmb_gate1.currentText().strip(),

            use_gate2=self.chk_gate2.isChecked(),
            gate2_visa=self.cmb_gate2.currentText().strip(),

            use_dual_gate=self.chk_dual.isChecked(),
            dual_gate_visa=self.cmb_dual.currentText().strip(),

            use_srs860_1=self.chk_srs860_1.isChecked(),
            srs860_1_visa=self.cmb_srs860_1.currentText().strip(),

            use_srs860_2=self.chk_srs860_2.isChecked(),
            srs860_2_visa=self.cmb_srs860_2.currentText().strip(),

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
    def _scan_mfli_devices(self):
        """Scan for all available MFLI devices and populate all device dropdowns."""
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

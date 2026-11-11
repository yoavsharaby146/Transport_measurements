"""
Magnet Sweep Rate Setup Dialog
-----------------------------------------------------------------
What this provides
- A small GUI shown right AFTER the pre-launch instrument dialog, but
  ONLY when the Cryomagnetics MPS4G magnet was selected for use
  (otherwise it is skipped silently).
- Reads the magnet's 5 current ranges (RANGE? i) and default charge
  rates (RATE? i) directly from the instrument and shows them
  READ-ONLY (the ranges cannot be edited here).
- The ONLY editable values are the per-range SAFETY RATES (max sweep
  rate in T/min). On Save they are written to instrument_overrides.json
  under the key 'magnet_safety_limits', where procedures/base.py picks
  them up for every magnet-sweeping procedure.

The port is opened briefly for the read and closed again so that
configuration.py can open it afterwards.
"""
from __future__ import annotations
import json
import os
import sys

from PyQt5 import QtWidgets, QtCore

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

# Parent directory hosts the Instruments package (same trick as configuration.py)
PARENT_DIR = os.path.dirname(THIS_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

OVERRIDES_JSON = os.path.join(THIS_DIR, "instrument_overrides.json")

# Field(current) conversion used by every procedure in this suite
# (driver: 1.0375 * 10 A per Tesla)
A_PER_T = 10.375

# Default safety limits (T/min) per current range 0-4 — must stay in sync
# with procedures.base.MAGNET_DEFAULT_SAFETY_RATES
DEFAULT_SAFETY_RATES = {0: 0.20, 1: 0.10, 2: 0.05, 3: 0.03, 4: 0.001}

SAFETY_RATE_MIN = 0.0001   # T/min — lowest editable safety rate
SAFETY_RATE_MAX = 0.5      # T/min — highest editable safety rate


def _load_overrides() -> dict:
    try:
        with open(OVERRIDES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _saved_safety_limits() -> dict:
    """Safety limits (T/min) previously saved, falling back to defaults."""
    limits = dict(DEFAULT_SAFETY_RATES)
    saved = _load_overrides().get("magnet_safety_limits") or {}
    for i in range(5):
        v = saved.get(str(i), saved.get(i))
        if v is None:
            continue
        try:
            limits[i] = float(v)
        except (TypeError, ValueError):
            pass
    return limits


def _save_safety_limits(limits: dict) -> None:
    """Merge the safety limits into instrument_overrides.json."""
    data = _load_overrides()
    data["magnet_safety_limits"] = {str(i): float(limits[i]) for i in range(5)}
    with open(OVERRIDES_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_magnet_info(com: str, baud: int, timeout: float):
    """Open the MPS4G briefly and read range limits & default rates.

    Returns (ranges_A, rates_A_s) lists for ranges 0-4, or (None, None)
    when the magnet cannot be reached. The port is always closed again.
    """
    try:
        from Instruments.Cryomagnetics_MPS4G import Cryomagnetics_MPS4G
        magnet = Cryomagnetics_MPS4G(com, baudrate=baud, timeout=timeout)
        try:
            magnet.remote()
            ranges_A = [float(getattr(magnet, f"current_range{i}")) for i in range(5)]
            rates_A_s = [float(getattr(magnet, f"current_rate{i}")) for i in range(5)]
            return ranges_A, rates_A_s
        finally:
            try:
                magnet.close()
            except Exception:
                pass
    except Exception:
        return None, None


class MagnetSetupDialog(QtWidgets.QDialog):
    """Shows the magnet's ranges & default rates (read-only) and lets the
    user edit ONLY the per-range safety rates (T/min)."""

    def __init__(self, ranges_A, rates_A_s, saved_limits, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Magnet Sweep Rate Setup (Cryomagnetics MPS4G)")
        self.setModal(True)
        self.setMinimumWidth(780)

        live = ranges_A is not None and rates_A_s is not None
        self._spins = {}

        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Ranges and default rates below are read from the magnet and are "
            "READ-ONLY.\nOnly the per-range safety rates (max sweep rate in T/min) "
            "may be edited. During a sweep, a requested rate\nis applied only where it "
            "does not exceed that range's safety limit; otherwise the default rate "
            "is kept.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if not live:
            warn = QtWidgets.QLabel(
                "WARNING: could not read the magnet (port busy/offline). "
                "Range/default-rate columns show 'n/a'; the safety rates below still apply.")
            warn.setStyleSheet("color: #b00000;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        grid = QtWidgets.QGridLayout()
        headers = ["Range", "Field span (T)", "Upper limit (A)",
                   "Default rate (T/min)", "Default rate (A/s)",
                   "Safety max rate (T/min)"]
        for col, text in enumerate(headers):
            grid.addWidget(QtWidgets.QLabel(f"<b>{text}</b>"), 0, col)

        lower_A = 0.0
        for i in range(5):
            grid.addWidget(QtWidgets.QLabel(str(i)), i + 1, 0)

            if live:
                upper_A = ranges_A[i]
                rate_A_s = rates_A_s[i]
                grid.addWidget(QtWidgets.QLabel(
                    f"{lower_A / A_PER_T:.3f} – {upper_A / A_PER_T:.3f}"), i + 1, 1)
                grid.addWidget(QtWidgets.QLabel(f"{upper_A:.3f}"), i + 1, 2)
                grid.addWidget(QtWidgets.QLabel(
                    f"{rate_A_s * 60.0 / A_PER_T:.4f}"), i + 1, 3)
                grid.addWidget(QtWidgets.QLabel(f"{rate_A_s:.5f}"), i + 1, 4)
                lower_A = upper_A
            else:
                for col in (1, 2, 3, 4):
                    grid.addWidget(QtWidgets.QLabel("n/a"), i + 1, col)

            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(SAFETY_RATE_MIN, SAFETY_RATE_MAX)
            spin.setDecimals(4)
            spin.setSingleStep(0.001)
            spin.setSuffix(" T/min")
            spin.setValue(float(saved_limits[i]))
            self._spins[i] = spin
            grid.addWidget(spin, i + 1, 5)

        layout.addLayout(grid)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def safety_limits(self) -> dict:
        return {i: self._spins[i].value() for i in range(5)}


def run_if_magnet_in_use() -> bool:
    """Show the magnet rate setup dialog when the magnet is selected in the
    pre-launch dialog; silently do nothing otherwise.

    Returns True when new safety limits were saved.
    """
    data = _load_overrides()
    if not (data.get("use_magnet") and data.get("magnet_com")):
        return False  # magnet not in use -> skip entirely

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    com = data.get("magnet_com")
    try:
        baud = int(data.get("magnet_baud", 9600))
        timeout = float(data.get("magnet_timeout_s", 0.3))
    except (TypeError, ValueError):
        baud, timeout = 9600, 0.3

    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        ranges_A, rates_A_s = _read_magnet_info(com, baud, timeout)
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()

    dlg = MagnetSetupDialog(ranges_A, rates_A_s, _saved_safety_limits())
    if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        print("[magnet_setup] cancelled — previously saved safety limits kept.")
        return False

    limits = dlg.safety_limits()

    # Gentle sanity check: rates normally must not increase with range
    if any(limits[i] < limits[i + 1] for i in range(4)):
        reply = QtWidgets.QMessageBox.question(
            None, "Unusual safety rates",
            "Safety rates normally decrease for higher-current ranges.\n"
            "Save these values anyway?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply != QtWidgets.QMessageBox.Yes:
            return False

    try:
        _save_safety_limits(limits)
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Save failed", str(e))
        return False
    print(f"[magnet_setup] safety rates saved: {limits}")
    return True


if __name__ == "__main__":
    # Standalone test: python magnet_setup.py
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    run_if_magnet_in_use()

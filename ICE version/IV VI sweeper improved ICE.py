import sys, os
import re
import csv
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import time
import threading
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, '..')
sys.path.insert(0, repo_root)  # front of path: resolves Instruments/ at repo root
# (this file lives in 'ICE version/', so the repo root is one level up —
# same convention as ICE version/configuration.py)

try:
    from Instruments.keithley2450_with_add_ons import Keithley2450
    from Instruments.yokogawa7651_with_add_ons import Yokogawa7651
    from Instruments.yokogawags200_with_add_ons import YokogawaGS200
    from Instruments.keithley2604B import Keithley2604B
except ImportError as e:
    print("\nCRITICAL ERROR: Could not import instrument drivers.")
    print(f"{e}")
    print("Make sure 'Instruments/' exists at the repository root.\n")

# ICE-only additions: Cryomagnetics MPS4G magnet (serial/COM). The magnet
# exists only on the ICE workstation, so these features are silently inert
# anywhere else (the row stays but cannot connect).
try:
    from Instruments.Cryomagnetics_MPS4G import Cryomagnetics_MPS4G
    from serial.tools import list_ports
except ImportError as e:
    print("\nCRITICAL ERROR: Could not import the magnet driver (needs pyserial).")
    print(f"{e}")
    Cryomagnetics_MPS4G = None
    list_ports = None

# Yokogawa fixed voltage ranges (no auto-range command on either unit)
V_RANGES = [10e-3, 100e-3, 1, 10, 30]

GATE_KINDS = {
    "Keithley 2450": "keithley",
    "Keithley 2604B": "k2604b",
    "Yokogawa 7651": "yoko7651",
    "Yokogawa GS200": "gs200",
}


# ==================== WINDOW COLOR PALETTES ====================
# Every color used by the window is defined HERE, in this one dictionary.
# To re-theme the program: set ACTIVE_THEME below ("light" or "dark") and
# restart the program (a running window does not live-update). Values are
# hex strings "#rrggbb" or any Tk color name such as "grey", "orange",
# "white".
LIGHT_THEME = {
    # --- window & panels ---
    "background":        "#f4f7fb",  # window background
    "surface":           "#ffffff",  # panel (LabelFrame) background
    "border":            "#dce4ee",  # panel borders
    "text":              "#253449",  # normal text
    "muted_text":        "#718096",  # subtitle / hint text
    "field":             "#ffffff",  # entry / combobox input fields
    "accent":            "#1768a5",  # title, section titles, selected tab
    "tab_inactive":      "#e2eaf3",  # unselected notebook tabs
    "tab_inactive_text": "#44566d",  # text on unselected tabs
    "button":            "#e7eef6",  # regular ttk buttons
    "button_hover":      "#d4e4f3",  # ttk buttons under the mouse
    "canvas":            "#fbf4f4",  # scrollable tab canvas

    # --- actions ---
    "run":               "#16845b",  # RUN SWEEP button
    "run_hover":         "#106b49",  # RUN SWEEP pressed/hover
    "abort":             "#ff000d",  # ABORT button
    "abort_hover":       "#a7353b",  # ABORT pressed/hover
    "action_text":       "#ffffff",  # text on RUN/ABORT buttons

    # --- log console ---
    "log_background":    "#14181f",
    "log_text":          "#d8dee9",
    "log_cursor":        "#26cca2",
    "log_selection":     "#3a5a80",

    # --- instrument status buttons ("Out:" / "Term:") ---
    "status_neutral":    "#e0e0e0",  # not connected / "Term: ---"
    "status_on":         "#90ee90",  # output ON
    "status_off":        "#ffcccb",  # output OFF
    "status_error":      "grey",     # status unknown (instrument error)
    "status_rear":       "orange",   # bias "Term: REAR"
}

# Inverted (dark-gray) variant: the "negative" of the light palette, but on
# a dark GRAY base (not black) for easier reading. The status chips keep
# their light pastel colors — they are indicator badges drawn with black
# text, so they stay readable on the dark background too.
DARK_THEME = {
    # --- window & panels ---
    "background":        "#333842",
    "surface":           "#3a4150",
    "border":            "#4a5364",
    "text":              "#e6e9ee",
    "muted_text":        "#9aa5b5",
    "field":             "#262b34",  # entry / combobox input fields
    "accent":            "#4fa3e3",
    "tab_inactive":      "#2e3440",
    "tab_inactive_text": "#c0c9d6",
    "button":            "#3f4756",
    "button_hover":      "#282e3b",
    "canvas":            "#2f343e",

    # --- actions ---
    "run":               "#2e9e6b",
    "run_hover":         "#237d54",
    "abort":             "#ff000d",
    "abort_hover":       "#a7353b",
    "action_text":       "#ffffff",

    # --- log console ---
    "log_background":    "#23272f",
    "log_text":          "#d8dee9",
    "log_cursor":        "#26cca2",
    "log_selection":     "#3a5a80",

    # --- instrument status buttons (light chips, same as light theme) ---
    "status_neutral":    "#e0e0e0",
    "status_on":         "#90ee90",
    "status_off":        "#ffcccb",
    "status_error":      "grey",
    "status_rear":       "orange",
}

# Light/dark setting: stored in instrument_overrides.json ('theme' key) and
# switched from the header button in the running program.
def palette_for(theme):
    return DARK_THEME if theme == "dark" else LIGHT_THEME


def _theme_overrides_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "instrument_overrides.json")


def load_theme_setting():
    try:
        with open(_theme_overrides_path(), "r", encoding="utf-8") as f:
            t = json.load(f).get("theme", "light")
        return t if t in ("light", "dark") else "light"
    except Exception:
        return "light"


def save_theme_setting(theme):
    data = {}
    try:
        with open(_theme_overrides_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["theme"] = theme
    with open(_theme_overrides_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


COLORS = palette_for(load_theme_setting())


def pick_v_range(level):
    """Smallest fixed Yokogawa range that fits |level|."""
    for r in V_RANGES:
        if abs(level) <= r:
            return r
    return V_RANGES[-1]


def arange_inclusive(start, end, step):
    """np.arange from start to end inclusive; works in both directions."""
    sign = 1.0 if end >= start else -1.0
    return list(np.arange(start, end + sign * step / 2.0, sign * step))


def ramp_sequence(start, target, step_v):
    """Inclusive list of intermediate levels from start to target in steps of step_v."""
    if abs(target - start) < 1e-9 or step_v <= 0:
        return []
    sign = 1.0 if target > start else -1.0
    n = int(abs(target - start) / step_v) + 1
    seq = [start + sign * step_v * (i + 1) for i in range(n)]
    seq[-1] = target  # snap the final point exactly onto the target
    return seq


def next_file_number(directory, sweep_type):
    """Next sequential file number in a folder, pymeasure unique_filename-style.

    Looks for existing 'IV_007_*.csv' / 'VI_007_*.csv' files and returns
    max(existing numbers) + 1, so numbering continues where the folder left off.
    Old timestamp-named files (IV_1763020000_...) are ignored: their numbers are
    far too large to be sequence counters.
    """
    n = 0
    pattern = re.compile(rf"^{sweep_type.upper()}_(\d+)_")
    try:
        for f in os.listdir(directory):
            m = pattern.match(f)
            if m and int(m.group(1)) < 1_000_000:
                n = max(n, int(m.group(1)) + 1)
    except OSError:
        pass  # folder missing/empty -> start at 000
    return n


# ==================== ICE-only: cryostat log reader ====================
# Same reader as the ICE version's configuration.py: today's ICElog file on
# the ICE PC, columns 5-8 of the last complete line are the cryostat
# temperatures (50K plate, 4K plate, VTI, probe) in Kelvin. configuration.py
# itself cannot be imported here — importing it would open every instrument.

ICE_TEMP_LOG_ROOT = r"C:\Users\ICE\Desktop\ICElog\Results"
TEMP_COLUMNS = ('50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)')


def read_ice_temperature(root=ICE_TEMP_LOG_ROOT, ext=".log",
                         timeout=5.0, poll=0.25, encoding="utf-8"):
    """Return the 4 cryostat temperatures (numpy array) from the last
    complete line of today's ICElog file.

    Raises on timeout/parse errors so callers can decide how to handle it
    (the sweep itself must never fail because of the temperature log).
    """
    root = Path(root)
    t0 = time.time()

    while True:
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = root / today / f"{today}{ext}"

        if file_path.is_file():
            break

        if (time.time() - t0) > timeout:
            raise FileNotFoundError(f"File not found within timeout: {file_path}")
        time.sleep(poll)

    # file exists: try to read the last complete line
    t0 = time.time()
    while True:
        try:
            with file_path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    raise RuntimeError("Log file is empty")

                pos = f.tell() - 1
                while pos >= 0:
                    f.seek(pos)
                    if f.read(1) not in (b"\n", b"\r"):
                        break
                    pos -= 1
                if pos < 0:
                    raise RuntimeError("Log file contains only newlines")

                while pos >= 0:
                    f.seek(pos)
                    if f.read(1) == b"\n":
                        pos += 1
                        break
                    pos -= 1

                f.seek(max(pos, 0))
                line = f.readline()
        except PermissionError:
            line = b""

        if line.endswith(b"\n") or (time.time() - t0) > timeout:
            break
        time.sleep(poll)

    raw = line.decode(encoding, errors="replace").rstrip("\r\n")
    fields = next(csv.reader([raw]))

    try:
        values = [float(fields[i]) for i in range(4, 8)]
    except (IndexError, ValueError) as e:
        raise RuntimeError(f"Cannot parse temperature columns 5-8: {e}") from e

    return np.array(values, dtype=float)


# Magnet field <-> current conversion used by the MPS4G driver (10.375 A per T)
A_PER_T = 10.375
# Per-range safety sweep rates (T/min) — fallback when instrument_overrides.json
# has no 'magnet_safety_limits' block (same defaults as the magnet setup dialog).
MAGNET_DEFAULT_SAFETY_RATES = {0: 0.20, 1: 0.10, 2: 0.05, 3: 0.03, 4: 0.001}


class GateChannel:
    """One gate voltage source (Keithley 2450 / Yokogawa 7651 / Yokogawa GS200).

    Owns its connection, uniform source API and UI panel so that
    Gate 1 and Gate 2 are fully independent instruments.
    """

    def __init__(self, index, app):
        self.index = index  # 1 or 2
        self.app = app      # main application (log, stop_event, buttons)
        self.inst = None
        self.kind = None    # 'keithley' | 'k2604b' | 'yoko7651' | 'gs200'
        self.smu_parent = None  # Keithley2604B box when kind == 'k2604b'
        self.chan_label = None  # 'smua' | 'smub' when kind == 'k2604b'

    @property
    def name(self):
        return f"Gate {self.index}"

    # ============================ UI ============================

    def build_connection_row(self, parent, row):
        ttk.Label(parent, text=f"Gate {self.index} (optional):").grid(
            row=row, column=0, padx=5, pady=2, sticky="e")
        ch_row = ttk.Frame(parent)
        ch_row.grid(row=row, column=1, sticky="ew")
        self.kind_combo = ttk.Combobox(ch_row, values=list(GATE_KINDS.keys()),
                                       state="readonly", width=15)
        self.kind_combo.current(0)
        self.kind_combo.pack(side="left")
        self.kind_combo.bind('<<ComboboxSelected>>',
                             lambda e: self._update_chan_visibility())
        # SMU channel selector (only shown for the dual-channel Keithley 2604B)
        self.chan_combo = ttk.Combobox(ch_row, values=["SMU A", "SMU B"],
                                       state="readonly", width=6)
        self.chan_combo.set("SMU A")
        self.addr_combo = ttk.Combobox(ch_row, width=24)
        self.chan_combo.pack_forget()  # hidden unless a 2604B is selected
        self.addr_combo.pack(side="left", padx=(5, 0), fill="x", expand=True)
        ttk.Button(parent, text="Connect", command=self.connect, width=9).grid(
            row=row, column=2, padx=5)
        # front/rear terminal control — only functional on a Keithley 2450
        # gate (same as the bias row); inert on the Yokogawas / 2604B
        self.btn_term = tk.Button(parent, text="Term: ---", bg=COLORS["status_neutral"],
                                  width=10, command=self.toggle_terminals)
        self.btn_term.grid(row=row, column=3, padx=5)
        self.btn_out = tk.Button(parent, text="Out: ---", bg=COLORS["status_neutral"], width=9,
                                 command=self.toggle_output)
        self.btn_out.grid(row=row, column=4, padx=5)
        ttk.Button(parent, text="Reset", command=self.reset, width=7).grid(
            row=row, column=5, padx=5)

    def build_config_panel(self, parent):
        """One half of section 2: source config + manual ramp for this gate."""
        p = self.app.saved_params
        box = ttk.LabelFrame(parent, text=f"Gate {self.index} Voltage Source & Ramping",
                             padding=5)

        cfg = ttk.Frame(box)
        cfg.pack(fill="x")
        ttk.Label(cfg, text="Compliance (A):").pack(side="left")
        self.ent_compliance = ttk.Entry(cfg, width=9)
        self.ent_compliance.insert(0, p[f'g{self.index}_compliance'])
        self.ent_compliance.pack(side="left", padx=3)

        self.lbl_nplc = ttk.Label(cfg, text="NPLC:")
        self.lbl_nplc.pack(side="left", padx=(12, 0))
        self.ent_nplc = ttk.Entry(cfg, width=5)
        self.ent_nplc.insert(0, p[f'g{self.index}_nplc'])
        self.ent_nplc.pack(side="left", padx=3)

        cfg2 = ttk.Frame(box)
        cfg2.pack(fill="x", pady=(4, 0))
        ttk.Label(cfg2, text="Target (V):").pack(side="left")
        self.ent_target = ttk.Entry(cfg2, width=9)
        self.ent_target.insert(0, p[f'g{self.index}_target'])
        self.ent_target.pack(side="left", padx=3)
        ttk.Label(cfg2, text="Step (mV):").pack(side="left", padx=(12, 0))
        self.ent_step = ttk.Entry(cfg2, width=7)
        self.ent_step.insert(0, p[f'g{self.index}_step'])
        self.ent_step.pack(side="left", padx=3)
        ttk.Label(cfg2, text="Rate (V/s):").pack(side="left", padx=(12, 0))
        self.ent_rate = ttk.Entry(cfg2, width=7)
        self.ent_rate.insert(0, p[f'g{self.index}_rate'])
        self.ent_rate.pack(side="left", padx=3)

        btns = ttk.Frame(box)
        btns.pack(fill="x", pady=(6, 0))
        self.btn_ramp = ttk.Button(btns, text="Ramp Gate", command=self.start_manual_ramp)
        self.btn_ramp.pack(side="left", padx=2)
        ttk.Button(btns, text="Configure Source", command=self.apply_config).pack(
            side="left", padx=2)
        ttk.Button(btns, text="Measure Once", command=self.measure_once).pack(
            side="left", padx=2)

        self.lbl_status = ttk.Label(box, text=f"Gate {self.index}: --- V",
                                    font=("Consolas", 9))
        self.lbl_status.pack(anchor="w", pady=(4, 0))
        # stacked full-width (Gate 1 above Gate 2) so both cards stay visible
        # next to the docked log even on small screens
        box.pack(fill="x", pady=2, padx=2)

    # ==================== CONNECTION ====================

    def connect(self):
        addr = self.addr_combo.get()
        if not addr:
            messagebox.showerror("Error", f"No address selected for Gate {self.index}")
            return
        kind = GATE_KINDS[self.kind_combo.get()]
        chan_label = None
        if kind == "k2604b":
            chan_label = "smua" if "A" in self.chan_combo.get() else "smub"

        # block duplicates: same address is only legal for two 2604B channels
        # of the same box (e.g. Gate 1 = smua, Gate 2 = smub)
        other = self.app.other_channel(self.index)
        if other.inst is not None and other.addr_combo.get() == addr:
            same_channel = (kind != "k2604b" or other.kind != "k2604b"
                            or chan_label == other.chan_label)
            if same_channel:
                messagebox.showerror(
                    "Error", f"Gate {other.index} is already connected to {addr}"
                             + (f" ({other.chan_label})" if other.chan_label else "")
                             + ".\nThe two gates must be different sources.")
                return

        try:
            if kind == "keithley":
                inst = Keithley2450(addr)
                inst.adapter.connection.timeout = 10000
                inst.adapter.connection.read_termination = '\n'
                inst.adapter.connection.write_termination = '\n'
            elif kind == "k2604b":
                parent = Keithley2604B(addr)
                parent.instrument.timeout = 10000
                self.smu_parent = parent
                inst = getattr(parent, chan_label)
            elif kind == "yoko7651":
                inst = Yokogawa7651(addr)
                # legacy protocol: no termination overrides (matches working GUI)
                inst.adapter.connection.timeout = 10000
            else:  # gs200
                inst = YokogawaGS200(addr)
                inst.adapter.connection.timeout = 10000
                inst.adapter.connection.read_termination = '\n'
                inst.adapter.connection.write_termination = '\n'
                inst.adapter.connection.clear()
            self.inst = inst
            self.kind = kind
            self.chan_label = chan_label
            self.apply_ui_kind()
            extra = f" ({chan_label.upper()})" if chan_label else ""
            self.app.log(f"Gate {self.index} ({self.kind_combo.get()}{extra}) "
                         f"connected: {addr}")
            self.update_status()
        except Exception as e:
            self._forget_connection()
            messagebox.showerror("Connection Error",
                                 f"Failed to connect Gate {self.index}:\n{e}")
            self.app.log(f"Gate {self.index} connection failed: {e}")

    def _forget_connection(self):
        self.inst = None
        self.kind = None
        self.smu_parent = None
        self.chan_label = None
        self.apply_ui_kind()

    def disconnect(self):
        if self.inst:
            # NOTE: output and level intentionally left untouched —
            # closing the program does not mean the experiment is over.
            level = self.read_level()
            try:
                on = self.output_on()
                v_str = f"{level:.4f} V" if level is not None else "unknown level"
                self.app.log(f"Gate {self.index} disconnected (left at {v_str}, output "
                             f"{'ON' if on else 'OFF'})")
            except Exception:
                self.app.log(f"Gate {self.index} disconnected")
            try:
                if self.kind == "k2604b":
                    self.smu_parent.close()
                else:
                    self.inst.adapter.connection.close()
            except Exception:
                pass
        self._forget_connection()
        self.update_status()

    def toggle_output(self):
        if not self.inst:
            return
        try:
            on = self.output_on()
            self.enable(not on)
            self.app.log(f"Gate {self.index} output {'OFF' if on else 'ON'}")
            time.sleep(0.1)
            self.update_status()
        except Exception as e:
            self.app.log(f"Gate {self.index} output error: {e}")

    def toggle_terminals(self):
        """Swap front/rear terminals (Keithley 2450 gates only, like bias)."""
        if not self.inst or self.kind != "keithley":
            return
        try:
            if "FRON" in self.inst.check_terminals():
                self.inst.use_rear_terminals()
            else:
                self.inst.use_front_terminals()
            time.sleep(0.2)
            self.update_status()
        except Exception as e:
            self.app.log(f"Gate {self.index} terminal error: {e}")

    def reset(self):
        if not self.inst:
            return
        try:
            if self.kind == "keithley":
                self.inst.reset()
            elif self.kind == "k2604b":
                self.smu_parent.reset()
            elif self.kind == "yoko7651":
                self.inst.write("RC;E")
                self.inst.write("H0;E")
            else:
                self.inst.reset()
                self.inst.source_mode = "voltage"
            self.app.log(f"Gate {self.index} reset")
            self.update_status()
        except Exception as e:
            self.app.log(f"Gate {self.index} reset error: {e}")

    def update_status(self):
        if not self.inst:
            self.btn_out.config(text="Out: ---", bg=COLORS["status_neutral"])
            self.btn_term.config(text="Term: ---", bg=COLORS["status_neutral"])
            self.lbl_status.config(text=f"Gate {self.index}: --- V")
            return
        if self.kind == "keithley":
            try:
                term = self.inst.check_terminals()
                self.btn_term.config(
                    text="Term: FRONT" if "FRON" in term else "Term: REAR",
                    bg=COLORS["status_on"] if "FRON" in term
                    else COLORS["status_rear"])
            except Exception:
                self.btn_term.config(text="Term: ???", bg=COLORS["status_error"])
        else:  # Yokogawas / 2604B channel: no selectable terminals
            self.btn_term.config(text="Term: ---", bg=COLORS["status_neutral"])
        try:
            on = self.output_on()
            self.btn_out.config(text="Out: ON" if on else "Out: OFF",
                                bg=COLORS["status_on"] if on else COLORS["status_off"])
        except Exception:
            self.btn_out.config(text="Out: ???", bg=COLORS["status_error"])

    def apply_ui_kind(self):
        """NPLC only applies to the Keithley 2450 gate; SMU selector only to 2604B."""
        state = "normal" if self.kind == "keithley" else "disabled"
        self.ent_nplc.config(state=state)
        self.lbl_nplc.config(foreground="black" if self.kind == "keithley" else "grey")
        self._update_chan_visibility()

    def _update_chan_visibility(self):
        """Show the SMU A/B selector only when Keithley 2604B is selected."""
        if GATE_KINDS[self.kind_combo.get()] == "k2604b":
            self.chan_combo.pack(side="left", before=self.addr_combo)
        else:
            self.chan_combo.pack_forget()

    # ==================== UNIFORM SOURCE API ====================

    def enable(self, on):
        if self.kind == "keithley":
            self.inst.enable_source() if on else self.inst.disable_source()
        elif self.kind == "k2604b":
            self.inst.output_on() if on else self.inst.output_off()
        elif self.kind == "yoko7651":
            self.inst.enable_source() if on else self.inst.disable_source()
        else:  # gs200
            self.inst.source_enabled = bool(on)

    def output_on(self):
        if self.kind == "k2604b":
            return bool(self.inst.is_output_on())
        return bool(self.inst.source_enabled)

    def set_level(self, level):
        if self.kind == "keithley":
            self.inst.source_voltage = level
        elif self.kind == "k2604b":
            self.inst.instrument.write(f"{self.inst.label}.source.levelv = {level}")
        elif self.kind == "yoko7651":
            self.inst.source_voltage = level
        else:  # gs200
            self.inst.source_level = level

    def read_level(self):
        """Return current gate level (float) or None if readback fails."""
        try:
            if self.kind == "k2604b":
                return float(self.inst.measure__voltage())
            if self.kind == "gs200":
                return float(self.inst.source_level)
            return float(self.inst.source_voltage)
        except Exception:
            return None

    def measure_voltage(self):
        """TRUE output-voltage measurement where the instrument can measure.

        Keithley 2450: ':MEAS:VOLT?' — measures the actual voltage at the
        terminals (catches compliance limiting, which the source register
        hides). Keithley 2604B channel: measure__voltage() (already a real
        measurement). The Yokogawa 7651 / GS200 are pure sources with no
        voltmeter function — falls back to the source setpoint readback.
        Returns None on failure.
        """
        try:
            if self.kind == "keithley":
                return float(self.inst.ask(":MEAS:VOLT?"))
            if self.kind == "k2604b":
                return float(self.inst.measure__voltage())
        except Exception:
            pass
        return self.read_level()

    def configure_source(self, compliance, nplc, max_abs_v=None):
        """Configure this gate instrument as a voltage source."""
        if max_abs_v is None:
            # cover manual target and (if this gate is looped) the loop range
            cands = []
            try:
                cands.append(abs(float(self.ent_target.get())))
            except ValueError:
                pass
            if self.app.loop_uses_gate(self.index):
                for ent in self.app.loop_range_entries(self.index):
                    try:
                        cands.append(abs(float(ent.get())))
                    except ValueError:
                        pass
            max_abs_v = max(cands) if cands else 1.0

        if self.kind == "keithley":
            self.inst.configure_voltage_source(nplc=nplc, current=1e-6,
                                               compliance_current=compliance)
        elif self.kind == "k2604b":
            self.inst.configure_voltage_source(voltage=0,
                                               current_limit=compliance)
        elif self.kind == "yoko7651":
            self.inst.apply_voltage(max_voltage=pick_v_range(max_abs_v),
                                    compliance_current=compliance)
        else:  # gs200
            self.inst.source_mode = "voltage"
            self.inst.source_range = pick_v_range(max_abs_v)
            self.inst.current_limit = compliance
            self.inst.source_level = 0
        self.app.log(f"Gate {self.index} source configured (compliance={compliance} A"
                     + (f", NPLC={nplc}" if self.kind == "keithley" else "") + ")")

    def ramp_params(self):
        """Parse step (mV) + rate (V/s) into (step_V, delay_s). Raises ValueError."""
        step_v = abs(float(self.ent_step.get())) / 1000.0
        rate = float(self.ent_rate.get())
        if rate <= 0:
            raise ValueError("gate ramp rate must be > 0")
        if step_v <= 0:
            raise ValueError("gate ramp step must be > 0")
        delay = step_v / rate
        return step_v, delay

    def apply_config(self):
        if not self.inst:
            messagebox.showerror("Error", f"Gate {self.index} not connected")
            return
        try:
            compliance = float(self.ent_compliance.get())
            nplc = float(self.ent_nplc.get())
        except ValueError:
            messagebox.showerror("Error", f"Invalid gate {self.index} parameters")
            return
        try:
            self.configure_source(compliance, nplc)
        except Exception as e:
            messagebox.showerror("Gate Config Error", str(e))
            self.app.log(f"Gate {self.index} config error: {e}")

    def ramp_to(self, target, step_v, delay, quiet=False):
        """Slowly ramp gate to target. Aborts if app.stop_event set. Blocking."""
        if self.kind == "keithley":
            def cb(v, i):
                self.app.root.after(0, lambda: self.lbl_status.config(
                    text=f"Gate {self.index}: {v:.4f} V | {i:.3e} A"))
                return self.app.stop_event.is_set()
            self.inst.voltage_ramping_with_monitor(target, step_v, delay, callback=cb)
        elif self.kind == "k2604b":
            # driver has no callback-based monitor: software ramp with abort checks
            start = self.read_level()
            if start is None:
                start = 0.0
            for v in ramp_sequence(start, target, step_v):
                self.set_level(v)
                self.app.root.after(0, lambda v=v: self.lbl_status.config(
                    text=f"Gate {self.index}: {v:.4f} V"))
                if self.app.stop_event.is_set():
                    return
                time.sleep(delay)
        else:
            # Yokos: callback(elapsed, level)
            def cb(_elapsed, level):
                self.app.root.after(0, lambda: self.lbl_status.config(
                    text=f"Gate {self.index}: {level:.4f} V"))
                return self.app.stop_event.is_set()
            start = self.read_level()
            if self.kind == "yoko7651":
                self.inst.ramping_with_monitor(target, step_v, delay, callback=cb,
                                               mode='voltage', start_level=start)
            else:
                self.inst.ramping_with_monitor(target, step_v, delay, callback=cb,
                                               start_level=start)
        if not quiet:
            self.app.log(f"Gate {self.index} at {target} V")

    def measure_once(self):
        if not self.inst:
            messagebox.showerror("Error", f"Gate {self.index} not connected")
            return
        try:
            voltage = self.read_level()
            current = None
            if self.kind == "keithley":
                try:
                    current = float(self.inst.ask(":MEAS:CURR?"))
                except Exception:
                    current = None
            elif self.kind == "k2604b":
                try:
                    current = float(self.inst.measure__current())
                except Exception:
                    current = None
            v_str = f"{voltage:.4f}" if voltage is not None else "---"
            i_str = f" | {current:.3e} A" if current is not None else ""
            self.lbl_status.config(text=f"Gate {self.index}: {v_str} V{i_str}")
            self.app.log(f"Gate {self.index} measurement: {v_str} V{i_str}")
        except Exception as e:
            self.app.log(f"Gate {self.index} measurement error: {e}")
            messagebox.showerror("Measurement Error",
                                 f"Failed to measure Gate {self.index}:\n{e}")

    # ==================== MANUAL GATE RAMP ====================

    def start_manual_ramp(self):
        if not self.inst:
            messagebox.showerror("Error", f"Gate {self.index} not connected")
            return
        try:
            target = float(self.ent_target.get())
            step_v, delay = self.ramp_params()
            compliance = float(self.ent_compliance.get())
            nplc = float(self.ent_nplc.get())
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid gate {self.index} parameters: {e}")
            return

        self.app.saved_params.update({
            f'g{self.index}_target': self.ent_target.get(),
            f'g{self.index}_step': self.ent_step.get(),
            f'g{self.index}_rate': self.ent_rate.get(),
            f'g{self.index}_compliance': self.ent_compliance.get(),
            f'g{self.index}_nplc': self.ent_nplc.get()})

        try:
            self.configure_source(compliance, nplc, max_abs_v=max(abs(target), 1e-3))
        except Exception as e:
            self.app.log(f"Gate {self.index} config error: {e}")
            messagebox.showerror("Gate Config Error", str(e))
            return

        self.btn_ramp.config(state="disabled")
        self.app.set_busy()
        ch = self

        def worker():
            try:
                if not ch.output_on():
                    ch.set_level(ch.read_level() or 0.0)
                    ch.enable(True)
                self.app.log(f"Ramping Gate {ch.index} to {target} V ...")
                ch.ramp_to(target, step_v, delay)
                self.app.log(f"Gate {ch.index} ramp complete"
                             if not self.app.stop_event.is_set()
                             else f"Gate {ch.index} ramp aborted")
            except Exception as e:
                self.app.log(f"Gate {ch.index} ramp error: {e}")
            finally:
                self.app.root.after(0, ch.restore_after_ramp)

        threading.Thread(target=worker, daemon=True).start()

    def restore_after_ramp(self):
        self.btn_ramp.config(state="normal")
        self.app.btn_abort.config(state="disabled")
        self.app.btn_run.config(state="normal")
        self.update_status()


class MagnetChannel:
    """Cryomagnetics MPS4G superconducting magnet (ICE setup, serial/COM).

    The magnet readout is a very slow serial query (~0.5 s), so it is never
    read during a sweep: the field is documented once after each completed
    bias sweep and stored as an extra CSV column, exactly like the gate
    voltages.

    Connection handling mirrors the updated ICE version: stale serial bytes
    are flushed on open, REMOTE mode is enabled, an open failure caused by
    the COM handle still being held (e.g. by a previous instance) is
    retried once, and the port is ALWAYS closed on disconnect so the next
    program can open it.
    """

    def __init__(self, app):
        self.app = app
        self.inst = None

    # ============================ UI ============================

    def build_connection_row(self, parent, row):
        ttk.Label(parent, text="Magnet (MPS4G, ICE):").grid(
            row=row, column=0, padx=5, pady=2, sticky="e")
        m_row = ttk.Frame(parent)
        m_row.grid(row=row, column=1, sticky="ew")
        self.combo = ttk.Combobox(m_row, width=9)
        self.combo.pack(side="left")
        ttk.Label(m_row, text="Baud:").pack(side="left", padx=(8, 0))
        self.ent_baud = ttk.Entry(m_row, width=7)
        self.ent_baud.insert(0, self.app.saved_params['magnet_baud'])
        self.ent_baud.pack(side="left", padx=2)
        ttk.Label(m_row, text="Timeout (s):").pack(side="left", padx=(8, 0))
        self.ent_timeout = ttk.Entry(m_row, width=5)
        self.ent_timeout.insert(0, self.app.saved_params['magnet_timeout'])
        self.ent_timeout.pack(side="left", padx=2)
        self.btn_connect = ttk.Button(parent, text="Connect", width=9,
                                      command=self.toggle_connection)
        self.btn_connect.grid(row=row, column=2, padx=5)
        self.lbl_status = ttk.Label(parent, text="B: --- T",
                                    font=("Consolas", 9))
        self.lbl_status.grid(row=row, column=3, columnspan=3, padx=5, sticky="w")

    # ==================== CONNECTION ====================

    def _open(self, com, baud, timeout):
        """Open the MPS4G and put it in REMOTE mode.

        ICE-version pattern: drop stale bytes so the first query response
        cannot be misaligned, and retry once when Windows has not yet
        released the COM handle from a previous instance.
        """
        try:
            inst = Cryomagnetics_MPS4G(com, baudrate=baud, timeout=timeout)
        except Exception:
            time.sleep(1.0)  # give Windows a moment to release the handle
            inst = Cryomagnetics_MPS4G(com, baudrate=baud, timeout=timeout)
        try:
            inst.serial.reset_input_buffer()
        except Exception:
            pass
        inst.remote()
        return inst

    def toggle_connection(self):
        if self.inst is not None:
            self.disconnect()
            return
        if Cryomagnetics_MPS4G is None:
            messagebox.showerror(
                "Error", "Magnet driver not available "
                         "(Instruments/Cryomagnetics_MPS4G.py)")
            return
        com = self.combo.get().strip()
        if not com:
            messagebox.showerror("Error", "No COM port selected for the magnet")
            return
        try:
            baud = int(self.ent_baud.get())
            timeout = float(self.ent_timeout.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid magnet baud/timeout values")
            return
        try:
            self.inst = self._open(com, baud, timeout)
        except Exception as e:
            self.inst = None
            messagebox.showerror("Connection Error",
                                 f"Failed to connect magnet:\n{e}")
            self.app.log(f"Magnet connection failed: {e}")
            return
        self.app.saved_params.update({'magnet_com': com,
                                       'magnet_baud': str(baud),
                                       'magnet_timeout': str(timeout)})
        self.btn_connect.config(text="Disconnect")
        self.app.log(f"Magnet (Cryomagnetics MPS4G) connected: {com} @ {baud}")
        try:
            field = self.read_field()
            if field is not None:
                self.app.log(f"Magnet field: {field:.4f} T")
        except Exception:
            pass  # status read is best-effort; connection itself succeeded
        # per-range safety limits are set once, right after connecting
        # (same values the ICE procedures read from instrument_overrides.json)
        self.open_safety_dialog()

    def disconnect(self):
        """Close the COM port properly (ICE-version cleanup pattern).

        The magnet output/field is intentionally left untouched — closing
        the program does not mean the experiment is over. Releasing the COM
        port is what matters: without it the next program run cannot open
        the magnet ("Access denied").
        """
        if self.inst is not None:
            try:
                self.inst.close()
            except Exception:
                pass
            self.app.log("Magnet disconnected (COM port released)")
        self.inst = None
        self.btn_connect.config(text="Connect")
        self.lbl_status.config(text="B: --- T")

    # ==================== READOUT ====================

    def read_field(self):
        """Slow blocking read of the magnetic field in Tesla. None on failure."""
        if self.inst is None:
            return None
        try:
            field = float(self.inst.magnet_field)
            self.app.root.after(0, lambda: self.lbl_status.config(
                text=f"B: {field:.4f} T"))
            return field
        except Exception as e:
            self.app.log(f"Magnet field read error: {e}")
            return None

    def read_field_button(self):
        """Manual button: read and log the magnetic field once (blocking)."""
        field = self.read_field()
        if field is not None:
            self.app.log(f"Magnet field: {field:.4f} T")
        # also feed the combined B/T readout in the environment panel
        self.app._env_field = field
        self.app._update_env_label()

    def update_field_status(self, field):
        """Refresh the magnet-tab status label (safe from worker threads)."""
        self.app.root.after(0, lambda: self.lbl_status.config(
            text=f"B: {field:.4f} T"))

    # ==================== FIELD CONTROL ====================

    def _safety_rates(self):
        """Per-range safety sweep rates (T/min) from instrument_overrides.json
        (saved by the magnet setup dialog); defaults if missing/unreadable."""
        limits = dict(MAGNET_DEFAULT_SAFETY_RATES)
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "instrument_overrides.json")
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f).get("magnet_safety_limits") or {}
            for i in range(5):
                v = saved.get(str(i), saved.get(i))
                if v is not None:
                    limits[i] = float(v)
        except Exception:
            pass
        return limits

    # ==================== SAFETY LIMITS SETUP DIALOG ====================

    SAFETY_RATE_MIN = 0.0001   # T/min — lowest editable safety rate
    SAFETY_RATE_MAX = 0.5      # T/min — highest editable safety rate

    def _overrides_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "instrument_overrides.json")

    def _save_safety_limits(self, limits):
        """Merge per-range safety limits into instrument_overrides.json
        (same key this GUI and the ICE procedures read back)."""
        data = {}
        try:
            with open(self._overrides_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["magnet_safety_limits"] = {str(i): float(limits[i]) for i in range(5)}
        with open(self._overrides_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def open_safety_dialog(self):
        """Modal dialog: set the per-range safety rates (T/min) once.

        Opens automatically right after the magnet connects and anytime
        via the 'Safety limits...' button. The saved values clamp every
        magnet ramp (manual and field loop) in this program.
        """
        dlg = tk.Toplevel(self.app.root)
        dlg.title("Magnet safety limits (per current range)")
        dlg.transient(self.app.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        # plain Toplevel keeps the light system background — paint it with
        # the palette so dark mode does not show grey gaps behind the widgets
        dlg.configure(bg=COLORS["background"])

        saved = self._safety_rates()

        ttk.Label(dlg, text="Per-range maximum sweep rates. The read-only columns "
                            "come from the connected instrument;\nonly the "
                            "safety limits (T/min) are editable. Saved to "
                            "instrument_overrides.json.",
                  style="Muted.TLabel", justify="left").grid(
                      row=0, column=0, columnspan=5, padx=10, pady=8, sticky="w")

        for c, text in enumerate(("Range", "Field span (T)", "Up to (A)",
                                  "Instrument rate (T/min)",
                                  "Safety limit (T/min)")):
            ttk.Label(dlg, text=text, font=("Segoe UI", 9, "bold")).grid(
                row=1, column=c, padx=6, pady=2)

        entries = {}
        lower_t = 0.0
        for i in range(5):
            rng_a = rate_a_s = None
            if self.inst is not None:  # live readout from the connected magnet
                try:
                    rng_a = float(getattr(self.inst, f"current_range{i}"))
                except Exception:
                    rng_a = None
                try:
                    rate_a_s = float(getattr(self.inst, f"current_rate{i}"))
                except Exception:
                    rate_a_s = None

            if rng_a is not None:
                span = f"{lower_t:.3f} – {rng_a / A_PER_T:.3f}"
                lower_t = rng_a / A_PER_T
            else:
                span = "n/a"
            ttk.Label(dlg, text=str(i)).grid(row=i + 2, column=0, padx=6)
            ttk.Label(dlg, text=span).grid(row=i + 2, column=1, padx=6)
            ttk.Label(dlg, text="n/a" if rng_a is None else f"{rng_a:.3f}").grid(
                row=i + 2, column=2, padx=6)
            ttk.Label(dlg, text="n/a" if rate_a_s is None
                      else f"{rate_a_s * 60.0 / A_PER_T:.4f}").grid(
                          row=i + 2, column=3, padx=6)
            ent = ttk.Entry(dlg, width=10)
            ent.insert(0, f"{saved[i]:.4f}")
            ent.grid(row=i + 2, column=4, padx=6, pady=1)
            entries[i] = ent

        status = ttk.Label(dlg, text="", foreground=COLORS["abort"])
        status.grid(row=8, column=0, columnspan=5, padx=10, sticky="w")

        def do_save():
            try:
                limits = {i: float(entries[i].get()) for i in range(5)}
            except ValueError:
                status.config(text="All safety limits must be numbers")
                return
            for v in limits.values():
                if not (self.SAFETY_RATE_MIN <= v <= self.SAFETY_RATE_MAX):
                    status.config(
                        text=f"Each limit must be {self.SAFETY_RATE_MIN:g}–"
                             f"{self.SAFETY_RATE_MAX:g} T/min")
                    return
            if any(limits[i] < limits[i + 1] for i in range(4)):
                if not messagebox.askyesno(
                        "Unusual safety rates",
                        "Safety rates normally decrease for higher-current "
                        "ranges.\nSave these values anyway?", parent=dlg):
                    return
            try:
                self._save_safety_limits(limits)
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=dlg)
                return
            self.app.log("Magnet safety limits saved: "
                         + ", ".join(f"R{i}={limits[i]:g} T/min" for i in range(5)))
            dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.grid(row=9, column=0, columnspan=5, padx=10, pady=10, sticky="e")
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=do_save).pack(side="left", padx=4)

    def apply_rate(self, rate_tmin):
        """Set every range's charge rate to `rate_tmin` (T/min), clamped to
        that range's safety limit — the sweep runs as fast as allowed, never
        faster (same semantics as the ICE procedures). Returns the original
        per-range rates (A/s) to hand to restore_rates()."""
        originals = {}
        limits = self._safety_rates()
        for i in range(5):
            originals[i] = float(getattr(self.inst, f"current_rate{i}"))
            applied = min(abs(rate_tmin), limits[i])
            rate_a_s = applied * A_PER_T / 60.0
            setattr(self.inst, f"current_rate{i}", rate_a_s)
            if applied < abs(rate_tmin):
                self.app.log(f"Range {i}: requested {rate_tmin:g} T/min exceeds "
                             f"safety limit {limits[i]:g} T/min — clamped")
        return originals

    def restore_rates(self, originals):
        """Restore the original per-range charge rates (A/s)."""
        for i, r in originals.items():
            try:
                setattr(self.inst, f"current_rate{i}", r)
            except Exception:
                pass

    def go_to_field(self, target_t, rate_tmin, progress=None):
        """Sweep to `target_t` T at `rate_tmin` T/min (safety-clamped).

        Blocking; polls the field every 0.5 s, aborts on stop_event.
        Returns True when the target is reached, False on abort/failure.
        """
        originals = self.apply_rate(rate_tmin)
        try:
            self.inst.go_to_target_field(target_t)
            tol = max(0.005, abs(target_t) * 0.005)
            while True:
                if self.app.stop_event.is_set():
                    return False
                time.sleep(0.5)
                try:
                    field = float(self.inst.magnet_field)
                except Exception:
                    continue  # transient serial glitch: keep polling
                if progress:
                    progress(field)
                if abs(field - target_t) <= tol:
                    return True
        finally:
            self.restore_rates(originals)


class IVVISweeperImproved:
    def __init__(self, root):
        global COLORS
        self.theme = load_theme_setting()
        COLORS = palette_for(self.theme)
        self.root = root
        self.root.title("IV/VI Sweeper ICE - Bias (K2450) + 2 Gates "
                        "+ Magnet (MPS4G) & Temperature")

        self.bias_inst = None
        self.gates = [GateChannel(1, self), GateChannel(2, self)]
        self.magnet = MagnetChannel(self)
        self.stop_event = threading.Event()
        # last manual environment readings shown in the field/temperature panel
        self._env_field = None
        self._env_temps = None
        # sequence runner state (JSON step list loaded in the Sequence tab)
        self._sequence_steps = []
        self._sequence_path = ""
        self._seq_abort = False

        self.saved_params = {
            # IV sweep (voltage source)
            'iv_sp1': "1000", 'iv_sp2': "-1000", 'iv_step': "10",
            'iv_delay': "0.01", 'iv_compliance': "1e-6",
            # VI sweep (current source)
            'vi_sp1': "1e-6", 'vi_sp2': "-1e-6", 'vi_step': "1e-7",
            'vi_delay': "0.01", 'vi_compliance': "1",
            # Bias source config
            'bias_nplc': "1",
            # Gate loop (shared ramp/settle settings)
            'gate_settle': "1", 'loop_ramp_step': "10", 'loop_ramp_delay': "0.05",
            'loop_points': "21",
            # Gate loop ranges
            'g1_start': "-5", 'g1_end': "5", 'g1_loop_step': "1",
            'g2_start': "-5", 'g2_end': "5", 'g2_loop_step': "1",
            # Magnet (ICE only, Cryomagnetics MPS4G over COM)
            'magnet_com': "", 'magnet_baud': "115200", 'magnet_timeout': "0.3",
            # Manual magnet control + field loop (ICE only)
            'mag_rate': "0.1", 'mag_target': "0",
            'field_start': "0", 'field_end': "1", 'field_step': "0.1",
            'field_rate': "0.1",
            'save_dir': "",
        }
        for i in (1, 2):
            self.saved_params.update({
                f'g{i}_compliance': "1e-3", f'g{i}_nplc': "1",
                f'g{i}_target': "0", f'g{i}_step': "10", f'g{i}_rate': "0.2",
            })

        self._tab_canvases = []  # tk canvases need manual recolor on theme switch
        self._build_ui()
        self.refresh_instruments()

    # ============================ UI ============================

    def _build_ui(self):
        self._setup_style()
        self.main_frame = ttk.Frame(self.root, padding=8)
        self.main_frame.pack(fill="both", expand=True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # title bar
        header = ttk.Frame(self.main_frame)
        header.pack(fill="x", pady=(0, 8))
        self.lbl_title = ttk.Label(header, text="IV/VI Sweeper — ICE",
                                   font=("Segoe UI", 15, "bold"),
                                   foreground=COLORS["accent"])
        self.lbl_title.pack(side="left")
        self.lbl_subtitle = ttk.Label(header,
                                      text="Bias (Keithley 2450)  •  2 Gates  •  "
                                           "Magnet (MPS4G) + Temperature",
                                      font=("Segoe UI", 9),
                                      foreground=COLORS["muted_text"])
        self.lbl_subtitle.pack(side="left", padx=12)
        # light/dark switch: saved to instrument_overrides.json and applied
        # LIVE (see apply_theme / toggle_theme) — no window restart
        self.btn_theme = ttk.Button(
            header, text=f"Theme: {self.theme.capitalize()}",
            command=self.toggle_theme, width=12)
        self.btn_theme.pack(side="right")
        ttk.Button(header, text="Help", width=7,
                   command=self.show_user_guide).pack(side="right", padx=6)

        # Left: compact tabs (connection, sweep setup, magnet). Right: the
        # activity log, docked so it is ALWAYS visible while switching tabs.
        # PanedWindow: the divider between the two is user-adjustable.
        body = ttk.PanedWindow(self.main_frame, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(0, 5))
        self.tabs = ttk.Notebook(body)
        body.add(self.tabs, weight=1)
        instruments = self._scrollable_tab("Instruments")
        sweep_setup = self._scrollable_tab("Sweep setup")

        # === 1. CONNECTION ===
        conn = ttk.LabelFrame(instruments, text="Instrument connections", padding=7)
        conn.pack(fill="x", pady=5)
        conn.columnconfigure(1, weight=1)
        conn.columnconfigure(3, weight=0)

        # Bias row (always Keithley 2450)
        ttk.Label(conn, text="Bias (Keithley 2450):").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.bias_combo = ttk.Combobox(conn, width=24)
        self.bias_combo.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(conn, text="Connect", command=self.connect_bias, width=9).grid(row=0, column=2, padx=5)
        self.btn_bias_term = tk.Button(conn, text="Term: ---", bg=COLORS["status_neutral"], width=10,
                                       command=self.toggle_bias_terminals)
        self.btn_bias_term.grid(row=0, column=3, padx=5)
        self.btn_bias_out = tk.Button(conn, text="Out: ---", bg=COLORS["status_neutral"], width=9,
                                      command=self.toggle_bias_output)
        self.btn_bias_out.grid(row=0, column=4, padx=5)
        ttk.Button(conn, text="Reset", command=self.reset_bias, width=7).grid(row=0, column=5, padx=5)

        # Gate 1 + Gate 2 rows (independent, selectable type)
        self.gates[0].build_connection_row(conn, 1)
        self.gates[1].build_connection_row(conn, 2)

        # Magnet row (ICE only: Cryomagnetics MPS4G over COM). The magnet
        # query is slow, so the field is documented once after each
        # completed sweep (like the gate info columns).
        self.magnet.build_connection_row(conn, 3)

        btns = ttk.Frame(conn)
        btns.grid(row=4, column=0, columnspan=6, pady=5)
        ttk.Button(btns, text="Scan Instruments", command=self.refresh_instruments).pack(side="left", padx=10)
        ttk.Button(btns, text="Refresh Status", command=self.refresh_all_status).pack(side="left", padx=10)

        # === 2. GATE SOURCES + ENVIRONMENT (Gate 1 | Gate 2 | Field & Temp) ===
        gates = ttk.LabelFrame(instruments,
                               text="Gate sources & environment", padding=6)
        gates.pack(fill="x", pady=5)
        holder = ttk.Frame(gates)
        holder.pack(fill="x")
        # Two gate cards share the width, environment readouts sit below.
        self.gates[0].build_config_panel(holder)
        self.gates[1].build_config_panel(holder)
        self._build_environment_panel(gates)

        # === 3. MEASUREMENT TYPE ===
        typ = ttk.LabelFrame(sweep_setup, text="Measurement mode", padding=7)
        typ.pack(fill="x", pady=5)
        self.sweep_type_var = tk.StringVar(value="iv")
        inner = ttk.Frame(typ)
        inner.pack()
        ttk.Radiobutton(inner, text="IV Sweep (Source Voltage, Measure Current)",
                        variable=self.sweep_type_var, value="iv",
                        command=self._update_ui_labels).pack(anchor="w")
        ttk.Radiobutton(inner, text="VI Sweep (Source Current, Measure Voltage)",
                        variable=self.sweep_type_var, value="vi",
                        command=self._update_ui_labels).pack(anchor="w")

        # === 4. BIAS SWEEP CONFIG ===
        cfgf = ttk.LabelFrame(sweep_setup, text="Bias sweep", padding=7)
        cfgf.pack(fill="x", pady=5)
        for c in range(8):
            cfgf.columnconfigure(c, weight=1)

        ttk.Label(cfgf, text="Sp1:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.ent_sp1 = ttk.Entry(cfgf, width=13)
        self.ent_sp1.grid(row=0, column=1, padx=5, sticky="ew")
        self.lbl_sp1_unit = ttk.Label(cfgf, text="mV")
        self.lbl_sp1_unit.grid(row=0, column=2, sticky="w")

        ttk.Label(cfgf, text="Sp2:").grid(row=0, column=3, padx=5, pady=2, sticky="e")
        self.ent_sp2 = ttk.Entry(cfgf, width=13)
        self.ent_sp2.grid(row=0, column=4, padx=5, sticky="ew")
        self.lbl_sp2_unit = ttk.Label(cfgf, text="mV")
        self.lbl_sp2_unit.grid(row=0, column=5, sticky="w")

        ttk.Label(cfgf, text="Step:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.ent_step = ttk.Entry(cfgf, width=13)
        self.ent_step.grid(row=1, column=1, padx=5, sticky="ew")
        self.lbl_step_unit = ttk.Label(cfgf, text="mV")
        self.lbl_step_unit.grid(row=1, column=2, sticky="w")

        ttk.Label(cfgf, text="Delay (s):").grid(row=1, column=3, padx=5, pady=2, sticky="e")
        self.ent_delay = ttk.Entry(cfgf, width=13)
        self.ent_delay.grid(row=1, column=4, padx=5, sticky="ew")

        self.lbl_compliance = ttk.Label(cfgf, text="Compliance (A):")
        self.lbl_compliance.grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.ent_compliance = ttk.Entry(cfgf, width=13)
        self.ent_compliance.grid(row=2, column=1, padx=5, sticky="ew")

        ttk.Label(cfgf, text="Bias NPLC:").grid(row=2, column=3, padx=5, pady=2, sticky="e")
        self.ent_bias_nplc = ttk.Entry(cfgf, width=13)
        self.ent_bias_nplc.insert(0, self.saved_params['bias_nplc'])
        self.ent_bias_nplc.grid(row=2, column=4, padx=5, sticky="ew")

        # === 5. GATE LOOP CONFIG ===
        loop = ttk.LabelFrame(sweep_setup, text="Gate sweep / mapping", padding=7)
        loop.pack(fill="x", pady=5)

        self.loop_mode_var = tk.StringVar(value="none")
        mf = ttk.Frame(loop)
        mf.pack(fill="x")
        for i, (val, txt) in enumerate((("none", "Bias only"),
                         ("gate1", "Gate 1 loop"),
                         ("gate2", "Gate 2 loop"),
                         ("dual", "Dual gate 2D map"),
                         ("movement", "Dual gate movement"))):
            ttk.Radiobutton(mf, text=txt, variable=self.loop_mode_var, value=val,
                            command=self._toggle_loop_entries).grid(
                                row=i // 2, column=i % 2, sticky="w",
                                padx=(2, 24), pady=2)

        rf = ttk.Frame(loop)
        rf.pack(fill="x", pady=(6, 0))

        # nesting order for the dual gate 2D loop (which gate is the outer loop)
        of = ttk.Frame(loop)
        of.pack(fill="x", pady=(2, 0))
        ttk.Label(of, text="Dual 2D nesting order:").pack(side="left")
        self.dual_outer_var = tk.StringVar(value="1")
        self.rb_dual_outer1 = ttk.Radiobutton(of, text="G1 outer / G2 inner",
                                              variable=self.dual_outer_var, value="1")
        self.rb_dual_outer1.pack(side="left", padx=8)
        self.rb_dual_outer2 = ttk.Radiobutton(of, text="G2 outer / G1 inner",
                                              variable=self.dual_outer_var, value="2")
        self.rb_dual_outer2.pack(side="left", padx=8)

        g1f = ttk.Frame(rf)
        g1f.pack(anchor="w", pady=2)
        ttk.Label(g1f, text="Gate 1:").pack(side="left")
        ttk.Label(g1f, text="Start (V):").pack(side="left", padx=(8, 0))
        self.ent_g1_start = ttk.Entry(g1f, width=8)
        self.ent_g1_start.insert(0, self.saved_params['g1_start'])
        self.ent_g1_start.pack(side="left", padx=2)
        ttk.Label(g1f, text="End (V):").pack(side="left", padx=(8, 0))
        self.ent_g1_end = ttk.Entry(g1f, width=8)
        self.ent_g1_end.insert(0, self.saved_params['g1_end'])
        self.ent_g1_end.pack(side="left", padx=2)
        ttk.Label(g1f, text="Step (V):").pack(side="left", padx=(8, 0))
        self.ent_g1_loop_step = ttk.Entry(g1f, width=8)
        self.ent_g1_loop_step.insert(0, self.saved_params['g1_loop_step'])
        self.ent_g1_loop_step.pack(side="left", padx=2)

        g2f = ttk.Frame(rf)
        g2f.pack(anchor="w", pady=2)
        ttk.Label(g2f, text="Gate 2:").pack(side="left")
        ttk.Label(g2f, text="Start (V):").pack(side="left", padx=(8, 0))
        self.ent_g2_start = ttk.Entry(g2f, width=8)
        self.ent_g2_start.insert(0, self.saved_params['g2_start'])
        self.ent_g2_start.pack(side="left", padx=2)
        ttk.Label(g2f, text="End (V):").pack(side="left", padx=(8, 0))
        self.ent_g2_end = ttk.Entry(g2f, width=8)
        self.ent_g2_end.insert(0, self.saved_params['g2_end'])
        self.ent_g2_end.pack(side="left", padx=2)
        ttk.Label(g2f, text="Step (V):").pack(side="left", padx=(8, 0))
        self.ent_g2_loop_step = ttk.Entry(g2f, width=8)
        self.ent_g2_loop_step.insert(0, self.saved_params['g2_loop_step'])
        self.ent_g2_loop_step.pack(side="left", padx=2)

        # shared settle + dedicated ramp parameters for gate movement in the loop
        sf = ttk.Frame(loop)
        sf.pack(fill="x", pady=(6, 0))
        ttk.Label(sf, text="Settle (s):").pack(side="left")
        self.ent_gate_settle = ttk.Entry(sf, width=6)
        self.ent_gate_settle.insert(0, self.saved_params['gate_settle'])
        self.ent_gate_settle.pack(side="left", padx=3)
        ttk.Label(sf, text="Ramp Step (mV):").pack(side="left", padx=(20, 0))
        self.ent_loop_ramp_step = ttk.Entry(sf, width=7)
        self.ent_loop_ramp_step.insert(0, self.saved_params['loop_ramp_step'])
        self.ent_loop_ramp_step.pack(side="left", padx=3)
        ttk.Label(sf, text="Ramp Delay (s):").pack(side="left", padx=(20, 0))
        self.ent_loop_ramp_delay = ttk.Entry(sf, width=7)
        self.ent_loop_ramp_delay.insert(0, self.saved_params['loop_ramp_delay'])
        self.ent_loop_ramp_delay.pack(side="left", padx=3)
        # common point count for the dual gate movement loop (disabled otherwise)
        # — own row so the writing is not cut next to the docked log
        sf2 = ttk.Frame(loop)
        sf2.pack(fill="x", pady=(2, 0))
        ttk.Label(sf2, text="Points:").pack(side="left")
        self.ent_loop_points = ttk.Entry(sf2, width=6)
        self.ent_loop_points.insert(0, self.saved_params['loop_points'])
        self.ent_loop_points.pack(side="left", padx=3)
        self.lbl_loop_points = ttk.Label(sf2, text="1 bias sweep",
                                         font=("Arial", 9, "bold"))
        self.lbl_loop_points.pack(side="left", padx=25)

        # plain-sweep (bias-only) options: the sweep NEVER drives the gates —
        # gate voltages are set manually in section 2 (Ramp Gate). These
        # checkboxes only select which gate voltages are DOCUMENTED in the
        # file (one true voltage measurement per sweep, if connected).
        af = ttk.Frame(loop)
        af.pack(fill="x", pady=(6, 0))
        ttk.Label(af, text="Plain sweep:").pack(side="left")
        self.rec_g1_var = tk.BooleanVar(value=False)
        self.chk_rec_g1 = ttk.Checkbutton(
            af, text="Record Gate 1 voltage column (gate not driven)",
            variable=self.rec_g1_var)
        self.chk_rec_g1.pack(side="left", padx=8)
        af2 = ttk.Frame(loop)
        af2.pack(fill="x", pady=(2, 0))
        self.rec_g2_var = tk.BooleanVar(value=False)
        self.chk_rec_g2 = ttk.Checkbutton(
            af2, text="Record Gate 2 voltage column (gate not driven)",
            variable=self.rec_g2_var)
        self.chk_rec_g2.pack(side="left", padx=8)

        # Newer ICE revision: independent readback of the non-swept gate in
        # single-gate loops. Keep this option on a separate row for laptops.
        held_row = ttk.Frame(loop)
        held_row.pack(fill="x", pady=(2, 0))
        self.held_readback_var = tk.BooleanVar(value=False)
        self.chk_held_readback = ttk.Checkbutton(
            held_row, text="Single-gate loops: record held-gate voltage readback (V)",
            variable=self.held_readback_var)
        self.chk_held_readback.pack(side="left", padx=8)

        # Returning the gates to 0 V after a gate loop is a user choice,
        # not a program default (the field return lives in the Magnet tab).
        # Own row so the text is not cut next to the docked log.
        held_row2 = ttk.Frame(loop)
        held_row2.pack(fill="x", pady=(2, 0))
        self.return_gates_var = tk.BooleanVar(value=False)
        self.chk_return_gates = ttk.Checkbutton(
            held_row2, text="Return gates to 0 V after loop",
            variable=self.return_gates_var)
        self.chk_return_gates.pack(side="left", padx=8)

        for e in (self.ent_g1_start, self.ent_g1_end, self.ent_g1_loop_step,
                  self.ent_g2_start, self.ent_g2_end, self.ent_g2_loop_step,
                  self.ent_loop_points):
            e.bind('<KeyRelease>', lambda ev: self._update_loop_points_label())

        # === 6. SAVE + EXECUTION ===
        ex = ttk.LabelFrame(self.main_frame, text="Save & execute", padding=7)
        ex.pack(fill="x", pady=(1, 0))
        row0 = ttk.Frame(ex)
        row0.pack(fill="x")
        ttk.Label(row0, text="Save Directory:").pack(side="left", padx=5)
        self.ent_dir = ttk.Entry(row0)
        self.ent_dir.insert(0, self.saved_params['save_dir'])
        self.ent_dir.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(row0, text="Browse...", command=self.browse_directory).pack(side="left", padx=5)

        row1 = ttk.Frame(ex)
        row1.pack(pady=4)
        self.btn_run = tk.Button(row1, text="RUN SWEEP", command=self.start_sweep,
                                 width=15, bg=COLORS["run"], fg=COLORS["action_text"],
                                 activebackground=COLORS["run_hover"],
                                 activeforeground=COLORS["action_text"],
                                 font=("Segoe UI", 10, "bold"),
                                 relief="flat", bd=0, padx=10, pady=6, cursor="hand2")
        self.btn_run.pack(side="left", padx=8)
        self.btn_abort = tk.Button(row1, text="ABORT", command=self.abort_sweep,
                                   width=10, bg=COLORS["abort"], fg=COLORS["action_text"],
                                   activebackground=COLORS["abort_hover"],
                                   activeforeground=COLORS["action_text"],
                                   font=("Segoe UI", 10, "bold"),
                                   relief="flat", bd=0, padx=10, pady=6, cursor="hand2",
                                   state="disabled")
        self.btn_abort.pack(side="left", padx=8)
        self.lbl_progress = ttk.Label(row1, text="Ready",
                                      font=("Segoe UI", 10, "bold"))
        self.lbl_progress.pack(side="left", padx=10)

        # === LOG (docked right, always visible; divider is draggable) ===
        logf = ttk.LabelFrame(body, text="Instrument & measurement messages", padding=8)
        body.add(logf, weight=0)
        self.log_text = tk.Text(logf, height=8, width=42, wrap="word",
                                state="disabled",
                                bg=COLORS["log_background"], fg=COLORS["log_text"],
                                insertbackground=COLORS["log_cursor"],
                                selectbackground=COLORS["log_selection"],
                                font=("Consolas", 9), relief="flat",
                                padx=8, pady=6)
        self.log_text.pack(fill="both", expand=True)

        # === 7. MAGNET CONTROL + FIELD LOOP (own tab, ICE only) ===
        mtab = self._scrollable_tab("Magnet control")
        # sequence tab last (right-most): Instruments, Sweep setup, Magnet
        # control, Sequence
        sequence_tab = self._scrollable_tab("Sequence")

        mctl = ttk.LabelFrame(mtab, text="Magnet control (manual)", padding=7)
        mctl.pack(fill="x", pady=5)
        rowm = ttk.Frame(mctl)
        rowm.pack(fill="x")
        ttk.Label(rowm, text="Sweep rate (T/min):").pack(side="left")
        self.ent_mag_rate = ttk.Entry(rowm, width=8)
        self.ent_mag_rate.insert(0, self.saved_params['mag_rate'])
        self.ent_mag_rate.pack(side="left", padx=3)
        ttk.Label(rowm, text="Target field (T):").pack(side="left", padx=(20, 0))
        self.ent_mag_target = ttk.Entry(rowm, width=8)
        self.ent_mag_target.insert(0, self.saved_params['mag_target'])
        self.ent_mag_target.pack(side="left", padx=3)
        # buttons on their own row so nothing is cut next to the docked log
        rowm2 = ttk.Frame(mctl)
        rowm2.pack(fill="x", pady=(4, 0))
        self.btn_mag_go = ttk.Button(rowm2, text="Go to target",
                                     command=self.start_manual_field_ramp)
        self.btn_mag_go.pack(side="left")
        ttk.Button(rowm2, text="Safety limits...",
                   command=self.magnet.open_safety_dialog).pack(side="left", padx=6)
        self.lbl_mag_status = ttk.Label(mctl, text="B: --- T",
                                        font=("Consolas", 9))
        self.lbl_mag_status.pack(anchor="w", pady=(4, 0))
        ttk.Label(mctl, text="The rate is applied to every range, clamped to the "
                             "per-range safety limits ('Safety limits...' button "
                             "or the dialog shown at connect).\n"
                             "ABORT stops the ramp (field left where it is).",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        flo = ttk.LabelFrame(mtab, text="Field loop (bias sweep at each field)",
                             padding=7)
        flo.pack(fill="x", pady=5)
        self.rb_field_loop = ttk.Radiobutton(
            flo, text="Field loop (bias vs B): run one bias sweep at every "
                      "field point\nbelow (overrides the Sweep setup loop mode)",
            variable=self.loop_mode_var, value="field",
            command=self._toggle_loop_entries)
        self.rb_field_loop.pack(anchor="w", pady=(0, 4))
        rowf = ttk.Frame(flo)
        rowf.pack(fill="x")
        ttk.Label(rowf, text="Start (T):").pack(side="left")
        self.ent_field_start = ttk.Entry(rowf, width=8)
        self.ent_field_start.insert(0, self.saved_params['field_start'])
        self.ent_field_start.pack(side="left", padx=2)
        ttk.Label(rowf, text="End (T):").pack(side="left", padx=(14, 0))
        self.ent_field_end = ttk.Entry(rowf, width=8)
        self.ent_field_end.insert(0, self.saved_params['field_end'])
        self.ent_field_end.pack(side="left", padx=2)
        ttk.Label(rowf, text="Step (T):").pack(side="left", padx=(14, 0))
        self.ent_field_step = ttk.Entry(rowf, width=8)
        self.ent_field_step.insert(0, self.saved_params['field_step'])
        self.ent_field_step.pack(side="left", padx=2)
        rowf2 = ttk.Frame(flo)
        rowf2.pack(fill="x", pady=(4, 0))
        ttk.Label(rowf2, text="Sweep rate (T/min):").pack(side="left")
        self.ent_field_rate = ttk.Entry(rowf2, width=8)
        self.ent_field_rate.insert(0, self.saved_params['field_rate'])
        self.ent_field_rate.pack(side="left", padx=3)
        self.lbl_field_points = ttk.Label(rowf2, text="",
                                          font=("Arial", 9, "bold"))
        self.lbl_field_points.pack(side="left", padx=25)
        # return-to-0 for the FIELD is configured here, next to the field loop
        self.return_field_var = tk.BooleanVar(value=False)
        self.chk_return_field = ttk.Checkbutton(
            flo, text="Return field to 0 T after loop",
            variable=self.return_field_var)
        self.chk_return_field.pack(anchor="w", pady=(4, 0))
        ttk.Label(flo, text="Forward sweep from Start to End. The field is swept "
                            "back to 0 T\nafter the loop only when 'Return field "
                            "to 0 T after loop' above is checked.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        for e in (self.ent_field_start, self.ent_field_end,
                  self.ent_field_step, self.ent_field_rate):
            e.bind('<KeyRelease>', lambda ev: self._update_loop_points_label())

        # === 8. SEQUENCE (JSON step list; GUI values are the defaults) ===
        sq = ttk.LabelFrame(sequence_tab, text="Measurement sequence", padding=7)
        sq.pack(fill="both", expand=True, pady=5)
        sqrow = ttk.Frame(sq)
        sqrow.pack(fill="x")
        ttk.Button(sqrow, text="Load sequence...",
                   command=self.load_sequence_file).pack(side="left")
        self.btn_seq_run = tk.Button(sqrow, text="RUN SEQUENCE",
                                     command=self.run_sequence, width=15,
                                     bg=COLORS["run"], fg=COLORS["action_text"],
                                     activebackground=COLORS["run_hover"],
                                     activeforeground=COLORS["action_text"],
                                     font=("Segoe UI", 10, "bold"),
                                     relief="flat", bd=0, padx=10, pady=4,
                                     cursor="hand2")
        self.btn_seq_run.pack(side="left", padx=12)
        self.lbl_seq_total = ttk.Label(sqrow, text="no sequence loaded",
                                       font=("Segoe UI", 10, "bold"))
        self.lbl_seq_total.pack(side="left", padx=10)
        self.lbl_seq_path = ttk.Label(sq, text="File: ---", style="Muted.TLabel")
        self.lbl_seq_path.pack(anchor="w", pady=(4, 0))

        # step editor: build sequences without writing JSON by hand.
        # 'Capture GUI' snapshots the current Sweep setup as one step.
        ops = ttk.Frame(sq)
        ops.pack(fill="x", pady=(4, 0))
        ttk.Button(ops, text="Add step...",
                   command=lambda: self.seq_edit_step(-1)).pack(side="left")
        ttk.Button(ops, text="Capture GUI",
                   command=self.seq_capture_gui).pack(side="left", padx=4)
        ttk.Button(ops, text="Edit...",
                   command=lambda: self.seq_edit_step(None)).pack(side="left")
        ttk.Button(ops, text="Delete",
                   command=self.seq_delete_step).pack(side="left", padx=4)
        ttk.Button(ops, text="Clear all",
                   command=self.seq_clear_all).pack(side="left")
        ttk.Button(ops, text="Up",
                   command=lambda: self.seq_move_step(-1)).pack(side="left")
        ttk.Button(ops, text="Down",
                   command=lambda: self.seq_move_step(1)).pack(side="left", padx=4)
        ttk.Button(ops, text="Save as...",
                   command=self.seq_save_file).pack(side="left", padx=(16, 0))
        ttk.Button(ops, text="Help / examples",
                   command=self.seq_help).pack(side="left", padx=4)

        treef = ttk.Frame(sq)
        treef.pack(fill="both", expand=True, pady=(4, 0))
        cols = ("idx", "name", "type", "mode", "bias", "gates", "field", "repeat")
        self.seq_tree = ttk.Treeview(treef, columns=cols, show="headings",
                                     height=10, selectmode="extended")
        headings = {"idx": "#", "name": "Name", "type": "Type", "mode": "Loop mode",
                    "bias": "Bias (sp1..sp2/step)", "gates": "Gates",
                    "field": "Field (T)", "repeat": "Repeat"}
        widths = {"idx": 34, "name": 170, "type": 60, "mode": 90,
                  "bias": 150, "gates": 190, "field": 130, "repeat": 60}
        for c in cols:
            self.seq_tree.heading(c, text=headings[c])
            self.seq_tree.column(c, width=widths[c], anchor="w",
                                 stretch=(c in ("name", "bias", "gates")))
        seqbar = ttk.Scrollbar(treef, orient="vertical", command=self.seq_tree.yview)
        self.seq_tree.configure(yscrollcommand=seqbar.set)
        seqbar.pack(side="right", fill="y")
        self.seq_tree.pack(side="left", fill="both", expand=True)
        # double-click a row to edit that step
        self.seq_tree.bind("<Double-1>",
                           lambda e: self.seq_edit_step(None))
        # Delete key removes the selected step(s)
        self.seq_tree.bind("<Delete>",
                           lambda e: self.seq_delete_step())
        ttk.Label(sq, text="Each step overrides the current Sweep setup values "
                           "(missing keys = GUI values). Keys: name, type "
                           "(sweep/wait), repeat, save_subdir, mode, sweep_type,\n"
                           "bias {sp1,sp2,step,delay,compliance}, gates {g1/g2 "
                           "{start,end,step,compliance,nplc,target}}, field "
                           "{start,end,step,rate}, settle, loop_ramp_step (mV),\n"
                           "loop_ramp_delay, points (movement), dual_outer, "
                           "doc_field, doc_temp, held_readback, record_gates, "
                           "return_gates, return_field. '#' comments allowed.",
                  style="Muted.TLabel", justify="left").pack(anchor="w", pady=(6, 0))

        self._update_ui_labels()
        self._toggle_loop_entries()

    def _scrollable_tab(self, title):
        """Scrollable tab (vertical + horizontal); still usable at 1366x768
        and high DPI. The frame stretches to the canvas width when the window
        is wide enough, and scrolls sideways when the content is wider."""
        outer = ttk.Frame(self.tabs)
        self.tabs.add(outer, text=f"  {title}  ")
        canvas = tk.Canvas(outer, bg=COLORS["canvas"], highlightthickness=0,
                           borderwidth=0)
        self._tab_canvases.append(canvas)  # recolored by apply_theme
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=(6, 6, 8, 8))
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        def on_canvas_config(e):
            # stretch the frame to the canvas size ONLY when the content is
            # smaller; leave natural size otherwise so BOTH scrollbars work
            # (forcing height would clip tall content and kill vertical scroll)
            if body.winfo_reqwidth() <= e.width:
                canvas.itemconfigure(window, width=e.width)
            if body.winfo_reqheight() <= e.height:
                canvas.itemconfigure(window, height=e.height)
        canvas.bind("<Configure>", on_canvas_config)

        # Windows uses delta increments of 120; scroll only over this tab.
        # Shift+wheel pans horizontally (same direction as vertical scroll).
        def wheel(event):
            if getattr(event, "state", 0) & 0x0001:  # Shift held
                canvas.xview_scroll(-int(event.delta / 120) if event.delta else 0,
                                    "units")
            else:
                canvas.yview_scroll(
                    -int(event.delta / 120) if event.delta else 0, "units")
        def bind_wheel(widget):
            widget.bind("<MouseWheel>", wheel, add="+")
            for child in widget.winfo_children():
                bind_wheel(child)
        # Mouse wheel on blank tab area (and on the canvas). The scrollbar
        # also works for controls not caught by the wheel binding.
        canvas.bind("<MouseWheel>", wheel)
        outer.bind("<MouseWheel>", wheel)
        return body

    def _setup_style(self):
        """Build every ttk style from the COLORS palette at the top of this file."""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        c = COLORS
        self.root.configure(bg=c["background"])
        style.configure(".", font=("Segoe UI", 9), background=c["background"],
                        foreground=c["text"])
        style.configure("TFrame", background=c["background"])
        style.configure("TLabelframe", background=c["surface"], borderwidth=1,
                        bordercolor=c["border"], relief="solid")
        style.configure("TLabelframe.Label", background=c["background"],
                        font=("Segoe UI Semibold", 10), foreground=c["accent"])
        style.configure("TLabel", background=c["background"], foreground=c["text"])
        style.configure("Muted.TLabel", background=c["background"],
                        foreground=c["muted_text"])
        style.configure("TButton", padding=(8, 4), background=c["button"],
                        foreground=c["text"], bordercolor=c["border"])
        style.map("TButton", background=[("active", c["button_hover"])])
        style.configure("TCheckbutton", padding=2, background=c["background"])
        style.configure("TRadiobutton", padding=2, background=c["background"])
        # clam's built-in hover state is a hardcoded near-white flash
        # (#eeebe7); map it to the palette so dark mode does not blink
        style.map("TCheckbutton", background=[("active", c["button_hover"])])
        style.map("TRadiobutton", background=[("active", c["button_hover"])])
        # sequence step table (Treeview) follows the palette too
        style.configure("Treeview", background=c["surface"],
                        foreground=c["text"], fieldbackground=c["surface"],
                        rowheight=22, bordercolor=c["border"])
        style.configure("Treeview.Heading", background=c["button"],
                        foreground=c["text"], font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", c["log_selection"])])
        style.map("Treeview.Heading", background=[("active", c["button_hover"])])
        style.configure("TCombobox", padding=2)
        style.configure("TEntry", padding=3)
        # input fields get EXPLICIT field/text colors: without this the
        # entries inherit the theme foreground (light in dark mode) over
        # the default white field background -> unreadable text
        style.configure("TEntry", fieldbackground=c["field"],
                        foreground=c["text"], insertcolor=c["text"])
        style.configure("TCombobox", fieldbackground=c["field"],
                        foreground=c["text"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", c["field"])],
                  foreground=[("readonly", c["text"])])
        style.configure("TNotebook", background=c["background"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7),
                        background=c["tab_inactive"],
                        foreground=c["tab_inactive_text"])
        style.map("TNotebook.Tab",
                  background=[("selected", c["surface"])],
                  foreground=[("selected", c["accent"])])
        # visible grab handle between the tab area and the docked log
        style.configure("TPanedwindow", background=c["border"])
        style.configure("Sash", sashthickness=6, background=c["border"])

    def _build_environment_panel(self, parent):
        """Field & temperature documentation panel, next to the gate panels.

        Field and temperature are independent slow readings, so each gets
        its own toggle (field needs the magnet; temperature needs ICElog).
        """
        box = ttk.LabelFrame(parent, text="Field & Temperature (ICE)", padding=5)
        self.doc_field_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Record field each sweep",
                        variable=self.doc_field_var).pack(anchor="w", pady=1)
        self.doc_temp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Record temperature each sweep",
                        variable=self.doc_temp_var).pack(anchor="w", pady=1)
        btns = ttk.Frame(box)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Read Field",
                   command=self.magnet.read_field_button).pack(
            side="left", padx=2)
        ttk.Button(btns, text="Read Temp",
                   command=self.read_temperature_once).pack(
            side="left", padx=2)
        self.lbl_env_status = ttk.Label(box, text="B: ---  |  T: ---",
                                        font=("Consolas", 9))
        self.lbl_env_status.pack(anchor="w", pady=(4, 0))
        # stacked full-width below the two gate cards (small-screen layout)
        box.pack(fill="x", pady=2, padx=2)

    def _update_env_label(self):
        """Refresh the small B/T readout in the environment panel."""
        b_str = (f"{self._env_field:.4f} T" if self._env_field is not None
                 else "---")
        t_str = (" / ".join(f"{v:.2f}" for v in self._env_temps) + " K"
                 if self._env_temps is not None else "---")
        self.lbl_env_status.config(text=f"B: {b_str}  |  T: {t_str}")

    # ==================== LOOP HELPERS ====================

    def loop_uses_gate(self, idx):
        mode = self.loop_mode_var.get()
        return (mode in ("dual", "movement")
                or (mode == "gate1" and idx == 1)
                or (mode == "gate2" and idx == 2))

    def loop_range_entries(self, idx):
        if idx == 1:
            return (self.ent_g1_start, self.ent_g1_end)
        return (self.ent_g2_start, self.ent_g2_end)

    def other_channel(self, idx):
        return self.gates[1] if idx == 1 else self.gates[0]

    def _toggle_loop_entries(self):
        mode = self.loop_mode_var.get()
        state1 = "normal" if mode in ("gate1", "dual", "movement") else "disabled"
        state2 = "normal" if mode in ("gate2", "dual", "movement") else "disabled"
        state_shared = "normal" if mode not in ("none", "field") else "disabled"
        for e in (self.ent_g1_start, self.ent_g1_end, self.ent_g1_loop_step):
            e.config(state=state1)
        for e in (self.ent_g2_start, self.ent_g2_end, self.ent_g2_loop_step):
            e.config(state=state2)
        if mode == "movement":
            # movement mode: both gates share one common point count (linspace);
            # per-gate steps are meaningless there
            self.ent_g1_loop_step.config(state="disabled")
            self.ent_g2_loop_step.config(state="disabled")
        # common point count only used by the dual gate movement loop
        self.ent_loop_points.config(
            state="normal" if mode == "movement" else "disabled")
        for e in (self.ent_gate_settle, self.ent_loop_ramp_step, self.ent_loop_ramp_delay):
            e.config(state=state_shared)
        # field loop entries live in the Magnet control tab
        state_f = "normal" if mode == "field" else "disabled"
        for e in (self.ent_field_start, self.ent_field_end,
                  self.ent_field_step, self.ent_field_rate):
            e.config(state=state_f)
        # nesting order only relevant for the dual 2D loop
        order_state = "normal" if mode == "dual" else "disabled"
        self.rb_dual_outer1.config(state=order_state)
        self.rb_dual_outer2.config(state=order_state)

        # 'record gate voltage' checkboxes only relevant without a gate loop
        # (in loop modes both gate columns are always written)
        rec_state = "normal" if mode == "none" else "disabled"
        self.chk_rec_g1.config(state=rec_state)
        self.chk_rec_g2.config(state=rec_state)
        # held-gate readback only meaningful in single-gate loop modes
        # (in dual/movement loops both gates are already recorded)
        held_state = "normal" if mode in ("gate1", "gate2") else "disabled"
        self.chk_held_readback.config(state=held_state)
        # separate return-to-0 options: gates here, field in the Magnet tab
        self.chk_return_gates.config(
            state="normal" if mode not in ("none", "field") else "disabled")
        self.chk_return_field.config(
            state="normal" if mode == "field" else "disabled")
        for gi, var in ((1, self.rec_g1_var), (2, self.rec_g2_var)):
            if mode == "none" and var.get() and self.gates[gi - 1].inst is None:
                self.log(f"Note: 'Record Gate {gi} voltage' is checked but "
                         f"Gate {gi} is not connected")

        need = {"gate1": [1], "gate2": [2], "dual": [1, 2], "movement": [1, 2]}.get(mode, [])
        missing = [gi for gi in need if self.gates[gi - 1].inst is None]
        if missing:
            self.log("Note: loop requires "
                     + ", ".join(f"Gate {gi}" for gi in missing) + " to be connected")
        self._update_loop_points_label()

    def _update_loop_points_label(self):
        mode = self.loop_mode_var.get()
        try:
            if mode in ("gate1", "dual"):
                n1 = len(arange_inclusive(float(self.ent_g1_start.get()),
                                          float(self.ent_g1_end.get()),
                                          abs(float(self.ent_g1_loop_step.get()))))
            if mode in ("gate2", "dual"):
                n2 = len(arange_inclusive(float(self.ent_g2_start.get()),
                                          float(self.ent_g2_end.get()),
                                          abs(float(self.ent_g2_loop_step.get()))))
            if mode == "none":
                text = "1 bias sweep"
            elif mode == "gate1":
                text = f"{n1} bias sweeps"
            elif mode == "gate2":
                text = f"{n2} bias sweeps"
            elif mode == "dual":
                outer = "G1" if self.dual_outer_var.get() == "1" else "G2"
                inner = "G2" if outer == "G1" else "G1"
                text = f"{n1} x {n2} = {n1 * n2} bias sweeps ({outer} outer, {inner} inner)"
            elif mode == "field":
                nf = len(arange_inclusive(float(self.ent_field_start.get()),
                                          float(self.ent_field_end.get()),
                                          abs(float(self.ent_field_step.get()))))
                text = f"{nf} bias sweeps (field loop)"
            else:  # movement: one common point count for both gates
                n = int(float(self.ent_loop_points.get()))
                text = f"{n} bias sweeps (both gates move together)"
        except ValueError:
            text = "---"
        self.lbl_loop_points.config(text=text)
        if hasattr(self, 'lbl_field_points'):
            self.lbl_field_points.config(text=text)

    def _update_ui_labels(self):
        st = self.sweep_type_var.get()
        if st == "iv":
            self.lbl_compliance.config(text="Compliance (A):")
            for l in (self.lbl_sp1_unit, self.lbl_sp2_unit, self.lbl_step_unit):
                l.config(text="mV")
            vals = ['iv_sp1', 'iv_sp2', 'iv_step', 'iv_delay', 'iv_compliance']
        else:
            self.lbl_compliance.config(text="Compliance (V):")
            for l in (self.lbl_sp1_unit, self.lbl_sp2_unit, self.lbl_step_unit):
                l.config(text="A")
            vals = ['vi_sp1', 'vi_sp2', 'vi_step', 'vi_delay', 'vi_compliance']
        entries = [self.ent_sp1, self.ent_sp2, self.ent_step, self.ent_delay, self.ent_compliance]
        for e, key in zip(entries, vals):
            e.delete(0, tk.END)
            e.insert(0, self.saved_params[key])

    def log(self, message):
        self.root.after(0, self._log_internal, message)

    def _log_internal(self, message):
        stamp = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _progress(self, text):
        self.root.after(0, lambda: self.lbl_progress.config(text=text))

    def set_busy(self):
        """Shared busy state for manual gate ramps and sweeps."""
        self.btn_run.config(state="disabled")
        self.btn_abort.config(state="normal")
        for ch in self.gates:
            ch.btn_ramp.config(state="disabled")
        self.stop_event.clear()

    # ==================== CONNECTION ====================

    def refresh_instruments(self):
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
            self.bias_combo['values'] = resources
            for ch in self.gates:
                ch.addr_combo['values'] = resources
            if resources:
                self.log(f"Found {len(resources)} instrument(s)")
            else:
                self.log("No instruments found")
        except Exception as e:
            self.log(f"Scan error: {e}")
        # COM ports for the magnet (ICE only)
        try:
            if list_ports is not None:
                ports = [p.device for p in list_ports.comports()]
                self.magnet.combo['values'] = ports
                if ports and not self.magnet.combo.get().strip():
                    self.magnet.combo.set(ports[0])
                self.log(f"Found {len(ports)} COM port(s)")
        except Exception as e:
            self.log(f"COM port scan error: {e}")

    def connect_bias(self):
        addr = self.bias_combo.get()
        if not addr:
            messagebox.showerror("Error", "No bias address selected")
            return
        try:
            self.bias_inst = Keithley2450(addr)
            if hasattr(self.bias_inst, 'adapter'):
                self.bias_inst.adapter.connection.timeout = 10000
                self.bias_inst.adapter.connection.read_termination = '\n'
                self.bias_inst.adapter.connection.write_termination = '\n'
            self.log(f"Bias (Keithley 2450) connected: {addr}")
            self.update_bias_status()
        except Exception as e:
            self.bias_inst = None
            messagebox.showerror("Connection Error", f"Failed to connect bias:\n{e}")
            self.log(f"Bias connection failed: {e}")

    def disconnect_bias(self):
        if self.bias_inst:
            # NOTE: output intentionally left in its current state —
            # closing the program does not mean the experiment is over.
            try:
                on = self.bias_inst.source_enabled
                self.log(f"Bias disconnected (output left {'ON' if on else 'OFF'})")
            except Exception:
                self.log("Bias disconnected")
            try:
                self.bias_inst.adapter.connection.close()
            except Exception:
                pass
            self.bias_inst = None

    def toggle_bias_terminals(self):
        if not self.bias_inst:
            return
        try:
            if "FRON" in self.bias_inst.check_terminals():
                self.bias_inst.use_rear_terminals()
            else:
                self.bias_inst.use_front_terminals()
            time.sleep(0.2)
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias terminal error: {e}")

    def toggle_bias_output(self):
        if not self.bias_inst:
            return
        try:
            if self.bias_inst.source_enabled:
                self.bias_inst.disable_source()
                self.log("Bias output OFF")
            else:
                self.bias_inst.enable_source()
                self.log("Bias output ON")
            time.sleep(0.1)
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias output error: {e}")

    def reset_bias(self):
        if not self.bias_inst:
            return
        try:
            self.bias_inst.reset()
            self.log("Bias reset")
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias reset error: {e}")

    def update_bias_status(self):
        if not self.bias_inst:
            self.btn_bias_term.config(text="Term: ---", bg=COLORS["status_neutral"])
            self.btn_bias_out.config(text="Out: ---", bg=COLORS["status_neutral"])
            return
        try:
            term = self.bias_inst.check_terminals()
            self.btn_bias_term.config(text="Term: FRONT" if "FRON" in term else "Term: REAR",
                                      bg=COLORS["status_on"] if "FRON" in term else COLORS["status_rear"])
        except Exception:
            self.btn_bias_term.config(text="Term: ???", bg=COLORS["status_error"])
        try:
            on = self.bias_inst.source_enabled
            self.btn_bias_out.config(text="Out: ON" if on else "Out: OFF",
                                     bg=COLORS["status_on"] if on else COLORS["status_off"])
        except Exception:
            self.btn_bias_out.config(text="Out: ???", bg=COLORS["status_error"])

    def refresh_all_status(self):
        self.update_bias_status()
        for ch in self.gates:
            ch.update_status()
        if self.magnet.inst is not None:
            self.magnet.read_field()  # slow (~0.5 s) but this is a manual button
        self.log("Status refreshed")

    def read_temperature_once(self):
        """Manual button: read and log the cryostat temperatures once.

        Independent of the magnet — this only reads the ICElog file.
        """
        temps = None
        try:
            temps = read_ice_temperature()
            self.log("Temperatures (50K/4K/VTI/probe): "
                     + " / ".join(f"{v:.2f} K" for v in temps))
        except Exception as e:
            self.log(f"Temperature log read error: {e}")
        # also feed the combined B/T readout in the environment panel
        self._env_temps = temps
        self._update_env_label()

    # ==================== SWEEP EXECUTION ====================

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, directory)

    def start_sweep(self):
        if not self.bias_inst:
            messagebox.showerror("Error", "Bias instrument not connected (must be Keithley 2450)")
            return
        try:
            params = self._collect_sweep_params()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        self.set_busy()
        threading.Thread(target=self._run_sweep_thread, args=(params,), daemon=True).start()

    def _collect_sweep_params(self, ov=None):
        """Read the GUI sweep settings into a validated params dict for
        _run_sweep_thread. `ov` is an optional sequence-step override dict
        (same key names as the sequence JSON); override values win over the
        GUI entries. Raises ValueError with a user-facing message."""
        ov = ov or {}
        bias_ov = ov.get('bias') or {}
        gates_ov = ov.get('gates') or {}
        g1ov = gates_ov.get('g1') or {}
        g2ov = gates_ov.get('g2') or {}
        field_ov = ov.get('field') or {}

        def pick(section, key, widget):
            # sequence override wins over the GUI entry
            if key in section:
                return str(section[key])
            return widget.get()

        def flag(key, var):
            if key in ov:
                return bool(ov[key])
            return bool(var.get())

        try:
            sp1 = float(pick(bias_ov, 'sp1', self.ent_sp1))
            sp2 = float(pick(bias_ov, 'sp2', self.ent_sp2))
            step = abs(float(pick(bias_ov, 'step', self.ent_step)))
            delay = float(pick(bias_ov, 'delay', self.ent_delay))
            compliance = float(pick(bias_ov, 'compliance', self.ent_compliance))
        except ValueError:
            raise ValueError("Invalid numeric parameters")

        save_dir = str(ov.get('save_dir', self.ent_dir.get()))
        subdir = str(ov.get('save_subdir', '')).strip()
        if subdir:  # per-step sub-folder inside the save directory
            save_dir = os.path.join(save_dir, subdir)
        if not save_dir:
            raise ValueError("Please select a save directory")

        sweep_type = str(ov.get('sweep_type', self.sweep_type_var.get()))
        mode = str(ov.get('mode', self.loop_mode_var.get()))
        # plain-sweep mode: gates are NEVER driven by the sweep (control them
        # manually via section 2). The checkboxes only choose which gate
        # voltages get documented as columns in the file.
        record_gates = []
        if mode == "none":
            if 'record_gates' in ov:
                record_gates = [int(g) for g in ov['record_gates']]
            else:
                record_gates = [gi for gi in (1, 2)
                                if (self.rec_g1_var.get() if gi == 1
                                    else self.rec_g2_var.get())]
        points = [(None, None)]
        gate_cfg = {}
        settle = ramp_step = ramp_delay = 0.0

        if mode not in ("none", "field"):
            try:
                settle = float(pick(ov, 'settle', self.ent_gate_settle))
                ramp_step = abs(float(pick(ov, 'loop_ramp_step',
                                           self.ent_loop_ramp_step))) / 1000.0
                ramp_delay = float(pick(ov, 'loop_ramp_delay',
                                        self.ent_loop_ramp_delay))
                g1s = float(pick(g1ov, 'start', self.ent_g1_start))
                g1e = float(pick(g1ov, 'end', self.ent_g1_end))
                g2s = float(pick(g2ov, 'start', self.ent_g2_start))
                g2e = float(pick(g2ov, 'end', self.ent_g2_end))
            except ValueError as e:
                raise ValueError(f"Invalid gate loop parameters: {e}")
            if ramp_step == 0 or ramp_delay < 0 or settle < 0:
                raise ValueError("Gate loop ramp step must be non-zero; "
                                 "settle and ramp delay must be >= 0")

        if mode == "field":
            # field loop: bias sweep at every field point (magnet required)
            if self.magnet.inst is None:
                raise ValueError("Field loop requires the magnet "
                                 "to be connected")
            try:
                fst = float(pick(field_ov, 'start', self.ent_field_start))
                fe = float(pick(field_ov, 'end', self.ent_field_end))
                fstep = abs(float(pick(field_ov, 'step', self.ent_field_step)))
                frate = float(pick(field_ov, 'rate', self.ent_field_rate))
            except ValueError as e:
                raise ValueError(f"Invalid field loop parameters: {e}")
            if frate <= 0:
                raise ValueError("Field sweep rate must be > 0")
            fields = arange_inclusive(fst, fe, fstep)
            if not fields:
                raise ValueError("Field loop produces no points")
        else:
            fields = []
            frate = 0.1

        if mode not in ("none", "field"):
            need = {"gate1": [1], "gate2": [2], "dual": [1, 2], "movement": [1, 2]}[mode]
            for gi in need:
                if self.gates[gi - 1].inst is None:
                    raise ValueError(f"Loop mode requires Gate {gi} to be connected")
                ch = self.gates[gi - 1]
                gov = g1ov if gi == 1 else g2ov
                try:
                    gate_cfg[f'g{gi}_compliance'] = float(
                        pick(gov, 'compliance', ch.ent_compliance))
                    gate_cfg[f'g{gi}_nplc'] = float(
                        pick(gov, 'nplc', ch.ent_nplc))
                except ValueError:
                    raise ValueError(f"Invalid gate {gi} compliance/NPLC parameters")

            def held_value(gi):
                """Constant voltage for a connected but non-looped gate."""
                gov = g2ov if gi == 2 else g1ov
                if 'target' in gov:
                    return float(gov['target'])
                ch = self.gates[gi - 1]
                if ch.inst is None:
                    return None
                return float(ch.ent_target.get())  # may raise ValueError

            try:
                if mode in ("gate1", "dual"):
                    g1st = abs(float(pick(g1ov, 'step', self.ent_g1_loop_step)))
                    list1 = arange_inclusive(g1s, g1e, g1st)
                    if not list1:
                        raise ValueError("Gate 1 loop produces no points")
                if mode in ("gate2", "dual"):
                    g2st = abs(float(pick(g2ov, 'step', self.ent_g2_loop_step)))
                    list2 = arange_inclusive(g2s, g2e, g2st)
                    if not list2:
                        raise ValueError("Gate 2 loop produces no points")

                if mode == "gate1":
                    held = held_value(2)  # Gate 2 stays at its manual target
                    points = [(v, held) for v in list1]
                elif mode == "gate2":
                    held = held_value(1)  # Gate 1 stays at its manual target
                    points = [(held, v) for v in list2]
                elif mode == "dual":
                    # full 2D map; nesting order is user-selectable
                    if str(ov.get('dual_outer', self.dual_outer_var.get())) == "2":
                        # Gate 2 outer loop, Gate 1 inner loop
                        points = [(v1, v2) for v2 in list2 for v1 in list1]
                    else:
                        # Gate 1 outer loop, Gate 2 inner loop
                        points = [(v1, v2) for v1 in list1 for v2 in list2]
                else:  # movement: both gates move together along a line with a
                    # common point count — keeps any linear combination of the
                    # gate voltages (carrier density n, displacement field D)
                    # on a well-defined constant-n or constant-D cut
                    npts = int(float(pick(ov, 'points', self.ent_loop_points)))
                    if npts < 1:
                        raise ValueError("Movement loop needs at least 1 point")
                    list1 = list(np.linspace(g1s, g1e, npts))
                    list2 = list(np.linspace(g2s, g2e, npts))
                    points = list(zip(list1, list2))
            except ValueError as e:
                raise ValueError(f"Invalid held-gate target (enter a valid Target "
                                 f"in section 2): {e}")

        # remember the GUI values for the next launch of this dialog
        if sweep_type == "iv":
            keys = ['iv_sp1', 'iv_sp2', 'iv_step', 'iv_delay', 'iv_compliance']
        else:
            keys = ['vi_sp1', 'vi_sp2', 'vi_step', 'vi_delay', 'vi_compliance']
        for key, ent in zip(keys, [self.ent_sp1, self.ent_sp2, self.ent_step,
                                   self.ent_delay, self.ent_compliance]):
            self.saved_params[key] = ent.get()
        self.saved_params['save_dir'] = self.ent_dir.get()

        params = {
            'sp1': sp1, 'sp2': sp2, 'step': step, 'delay': delay,
            'compliance': compliance, 'save_dir': save_dir, 'sweep_type': sweep_type,
            'mode': mode, 'points': points, 'settle': settle,
            'loop_ramp_step': ramp_step, 'loop_ramp_delay': ramp_delay,
            'doc_field': flag('doc_field', self.doc_field_var),
            'doc_temp': flag('doc_temp', self.doc_temp_var),
            'record_gates': record_gates,
            'fields': fields,
            'field_rate': frate if mode == "field" else 0.1,
            'held_readback': (flag('held_readback', self.held_readback_var)
                              and mode in ("gate1", "gate2")),
            'return_gates': (flag('return_gates', self.return_gates_var)
                             and mode not in ("none", "field")),
            'return_field': (flag('return_field', self.return_field_var)
                             and mode == "field"),
        }
        params.update(gate_cfg)
        return params

    def abort_sweep(self):
        self._seq_abort = True  # stops the whole sequence, not just this sweep
        self.stop_event.set()
        self.log("Abort requested...")

    # ==================== SEQUENCE (JSON STEP LIST) ====================

    def load_sequence_file(self):
        path = filedialog.askopenfilename(
            title="Load measurement sequence",
            filetypes=[("JSON / text", "*.json *.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            steps = self._parse_sequence_file(path)
        except Exception as e:
            messagebox.showerror("Sequence error", f"Cannot load sequence:\n{e}")
            return
        self._sequence_steps = steps
        self._sequence_path = path
        self.lbl_seq_path.config(text=f"File: {path}")
        self._fill_sequence_tree()
        self.log(f"Sequence loaded: {len(steps)} step(s) from "
                 f"{os.path.basename(path)}")

    @staticmethod
    def _parse_sequence_file(path):
        """Read a sequence JSON file ('#' comments allowed, repo convention)."""
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        stripped = "\n".join(line.split("#", 1)[0] for line in raw.splitlines())
        data = json.loads(stripped)
        if not isinstance(data, list) or not data:
            raise ValueError("sequence file must be a non-empty JSON list of steps")
        for i, s in enumerate(data):
            if not isinstance(s, dict):
                raise ValueError(f"step {i + 1} is not a JSON object")
            stype = str(s.get("type", "sweep"))
            if stype not in ("sweep", "wait"):
                raise ValueError(f"step {i + 1}: unknown type '{stype}' "
                                 "(use 'sweep' or 'wait')")
            if stype == "wait":
                try:
                    float(s.get("seconds", 0))
                except (TypeError, ValueError):
                    raise ValueError(f"step {i + 1}: 'seconds' must be a number")
            try:
                if int(s.get("repeat", 1)) < 1:
                    raise ValueError(f"step {i + 1}: repeat must be >= 1")
            except (TypeError, ValueError):
                raise ValueError(f"step {i + 1}: repeat must be a number >= 1")
        return data

    def _estimate_seq_sweeps(self, step):
        """Bias sweeps one step will produce (None when not computable)."""
        mode = str(step.get('mode', self.loop_mode_var.get()))
        try:
            if mode == "none":
                return 1
            if mode == "field":
                f = step.get('field') or {}
                fst = float(f.get('start', self.ent_field_start.get()))
                fe = float(f.get('end', self.ent_field_end.get()))
                fs = abs(float(f.get('step', self.ent_field_step.get())))
                return len(arange_inclusive(fst, fe, fs))
            gates = step.get('gates') or {}
            g1 = gates.get('g1') or {}
            g2 = gates.get('g2') or {}
            if mode == "movement":
                return int(float(step.get('points', self.ent_loop_points.get())))
            n1 = n2 = None
            if mode in ("gate1", "dual"):
                n1 = len(arange_inclusive(float(g1.get('start', self.ent_g1_start.get())),
                                          float(g1.get('end', self.ent_g1_end.get())),
                                          abs(float(g1.get('step', self.ent_g1_loop_step.get())))))
            if mode in ("gate2", "dual"):
                n2 = len(arange_inclusive(float(g2.get('start', self.ent_g2_start.get())),
                                          float(g2.get('end', self.ent_g2_end.get())),
                                          abs(float(g2.get('step', self.ent_g2_loop_step.get())))))
            if mode == "gate1":
                return n1
            if mode == "gate2":
                return n2
            return (n1 or 0) * (n2 or 0)
        except (ValueError, TypeError, KeyError):
            return None

    def _fill_sequence_tree(self):
        """Preview the loaded sequence in the Sequence tab table."""
        self.seq_tree.delete(*self.seq_tree.get_children())
        total_sweeps, total_wait = 0, 0.0
        for i, s in enumerate(self._sequence_steps):
            stype = str(s.get('type', 'sweep'))
            reps = max(1, int(s.get('repeat', 1)))
            gates = s.get('gates') or {}
            gate_txt = []
            for gi, key in ((1, 'g1'), (2, 'g2')):
                g = gates.get(key) or {}
                if 'end' in g:
                    gate_txt.append(f"G{gi}: {g['start']}..{g['end']}"
                                    + (f"/{g['step']}" if 'step' in g else ""))
                elif 'target' in g or 'start' in g:
                    gate_txt.append(f"G{gi}: {g.get('target', g.get('start'))} V")
            f = s.get('field') or {}
            field_txt = (f"{f['start']}..{f['end']}/{f['step']}"
                         + (f" @{f['rate']} T/min" if 'rate' in f else "")
                         if 'start' in f else "")
            b = s.get('bias') or {}
            bias_txt = (f"{b.get('sp1', '?')}..{b.get('sp2', '?')}"
                        + (f"/{b['step']}" if 'step' in b else "")) if b else ""
            if stype == 'wait':
                secs = float(s.get('seconds', 0))
                total_wait += secs * reps
            else:
                n = self._estimate_seq_sweeps(s)
                total_sweeps += (n * reps) if n is not None else 0
            self.seq_tree.insert("", "end", values=(
                i + 1, str(s.get('name', '')), stype,
                str(s.get('mode', '(GUI)')) if stype == 'sweep' else '',
                bias_txt, "; ".join(gate_txt), field_txt, reps))
        sweeps_txt = f"{total_sweeps} bias sweeps" if total_sweeps else "sweeps: ?"
        wait_txt = f" + {total_wait:g} s waiting" if total_wait else ""
        self.lbl_seq_total.config(
            text=(f"{len(self._sequence_steps)} steps — {sweeps_txt}{wait_txt}"
                  if self._sequence_steps else "no sequence loaded"))

    # ==================== SEQUENCE EDITOR ====================

    def seq_selected_index(self):
        sel = self.seq_tree.selection()
        return self.seq_tree.index(sel[0]) if sel else None

    def seq_edit_step(self, index=None):
        """Open the step editor. index=-1 creates a new step; index=None
        edits the selected table row."""
        if index is None:
            index = self.seq_selected_index()
            if index is None:
                messagebox.showerror("Error", "Select a step in the table first")
                return
        step = dict(self._sequence_steps[index]) \
            if 0 <= index < len(self._sequence_steps) else {}
        result = self._seq_step_dialog(step)
        if result is None:
            return
        if index == -1:
            self._sequence_steps.append(result)
            index = len(self._sequence_steps) - 1
        else:
            self._sequence_steps[index] = result
        self._fill_sequence_tree()
        children = self.seq_tree.get_children()
        if children:
            self.seq_tree.selection_set(children[min(index, len(children) - 1)])
            self.seq_tree.see(children[min(index, len(children) - 1)])

    def seq_delete_step(self):
        """Delete ALL selected steps (Ctrl/Shift-click for multi-select) and
        keep the selection on the row that follows the deleted block."""
        indices = sorted(self.seq_tree.index(s) for s in self.seq_tree.selection())
        if not indices:
            messagebox.showerror("Error", "Select step(s) in the table first")
            return
        for i in reversed(indices):
            del self._sequence_steps[i]
        self._fill_sequence_tree()
        children = self.seq_tree.get_children()
        if children:
            keep = min(indices[0], len(children) - 1)
            self.seq_tree.selection_set(children[keep])
            self.seq_tree.see(children[keep])

    def seq_clear_all(self):
        if not self._sequence_steps:
            return
        if messagebox.askyesno("Clear sequence",
                               f"Delete all {len(self._sequence_steps)} step(s)?"):
            self._sequence_steps = []
            self._fill_sequence_tree()

    def seq_move_step(self, delta):
        index = self.seq_selected_index()
        if index is None:
            messagebox.showerror("Error", "Select a step in the table first")
            return
        new = index + delta
        if not 0 <= new < len(self._sequence_steps):
            return
        self._sequence_steps[index], self._sequence_steps[new] = \
            self._sequence_steps[new], self._sequence_steps[index]
        self._fill_sequence_tree()
        children = self.seq_tree.get_children()
        self.seq_tree.selection_set(children[new])
        self.seq_tree.see(children[new])

    def seq_save_file(self):
        if not self._sequence_steps:
            messagebox.showerror("Error", "No steps to save")
            return
        path = filedialog.asksaveasfilename(
            title="Save sequence", defaultextension=".json",
            initialfile="sequence.json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._sequence_steps, f, indent=2)
        self._sequence_path = path
        self.lbl_seq_path.config(text=f"File: {path}")
        self.log(f"Sequence saved: {path}")

    def seq_capture_gui(self):
        """Snapshot the current Sweep setup / Magnet tab values as one new
        sequence step (fastest way to build a sequence: set the GUI, capture,
        change one thing, capture again...)."""
        try:
            step = {
                'name': f'from GUI {time.strftime("%H:%M")}',
                'type': 'sweep',
                'mode': self.loop_mode_var.get(),
                'sweep_type': self.sweep_type_var.get(),
                'bias': {'sp1': float(self.ent_sp1.get()),
                         'sp2': float(self.ent_sp2.get()),
                         'step': abs(float(self.ent_step.get())),
                         'delay': float(self.ent_delay.get()),
                         'compliance': float(self.ent_compliance.get())},
                'settle': float(self.ent_gate_settle.get()),
                'loop_ramp_step': abs(float(self.ent_loop_ramp_step.get())),
                'loop_ramp_delay': float(self.ent_loop_ramp_delay.get()),
                'points': int(float(self.ent_loop_points.get())),
                'doc_field': self.doc_field_var.get(),
                'doc_temp': self.doc_temp_var.get(),
                'held_readback': self.held_readback_var.get(),
                'return_gates': self.return_gates_var.get(),
                'return_field': self.return_field_var.get(),
            }
            gates = {}
            for gi, key in ((1, 'g1'), (2, 'g2')):
                ch = self.gates[gi - 1]
                s_ent, e_ent, st_ent = ((self.ent_g1_start, self.ent_g1_end,
                                         self.ent_g1_loop_step) if gi == 1 else
                                        (self.ent_g2_start, self.ent_g2_end,
                                         self.ent_g2_loop_step))
                gates[key] = {'start': float(s_ent.get()),
                              'end': float(e_ent.get()),
                              'step': abs(float(st_ent.get())),
                              'compliance': float(ch.ent_compliance.get()),
                              'nplc': float(ch.ent_nplc.get())}
            if step['mode'] == 'field':
                step['field'] = {'start': float(self.ent_field_start.get()),
                                 'end': float(self.ent_field_end.get()),
                                 'step': abs(float(self.ent_field_step.get())),
                                 'rate': float(self.ent_field_rate.get())}
            else:
                step['gates'] = gates
        except ValueError:
            messagebox.showerror("Error", "GUI values are not all valid numbers")
            return
        self._sequence_steps.append(step)
        self._fill_sequence_tree()
        self.log(f"Sequence: captured GUI settings as step "
                 f"{len(self._sequence_steps)}")

    USER_GUIDE_TEXT = """IV/VI SWEEPER (ICE) — USER GUIDE
================================

WHAT THIS PROGRAM DOES
----------------------
Runs hysteresis bias sweeps on a Keithley 2450 (voltage or current source)
while optionally looping gate voltages (2 independent gate sources) or the
magnetic field (Cryomagnetics MPS4G). Every sweep is saved as a numbered
CSV in your save directory; gate voltages, field and cryostat temperatures
are recorded as extra columns.

1. CONNECT (Instruments tab)
----------------------------
- "Scan Instruments" fills the VISA address lists; "Refresh Status"
  re-reads every output/terminal state.
- Bias: always a Keithley 2450. "Term:" switches FRONT/REAR terminals,
  "Out:" toggles the output, "Reset" resets the instrument.
- Gate 1 / Gate 2: pick the source type (Keithley 2450, Keithley 2604B
  channel A/B, Yokogawa 7651, Yokogawa GS200) and address. "Term:" only
  works on a 2450 gate.
- Magnet (MPS4G): pick the COM port. On connect a SAFETY LIMITS dialog
  opens: set the per-range maximum sweep rates (T/min) once. They are
  saved to instrument_overrides.json and clamp EVERY magnet ramp in this
  program and in the Transport-measurements procedures.
- Closing the window always releases the COM port; outputs and levels are
  intentionally left as they are.

2. GATE SOURCES (Instruments tab)
---------------------------------
Each gate card: compliance, NPLC (2450 only), manual ramp target/step/
rate, "Ramp Gate", "Configure Source", "Measure Once". The plain sweep
never drives the gates — control them here.

3. FIELD & TEMPERATURE (Instruments tab)
----------------------------------------
Independent toggles to record the magnet field and/or the 4 cryostat
temperatures (from the ICElog file) once AFTER each sweep, as extra CSV
columns. Manual one-shot readings via "Read Field" / "Read Temp".

4. SWEEP SETUP
--------------
- Measurement mode: IV (source V, measure I) or VI (source I, measure V).
- Bias sweep: Sp1/Sp2/Step/Delay + compliance (A for IV, V for VI).
- Loop modes:
    Bias only    one hysteresis sweep; gates stay under manual control
    Gate 1/2     bias sweep at every gate voltage (other gate held at its
                 manual Target, or at the value given in a sequence step)
    Dual 2D      full 2D map; nesting order selectable (G1/G2 outer)
    Movement     both gates move together along a line (constant-n /
                 constant-D cuts), common point count
    Field        bias sweep at every field point (configured in the
                 Magnet control tab)
- "Return gates to 0 V after loop" and "Return field to 0 T after loop"
  are OPTIONS (checkboxes) — unchecked, everything is left where the
  loop ended.
- The tab scrolls vertically (wheel) and horizontally (Shift+wheel).

5. MAGNET CONTROL
-----------------
- Manual: sweep rate (T/min, clamped per range by the safety limits) and
  target field. ABORT stops the ramp, field left where it is.
- Field loop: Start/End/Step/Rate for the loop; the loop radio here
  overrides the Sweep-setup loop mode.
- "Safety limits..." reopens the per-range limits dialog anytime.

6. SAVE & EXECUTE
-----------------
Pick a Save Directory, press RUN SWEEP (ABORT stops). Files are named
IV_007_G1_1.000V_B_0.250T_T_1.23K_Sp1_1000mV_...  with sequential numbers
continuing past existing files. The divider between the tabs and the log
is draggable.

"Theme:" switches light/dark live.

7. SEQUENCE (right-most tab)
----------------------------
Automate long measurements: a list of steps, each overriding the current
Sweep-setup values (missing keys = GUI values). Build it WITHOUT writing
JSON: set the GUI and press "Capture GUI" for each configuration, or use
"Add step..." (full editor; blank fields inherit GUI values). Edit with
double-click; reorder with Up/Down; "Save as..." writes a JSON file you
can reload or hand-edit ('#' comments allowed). "Help / examples" has the
key reference and insertable examples. ABORT stops the current sweep and
the whole sequence.

EXAMPLE MEASUREMENTS
====================
Example 1 — careful first measurement
  1. Connect bias; set IV, Sp1/Sp2 = +/-100 mV, step 5 mV, compliance
     100 nA. Save directory -> RUN SWEEP. Check the CSV.
  2. Ramp Gate 1 manually to a few volts and repeat.

Example 2 — gate sweep
  Loop mode "Gate 1 loop", Start -4 V, End 4 V, Step 0.5 V, Settle 1 s.
  Tick "Return gates to 0 V after loop" if you want the gates back at 0.
  RUN SWEEP -> one CSV per gate voltage, named by voltage.

Example 3 — hysteresis vs magnetic field
  Connect the magnet, set the safety limits. Magnet control tab: field
  loop 0 -> 1 T, step 0.1 T, rate 0.05 T/min. Tick "Record temperature
  each sweep". RUN SWEEP -> bias sweep at every field, B in every file.

Example 4 — gates x fields overnight (Sequence tab)
  "Help / examples" -> "Insert example: gates x fields" gives a working
  skeleton (ramp to a fixed field, gate sweep, next field...). Edit the
  field values / gate range with double-click, Save as..., RUN SEQUENCE.

SAFETY NOTES
------------
- Magnet ramps NEVER exceed the per-range safety limits (clamped + logged).
- Gate voltages always ramp slowly (ramp step/delay), never jump.
- Closing the program or aborting does not switch outputs off or quench
  the field; it only stops the automation.
"""

    def show_user_guide(self):
        """Program-wide user guide window (how to use + examples)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("User guide")
        dlg.configure(bg=COLORS["background"])
        dlg.transient(self.root)
        dlg.geometry("760x640")
        txt = tk.Text(dlg, wrap="word",
                      bg=COLORS["log_background"], fg=COLORS["log_text"],
                      font=("Consolas", 9), relief="flat", padx=10, pady=8)
        bar = ttk.Scrollbar(dlg, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", self.USER_GUIDE_TEXT)
        txt.config(state="disabled")
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(side="bottom",
                                                                pady=6)

    SEQ_HELP_TEXT = """HOW SEQUENCES WORK
==================
A sequence is a flat list of steps, run top to bottom. Every step OVERRIDES
the current Sweep setup GUI values; keys left out inherit the GUI values.
Fastest workflow: set the GUI, press "Capture GUI", change one thing,
capture again.

Step types
----------
  sweep (default)  one full measurement as configured in Sweep setup
  wait             pause; "seconds" required (abortable via ABORT)

Step keys (all optional unless noted)
-------------------------------------
  name            label shown in the table and log
  type            "sweep" or "wait"
  repeat          run this step N times (default 1; files auto-number)
  save_subdir     write this step's files into a sub-folder of Save Directory
  mode            none | gate1 | gate2 | dual | movement | field
  sweep_type      "iv" or "vi"
  bias            { sp1, sp2, step, delay, compliance }
  gates           { g1, g2 } each { start, end, step, compliance, nplc,
                   target }  ("target" = held-gate voltage in single-gate loops)
  field           { start, end, step, rate (T/min) }   mode "field"
  settle, loop_ramp_step (mV), loop_ramp_delay, points (movement),
  dual_outer      "1" or "2"  (which gate is outer in dual 2D maps)
  doc_field, doc_temp, held_readback, record_gates ([1,2]),
  return_gates, return_field   true/false overrides of the GUI checkboxes

Nesting / cross products (gates x fields etc.)
---------------------------------------------
There is no nested loop construct; expand it flat. A field step with
start == end means "ramp the magnet to B, sweep bias there". Follow it
with a gate-loop step and the gate sweep runs AT that field (the magnet
holds its position). See example 1 below.

Safety: every magnet ramp is clamped to the per-range safety limits
(Safety limits... button, Magnet control tab); gate moves always ramp
slowly; ABORT stops the current sweep and the whole sequence.
"""

    SEQ_EXAMPLE_GATEFIELD = [
        {"name": "go to 0.25T", "mode": "field",
         "field": {"start": 0.25, "end": 0.25, "step": 0.1, "rate": 0.05},
         "return_field": False},
        {"name": "gate sweep @0.25T", "mode": "gate1",
         "gates": {"g1": {"start": -4, "end": 4, "step": 0.5}},
         "return_gates": True},
        {"name": "go to 0.50T", "mode": "field",
         "field": {"start": 0.50, "end": 0.50, "step": 0.1, "rate": 0.05},
         "return_field": False},
        {"name": "gate sweep @0.50T", "mode": "gate1",
         "gates": {"g1": {"start": -4, "end": 4, "step": 0.5}},
         "return_gates": True},
    ]

    SEQ_EXAMPLE_LADDER = [
        {"name": "careful first look", "repeat": 2,
         "bias": {"sp1": 200, "sp2": -200, "step": 5, "compliance": 1e-9},
         "save_subdir": "low_bias"},
        {"name": "wider span",
         "bias": {"sp1": 1000, "sp2": -1000, "step": 10, "compliance": 1e-8}},
        {"name": "settle 5 min", "type": "wait", "seconds": 300},
        {"name": "gate map at working bias", "mode": "dual",
         "gates": {"g1": {"start": -3, "end": 3, "step": 1},
                   "g2": {"start": -3, "end": 3, "step": 1}},
         "doc_temp": True, "return_gates": True},
    ]

    def seq_help(self):
        """Sequence help dialog: format reference + insertable examples."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Sequence help & examples")
        dlg.configure(bg=COLORS["background"])
        dlg.transient(self.root)
        dlg.grab_set()

        txt = tk.Text(dlg, wrap="word", width=78, height=26,
                      bg=COLORS["log_background"], fg=COLORS["log_text"],
                      font=("Consolas", 9), relief="flat", padx=8, pady=6)
        bar = ttk.Scrollbar(dlg, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", self.SEQ_HELP_TEXT)
        txt.config(state="disabled")

        def add_example(steps, label):
            def _add():
                self._sequence_steps.extend([dict(s) for s in steps])
                self._fill_sequence_tree()
                self.log(f"Sequence: appended example '{label}' "
                         f"({len(steps)} steps)")
                dlg.destroy()
            return _add

        btns = ttk.Frame(dlg)
        btns.pack(fill="x", side="bottom", padx=8, pady=8)
        ttk.Button(btns, text="Insert example: gates x fields",
                   command=add_example(self.SEQ_EXAMPLE_GATEFIELD,
                                       "gates x fields")).pack(side="left")
        ttk.Button(btns, text="Insert example: bias ladder + gate map",
                   command=add_example(self.SEQ_EXAMPLE_LADDER,
                                       "bias ladder")).pack(side="left",
                                                            padx=6)
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(
            side="right")

    def _seq_step_dialog(self, step):
        """Modal editor for ONE sequence step.

        Empty numeric field = inherit the GUI value at run time (same rule
        as the JSON file). Flag combos: blank = inherit, 'on'/'off' override.
        Returns the new step dict, or None when cancelled.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Sequence step")
        dlg.configure(bg=COLORS["background"])
        dlg.transient(self.root)
        dlg.grab_set()
        step = step or {}
        stype = str(step.get('type', 'sweep'))
        entries = {}   # (key, subkey) -> Entry, subkey None for top-level
        combos = {}    # flag name -> tri-state combobox ('' / on / off)

        def get_val(key, sub=None):
            if sub is None:
                v = step.get(key)
            else:
                v = (step.get(key) or {}).get(sub)
            return '' if v is None else str(v)

        def frow(parent, label, key, sub=None, width=9):
            ttk.Label(parent, text=label).pack(side="left")
            ent = ttk.Entry(parent, width=width)
            ent.insert(0, get_val(key, sub))
            ent.pack(side="left", padx=(3, 14))
            entries[(key, sub)] = ent
            return ent

        def flag_row(parent, label, key):
            ttk.Label(parent, text=label).pack(side="left", padx=(0, 3))
            v = step.get(key)
            cb = ttk.Combobox(parent, values=["", "on", "off"], width=4,
                              state="readonly")
            cb.set("" if v is None else ("on" if v else "off"))
            cb.pack(side="left", padx=(0, 16))
            combos[key] = cb

        # --- header: name / type / repeat / wait seconds ---
        top = ttk.Frame(dlg)
        top.pack(fill="x", padx=10, pady=8)
        frow(top, "Name:", 'name', width=22)
        ttk.Label(top, text="Type:").pack(side="left")
        type_cb = ttk.Combobox(top, values=["sweep", "wait"], width=6,
                               state="readonly")
        type_cb.set(stype)
        type_cb.pack(side="left", padx=(3, 14))
        frow(top, "Repeat:", 'repeat', width=4)

        waitf = ttk.LabelFrame(dlg, text="Wait step", padding=5)
        waitf.pack(fill="x", padx=10, pady=4)
        frow(waitf, "Seconds:", 'seconds', width=9)

        # --- bias ---
        biasf = ttk.LabelFrame(dlg, text="Bias sweep (blank = GUI value)",
                               padding=5)
        biasf.pack(fill="x", padx=10, pady=4)
        brow = ttk.Frame(biasf)
        brow.pack(fill="x")
        for lbl, k in (("Sp1:", 'sp1'), ("Sp2:", 'sp2'), ("Step:", 'step'),
                       ("Delay:", 'delay'), ("Compliance:", 'compliance')):
            ttk.Label(brow, text=lbl).pack(side="left")
            ent = ttk.Entry(brow, width=9)
            ent.insert(0, get_val('bias', k))
            ent.pack(side="left", padx=(3, 14))
            entries[('bias', k)] = ent
        sweep_type_row = ttk.Frame(biasf)
        sweep_type_row.pack(fill="x")
        ttk.Label(sweep_type_row, text="Measurement:").pack(side="left")
        st_cb = ttk.Combobox(sweep_type_row, values=["iv", "vi"], width=4,
                             state="readonly")
        st_cb.set(str(step.get('sweep_type', 'iv')))
        st_cb.pack(side="left", padx=3)

        # --- loop mode ---
        modef = ttk.LabelFrame(dlg, text="Loop mode", padding=5)
        modef.pack(fill="x", padx=10, pady=4)
        mode_var = tk.StringVar(value=str(step.get('mode', 'none')))
        for val, txt in (("none", "Bias only"), ("gate1", "Gate 1"),
                         ("gate2", "Gate 2"), ("dual", "Dual 2D"),
                         ("movement", "Movement"), ("field", "Field")):
            ttk.Radiobutton(modef, text=txt, variable=mode_var,
                            value=val).pack(side="left", padx=6)

        # --- gates ---
        gatef = ttk.LabelFrame(dlg, text="Gates (blank = GUI value; loop "
                                         "modes use start/end/step, held gate "
                                         "uses target)", padding=5)
        gatef.pack(fill="x", padx=10, pady=4)
        for gi, key in ((1, 'g1'), (2, 'g2')):
            row = ttk.Frame(gatef)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"Gate {gi}:", width=7).pack(side="left")
            for lbl, k, w in (("Start", 'start', 7), ("End", 'end', 7),
                              ("Step", 'step', 6), ("Compl.", 'compliance', 7),
                              ("NPLC", 'nplc', 5), ("Target", 'target', 7)):
                ttk.Label(row, text=lbl).pack(side="left", padx=(8, 0))
                ent = ttk.Entry(row, width=w)
                ent.insert(0, get_val(key, k))
                ent.pack(side="left", padx=2)
                entries[(key, k)] = ent

        # --- field ---
        fieldf = ttk.LabelFrame(dlg, text="Field loop (blank = GUI value)",
                                padding=5)
        fieldf.pack(fill="x", padx=10, pady=4)
        frow1 = ttk.Frame(fieldf)
        frow1.pack(fill="x")
        for lbl, k in (("Start (T):", 'start'), ("End (T):", 'end'),
                       ("Step (T):", 'step'), ("Rate (T/min):", 'rate')):
            ttk.Label(frow1, text=lbl).pack(side="left")
            ent = ttk.Entry(frow1, width=8)
            ent.insert(0, get_val('field', k))
            ent.pack(side="left", padx=(3, 14))
            entries[('field', k)] = ent

        # --- shared loop parameters ---
        loopf = ttk.LabelFrame(dlg, text="Loop parameters (blank = GUI value)",
                               padding=5)
        loopf.pack(fill="x", padx=10, pady=4)
        lrow = ttk.Frame(loopf)
        lrow.pack(fill="x")
        for lbl, k, w in (("Settle (s):", 'settle', 6),
                          ("Ramp step (mV):", 'loop_ramp_step', 6),
                          ("Ramp delay (s):", 'loop_ramp_delay', 6),
                          ("Points (movement):", 'points', 5)):
            ttk.Label(lrow, text=lbl).pack(side="left")
            ent = ttk.Entry(lrow, width=w)
            ent.insert(0, get_val(k))
            ent.pack(side="left", padx=(3, 14))
            entries[(k, None)] = ent
        ttk.Label(lrow, text="Dual outer:").pack(side="left")
        outer_cb = ttk.Combobox(lrow, values=["", "1", "2"], width=3,
                                state="readonly")
        outer_cb.set("" if step.get('dual_outer') is None
                     else str(step['dual_outer']))
        outer_cb.pack(side="left", padx=3)

        # --- flags + save location ---
        optf = ttk.LabelFrame(dlg, text="Options (blank = GUI value)", padding=5)
        optf.pack(fill="x", padx=10, pady=4)
        orow1 = ttk.Frame(optf)
        orow1.pack(fill="x")
        for lbl, k in (("Record field", 'doc_field'), ("Record temp", 'doc_temp'),
                       ("Held readback", 'held_readback'),
                       ("Return gates", 'return_gates'),
                       ("Return field", 'return_field')):
            flag_row(orow1, lbl + ":", k)
        orow2 = ttk.Frame(optf)
        orow2.pack(fill="x", pady=(4, 0))
        frow(orow2, "Record gates (e.g. 1,2):", 'record_gates', width=6)
        frow(orow2, "Save subfolder:", 'save_subdir', width=14)

        status = ttk.Label(dlg, text="", foreground=COLORS["abort"])
        status.pack(anchor="w", padx=10)

        def read_float(key, sub):
            txt = entries[(key, sub)].get().strip()
            if txt == '':
                return None  # inherit the GUI value
            return float(txt)  # ValueError -> caught below

        def collect():
            new = {}
            if entries[('name', None)].get().strip():
                new['name'] = entries[('name', None)].get().strip()
            new['type'] = type_cb.get()
            try:
                rep = entries[('repeat', None)].get().strip()
                new['repeat'] = max(1, int(float(rep))) if rep else 1
                if new['type'] == 'wait':
                    secs = read_float('seconds', None)
                    if secs is None:
                        raise ValueError("'seconds' is required for a wait step")
                    new['seconds'] = secs
                    return new
                bias = {}
                for k in ('sp1', 'sp2', 'step', 'delay', 'compliance'):
                    v = read_float('bias', k)
                    if v is not None:
                        bias[k] = v
                if bias:
                    new['bias'] = bias
                new['mode'] = mode_var.get()
                if st_cb.get() != 'iv':
                    new['sweep_type'] = st_cb.get()
                gates = {}
                for key in ('g1', 'g2'):
                    g = {}
                    for k in ('start', 'end', 'step', 'compliance', 'nplc',
                              'target'):
                        v = read_float(key, k)
                        if v is not None:
                            g[k] = v
                    if g:
                        gates[key] = g
                if gates:
                    new['gates'] = gates
                field = {}
                for k in ('start', 'end', 'step', 'rate'):
                    v = read_float('field', k)
                    if v is not None:
                        field[k] = v
                if field:
                    new['field'] = field
                for k in ('settle', 'loop_ramp_step', 'loop_ramp_delay',
                          'points'):
                    v = read_float(k, None)
                    if v is not None:
                        new[k] = v
                if outer_cb.get():
                    new['dual_outer'] = outer_cb.get()
                for k, cb in combos.items():
                    if cb.get():
                        new[k] = (cb.get() == 'on')
                rg = entries[('record_gates', None)].get().strip()
                if rg:
                    new['record_gates'] = [int(x) for x in rg.split(',')
                                           if x.strip().isdigit()]
                sub = entries[('save_subdir', None)].get().strip()
                if sub:
                    new['save_subdir'] = sub
                return new
            except ValueError:
                status.config(text="All numeric fields must be numbers "
                                   "(or blank to inherit the GUI value)")
                return None

        result = {}

        def on_ok():
            data = collect()
            if data is not None:
                result.update(data)
                dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
            side="right", padx=4)
        ttk.Button(btns, text="OK", command=on_ok).pack(side="right", padx=4)
        dlg.wait_window()
        return result or None

    def run_sequence(self):
        if not self._sequence_steps:
            messagebox.showerror("Error", "No sequence loaded (Load sequence...)")
            return
        if not self.bias_inst:
            messagebox.showerror("Error", "Bias instrument not connected "
                                          "(must be Keithley 2450)")
            return
        try:
            self._collect_sweep_params()  # validate the GUI defaults early
        except ValueError as e:
            messagebox.showerror("Error", f"Fix the Sweep setup first ({e})")
            return
        if not messagebox.askyesno(
                "Run sequence",
                f"Run {len(self._sequence_steps)} step(s)?\n"
                "ABORT stops the current sweep and the whole sequence."):
            return
        self._seq_abort = False
        self.set_busy()
        self.btn_seq_run.config(state="disabled")
        threading.Thread(target=self._run_sequence_thread,
                         args=(list(self._sequence_steps),), daemon=True).start()

    def _run_sequence_thread(self, steps):
        """Run every sequence step on this worker thread.

        Each sweep step reuses _run_sweep_thread via _collect_sweep_params
        (GUI values as defaults, step values as overrides), so every safety
        feature (magnet rate clamping, slow gate ramps, compliances) applies
        exactly as in a manual sweep. _run_sweep_thread CLEARS stop_event
        during its return-to-zero ramps, so the sequence-level abort intent
        is tracked separately in _seq_abort.
        """
        try:
            n_steps = len(steps)
            for si, step in enumerate(steps):
                if self._seq_abort or self.stop_event.is_set():
                    break
                name = str(step.get('name', f'step {si + 1}'))
                reps = max(1, int(step.get('repeat', 1)))
                stype = str(step.get('type', 'sweep'))
                if stype == 'wait':
                    secs = float(step.get('seconds', 0))
                    self.log(f"[Sequence {si + 1}/{n_steps}] '{name}': "
                             f"waiting {secs:g} s")
                    end_t = time.time() + secs
                    while time.time() < end_t and not self._seq_abort:
                        time.sleep(min(0.5, max(0.0, end_t - time.time())))
                    continue
                for rep in range(1, reps + 1):
                    if self._seq_abort or self.stop_event.is_set():
                        break
                    suffix = f" [{rep}/{reps}]" if reps > 1 else ""
                    self._progress(f"Sequence {si + 1}/{n_steps}{suffix}: {name}")
                    self.log(f"[Sequence {si + 1}/{n_steps}] '{name}'{suffix}")
                    try:
                        params = self._collect_sweep_params(step)
                    except ValueError as e:
                        self.log(f"Sequence step '{name}' invalid: {e} "
                                 "— sequence stopped")
                        self._progress(f"Error: {e}")
                        return
                    self._run_sweep_thread(params)
            if self._seq_abort or self.stop_event.is_set():
                self.log("Sequence aborted")
                self._progress("Sequence aborted")
            else:
                self.log("Sequence complete!")
                self._progress("Sequence complete")
        except Exception as e:
            self.log(f"Sequence error: {e}")
            self._progress(f"Error: {e}")
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror(
                "Sequence Error", err_msg))
        finally:
            self._seq_abort = False
            self.stop_event.clear()
            self.root.after(0, lambda: self.btn_seq_run.config(state="normal"))

    def _run_single_bias_sweep(self, p):
        """Configure + run one hysteresis sweep on the Keithley bias. Returns arrays."""
        if p['sweep_type'] == "iv":
            self.log(f"Bias sweep: 0 -> {p['sp1']} mV -> {p['sp2']} mV -> 0")
            self.log("Step 1/3: configuring instrument (reset + clist)...")
            self.bias_inst.create_hysteresis_voltage_sweep_config_list(
                Sp1=p['sp1'], Sp2=p['sp2'], step=p['step'],
                curr_range=p['compliance'])
            self.log("Step 2/3: running sweep + reading buffer (blocking)...")
            output = self.bias_inst.run_clist_sweep(delay=p['delay'], sweep_type='voltage')
            self.log("Sweep data received.")
        else:
            self.log(f"Bias sweep: 0 -> {p['sp1']} A -> {p['sp2']} A -> 0")
            self.log("Step 1/3: configuring instrument (reset + clist)...")
            self.bias_inst.create_hysteresis_current_sweep_config_list(
                Sp1=p['sp1'], Sp2=p['sp2'], step=p['step'],
                volt_range=p['compliance'])
            self.log("Step 2/3: running sweep + reading buffer (blocking)...")
            output = self.bias_inst.run_clist_sweep(delay=p['delay'], sweep_type='current')
            self.log("Sweep data received.")

        data = [float(x) for x in output.split(',')]
        measured = np.array(data[0::3])
        sourced = np.array(data[1::3])
        times = np.array(data[2::3])
        return measured, sourced, times

    def _document_field(self):
        """Read the magnet field once (post-sweep). None when unavailable."""
        if self.magnet.inst is None:
            self.log("Note: magnet not connected — no field column")
            return None
        self._progress("Reading magnet field ...")
        field = self.magnet.read_field()
        if field is not None:
            self.log(f"Magnetic field: {field:.4f} T")
        else:
            self.log("Note: magnet field read failed — no field column")
        return field

    def _document_temperature(self):
        """Read the cryostat temperatures once (post-sweep).

        Independent of the magnet. None when the ICElog is unreadable.
        """
        try:
            temps = read_ice_temperature()
            self.log("Temperatures (50K/4K/VTI/probe): "
                     + " / ".join(f"{v:.2f} K" for v in temps))
            return temps
        except Exception as e:
            self.log(f"Note: temperature log unavailable ({e}) "
                     "— no temperature columns")
            return None

    def _magnet_progress(self, field, target, i=0, n=1):
        """Progress hook for field ramps (runs on the worker thread)."""
        self.magnet.update_field_status(field)
        self._progress(f"Field ramp: B = {field:.3f} T -> {target:.3f} T "
                       f"(sweep {i + 1}/{n})")

    def start_manual_field_ramp(self):
        """Manual button: sweep the magnet to the target field at the rate."""
        if self.magnet.inst is None:
            messagebox.showerror("Error", "Magnet not connected")
            return
        try:
            rate = abs(float(self.ent_mag_rate.get()))
            target = float(self.ent_mag_target.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid rate/target values")
            return
        if rate <= 0:
            messagebox.showerror("Error", "Field sweep rate must be > 0")
            return
        self.saved_params.update({'mag_rate': str(rate),
                                  'mag_target': self.ent_mag_target.get()})
        self.btn_mag_go.config(state="disabled")
        self.set_busy()
        self.log(f"Sweeping field to {target} T at {rate} T/min ...")

        def worker():
            try:
                ok = self.magnet.go_to_field(
                    target, rate,
                    progress=lambda f: self._magnet_progress(f, target))
                if self.stop_event.is_set():
                    self.log("Field ramp aborted (field left where it was)")
                elif ok:
                    self.log(f"Field ramp complete: B = {target:.4f} T")
                else:
                    self.log("Field ramp failed")
            except Exception as e:
                self.log(f"Field ramp error: {e}")
            finally:
                self.root.after(0, self.restore_after_field_ramp)

        threading.Thread(target=worker, daemon=True).start()

    def restore_after_field_ramp(self):
        self.btn_mag_go.config(state="normal")
        self.btn_abort.config(state="disabled")
        self.btn_run.config(state="normal")
        for ch in self.gates:
            ch.btn_ramp.config(state="normal")

    def _ramp_gates_together(self, targets, step_v, delay, start_from=None):
        """Ramp Gate 1 and Gate 2 in lock-step (interleaved small steps).

        targets: (vg1, vg2); None entries / unconnected gates are skipped.
        Blocking; aborts if stop_event is set.
        """
        seqs = {}
        for gi in (1, 2):
            tgt = targets[gi - 1]
            ch = self.gates[gi - 1]
            if tgt is None or ch.inst is None:
                continue
            if start_from is not None and start_from[gi - 1] is not None:
                start = start_from[gi - 1]
            else:
                start = ch.read_level()
            if start is None:
                start = 0.0
            seq = ramp_sequence(start, tgt, step_v)
            if seq:
                seqs[gi] = seq

        while seqs:
            for gi in list(seqs):
                v = seqs[gi].pop(0)
                self.gates[gi - 1].set_level(v)
                self.root.after(0, lambda gi=gi, v=v: self.gates[gi - 1].lbl_status.config(
                    text=f"Gate {gi}: {v:.4f} V"))
            for gi in [g for g, s in seqs.items() if not s]:
                del seqs[gi]
            if self.stop_event.is_set():
                return
            time.sleep(delay)

    def _run_sweep_thread(self, p):
        try:
            sweep_type = p['sweep_type']
            mode = p['mode']
            points = p['points']
            fields = p.get('fields') or []
            seq = fields if mode == "field" else points
            gate_loop = mode not in ("none", "field")
            # gates that are actually driven during this run (held gates included)
            involved = [gi for gi in (1, 2)
                        if any(pt[gi - 1] is not None for pt in points)]

            if mode == "field":
                self.log(f"Field loop: {len(seq)} bias sweeps, "
                         f"{seq[0]:.3f} T -> {seq[-1]:.3f} T at "
                         f"{p['field_rate']:g} T/min"
                         + (" (programmed field recorded; manual readback skipped)"
                            if p.get('doc_field') else ""))
            elif gate_loop:
                self.log(f"Gate loop mode '{mode}': {len(points)} bias sweeps")
            elif involved:
                self.log("Single sweep with gate target(s) applied")
            if involved:
                # configure every involved gate, then ramp slowly to the first point
                for gi in involved:
                    vals = [pt[gi - 1] for pt in points]
                    self.gates[gi - 1].configure_source(
                        p[f'g{gi}_compliance'], p[f'g{gi}_nplc'],
                        max_abs_v=max(abs(v) for v in vals))
                for gi in involved:
                    ch = self.gates[gi - 1]
                    if not ch.output_on():
                        ch.set_level(0.0)
                        ch.enable(True)
                        time.sleep(0.2)

                first = points[0]
                self.log("Ramping gates slowly to initial values ...")
                if mode == "movement":
                    self._ramp_gates_together(first, p['loop_ramp_step'],
                                              p['loop_ramp_delay'])
                else:
                    for gi in involved:
                        if first[gi - 1] is not None:
                            self.log(f"Ramping Gate {gi} to {first[gi - 1]} V ...")
                            self.gates[gi - 1].ramp_to(first[gi - 1],
                                                       p['loop_ramp_step'],
                                                       p['loop_ramp_delay'])
                if self.stop_event.is_set():
                    self.log("Aborted before first sweep")
                    return

            os.makedirs(p['save_dir'], exist_ok=True)

            for i, pt in enumerate(seq):
                if self.stop_event.is_set():
                    break

                if mode == "field":
                    # ramp the magnet from the previous field point to this one
                    prev_f = seq[i - 1] if i > 0 else None
                    if prev_f is None or pt != prev_f:
                        self.log(f"Sweeping field -> {pt:.3f} T ...")
                        self._progress(f"Sweep {i + 1}/{len(seq)}: "
                                       f"ramping to B = {pt:.3f} T")
                        self.magnet.go_to_field(
                            pt, p.get('field_rate', 0.1),
                            progress=lambda f: self._magnet_progress(f, pt, i,
                                                                     len(seq)))
                        if self.stop_event.is_set():
                            break
                elif i > 0:
                    prev = points[i - 1] if i > 0 else None
                    if mode == "movement":
                        self.log(f"Moving gates -> G1={pt[0]} V, G2={pt[1]} V ...")
                        self._ramp_gates_together(pt, p['loop_ramp_step'],
                                                  p['loop_ramp_delay'], start_from=prev)
                    else:
                        for gi in (1, 2):
                            if pt[gi - 1] is None:
                                continue
                            if prev is not None and pt[gi - 1] == prev[gi - 1]:
                                continue  # held gate: already at this value
                            self.log(f"Ramping Gate {gi} {prev[gi - 1]} V "
                                     f"-> {pt[gi - 1]} V ...")
                            self.gates[gi - 1].ramp_to(pt[gi - 1], p['loop_ramp_step'],
                                                       p['loop_ramp_delay'])
                    if self.stop_event.is_set():
                        break

                if involved:
                    desc = ", ".join(f"G{gi}={pt[gi - 1]} V"
                                     for gi in (1, 2) if pt[gi - 1] is not None)
                    self._progress(f"Sweep {i + 1}/{len(points)} @ {desc}")
                    time.sleep(p['settle'])
                else:
                    self._progress("Running sweep...")

                measured, sourced, times = self._run_single_bias_sweep(p)

                # Magnetic field and cryostat temperature are independent
                # slow readings (magnet ~0.5 s/serial query, temperature
                # from the ICElog file): each is documented once, AFTER the
                # sweep is over, only when its own toggle is checked, and
                # stored as extra columns like the gate voltages.
                field_val, temp_vals = None, None
                if p.get('doc_field') and mode != "field":
                    field_val = self._document_field()
                if p.get('doc_temp'):
                    temp_vals = self._document_temperature()

                # single-gate loops: optionally read the held gate's ACTUAL
                # voltage once per sweep (its programmed target is already
                # recorded as a constant column)
                readback_val = None
                held_gi = {"gate1": 2, "gate2": 1}.get(mode)
                if p.get('held_readback') and held_gi is not None:
                    ch = self.gates[held_gi - 1]
                    if ch.inst is None:
                        self.log(f"Note: Gate {held_gi} not connected — "
                                 "no readback column")
                    elif not ch.output_on():
                        # measuring with the output OFF would record a
                        # meaningless ~0 V / floating reading
                        self.log(f"Note: Gate {held_gi} output is OFF — "
                                 "no readback column")
                    else:
                        readback_val = ch.measure_voltage()
                        if readback_val is not None:
                            self.log(f"Gate {held_gi} voltage: "
                                     f"{readback_val:.4f} V")
                        else:
                            self.log(f"Note: Gate {held_gi} readback failed "
                                     "— no readback column")

                # plain sweeps: document the manually-set gate voltages. The
                # sweep never drives the gates — one true voltage measurement
                # per recorded gate, post-sweep, only when connected + output
                # on. The recorded value goes into Gate{n}Voltage(V).
                gate_readings = {}
                if mode == "none" and p.get('record_gates'):
                    for gi in p['record_gates']:
                        ch = self.gates[gi - 1]
                        if ch.inst is None:
                            self.log(f"Note: Gate {gi} not connected — "
                                     "no voltage column")
                        elif not ch.output_on():
                            # measuring with the output OFF would record a
                            # meaningless ~0 V / floating reading
                            self.log(f"Note: Gate {gi} output is OFF — "
                                     "no voltage column")
                        else:
                            v = ch.measure_voltage()
                            if v is None:
                                self.log(f"Note: Gate {gi} voltage read "
                                         "failed — no voltage column")
                            else:
                                gate_readings[gi] = v
                                self.log(f"Gate {gi} voltage: {v:.4f} V")

                # sequential file number within the save folder (pymeasure-style:
                # IV_000, IV_001, ... continuing past existing files)
                num = next_file_number(p['save_dir'], sweep_type)
                vg1, vg2 = pt if mode != "field" else (None, None)
                gate_str = ""
                if vg1 is not None:
                    gate_str += f"_G1_{vg1:.3f}V"
                if vg2 is not None:
                    gate_str += f"_G2_{vg2:.3f}V"
                if field_val is not None:
                    gate_str += f"_B_{field_val:.3f}T"
                if mode == "field":
                    gate_str += f"_B_{pt:.3f}T"
                if temp_vals is not None:
                    # fourth temperature = probe temp: one tag for the file name
                    gate_str += f"_T_{temp_vals[3]:.2f}K"
                if sweep_type == "iv":
                    name = f"IV_{num:03d}{gate_str}_Sp1_{p['sp1']}mV_Sp2_{p['sp2']}mV"
                    header, x, y = "Voltage(V),Current(A),Time(s)", sourced, measured
                else:
                    name = f"VI_{num:03d}{gate_str}_Sp1_{p['sp1']}A_Sp2_{p['sp2']}A"
                    header, x, y = "Current(A),Voltage(V),Time(s)", sourced, measured

                # gate voltages recorded as extra columns so each row is self-describing
                cols = [x, y, times]
                if vg1 is not None:
                    header += ",Gate1Voltage(V)"
                    cols.append(np.full(x.size, vg1))
                if vg2 is not None:
                    header += ",Gate2Voltage(V)"
                    cols.append(np.full(x.size, vg2))
                # plain sweeps: manually-set gate voltages (true measurement
                # taken once, after the sweep)
                if gate_readings.get(1) is not None:
                    header += ",Gate1Voltage(V)"
                    cols.append(np.full(x.size, gate_readings[1]))
                if gate_readings.get(2) is not None:
                    header += ",Gate2Voltage(V)"
                    cols.append(np.full(x.size, gate_readings[2]))
                # magnetic field + cryostat temperatures: one reading taken
                # after the sweep finished (slow instruments), repeated on
                # every row so each file is self-describing
                if field_val is not None:
                    header += ",field(T)"
                    cols.append(np.full(x.size, field_val))
                if mode == "field":
                    # programmed loop field, one reading per point
                    header += ",field(T)"
                    cols.append(np.full(x.size, pt))
                if temp_vals is not None:
                    for col_name, v in zip(TEMP_COLUMNS, temp_vals):
                        header += f",{col_name}"
                        cols.append(np.full(x.size, v))
                if readback_val is not None:
                    header += f",Gate{held_gi}Readback(V)"
                    cols.append(np.full(x.size, readback_val))

                csv_path = os.path.join(p['save_dir'], name + ".csv")
                np.savetxt(csv_path, np.vstack(cols).T, delimiter=',', header=header)
                self.log(f"Saved: {name}.csv")

            # After a loop, gates (0 V) and field (0 T) are returned to zero
            # ONLY when the user checked the matching 'Return ... to 0' box
            # (gates: Sweep setup tab, field: Magnet control tab).
            # Single-sweep gate targets always stay (they are manual control).
            if mode == "field":
                if p.get('return_field'):
                    # sweep the field back to zero at the loop's rate
                    if not self.stop_event.is_set():
                        self.log("Sweeping field back to 0 T ...")
                    self.stop_event.clear()
                    self.magnet.go_to_field(
                        0.0, p.get('field_rate', 0.1),
                        progress=lambda f: self._magnet_progress(f, 0.0, 0, 1))
                else:
                    self.log(f"Field loop done — field left at {seq[-1]:.3f} T "
                             "(return-to-0 not selected)")
            elif gate_loop and involved:
                if p.get('return_gates'):
                    if not self.stop_event.is_set():
                        self.log("Ramping gates back to 0 V ...")
                    self.stop_event.clear()
                    if mode == "movement":
                        self._ramp_gates_together((0.0, 0.0), p['loop_ramp_step'],
                                                  p['loop_ramp_delay'])
                    else:
                        for gi in involved:
                            self.gates[gi - 1].ramp_to(0.0, p['loop_ramp_step'],
                                                       p['loop_ramp_delay'])
                else:
                    desc = ", ".join(f"Gate {gi} at {points[-1][gi - 1]} V"
                                     for gi in involved)
                    self.log(f"Gate loop done — left {desc} "
                             "(return-to-0 not selected)")
            elif involved:
                desc = ", ".join(f"Gate {gi} at {points[-1][gi - 1]} V"
                                 for gi in involved)
                self.log(f"Single sweep done — left {desc} "
                         "(use Ramp Gate to change)")

            if self.stop_event.is_set():
                self.log("Sweep aborted")
                self._progress("Aborted")
            else:
                self._progress("Complete")
                self.log("Sweep complete!")

        except Exception as e:
            self.log(f"Sweep error: {e}")
            self._progress(f"Error: {e}")
            # capture the message now: the except variable is deleted when
            # the block exits, so a deferred lambda would raise NameError
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Sweep Error", err_msg))
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, lambda: self.btn_abort.config(state="disabled"))
            for ch in self.gates:
                self.root.after(0, lambda ch=ch: ch.btn_ramp.config(state="normal"))

    def apply_theme(self, theme):
        """Switch the palette LIVE: ttk widgets follow _setup_style instantly;
        the plain tk widgets whose colors were baked at creation (tab
        canvases, log text, RUN/ABORT, header labels, status chips) are
        re-configured here. No window restart needed."""
        global COLORS
        self.theme = theme
        COLORS = palette_for(theme)
        self.root.configure(bg=COLORS["background"])
        self._setup_style()  # restyles every ttk widget in place
        self.lbl_title.config(foreground=COLORS["accent"])
        self.lbl_subtitle.config(foreground=COLORS["muted_text"])
        self.btn_theme.config(text=f"Theme: {theme.capitalize()}")
        self.log_text.config(bg=COLORS["log_background"],
                             fg=COLORS["log_text"],
                             insertbackground=COLORS["log_cursor"],
                             selectbackground=COLORS["log_selection"])
        for cv in self._tab_canvases:
            cv.config(bg=COLORS["canvas"])
        self.btn_run.config(bg=COLORS["run"],
                            activebackground=COLORS["run_hover"])
        self.btn_seq_run.config(bg=COLORS["run"],
                                activebackground=COLORS["run_hover"])
        self.btn_abort.config(bg=COLORS["abort"],
                              activebackground=COLORS["abort_hover"])
        # status chips repaint from their current instrument state
        self.update_bias_status()
        for ch in self.gates:
            ch.update_status()

    def toggle_theme(self):
        """Switch light/dark theme instantly; saved to instrument_overrides.json."""
        new_theme = "dark" if self.theme == "light" else "light"
        save_theme_setting(new_theme)
        self.apply_theme(new_theme)
        self.log(f"Theme switched to {new_theme}")

    def cleanup(self):
        self.stop_event.set()
        self.disconnect_bias()
        for ch in self.gates:
            ch.disconnect()
        self.magnet.disconnect()


def main():
    root = tk.Tk()
    # Compact layout for a 14-inch laptop: honor available screen space.
    # Vertical scrollbars keep every option accessible at higher scaling.
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    width = min(1280, max(900, screen_w - 80))
    height = min(680, max(520, screen_h - 95))
    root.geometry(f"{width}x{height}")
    root.minsize(min(760, width), min(520, height))
    app = IVVISweeperImproved(root)

    def on_closing():
        try:
            app.cleanup()  # stop threads, close connections + COM port
        except Exception:
            pass
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
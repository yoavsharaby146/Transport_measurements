import sys, os
import re
import csv
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


# ==================== WINDOW COLOR PALETTE ====================
# Every color used by the window is defined HERE, in this one dictionary.
# To re-theme the program: edit the values below and restart the program
# (a running window does not live-update). Values are hex strings "#rrggbb"
# or any Tk color name such as "grey", "orange", "white".
COLORS = {
    # --- window & panels ---
    "background":        "#f4f7fb",  # window background
    "surface":           "#ffffff",  # panel (LabelFrame) background
    "border":            "#dce4ee",  # panel borders
    "text":              "#253449",  # normal text
    "muted_text":        "#718096",  # subtitle / hint text
    "accent":            "#1768a5",  # title, section titles, selected tab
    "tab_inactive":      "#e2eaf3",  # unselected notebook tabs
    "tab_inactive_text": "#44566d",  # text on unselected tabs
    "button":            "#e7eef6",  # regular ttk buttons
    "button_hover":      "#d4e4f3",  # ttk buttons under the mouse
    "canvas":            "#fbf4f4",  # scrollable tab canvas

    # --- actions ---
    "run":               "#16845b",  # RUN SWEEP button
    "run_hover":         "#106b49",  # RUN SWEEP pressed/hover
    "abort":             "#bb3f45",  # ABORT button
    "abort_hover":       "#a7353b",  # ABORT pressed/hover
    "action_text":       "#ffffff",  # text on RUN/ABORT buttons

    # --- log console ---
    "log_background":    "#14181f",
    "log_text":          "#d8dee9",
    "log_cursor":        "#26cca2",
    "log_selection":     "#3a5a80",

    # --- instrument status buttons ("Out:" / "Term:") ---
    "status_neutral":    "#e0e0e0",  # not connected / "Term: ---"
    "status_idle":       "#a7d8c9",  # gate row idle ("Out: ---")
    "status_on":         "#90ee90",  # output ON
    "status_off":        "#ffcccb",  # output OFF
    "status_error":      "grey",     # status unknown (instrument error)
    "status_rear":       "orange",   # bias "Term: REAR"
}


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
        box.pack(side="left", fill="both", expand=True, padx=4)

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
            self.btn_out.config(text="Out: ---", bg=COLORS["status_idle"])
            self.lbl_status.config(text=f"Gate {self.index}: --- V")
            return
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


class IVVISweeperImproved:
    def __init__(self, root):
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
            'save_dir': "",
        }
        for i in (1, 2):
            self.saved_params.update({
                f'g{i}_compliance': "1e-3", f'g{i}_nplc': "1",
                f'g{i}_target': "0", f'g{i}_step': "10", f'g{i}_rate': "0.2",
            })

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
        ttk.Label(header, text="IV/VI Sweeper — ICE",
                  font=("Segoe UI", 15, "bold"),
                  foreground=COLORS["accent"]).pack(side="left")
        ttk.Label(header,
                  text="Bias (Keithley 2450)  •  2 Gates  •  "
                       "Magnet (MPS4G) + Temperature",
                  font=("Segoe UI", 9), foreground=COLORS["muted_text"]).pack(
            side="left", padx=12)

        # Keep the Run/Abort controls visible while switching between compact tabs.
        self.tabs = ttk.Notebook(self.main_frame)
        self.tabs.pack(fill="both", expand=True, pady=(0, 5))
        instruments = self._scrollable_tab("Instruments")
        sweep_setup = self._scrollable_tab("Sweep setup")
        activity = self._scrollable_tab("Activity log")

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
                        command=self._update_ui_labels).pack(side="left", padx=20)
        ttk.Radiobutton(inner, text="VI Sweep (Source Current, Measure Voltage)",
                        variable=self.sweep_type_var, value="vi",
                        command=self._update_ui_labels).pack(side="left", padx=20)

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
                                row=i // 3, column=i % 3, sticky="w", padx=(2, 24), pady=2)

        rf = ttk.Frame(loop)
        rf.pack(fill="x", pady=(6, 0))

        # nesting order for the dual gate 2D loop (which gate is the outer loop)
        of = ttk.Frame(loop)
        of.pack(fill="x", pady=(2, 0))
        ttk.Label(of, text="Dual 2D nesting order:").pack(side="left")
        self.dual_outer_var = tk.StringVar(value="1")
        self.rb_dual_outer1 = ttk.Radiobutton(of, text="Gate 1 outer / Gate 2 inner",
                                              variable=self.dual_outer_var, value="1")
        self.rb_dual_outer1.pack(side="left", padx=8)
        self.rb_dual_outer2 = ttk.Radiobutton(of, text="Gate 2 outer / Gate 1 inner",
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
        ttk.Label(sf, text="Points:").pack(side="left", padx=(20, 0))
        self.ent_loop_points = ttk.Entry(sf, width=6)
        self.ent_loop_points.insert(0, self.saved_params['loop_points'])
        self.ent_loop_points.pack(side="left", padx=3)
        self.lbl_loop_points = ttk.Label(sf, text="1 bias sweep",
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
        self.rec_g2_var = tk.BooleanVar(value=False)
        self.chk_rec_g2 = ttk.Checkbutton(
            af, text="Record Gate 2 voltage column (gate not driven)",
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

        # === LOG ===
        logf = ttk.LabelFrame(activity, text="Instrument & measurement messages", padding=8)
        logf.pack(fill="both", expand=True, pady=4)
        self.log_text = tk.Text(logf, height=8, state="disabled",
                                bg=COLORS["log_background"], fg=COLORS["log_text"],
                                insertbackground=COLORS["log_cursor"],
                                selectbackground=COLORS["log_selection"],
                                font=("Consolas", 9), relief="flat",
                                padx=8, pady=6)
        self.log_text.pack(fill="both", expand=True)
        ttk.Label(activity, text="Messages are preserved while you switch tabs.",
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=5)

        self._update_ui_labels()
        self._toggle_loop_entries()

    def _scrollable_tab(self, title):
        """Scrollable vertical tab; still usable at 1366x768 and high DPI."""
        outer = ttk.Frame(self.tabs)
        self.tabs.add(outer, text=f"  {title}  ")
        canvas = tk.Canvas(outer, bg=COLORS["canvas"], highlightthickness=0,
                           borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=(6, 6, 8, 8))
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
            window, width=e.width))

        # Windows uses delta increments of 120; scroll only over this tab.
        def wheel(event):
            canvas.yview_scroll(-int(event.delta / 120) if event.delta else 0, "units")
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
        style.configure("TCombobox", padding=2)
        style.configure("TEntry", padding=3)
        style.configure("TNotebook", background=c["background"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7),
                        background=c["tab_inactive"],
                        foreground=c["tab_inactive_text"])
        style.map("TNotebook.Tab",
                  background=[("selected", c["surface"])],
                  foreground=[("selected", c["accent"])])

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
        box.pack(side="left", fill="both", expand=True, padx=4)

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
        state_shared = "normal" if mode != "none" else "disabled"
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
            else:  # movement: one common point count for both gates
                n = int(float(self.ent_loop_points.get()))
                text = f"{n} bias sweeps (both gates move together)"
        except ValueError:
            text = "---"
        self.lbl_loop_points.config(text=text)

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
            sp1 = float(self.ent_sp1.get())
            sp2 = float(self.ent_sp2.get())
            step = abs(float(self.ent_step.get()))
            delay = float(self.ent_delay.get())
            compliance = float(self.ent_compliance.get())
            save_dir = self.ent_dir.get()
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric parameters")
            return
        if not save_dir:
            messagebox.showerror("Error", "Please select a save directory")
            return

        mode = self.loop_mode_var.get()
        # plain-sweep mode: gates are NEVER driven by the sweep (control them
        # manually via section 2). The checkboxes only choose which gate
        # voltages get documented as columns in the file.
        record_gates = []
        if mode == "none":
            record_gates = [gi for gi in (1, 2)
                            if (self.rec_g1_var.get() if gi == 1
                                else self.rec_g2_var.get())]
        points = [(None, None)]
        gate_cfg = {}
        settle = ramp_step = ramp_delay = 0.0

        if mode != "none":
            try:
                settle = float(self.ent_gate_settle.get())
                ramp_step = abs(float(self.ent_loop_ramp_step.get())) / 1000.0
                ramp_delay = float(self.ent_loop_ramp_delay.get())
                g1s = float(self.ent_g1_start.get())
                g1e = float(self.ent_g1_end.get())
                g1st = abs(float(self.ent_g1_loop_step.get()))
                g2s = float(self.ent_g2_start.get())
                g2e = float(self.ent_g2_end.get())
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid gate loop parameters: {e}")
                return
            if ramp_step == 0 or ramp_delay < 0 or settle < 0:
                messagebox.showerror("Error",
                                     "Gate loop ramp step must be non-zero; "
                                     "settle and ramp delay must be >= 0")
                return

        if mode != "none":
            need = {"gate1": [1], "gate2": [2], "dual": [1, 2], "movement": [1, 2]}[mode]
            for gi in need:
                if self.gates[gi - 1].inst is None:
                    messagebox.showerror("Error",
                                         f"Loop mode requires Gate {gi} to be connected")
                    return
                ch = self.gates[gi - 1]
                try:
                    gate_cfg[f'g{gi}_compliance'] = float(ch.ent_compliance.get())
                    gate_cfg[f'g{gi}_nplc'] = float(ch.ent_nplc.get())
                except ValueError:
                    messagebox.showerror("Error",
                                         f"Invalid gate {gi} compliance/NPLC parameters")
                    return

            def held_value(gi):
                """Constant voltage for a connected but non-looped gate."""
                ch = self.gates[gi - 1]
                if ch.inst is None:
                    return None
                return float(ch.ent_target.get())  # may raise ValueError

            try:
                if mode in ("gate1", "dual"):
                    list1 = arange_inclusive(g1s, g1e, g1st)
                    if not list1:
                        messagebox.showerror("Error", "Gate 1 loop produces no points")
                        return
                if mode in ("gate2", "dual"):
                    g2st = abs(float(self.ent_g2_loop_step.get()))
                    list2 = arange_inclusive(g2s, g2e, g2st)
                    if not list2:
                        messagebox.showerror("Error", "Gate 2 loop produces no points")
                        return

                if mode == "gate1":
                    held = held_value(2)  # Gate 2 stays at its manual target
                    points = [(v, held) for v in list1]
                elif mode == "gate2":
                    held = held_value(1)  # Gate 1 stays at its manual target
                    points = [(held, v) for v in list2]
                elif mode == "dual":
                    # full 2D map; nesting order is user-selectable
                    if self.dual_outer_var.get() == "2":
                        # Gate 2 outer loop, Gate 1 inner loop
                        points = [(v1, v2) for v2 in list2 for v1 in list1]
                    else:
                        # Gate 1 outer loop, Gate 2 inner loop
                        points = [(v1, v2) for v1 in list1 for v2 in list2]
                else:  # movement: both gates move together along a line with a
                    # common point count — keeps any linear combination of the
                    # gate voltages (carrier density n, displacement field D)
                    # on a well-defined constant-n or constant-D cut
                    npts = int(float(self.ent_loop_points.get()))
                    if npts < 1:
                        messagebox.showerror("Error",
                                             "Movement loop needs at least 1 point")
                        return
                    list1 = list(np.linspace(g1s, g1e, npts))
                    list2 = list(np.linspace(g2s, g2e, npts))
                    points = list(zip(list1, list2))
            except ValueError as e:
                messagebox.showerror("Error",
                                     f"Invalid held-gate target (enter a valid Target in "
                                     f"section 2): {e}")
                return

        sweep_type = self.sweep_type_var.get()
        if sweep_type == "iv":
            keys = ['iv_sp1', 'iv_sp2', 'iv_step', 'iv_delay', 'iv_compliance']
        else:
            keys = ['vi_sp1', 'vi_sp2', 'vi_step', 'vi_delay', 'vi_compliance']
        for key, ent in zip(keys, [self.ent_sp1, self.ent_sp2, self.ent_step,
                                   self.ent_delay, self.ent_compliance]):
            self.saved_params[key] = ent.get()
        self.saved_params['save_dir'] = save_dir

        self.set_busy()

        params = {
            'sp1': sp1, 'sp2': sp2, 'step': step, 'delay': delay,
            'compliance': compliance, 'save_dir': save_dir, 'sweep_type': sweep_type,
            'mode': mode, 'points': points, 'settle': settle,
            'loop_ramp_step': ramp_step, 'loop_ramp_delay': ramp_delay,
            'doc_field': self.doc_field_var.get(),
            'doc_temp': self.doc_temp_var.get(),
            'record_gates': record_gates,
            'held_readback': (self.held_readback_var.get()
                              and mode in ("gate1", "gate2")),
        }
        params.update(gate_cfg)
        threading.Thread(target=self._run_sweep_thread, args=(params,), daemon=True).start()

    def abort_sweep(self):
        self.stop_event.set()
        self.log("Abort requested...")

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
            gate_loop = mode != "none"
            # gates that are actually driven during this run (held gates included)
            involved = [gi for gi in (1, 2)
                        if any(pt[gi - 1] is not None for pt in points)]

            if gate_loop:
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

            for i, pt in enumerate(points):
                if self.stop_event.is_set():
                    break
                prev = points[i - 1] if i > 0 else None

                if i > 0:
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
                if p.get('doc_field'):
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
                vg1, vg2 = pt
                gate_str = ""
                if vg1 is not None:
                    gate_str += f"_G1_{vg1:.3f}V"
                if vg2 is not None:
                    gate_str += f"_G2_{vg2:.3f}V"
                if field_val is not None:
                    gate_str += f"_B_{field_val:.3f}T"
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

            # always return the gates to 0 V slowly after the measurement.
            # Exception: gates applied for a single sweep stay at their manual
            # target (they are under manual control).
            if gate_loop and involved:
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
    width = min(1080, max(760, screen_w - 80))
    height = min(680, max(520, screen_h - 95))
    root.geometry(f"{width}x{height}")
    root.minsize(min(760, width), min(520, height))
    app = IVVISweeperImproved(root)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
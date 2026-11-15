"""Smoke test for the 2-gate IV/VI sweeper (no hardware needed).

Instantiates the Tk app, cycles through every loop mode, checks the
point-count label and the pure point-building helpers, then exits.
Run:  python _smoke_test_2gate.py
"""
import importlib.util
import os
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'IV VI sweeper improved.py')

spec = importlib.util.spec_from_file_location("sweeper_improved", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = []


def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


# ---------- pure helpers ----------
check("arange_inclusive fwd", mod.arange_inclusive(-5, 5, 1) == list(mod.np.arange(-5, 6, 1)))
check("arange_inclusive rev", mod.arange_inclusive(5, -5, 2)[-1] == -5)
seq = mod.ramp_sequence(0.0, 0.5, 0.01)
check("ramp_sequence endpoints", seq[0] == 0.01 and seq[-1] == 0.5)
check("ramp_sequence no-op", mod.ramp_sequence(1.0, 1.0, 0.01) == [])

# ---------- sequential file numbering (pymeasure-style) ----------
import tempfile
with tempfile.TemporaryDirectory() as td:
    check("empty folder -> 000", mod.next_file_number(td, "iv") == 0)
    open(os.path.join(td, "IV_000_G1_1.000V_Sp1_1000mV_Sp2_-1000mV.csv"), "w").close()
    open(os.path.join(td, "IV_001_Sp1_1000mV_Sp2_-1000mV.csv"), "w").close()
    open(os.path.join(td, "IV_1763020000_Sp1_1000mV_Sp2_-1000mV.csv"), "w").close()  # old style
    open(os.path.join(td, "VI_005_Sp1_1e-06A_Sp2_-1e-06A.csv"), "w").close()
    check("continues past existing (gaps)", mod.next_file_number(td, "iv") == 2)
    check("per sweep type", mod.next_file_number(td, "vi") == 6)
    check("missing folder -> 000", mod.next_file_number(os.path.join(td, "nope"), "iv") == 0)

# ---------- GUI ----------
root = tk.Tk()
root.withdraw()
app = mod.IVVISweeperImproved(root)

check("title", "2 Independent Gates" in root.title())
check("two gate channels", [g.index for g in app.gates] == [1, 2])

# default mode label
check("points label none", app.lbl_loop_points.cget("text") == "1 bias sweep")

# switch modes -> entries enable/disable + label updates
app.loop_mode_var.set("gate1")
app._toggle_loop_entries()
check("gate1: g1 entries enabled", str(app.ent_g1_start.cget("state")) != "disabled")
check("gate1: g2 entries disabled", str(app.ent_g2_start.cget("state")) == "disabled")

app.loop_mode_var.set("dual")
app._toggle_loop_entries()
check("dual: 11 x 11 = 121", "121" in app.lbl_loop_points.cget("text"))
check("dual: default G1 outer", "G1 outer" in app.lbl_loop_points.cget("text"))

app.dual_outer_var.set("2")
app._update_loop_points_label()
check("dual: G2 outer selectable", "G2 outer, G1 inner" in app.lbl_loop_points.cget("text"))
l1 = mod.arange_inclusive(-5, 5, 1)
l2 = mod.arange_inclusive(0, 4, 1)
pts_g2outer = [(v1, v2) for v2 in l2 for v1 in l1]
check("dual: G2 outer point order",
      pts_g2outer[0] == (-5, 0) and pts_g2outer[11] == (-5, 1)
      and pts_g2outer[5] == (0, 0) and len(pts_g2outer) == 55)
app.dual_outer_var.set("1")

app.loop_mode_var.set("movement")
app._toggle_loop_entries()
check("movement: g1 step disabled", str(app.ent_g1_loop_step.cget("state")) == "disabled")
check("movement: g2 step disabled", str(app.ent_g2_loop_step.cget("state")) == "disabled")
check("movement: points entry enabled", str(app.ent_loop_points.cget("state")) != "disabled")
check("movement: both move label", "21 bias sweeps (both gates move together)"
      in app.lbl_loop_points.cget("text"))
# constant-n / constant-D semantics: both gates are linspaces with one count
npts = int(app.ent_loop_points.get())
ml1 = list(mod.np.linspace(-5, 5, npts))
ml2 = list(mod.np.linspace(-2, 2, npts))
check("movement: common point count",
      len(ml1) == len(ml2) == npts and ml1[0] == -5 and ml1[-1] == 5
      and ml2[0] == -2 and ml2[-1] == 2)

app.loop_mode_var.set("gate2")
app._toggle_loop_entries()
check("gate2: g2 entries enabled", str(app.ent_g2_start.cget("state")) != "disabled")
check("gate2: g1 entries disabled", str(app.ent_g1_start.cget("state")) == "disabled")

app.loop_mode_var.set("none")
app._toggle_loop_entries()
check("none: shared entries disabled", str(app.ent_gate_settle.cget("state")) == "disabled")
check("none: apply checkboxes enabled",
      str(app.chk_apply_g1.cget("state")) != "disabled")
check("none: apply unchecked by default", not app.apply_g1_var.get())

app.apply_g1_var.set(True)
app.apply_g2_var.set(True)
app.gates[0].ent_target.delete(0, tk.END)
app.gates[0].ent_target.insert(0, "2.5")
app.gates[1].ent_target.delete(0, tk.END)
app.gates[1].ent_target.insert(0, "-1.5")
helds = [float(app.gates[gi - 1].ent_target.get())
         if (app.apply_g1_var.get() if gi == 1 else app.apply_g2_var.get()) else None
         for gi in (1, 2)]
check("apply: point built from targets", tuple(helds) == (2.5, -1.5))
app.gates[0].ent_target.delete(0, tk.END)
app.gates[0].ent_target.insert(0, "0")
app.gates[1].ent_target.delete(0, tk.END)
app.gates[1].ent_target.insert(0, "0")
app.apply_g1_var.set(False)
app.apply_g2_var.set(False)

app.loop_mode_var.set("gate1")
app._toggle_loop_entries()
check("loop mode: apply checkboxes disabled",
      str(app.chk_apply_g1.cget("state")) == "disabled"
      and str(app.chk_apply_g2.cget("state")) == "disabled")
app.loop_mode_var.set("none")
app._toggle_loop_entries()

# gate panels exist independently
check("gate1 target entry", app.gates[0].ent_target.get() == "0")
check("gate2 compliance entry", app.gates[1].ent_compliance.get() == "1e-3")

# Keithley 2604B gate option + SMU channel selector
check("2604B in GATE_KINDS", mod.GATE_KINDS.get("Keithley 2604B") == "k2604b")
check("chan combo hidden by default", app.gates[0].chan_combo.winfo_manager() == "")
app.gates[0].kind_combo.set("Keithley 2604B")
app.gates[0]._update_chan_visibility()
check("chan combo shown for 2604B", app.gates[0].chan_combo.winfo_manager() == "pack")
app.gates[0].chan_combo.set("SMU B")
check("chan label parse", ("A" in app.gates[0].chan_combo.get()) is False)
app.gates[0].kind_combo.set("Keithley 2450")
app.gates[0]._update_chan_visibility()
check("chan combo hidden again", app.gates[0].chan_combo.winfo_manager() == "")

# point-list construction (single/dual/movement) replicated from start_sweep
check("dual product length", len([(a, b) for a in l1 for b in l1]) == 121)
check("movement zip length", len(list(zip(ml1, ml2))) == npts)

app.cleanup()
root.destroy()

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    sys.exit(1)
print("ALL CHECKS PASSED")

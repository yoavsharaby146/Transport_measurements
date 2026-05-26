"""
RV / dV_dI  SEQUENCE BUILDER  —  GUI
======================================
Build a measurement sequence of RV + dV_dI block pairs.
Each voltage entry carries its own step size.
The global "Default step" pre-fills the field when adding entries.

Usage:
    python RV_dV_dI_sequence_generator_interactive.py
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ─────────────────────────────────────────────────────────────────
#   File writing
# ─────────────────────────────────────────────────────────────────

def generate_sequence(filepath: str,
                      voltage_entries: list[tuple[float, float]],   # (voltage, step_mv)
                      sweep_mode: str,
                      dc_bias_targets: list[float],
                      aux_step_mv: float) -> None:
    with open(filepath, 'w') as f:
        for v_target, v_step in voltage_entries:
            # RV block
            f.write(f'- "Measurement Type", "[\'RV\']"\n')
            f.write(f'-- "Target Voltage(V)", "[{v_target:g}]"\n')
            f.write(f'-- "Step size(mV)", "[{v_step:g}]"\n')

            # dV_dI block
            f.write(f'- "Measurement Type", "[\'dV_dI\']"\n')
            f.write(f'-- "Sweep Mode","[\'{sweep_mode}\']"\n')
            if sweep_mode == "Sweep and Return":
                bias_val = dc_bias_targets[0] if dc_bias_targets else 0
                f.write(f'-- "Auxiliary DC Bias Target  (V)", "[{bias_val:g}]"\n')
            else:
                bias_str = ",".join(f"{b:g}" for b in dc_bias_targets)
                f.write(f'-- "Auxiliary DC Bias Target  (V)", "[{bias_str}]"\n')
            f.write(f'-- "Target Voltage(V)", "[{v_target:g}]"\n')
            f.write(f'--- "Auxiliary step (mV)", "[{aux_step_mv:g}]"\n')


# ─────────────────────────────────────────────────────────────────
#   Main application window
# ─────────────────────────────────────────────────────────────────

SWEEP_MODES = ["Sweep to setpoint", "Sweep and Return"]


class SequenceBuilder(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("RV / dV_dI  Sequence Builder")
        self.geometry("980x640")
        self.minsize(780, 500)

        # list of (voltage: float, step_mv: float) tuples
        self.voltage_entries: list[tuple[float, float]] = []
        self.biases:          list[float] = []

        self._build_ui()
        self._refresh_voltage_list()
        self._refresh_bias_list()
        self._refresh_summary()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):

        # ── top settings bar ─────────────────────────────────────
        settings = tk.Frame(self, bg='#2b2b2b', pady=8)
        settings.pack(fill='x')

        def slbl(text):
            return tk.Label(settings, text=text, bg='#2b2b2b', fg='white',
                            font=('Arial', 10))

        slbl('  Default voltage step (mV):').pack(side='left')
        self._vstep_default_var = tk.StringVar(value='5')
        ttk.Entry(settings, textvariable=self._vstep_default_var, width=8).pack(side='left', padx=(2, 18))

        slbl('Sweep mode:').pack(side='left')
        self._sweep_var = tk.StringVar(value=SWEEP_MODES[0])
        sweep_cb = ttk.Combobox(settings, textvariable=self._sweep_var,
                                values=SWEEP_MODES, state='readonly', width=22)
        sweep_cb.pack(side='left', padx=(2, 18))
        sweep_cb.bind('<<ComboboxSelected>>', self._on_sweep_mode_change)

        slbl('Aux step (mV):').pack(side='left')
        self._aux_step_var = tk.StringVar(value='2')
        ttk.Entry(settings, textvariable=self._aux_step_var, width=8).pack(side='left', padx=(2, 0))

        # ── main area ────────────────────────────────────────────
        main = tk.Frame(self)
        main.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self._build_voltage_panel(main)

        ttk.Separator(main, orient='vertical').pack(side='left', fill='y', padx=10)

        self._build_bias_panel(main)

        ttk.Separator(main, orient='vertical').pack(side='left', fill='y', padx=10)

        self._build_summary_panel(main)

        # ── bottom bar ───────────────────────────────────────────
        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill='x')

        ttk.Label(bottom, text='Output file:').pack(side='left')
        self._filename_var = tk.StringVar(value='RV_dV_dI_sequence.txt')
        ttk.Entry(bottom, textvariable=self._filename_var, width=42).pack(side='left', padx=6)
        ttk.Button(bottom, text='Browse…', command=self._browse_save).pack(side='left', padx=2)
        ttk.Button(bottom, text='⚡  Generate File',
                   command=self._generate).pack(side='right', padx=4)

    # ── voltage panel ────────────────────────────────────────────

    def _build_voltage_panel(self, parent):
        frame = tk.Frame(parent)
        frame.pack(side='left', fill='both', expand=True)

        ttk.Label(frame, text='Target Voltages',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 6))

        # Single-add row: voltage + per-entry step
        row1 = ttk.Frame(frame)
        row1.pack(fill='x', pady=(0, 2))

        ttk.Label(row1, text='V (V):').pack(side='left')
        self._v_entry_var = tk.StringVar()
        v_entry = ttk.Entry(row1, textvariable=self._v_entry_var, width=8)
        v_entry.pack(side='left', padx=(2, 8))
        v_entry.bind('<Return>', lambda _: self._vstep_entry.focus_set())

        ttk.Label(row1, text='Step (mV):').pack(side='left')
        self._v_step_entry_var = tk.StringVar()
        # pre-fill from default when user clicks into the step field
        self._vstep_entry = ttk.Entry(row1, textvariable=self._v_step_entry_var, width=8)
        self._vstep_entry.pack(side='left', padx=(2, 8))
        self._vstep_entry.bind('<FocusIn>',  self._prefill_step)
        self._vstep_entry.bind('<Return>',   lambda _: self._add_voltage())

        ttk.Button(row1, text='Add', command=self._add_voltage).pack(side='left', padx=2)

        # Action buttons row
        row2 = ttk.Frame(frame)
        row2.pack(fill='x', pady=(2, 4))
        ttk.Button(row2, text='Reverse',  command=self._reverse_voltages).pack(side='left', padx=2)
        ttk.Button(row2, text='Clear all', command=self._clear_voltages).pack(side='left', padx=2)
        ttk.Button(row2, text='Set step → all',
                   command=self._apply_default_step_to_all).pack(side='left', padx=10)

        # Bulk-import row
        row3 = ttk.Frame(frame)
        row3.pack(fill='x', pady=(0, 6))
        ttk.Label(row3, text='Bulk V (comma-sep):').pack(side='left')
        self._bulk_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self._bulk_var, width=26).pack(side='left', padx=4)
        ttk.Button(row3, text='Import', command=self._bulk_import).pack(side='left')

        # Listbox + scrollbar
        lb_frame = tk.Frame(frame)
        lb_frame.pack(fill='both', expand=True)

        sb = ttk.Scrollbar(lb_frame, orient='vertical')
        self.v_listbox = tk.Listbox(lb_frame,
                                    yscrollcommand=sb.set,
                                    selectmode='single',
                                    font=('Consolas', 10),
                                    activestyle='dotbox',
                                    height=14)
        sb.config(command=self.v_listbox.yview)
        self.v_listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.v_listbox.bind('<Delete>', lambda _: self._delete_voltage())
        self.v_listbox.bind('<<ListboxSelect>>', self._on_v_select)

        # Move / delete / edit buttons
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_row, text='↑  Up',     command=self._move_v_up).pack(side='left', padx=2)
        ttk.Button(btn_row, text='↓  Down',   command=self._move_v_down).pack(side='left', padx=2)
        ttk.Button(btn_row, text='✕  Delete', command=self._delete_voltage).pack(side='left', padx=2)
        ttk.Button(btn_row, text='✎  Edit step',
                   command=self._edit_step).pack(side='left', padx=(12, 2))

    # ── bias panel ───────────────────────────────────────────────

    def _build_bias_panel(self, parent):
        frame = tk.Frame(parent, width=210)
        frame.pack(side='left', fill='y')
        frame.pack_propagate(False)

        self._bias_title_var = tk.StringVar(value='DC Bias Targets (V)')
        ttk.Label(frame, textvariable=self._bias_title_var,
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 6))

        add_row = ttk.Frame(frame)
        add_row.pack(fill='x', pady=(0, 6))
        self._b_entry_var = tk.StringVar()
        b_entry = ttk.Entry(add_row, textvariable=self._b_entry_var, width=9)
        b_entry.pack(side='left', padx=(0, 4))
        b_entry.bind('<Return>', lambda _: self._add_bias())
        ttk.Button(add_row, text='Add', command=self._add_bias).pack(side='left', padx=2)

        lb_frame = tk.Frame(frame)
        lb_frame.pack(fill='x')
        sb = ttk.Scrollbar(lb_frame, orient='vertical')
        self.b_listbox = tk.Listbox(lb_frame,
                                    yscrollcommand=sb.set,
                                    selectmode='single',
                                    font=('Consolas', 10),
                                    activestyle='dotbox',
                                    height=10)
        sb.config(command=self.b_listbox.yview)
        self.b_listbox.pack(side='left', fill='x', expand=True)
        sb.pack(side='right', fill='y')
        self.b_listbox.bind('<Delete>', lambda _: self._delete_bias())

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_row, text='↑', width=3, command=self._move_b_up).pack(side='left', padx=2)
        ttk.Button(btn_row, text='↓', width=3, command=self._move_b_down).pack(side='left', padx=2)
        ttk.Button(btn_row, text='✕', width=3, command=self._delete_bias).pack(side='left', padx=2)

        self._bias_note_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._bias_note_var,
                  foreground='#b07d00', font=('Arial', 8, 'italic'),
                  wraplength=195, justify='left').pack(anchor='w', pady=(8, 0))

    # ── summary panel ────────────────────────────────────────────

    def _build_summary_panel(self, parent):
        frame = tk.Frame(parent, width=160)
        frame.pack(side='left', fill='y')
        frame.pack_propagate(False)

        ttk.Label(frame, text='Summary',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 8))

        self._summary_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._summary_var,
                  font=('Consolas', 10), justify='left').pack(anchor='w')

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        ttk.Label(frame,
                  text="Del  → remove\n↑↓   → reorder\nReturn → add\n\n"
                       "Select entry then\n'Edit step' to change\nits step size.",
                  foreground='gray', font=('Arial', 8)).pack(anchor='w')

    # ── sweep mode ───────────────────────────────────────────────

    def _on_sweep_mode_change(self, event=None):
        mode = self._sweep_var.get()
        if mode == "Sweep and Return":
            self._bias_title_var.set('DC Bias Target (V)')
            self._bias_note_var.set('⚠ Sweep and Return: only the first listed value is used.')
        else:
            self._bias_title_var.set('DC Bias Targets (V)')
            self._bias_note_var.set('')
        self._refresh_bias_list()

    # ── voltage helpers ──────────────────────────────────────────

    def _prefill_step(self, event=None):
        """Pre-fill step field with default only if currently empty."""
        if not self._v_step_entry_var.get().strip():
            self._v_step_entry_var.set(self._vstep_default_var.get())

    def _on_v_select(self, event=None):
        """When user selects a listbox row, load its values into the entry fields."""
        idx = self._v_selected()
        if idx is None:
            return
        v, s = self.voltage_entries[idx]
        self._v_entry_var.set(f'{v:g}')
        self._v_step_entry_var.set(f'{s:g}')

    def _refresh_voltage_list(self):
        self.v_listbox.delete(0, tk.END)
        for i, (v, s) in enumerate(self.voltage_entries):
            self.v_listbox.insert(tk.END, f"  {i+1:>3}.  {v:>8g} V    step: {s:g} mV")
        self._refresh_summary()

    def _parse_v_and_step(self) -> tuple[float, float] | None:
        """Parse and validate the voltage and step fields. Returns (v, step) or None."""
        raw_v = self._v_entry_var.get().strip()
        raw_s = self._v_step_entry_var.get().strip()

        if not raw_s:
            raw_s = self._vstep_default_var.get().strip()

        try:
            v = float(raw_v)
        except ValueError:
            messagebox.showerror('Invalid voltage', f"'{raw_v}' is not a valid number.")
            return None
        try:
            s = float(raw_s)
            if s <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('Invalid step', f"Step size must be a positive number (got '{raw_s}').")
            return None
        return v, s

    def _add_voltage(self):
        parsed = self._parse_v_and_step()
        if parsed is None:
            return
        v, s = parsed
        idx = self._v_selected()
        if idx is not None:
            self.voltage_entries.insert(idx + 1, (v, s))
            self._refresh_voltage_list()
            self.v_listbox.selection_set(idx + 1)
            self.v_listbox.see(idx + 1)
        else:
            self.voltage_entries.append((v, s))
            self._refresh_voltage_list()
            self.v_listbox.selection_set(tk.END)
            self.v_listbox.see(tk.END)
        self._v_entry_var.set('')
        self._v_step_entry_var.set('')

    def _edit_step(self):
        """Open a small dialog to change the step of the selected entry."""
        idx = self._v_selected()
        if idx is None:
            messagebox.showinfo('No selection', 'Select a voltage entry first.')
            return
        v, s = self.voltage_entries[idx]

        dlg = tk.Toplevel(self)
        dlg.title(f'Edit step for {v:g} V')
        dlg.resizable(False, False)
        dlg.grab_set()

        ttk.Label(dlg, text=f'Voltage: {v:g} V', font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(14, 6), sticky='w')
        ttk.Label(dlg, text='New step (mV):').grid(row=1, column=0, padx=14, pady=6, sticky='w')
        step_var = tk.StringVar(value=f'{s:g}')
        step_entry = ttk.Entry(dlg, textvariable=step_var, width=10)
        step_entry.grid(row=1, column=1, padx=14, pady=6)
        step_entry.focus_set()
        step_entry.select_range(0, tk.END)

        def apply():
            raw = step_var.get().strip()
            try:
                new_s = float(raw)
                if new_s <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Invalid', f"'{raw}' is not a valid positive number.", parent=dlg)
                return
            self.voltage_entries[idx] = (v, new_s)
            self._refresh_voltage_list()
            self.v_listbox.selection_set(idx)
            dlg.destroy()

        step_entry.bind('<Return>', lambda _: apply())
        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(4, 14))
        ttk.Button(btn_row, text='Apply', command=apply).pack(side='left', padx=6)
        ttk.Button(btn_row, text='Cancel', command=dlg.destroy).pack(side='left', padx=6)

    def _bulk_import(self):
        """Import voltages from a comma-separated list, using the default step for all."""
        raw = self._bulk_var.get().strip()
        raw_s = self._vstep_default_var.get().strip()
        try:
            default_step = float(raw_s)
            if default_step <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('Invalid default step',
                                 'Set a valid default step size before bulk import.')
            return
        try:
            vals = [float(x.strip()) for x in raw.split(',') if x.strip()]
        except ValueError:
            messagebox.showerror('Invalid values', 'Could not parse all entries as numbers.')
            return
        if not vals:
            return
        self.voltage_entries.extend((v, default_step) for v in vals)
        self._refresh_voltage_list()
        self._bulk_var.set('')

    def _apply_default_step_to_all(self):
        """Set the default step on every existing entry."""
        if not self.voltage_entries:
            return
        raw_s = self._vstep_default_var.get().strip()
        try:
            s = float(raw_s)
            if s <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('Invalid default step',
                                 f"'{raw_s}' is not a valid positive number.")
            return
        self.voltage_entries = [(v, s) for v, _ in self.voltage_entries]
        self._refresh_voltage_list()

    def _reverse_voltages(self):
        if not self.voltage_entries:
            return
        self.voltage_entries.reverse()
        self._refresh_voltage_list()

    def _clear_voltages(self):
        if not self.voltage_entries:
            return
        if messagebox.askyesno('Clear all', 'Remove all target voltages?'):
            self.voltage_entries.clear()
            self._refresh_voltage_list()

    def _v_selected(self) -> int | None:
        sel = self.v_listbox.curselection()
        return sel[0] if sel else None

    def _delete_voltage(self):
        idx = self._v_selected()
        if idx is None:
            return
        self.voltage_entries.pop(idx)
        self._refresh_voltage_list()
        if self.voltage_entries:
            self.v_listbox.selection_set(min(idx, len(self.voltage_entries) - 1))

    def _move_v_up(self):
        idx = self._v_selected()
        if idx is None or idx == 0:
            return
        self.voltage_entries[idx], self.voltage_entries[idx - 1] = \
            self.voltage_entries[idx - 1], self.voltage_entries[idx]
        self._refresh_voltage_list()
        self.v_listbox.selection_set(idx - 1)
        self.v_listbox.see(idx - 1)

    def _move_v_down(self):
        idx = self._v_selected()
        if idx is None or idx >= len(self.voltage_entries) - 1:
            return
        self.voltage_entries[idx], self.voltage_entries[idx + 1] = \
            self.voltage_entries[idx + 1], self.voltage_entries[idx]
        self._refresh_voltage_list()
        self.v_listbox.selection_set(idx + 1)
        self.v_listbox.see(idx + 1)

    # ── bias list operations ─────────────────────────────────────

    def _refresh_bias_list(self):
        self.b_listbox.delete(0, tk.END)
        for i, b in enumerate(self.biases):
            prefix = '→' if (i == 0 and self._sweep_var.get() == "Sweep and Return") else ' '
            self.b_listbox.insert(tk.END, f"  {prefix} {i+1:>2}.  {b:g} V")
        self._refresh_summary()

    def _add_bias(self):
        raw = self._b_entry_var.get().strip()
        try:
            b = float(raw)
        except ValueError:
            messagebox.showerror('Invalid value', f"'{raw}' is not a valid number.")
            return
        self.biases.append(b)
        self._refresh_bias_list()
        self._b_entry_var.set('')

    def _b_selected(self) -> int | None:
        sel = self.b_listbox.curselection()
        return sel[0] if sel else None

    def _delete_bias(self):
        idx = self._b_selected()
        if idx is None:
            return
        self.biases.pop(idx)
        self._refresh_bias_list()
        if self.biases:
            self.b_listbox.selection_set(min(idx, len(self.biases) - 1))

    def _move_b_up(self):
        idx = self._b_selected()
        if idx is None or idx == 0:
            return
        self.biases[idx], self.biases[idx - 1] = self.biases[idx - 1], self.biases[idx]
        self._refresh_bias_list()
        self.b_listbox.selection_set(idx - 1)

    def _move_b_down(self):
        idx = self._b_selected()
        if idx is None or idx >= len(self.biases) - 1:
            return
        self.biases[idx], self.biases[idx + 1] = self.biases[idx + 1], self.biases[idx]
        self._refresh_bias_list()
        self.b_listbox.selection_set(idx + 1)

    # ── summary ──────────────────────────────────────────────────

    def _refresh_summary(self):
        n_v  = len(self.voltage_entries)
        n_b  = len(self.biases)
        mode = self._sweep_var.get() if hasattr(self, '_sweep_var') else ''
        n_b_used = 1 if mode == "Sweep and Return" else n_b
        lines = [
            f"Voltages:    {n_v}",
            f"Bias pts:    {n_b_used}" + (f" / {n_b}" if mode == "Sweep and Return" and n_b > 1 else ""),
            f"Block pairs: {n_v}",
            f"Total blocks:{n_v * 2}",
        ]
        self._summary_var.set('\n'.join(lines))

    # ── file operations ──────────────────────────────────────────

    def _browse_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=os.path.basename(self._filename_var.get()),
        )
        if path:
            self._filename_var.set(path)

    def _generate(self):
        if not self.voltage_entries:
            messagebox.showwarning('No voltages', 'Add at least one target voltage.')
            return
        if not self.biases:
            messagebox.showwarning('No bias targets', 'Add at least one DC bias target.')
            return
        try:
            aux_step = float(self._aux_step_var.get())
            if aux_step <= 0:
                raise ValueError("Aux step must be > 0.")
        except ValueError as e:
            messagebox.showerror('Invalid setting', str(e))
            return

        filepath = self._filename_var.get().strip()
        if not filepath:
            messagebox.showwarning('No filename', 'Please enter an output filename.')
            return

        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            generate_sequence(filepath, self.voltage_entries,
                              self._sweep_var.get(), self.biases, aux_step)
            mode = self._sweep_var.get()
            n_b_used = 1 if mode == "Sweep and Return" else len(self.biases)
            messagebox.showinfo(
                'Done',
                f"Sequence written successfully!\n\n"
                f"File:        {filepath}\n"
                f"Voltages:    {len(self.voltage_entries)}\n"
                f"Bias points: {n_b_used}\n"
                f"Mode:        {mode}\n"
                f"Block pairs: {len(self.voltage_entries)}"
            )
        except Exception as e:
            messagebox.showerror('Write error', str(e))


# ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app = SequenceBuilder()
    app.mainloop()
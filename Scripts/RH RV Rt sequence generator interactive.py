"""
RH / RV / Rt  SEQUENCE BUILDER  —  GUI
=======================================
Build a custom measurement sequence by adding RH, RV, and Rt blocks
in any order. Blocks can be reordered, edited, and deleted before
generating the output file.

Usage:
    python RH_RV_Rt_sequence_builder.py
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Union


# ─────────────────────────────────────────────────────────────────
#   Core writing helpers  (unchanged from original)
# ─────────────────────────────────────────────────────────────────

def _format_value(value: Union[int, float, str]) -> str:
    if isinstance(value, str):
        return value
    return f"{value:g}"


def write_block(f, measurement_type: str,
                params: list[tuple[str, Union[int, float, str], int]]) -> None:
    f.write(f'- "Measurement Type", "[\'{measurement_type}\']"\n')
    for label, value, level in params:
        dashes = '-' * (level + 1)
        formatted = _format_value(value)
        f.write(f'{dashes} "{label}", "[{formatted}]"\n')


# ─────────────────────────────────────────────────────────────────
#   Block data model
# ─────────────────────────────────────────────────────────────────

# Each block is a dict describing one measurement step.
# Keys depend on block type:
#
# RH  → { type, field_t, use_magnet }
# RV  → { type, smu, voltage_v, step_mv, use_magnet }
# Rt  → { type, acq_s, voltage_v, field_t, use_magnet }

BLOCK_COLORS = {
    'RH': '#d0e8ff',   # blue tint
    'RV': '#d4f0d4',   # green tint
    'Rt': '#fff0cc',   # amber tint
}

BLOCK_LABELS = {
    'RH': 'RH  — Move Magnet',
    'RV': 'RV  — Voltage Sweep',
    'Rt': 'Rt  — Wait / Acquire',
}


def block_summary(block: dict) -> str:
    """One-line human-readable summary shown in the sequence list."""
    t = block['type']
    if t == 'RH':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return f"RH  |  H = {_format_value(block['field_t'])} T   ({mag})  |  delay = {_format_value(block['acq_delay'])} s"
    if t == 'RV':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return (f"RV  |  SMU = {block['smu']}   "
                f"V → {_format_value(block['voltage_v'])} V   "
                f"step = {_format_value(block['step_mv'])} mV   ({mag})  |  delay = {_format_value(block['acq_delay'])} s")
    if t == 'Rt':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return (f"Rt  |  acq = {_format_value(block['acq_s'])} s   "
                f"V = {_format_value(block['voltage_v'])} V   "
                f"H = {_format_value(block['field_t'])} T   ({mag})  |  delay = {_format_value(block['acq_delay'])} s")
    return str(block)


def block_to_file_params(block: dict) -> list[tuple[str, Union[int, float, str], int]]:
    """Convert a block dict to the params list expected by write_block()."""
    t = block['type']
    mag = block['use_magnet']   # already stored as the string 'True' or 'False'
    if t == 'RH':
        return [
            ('Target field (T)',  block['field_t'],   1),
            ('Acquisition Delay (s)', block['acq_delay'], 2),
            ('Use Magnet',        mag,                3),
        ]
    if t == 'RV':
        return [
            ('User defined SMU',  block['smu'],       1),
            ('Target Voltage(V)', block['voltage_v'], 2),
            ('Step size(mV)',     block['step_mv'],   3),
            ('Acquisition Delay (s)', block['acq_delay'], 4),
            ('Use Magnet',        mag,                5),
        ]
    if t == 'Rt':
        return [
            ('Acquisition Length (s)', block['acq_s'],    1),
            ('Acquisition Delay (s)', block['acq_delay'], 2),
            ('Target Voltage(V)',      block['voltage_v'], 3),
            ('Target field (T)',       block['field_t'],   4),
            ('Use Magnet',             mag,                5),
        ]
    return []


# ─────────────────────────────────────────────────────────────────
#   Add / Edit block dialog
# ─────────────────────────────────────────────────────────────────

class BlockDialog(tk.Toplevel):
    """
    Modal dialog to create or edit a single measurement block.
    On OK, self.result is set to the block dict; on Cancel it remains None.
    """

    def __init__(self, parent, block_type: str, existing: dict | None = None):
        super().__init__(parent)
        self.result: dict | None = None
        self.block_type = block_type
        self.title(f"{'Edit' if existing else 'Add'}  {BLOCK_LABELS[block_type]}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        pad = dict(padx=10, pady=4)

        # ── header ──────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BLOCK_COLORS[block_type])
        hdr.pack(fill='x')
        tk.Label(hdr, text=BLOCK_LABELS[block_type],
                 bg=BLOCK_COLORS[block_type],
                 font=('Arial', 12, 'bold'),
                 pady=8).pack()

        form = ttk.Frame(self, padding=12)
        form.pack(fill='both', expand=True)

        # ── fields depend on block type ──────────────────────────
        self._vars: dict[str, tk.Variable] = {}

        def add_float(row, label, key, default):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', **pad)
            v = tk.StringVar(value=str(existing[key] if existing else default))
            ttk.Entry(form, textvariable=v, width=16).grid(row=row, column=1, sticky='ew', **pad)
            self._vars[key] = v

        def add_check(row, label, key, default=True):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', **pad)
            # existing[key] may be stored as the string 'True'/'False' — convert back to bool
            if existing:
                raw_val = existing[key]
                init = (raw_val == "'True'") if isinstance(raw_val, str) else bool(raw_val)
            else:
                init = default
            v = tk.BooleanVar(value=init)
            ttk.Checkbutton(form, variable=v).grid(row=row, column=1, sticky='w', **pad)
            self._vars[key] = v

        r = 0
        if block_type == 'RH':
            add_float(r, 'Target field (T):', 'field_t', 0.0);   r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0);r += 1
            add_check(r, 'Use Magnet:', 'use_magnet', True);       r += 1

        elif block_type == 'RV':
            SMU_OPTIONS = ['smua', 'smub', 'Gate_1', 'Gate_2']
            ttk.Label(form, text='User defined SMU:').grid(row=r, column=0, sticky='w', **pad)
            smu_default = existing['smu'].strip("'") if existing else 'Gate_1'
            smu_var = tk.StringVar(value=smu_default)
            smu_combo = ttk.Combobox(form, textvariable=smu_var, values=SMU_OPTIONS,
                                     state='readonly', width=14)
            smu_combo.grid(row=r, column=1, sticky='ew', **pad)
            self._vars['smu'] = smu_var
            r += 1
            add_float(r, 'Target Voltage (V):', 'voltage_v', 5.0); r += 1
            add_float(r, 'Step size (mV):', 'step_mv', 10.0);      r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0); r += 1
            add_check(r, 'Use Magnet:', 'use_magnet', False);       r += 1

        elif block_type == 'Rt':
            add_float(r, 'Acquisition Length (s):', 'acq_s', 30.0); r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0);r += 1
            add_float(r, 'Target Voltage (V):', 'voltage_v', 0.0);  r += 1
            add_float(r, 'Target field (T):', 'field_t', 0.0);      r += 1
            add_check(r, 'Use Magnet:', 'use_magnet', True);         r += 1

        form.columnconfigure(1, weight=1)

        # ── buttons ──────────────────────────────────────────────
        btn_frame = ttk.Frame(self, padding=(12, 4, 12, 12))
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text='OK',     command=self._ok).pack(side='right', padx=4)
        ttk.Button(btn_frame, text='Cancel', command=self.destroy).pack(side='right', padx=4)

        self.bind('<Return>', lambda _: self._ok())
        self.bind('<Escape>', lambda _: self.destroy())

        # Center on parent
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        self.wait_window()

    def _ok(self):
        # Parse and validate all float fields
        float_keys = {
            'RH':  ['field_t','acq_delay'],
            'RV':  ['voltage_v', 'step_mv','acq_delay'],
            'Rt':  ['acq_s','acq_delay', 'voltage_v', 'field_t'],
        }[self.block_type]

        block = {'type': self.block_type}
        for key, var in self._vars.items():
            if key == 'smu':
                block[key] = f"'{var.get()}'"
            elif key in float_keys:
                raw = var.get().strip()
                try:
                    block[key] = float(raw)
                except ValueError:
                    messagebox.showerror('Invalid value',
                                         f"'{raw}' is not a valid number for '{key}'.",
                                         parent=self)
                    return
            else:
                # Store as the explicit string 'True'/'False' so _format_value
                # never falls through to numeric formatting (which would give 1/0)
                block[key] = "'"'True'"'" if var.get() else "'"'False'"'"

        # Extra validation
        if self.block_type == 'RV' and block.get('step_mv', 0) <= 0:
            messagebox.showerror('Invalid value', 'Step size must be > 0.', parent=self)
            return
        if self.block_type == 'Rt' and block.get('acq_s', 0) <= 0:
            messagebox.showerror('Invalid value', 'Acquisition length must be > 0.', parent=self)
            return

        self.result = block
        self.destroy()


# ─────────────────────────────────────────────────────────────────
#   Main application window
# ─────────────────────────────────────────────────────────────────

class SequenceBuilder(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("RH / RV / Rt  Sequence Builder")
        self.geometry("860x600")
        self.minsize(700, 480)

        self.sequence: list[dict] = []   # list of block dicts

        self._build_ui()
        self._refresh_list()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self):
        # ── top toolbar ─────────────────────────────────────────
        toolbar = tk.Frame(self, bg='#2b2b2b', pady=6)
        toolbar.pack(fill='x')

        def add_btn(label, color, cmd, tooltip=''):
            b = tk.Button(toolbar, text=label, bg=color, fg='white',
                          font=('Arial', 10, 'bold'),
                          relief='flat', padx=12, pady=4,
                          cursor='hand2', command=cmd)
            b.pack(side='left', padx=6)
            return b

        add_btn('＋ Add RH', '#3a7abf', lambda: self._add_block('RH'))
        add_btn('＋ Add RV', '#2e8b57', lambda: self._add_block('RV'))
        add_btn('＋ Add Rt', '#b07d00', lambda: self._add_block('Rt'))

        tk.Frame(toolbar, bg='#2b2b2b', width=20).pack(side='left')  # spacer

        add_btn('✎  Edit',    '#555', self._edit_selected)
        add_btn('↑  Up',      '#555', self._move_up)
        add_btn('↓  Down',    '#555', self._move_down)
        add_btn('✕  Delete',  '#933', self._delete_selected)

        # ── main area: list + counter sidebar ───────────────────
        main = tk.Frame(self)
        main.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        # Sequence listbox with scrollbar
        list_frame = tk.Frame(main)
        list_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(list_frame, text='Measurement Sequence',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 4))

        sb = ttk.Scrollbar(list_frame, orient='vertical')
        self.listbox = tk.Listbox(list_frame,
                                   yscrollcommand=sb.set,
                                   selectmode='single',
                                   font=('Consolas', 10),
                                   activestyle='dotbox',
                                   height=20)
        sb.config(command=self.listbox.yview)
        self.listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.listbox.bind('<Double-Button-1>', lambda _: self._edit_selected())
        self.listbox.bind('<Delete>', lambda _: self._delete_selected())

        # Counter sidebar
        side = ttk.Frame(main, padding=(12, 0, 0, 0))
        side.pack(side='right', fill='y')

        ttk.Label(side, text='Block counts',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 8))

        self._count_vars = {}
        for btype, color in BLOCK_COLORS.items():
            row = tk.Frame(side, bg=color, padx=8, pady=4)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=btype, bg=color,
                     font=('Arial', 10, 'bold'), width=4).pack(side='left')
            v = tk.StringVar(value='0')
            self._count_vars[btype] = v
            tk.Label(row, textvariable=v, bg=color,
                     font=('Arial', 10), width=4).pack(side='left')

        ttk.Separator(side, orient='horizontal').pack(fill='x', pady=8)
        ttk.Label(side, text='Total:').pack(anchor='w')
        self._total_var = tk.StringVar(value='0')
        ttk.Label(side, textvariable=self._total_var,
                  font=('Arial', 14, 'bold')).pack(anchor='w')

        # Quick-help
        ttk.Separator(side, orient='horizontal').pack(fill='x', pady=8)
        help_text = ("Double-click to edit\n"
                     "Del key to remove\n"
                     "Use ↑↓ to reorder")
        ttk.Label(side, text=help_text,
                  foreground='gray', font=('Arial', 8)).pack(anchor='w')

        # ── bottom bar: filename + generate ─────────────────────
        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill='x')

        ttk.Label(bottom, text='Output file:').pack(side='left')
        self._filename_var = tk.StringVar(value='custom_sequence.txt')
        ttk.Entry(bottom, textvariable=self._filename_var, width=40).pack(side='left', padx=6)
        ttk.Button(bottom, text='Browse…', command=self._browse_save).pack(side='left', padx=2)

        ttk.Button(bottom, text='⚡  Generate File',
                   command=self._generate,
                   style='Accent.TButton').pack(side='right', padx=4)
        ttk.Button(bottom, text='Clear All',
                   command=self._clear_all).pack(side='right', padx=4)

    # ── sequence list helpers ────────────────────────────────────

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        counts = {'RH': 0, 'RV': 0, 'Rt': 0}
        for i, block in enumerate(self.sequence):
            summary = f"{i+1:>3}.  {block_summary(block)}"
            self.listbox.insert(tk.END, summary)
            self.listbox.itemconfig(i, bg=BLOCK_COLORS[block['type']])
            counts[block['type']] += 1

        for btype, v in self._count_vars.items():
            v.set(str(counts[btype]))
        self._total_var.set(str(len(self.sequence)))

    def _selected_index(self) -> int | None:
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    # ── block operations ─────────────────────────────────────────

    def _add_block(self, block_type: str):
        dlg = BlockDialog(self, block_type)
        if dlg.result:
            idx = self._selected_index()
            if idx is not None:
                # Insert after current selection
                self.sequence.insert(idx + 1, dlg.result)
                self._refresh_list()
                self.listbox.selection_set(idx + 1)
            else:
                self.sequence.append(dlg.result)
                self._refresh_list()
                self.listbox.selection_set(tk.END)
            self.listbox.see(self.listbox.curselection()[0])

    def _edit_selected(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo('Nothing selected', 'Select a block to edit.')
            return
        block = self.sequence[idx]
        dlg = BlockDialog(self, block['type'], existing=block)
        if dlg.result:
            self.sequence[idx] = dlg.result
            self._refresh_list()
            self.listbox.selection_set(idx)

    def _delete_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        self.sequence.pop(idx)
        self._refresh_list()
        # Keep selection near the deleted item
        if self.sequence:
            new_idx = min(idx, len(self.sequence) - 1)
            self.listbox.selection_set(new_idx)

    def _move_up(self):
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        self.sequence[idx], self.sequence[idx - 1] = \
            self.sequence[idx - 1], self.sequence[idx]
        self._refresh_list()
        self.listbox.selection_set(idx - 1)
        self.listbox.see(idx - 1)

    def _move_down(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.sequence) - 1:
            return
        self.sequence[idx], self.sequence[idx + 1] = \
            self.sequence[idx + 1], self.sequence[idx]
        self._refresh_list()
        self.listbox.selection_set(idx + 1)
        self.listbox.see(idx + 1)

    def _clear_all(self):
        if not self.sequence:
            return
        if messagebox.askyesno('Clear all', 'Remove all blocks from the sequence?'):
            self.sequence.clear()
            self._refresh_list()

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
        if not self.sequence:
            messagebox.showwarning('Empty sequence',
                                   'Add at least one block before generating.')
            return

        filepath = self._filename_var.get().strip()
        if not filepath:
            messagebox.showwarning('No filename', 'Please enter an output filename.')
            return

        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, 'w') as f:
                for block in self.sequence:
                    write_block(f, block['type'], block_to_file_params(block))

            counts = {'RH': 0, 'RV': 0, 'Rt': 0}
            for b in self.sequence:
                counts[b['type']] += 1

            messagebox.showinfo(
                'Done',
                f"Sequence written successfully!\n\n"
                f"File:   {filepath}\n"
                f"Blocks: {len(self.sequence)}  "
                f"(RH: {counts['RH']}, RV: {counts['RV']}, Rt: {counts['Rt']})"
            )
        except Exception as e:
            messagebox.showerror('Write error', str(e))


# ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app = SequenceBuilder()
    app.mainloop()

"""
RH / RV / Rt  SEQUENCE BUILDER  —  GUI
=======================================
Build a custom measurement sequence by adding RH, RV, and Rt blocks
in any order. Blocks can be reordered, edited, and deleted before
generating the output file.

Loops: wrap any group of blocks in a loop that sweeps a parameter
(field or gate voltage). Loops can be nested — e.g. a voltage sweep
loop inside a field sweep loop, or two different gate-voltage loops
nested to build a 2D gate map.

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
#   Node data model  (blocks + loops)
# ─────────────────────────────────────────────────────────────────

# A sequence is a tree. Nodes are either:
#
# Leaf block (unchanged dict):
#   RH  → { type:'RH', field_t, sweep_rate, acq_delay, use_magnet }
#   RV  → { type:'RV', smu, voltage_v, step_mv, acq_delay, use_magnet }
#   Rt  → { type:'Rt', acq_s, acq_delay, voltage_v, field_t, use_magnet }
#
# Loop node:
#   { type:'LOOP', param:'field_t'|'voltage_v', param_label:str,
#     smu:None|"'Gate_1'", values:[float,...], children:[node,...] }
#
#   field_t loop  → overrides field_t on every block that has it
#   voltage_v loop → overrides voltage_v on RV blocks whose smu matches;
#                    Rt is never auto-overridden (set its voltage by hand)

LOOP_MARK = '🔁'

SMU_OPTIONS = ['smua', 'smub', 'Gate_1', 'Gate_2']

LOOP_PARAMS = {
    'field_t':  'Field (T)',
    'voltage_v': 'Voltage (V)',
}

BLOCK_COLORS = {
    'RH': '#d0e8ff',   # blue tint
    'RV': '#d4f0d4',   # green tint
    'Rt': '#fff0cc',   # amber tint
    'LOOP': '#ece0f8', # purple tint
}

BLOCK_LABELS = {
    'RH': 'RH  — Move Magnet',
    'RV': 'RV  — Voltage Sweep',
    'Rt': 'Rt  — Wait / Acquire',
}


def is_loop(node: dict) -> bool:
    return node.get('type') == 'LOOP'


def block_summary(block: dict) -> str:
    """One-line human-readable summary shown in the sequence list."""
    t = block['type']
    if t == 'RH':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return (f"RH  |  H = {_format_value(block['field_t'])} T   ({mag})"
                f"   rate = {_format_value(block['sweep_rate'])} T/min"
                f"   delay = {_format_value(block['acq_delay'])} s")
    if t == 'RV':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return (f"RV  |  SMU = {block['smu']}   "
                f"V → {_format_value(block['voltage_v'])} V   "
                f"step = {_format_value(block['step_mv'])} mV   ({mag})"
                f"   delay = {_format_value(block['acq_delay'])} s")
    if t == 'Rt':
        mag = '✓ magnet' if block['use_magnet'] == "'True'" else '✗ magnet'
        return (f"Rt  |  acq = {_format_value(block['acq_s'])} s   "
                f"V = {_format_value(block['voltage_v'])} V   "
                f"H = {_format_value(block['field_t'])} T   ({mag})"
                f"   delay = {_format_value(block['acq_delay'])} s")
    return str(block)


def loop_summary(node: dict) -> str:
    vals = ', '.join(_format_value(v) for v in node['values'])
    smu_tag = f"   [SMU {node['smu']}]" if node['param'] == 'voltage_v' else ''
    return (f"{LOOP_MARK} Loop: {node['param_label']} ∈ [{vals}]"
            f"   ({len(node['values'])} pts){smu_tag}")


def node_summary(node: dict) -> str:
    return loop_summary(node) if is_loop(node) else block_summary(node)


def block_to_file_params(block: dict) -> list[tuple[str, Union[int, float, str], int]]:
    """Convert a block dict to the params list expected by write_block()."""
    t = block['type']
    mag = block['use_magnet']
    if t == 'RH':
        return [
            ('Target field (T)',     block['field_t'],   1),
            ('Sweep rate (T/min)',   block['sweep_rate'], 2),
            ('Acquisition Delay (s)', block['acq_delay'], 3),
            ('Use Magnet',           mag,                4),
        ]
    if t == 'RV':
        return [
            ('User defined SMU',     block['smu'],       1),
            ('Target Voltage(V)',    block['voltage_v'], 2),
            ('Step size(mV)',        block['step_mv'],   3),
            ('Acquisition Delay (s)', block['acq_delay'], 4),
            ('Use Magnet',           mag,                5),
        ]
    if t == 'Rt':
        return [
            ('Acquisition Length (s)', block['acq_s'],    1),
            ('Acquisition Delay (s)',  block['acq_delay'], 2),
            ('Target Voltage(V)',      block['voltage_v'], 3),
            ('Target field (T)',       block['field_t'],   4),
            ('Use Magnet',             mag,                5),
        ]
    return []


# ─────────────────────────────────────────────────────────────────
#   Tree → flat block expansion  (loops unrolled at generate time)
# ─────────────────────────────────────────────────────────────────

def _expand_sequence(nodes: list[dict],
                     overrides: dict | None = None) -> list[dict]:
    """
    Walk the tree, unrolling loops. `overrides` maps an override key
    (param, smu) -> value. Nesting accumulates: an outer field loop and
    an inner gate-voltage loop both reach the leaves.
    """
    overrides = overrides or {}
    out: list[dict] = []
    for node in nodes:
        if is_loop(node):
            key = (node['param'], node['smu'])
            for val in node['values']:
                child_overrides = {**overrides, key: val}
                out.extend(_expand_sequence(node['children'], child_overrides))
        else:
            block = dict(node)
            for (param, smu), val in overrides.items():
                if param == 'field_t' and 'field_t' in block:
                    block['field_t'] = val
                elif param == 'voltage_v':
                    # Only auto-overwrite the RV gate we are sweeping.
                    # Rt keeps its hand-set voltage.
                    if block['type'] == 'RV' and block.get('smu') == smu:
                        block['voltage_v'] = val
            out.append(block)
    return out


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
            add_float(r, 'Target field (T):', 'field_t', 0.0);      r += 1
            add_float(r, 'Sweep rate (T/min):', 'sweep_rate', 0.1); r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0); r += 1
            add_check(r, 'Use Magnet:', 'use_magnet', True);         r += 1

        elif block_type == 'RV':
            ttk.Label(form, text='User defined SMU:').grid(row=r, column=0, sticky='w', **pad)
            smu_default = existing['smu'].strip("'") if existing else 'Gate_1'
            smu_var = tk.StringVar(value=smu_default)
            smu_combo = ttk.Combobox(form, textvariable=smu_var, values=SMU_OPTIONS,
                                     state='readonly', width=14)
            smu_combo.grid(row=r, column=1, sticky='ew', **pad)
            self._vars['smu'] = smu_var
            r += 1
            add_float(r, 'Target Voltage (V):', 'voltage_v', 5.0);  r += 1
            add_float(r, 'Step size (mV):', 'step_mv', 10.0);       r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0); r += 1
            add_check(r, 'Use Magnet:', 'use_magnet', False);        r += 1

        elif block_type == 'Rt':
            add_float(r, 'Acquisition Length (s):', 'acq_s', 30.0); r += 1
            add_float(r, 'Acquisition Delay (s):', 'acq_delay', 1.0); r += 1
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
        float_keys = {
            'RH':  ['field_t', 'sweep_rate', 'acq_delay'],
            'RV':  ['voltage_v', 'step_mv', 'acq_delay'],
            'Rt':  ['acq_s', 'acq_delay', 'voltage_v', 'field_t'],
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
                block[key] = "'True'" if var.get() else "'False'"

        if self.block_type == 'RV' and block.get('step_mv', 0) <= 0:
            messagebox.showerror('Invalid value', 'Step size must be > 0.', parent=self)
            return
        if self.block_type == 'Rt' and block.get('acq_s', 0) <= 0:
            messagebox.showerror('Invalid value', 'Acquisition length must be > 0.', parent=self)
            return

        self.result = block
        self.destroy()


# ─────────────────────────────────────────────────────────────────
#   Loop dialog
# ─────────────────────────────────────────────────────────────────

class LoopDialog(tk.Toplevel):
    """
    Modal dialog to create or edit a LOOP node.
    Pick swept parameter (Field / Voltage), and for Voltage pick the SMU
    so two different gates can be nested without shadowing each other.
    """

    def __init__(self, parent, existing: dict | None = None):
        super().__init__(parent)
        self.result: dict | None = None
        self.title(f"{'Edit' if existing else 'Add'}  Loop")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        pad = dict(padx=10, pady=4)

        hdr = tk.Frame(self, bg=BLOCK_COLORS['LOOP'])
        hdr.pack(fill='x')
        tk.Label(hdr, text='🔁  Sweep Loop',
                 bg=BLOCK_COLORS['LOOP'],
                 font=('Arial', 12, 'bold'), pady=8).pack()

        form = ttk.Frame(self, padding=12)
        form.pack(fill='both', expand=True)

        # ── parameter ─────────────────────────────────────────────
        ttk.Label(form, text='Sweep parameter:',
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2,
                                                   sticky='w', pady=(0, 4))
        self._param_var = tk.StringVar(
            value=existing['param'] if existing else 'field_t')
        for val, lbl in LOOP_PARAMS.items():
            ttk.Radiobutton(form, text=lbl, value=val,
                            variable=self._param_var,
                            command=self._toggle_smu).grid(
                row=1, column=0 if val == 'field_t' else 1,
                sticky='w', padx=6)

        # ── SMU (only meaningful for voltage) ─────────────────────
        self._smu_row = 2
        ttk.Label(form, text='Gate SMU to sweep:',
                  font=('Arial', 10, 'bold')).grid(row=self._smu_row, column=0,
                                                   columnspan=2, sticky='w',
                                                   pady=(10, 4))
        smu_default = (existing['smu'].strip("'") if existing and existing['smu']
                       else 'Gate_1')
        self._smu_var = tk.StringVar(value=smu_default)
        self._smu_combo = ttk.Combobox(form, textvariable=self._smu_var,
                                       values=SMU_OPTIONS, state='readonly',
                                       width=14)
        self._smu_combo.grid(row=self._smu_row + 1, column=0, columnspan=2,
                             sticky='w', padx=6)

        # ── value mode ────────────────────────────────────────────
        mode_row = self._smu_row + 2
        ttk.Label(form, text='Value entry mode:',
                  font=('Arial', 10, 'bold')).grid(row=mode_row, column=0,
                                                   columnspan=2, sticky='w',
                                                   pady=(10, 4))
        self._mode_var = tk.StringVar(
            value=existing.get('_mode', 'linspace') if existing else 'linspace')
        ttk.Radiobutton(form, text='Linspace', value='linspace',
                        variable=self._mode_var,
                        command=self._toggle_mode).grid(row=mode_row + 1,
                                                        column=0, sticky='w', padx=6)
        ttk.Radiobutton(form, text='Explicit list', value='explicit',
                        variable=self._mode_var,
                        command=self._toggle_mode).grid(row=mode_row + 1,
                                                        column=1, sticky='w', padx=6)

        # linspace inputs
        ls_row = mode_row + 2
        self._ls_frame = ttk.Frame(form)
        self._ls_frame.grid(row=ls_row, column=0, columnspan=2, sticky='ew')
        self._ls_vars = {}
        for i, (lbl, key, default) in enumerate(
                [('Start', 'start', 0.0), ('End', 'end', 1.0),
                 ('# points', 'npts', 5)]):
            ttk.Label(self._ls_frame, text=lbl).grid(row=0, column=i * 2, padx=4)
            if existing and existing.get('_mode') == 'linspace':
                dv = existing['_ls'].get(key, default)
            else:
                dv = default
            v = tk.StringVar(value=str(dv))
            ttk.Entry(self._ls_frame, textvariable=v, width=6).grid(
                row=0, column=i * 2 + 1, padx=4)
            self._ls_vars[key] = v

        # explicit input
        ex_row = ls_row + 1
        self._ex_frame = ttk.Frame(form)
        self._ex_frame.grid(row=ex_row, column=0, columnspan=2, sticky='ew')
        ttk.Label(self._ex_frame, text='Values (comma-separated):').grid(
            row=0, column=0, padx=4)
        ex_default = (', '.join(str(v) for v in existing['values'])
                      if existing and existing.get('_mode') == 'explicit'
                      else '0, 0.5, 1')
        self._ex_var = tk.StringVar(value=ex_default)
        ttk.Entry(self._ex_frame, textvariable=self._ex_var, width=30).grid(
            row=0, column=1, padx=4)

        # ── buttons ───────────────────────────────────────────────
        btn_frame = ttk.Frame(self, padding=(12, 4, 12, 12))
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text='OK',     command=self._ok).pack(side='right', padx=4)
        ttk.Button(btn_frame, text='Cancel', command=self.destroy).pack(side='right', padx=4)

        self.bind('<Return>', lambda _: self._ok())
        self.bind('<Escape>', lambda _: self.destroy())

        self._toggle_smu()
        self._toggle_mode()

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        self.wait_window()

    def _toggle_smu(self):
        state = 'normal' if self._param_var.get() == 'voltage_v' else 'disabled'
        self._smu_combo.config(state='readonly' if state == 'normal' else 'disabled')

    def _toggle_mode(self):
        if self._mode_var.get() == 'linspace':
            self._ex_frame.grid_remove()
            self._ls_frame.grid()
        else:
            self._ls_frame.grid_remove()
            self._ex_frame.grid()

    def _ok(self):
        param = self._param_var.get()
        mode = self._mode_var.get()

        try:
            if mode == 'linspace':
                start = float(self._ls_vars['start'].get())
                end = float(self._ls_vars['end'].get())
                npts = int(self._ls_vars['npts'].get())
                if npts < 1:
                    raise ValueError('need at least 1 point')
                if npts == 1:
                    values = [start]
                else:
                    step = (end - start) / (npts - 1)
                    values = [start + step * i for i in range(npts)]
            else:
                values = [float(v.strip())
                          for v in self._ex_var.get().split(',') if v.strip()]
                if not values:
                    raise ValueError('empty list')
        except ValueError as exc:
            messagebox.showerror('Invalid values',
                                 f'Could not parse loop values: {exc}',
                                 parent=self)
            return

        self.result = {
            'type': 'LOOP',
            'param': param,
            'param_label': LOOP_PARAMS[param],
            'smu': f"'{self._smu_var.get()}'" if param == 'voltage_v' else None,
            'values': values,
            '_mode': mode,
        }
        if mode == 'linspace':
            self.result['_ls'] = {
                'start': self._ls_vars['start'].get(),
                'end': self._ls_vars['end'].get(),
                'npts': self._ls_vars['npts'].get(),
            }
        self.destroy()


# ─────────────────────────────────────────────────────────────────
#   Main application window
# ─────────────────────────────────────────────────────────────────

class SequenceBuilder(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("RH / RV / Rt  Sequence Builder")
        self.geometry("960x620")
        self.minsize(780, 500)

        self.sequence: list[dict] = []   # tree: list of nodes (blocks or loops)

        # Parallel list mapping each displayed row to its tree location:
        # (parent_children_list, index_in_parent, depth)
        self._rows: list[tuple[list[dict], int, int]] = []

        self._build_ui()
        self._refresh_list()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self):
        # ttk style used by the Generate button
        style = ttk.Style(self)
        try:
            style.theme_use(style.theme_use())  # keep current theme
        except tk.TclError:
            pass
        style.configure('Accent.TButton', font=('Arial', 10, 'bold'))

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

        add_btn('🔁 Wrap in Loop', '#7a4fb5', self._wrap_in_loop)
        add_btn('✎  Edit',    '#555', self._edit_selected)
        add_btn('↑  Up',      '#555', self._move_up)
        add_btn('↓  Down',    '#555', self._move_down)
        add_btn('✕  Delete',  '#933', self._delete_selected)

        tk.Frame(toolbar, bg='#2b2b2b', width=10).pack(side='left')  # spacer
        add_btn('Open Loop', '#4a6fa5', self._unwrap_loop,
                tooltip='Move a loop\'s children out and delete the loop')
        add_btn('❓ Help', '#444', self._show_help,
                tooltip='Open the usage guide')

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
                                  selectmode='extended',
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

        ttk.Label(side, text='Expanded block counts',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 8))

        self._count_vars = {}
        for btype, color in BLOCK_COLORS.items():
            if btype == 'LOOP':
                continue
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
        help_text = ("Select blocks → Wrap in Loop\n"
                     "Double-click to edit\n"
                     "Del key to remove\n"
                     "Use ↑↓ to reorder (same level)\n"
                     "Add while a loop is selected\n"
                     "  inserts inside that loop\n"
                     "Open Loop dissolves a loop")
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

    # ── sequence list helpers (tree → flat rows) ────────────────

    def _walk(self, nodes: list[dict], depth: int,
              parent_list: list[dict]):
        for i, node in enumerate(nodes):
            self._rows.append((parent_list, i, depth))
            if is_loop(node):
                self._walk(node['children'], depth + 1, node['children'])

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        self._rows = []
        self._walk(self.sequence, 0, self.sequence)

        for row_idx, (parent_list, i, depth) in enumerate(self._rows):
            node = parent_list[i]
            indent = '│  ' * depth
            summary = node_summary(node)
            self.listbox.insert(row_idx, f"{indent}{summary}")
            self.listbox.itemconfig(row_idx, bg=BLOCK_COLORS[node['type']])

        # counts from the fully-expanded (unrolled) tree
        expanded = _expand_sequence(self.sequence)
        counts = {'RH': 0, 'RV': 0, 'Rt': 0}
        for b in expanded:
            counts[b['type']] += 1
        for btype, v in self._count_vars.items():
            v.set(str(counts[btype]))
        self._total_var.set(str(len(expanded)))

    def _selected_indices(self) -> list[int]:
        return list(self.listbox.curselection())

    def _single_selected(self) -> int | None:
        sel = self._selected_indices()
        return sel[0] if len(sel) == 1 else None

    # ── block operations ─────────────────────────────────────────

    def _add_block(self, block_type: str):
        dlg = BlockDialog(self, block_type)
        if not dlg.result:
            return

        idx = self._single_selected()
        if idx is None:
            self.sequence.append(dlg.result)
            self._refresh_list()
            self.listbox.selection_set(tk.END)
        else:
            parent_list, i, depth = self._rows[idx]
            target = parent_list[i]
            if is_loop(target):
                # building the loop's contents
                target['children'].insert(0, dlg.result)
                new_owner, new_pos = target['children'], 0
            else:
                parent_list.insert(i + 1, dlg.result)
                new_owner, new_pos = parent_list, i + 1
            self._refresh_list()
            # reselect the newly-added block by identity, not by guessing
            for ridx, (pl, ii, _) in enumerate(self._rows):
                if pl is new_owner and ii == new_pos:
                    self.listbox.selection_set(ridx)
                    break
        try:
            self.listbox.see(self.listbox.curselection()[0])
        except tk.TclError:
            pass

    def _wrap_in_loop(self):
        sel = self._selected_indices()
        if not sel:
            messagebox.showinfo('Nothing selected',
                                'Select one or more sibling blocks to wrap.')
            return

        # All selected rows must share the same parent list and be contiguous.
        parents = {id(self._rows[s][0]) for s in sel}
        if len(parents) != 1:
            messagebox.showerror('Cannot wrap',
                                 'Selection must be siblings (same nesting level).')
            return
        parent_list = self._rows[sel[0]][0]
        indices_in_parent = [self._rows[s][1] for s in sel]
        if indices_in_parent != list(range(min(indices_in_parent),
                                          max(indices_in_parent) + 1)):
            messagebox.showerror('Cannot wrap',
                                 'Selection must be contiguous.')
            return

        dlg = LoopDialog(self)
        if not dlg.result:
            return

        lo, hi = min(indices_in_parent), max(indices_in_parent)
        children = parent_list[lo:hi + 1]
        dlg.result['children'] = children
        parent_list[lo:hi + 1] = [dlg.result]
        self._refresh_list()

        # select the new loop row
        for ridx, (pl, ii, _) in enumerate(self._rows):
            if pl is parent_list and ii == lo:
                self.listbox.selection_set(ridx)
                break

    def _unwrap_loop(self):
        idx = self._single_selected()
        if idx is None:
            messagebox.showinfo('Nothing selected', 'Select a loop to open.')
            return
        parent_list, i, _ = self._rows[idx]
        node = parent_list[i]
        if not is_loop(node):
            messagebox.showinfo('Not a loop', 'Select a loop node to open.')
            return
        # splice children back into parent
        parent_list[i:i + 1] = node['children']
        self._refresh_list()
        # select first ex-child if any
        if node['children']:
            for ridx, (pl, ii, _) in enumerate(self._rows):
                if pl is parent_list and ii == i:
                    self.listbox.selection_set(ridx)
                    break

    def _edit_selected(self):
        idx = self._single_selected()
        if idx is None:
            messagebox.showinfo('Nothing selected', 'Select a single node to edit.')
            return
        parent_list, i, _ = self._rows[idx]
        node = parent_list[i]
        if is_loop(node):
            dlg = LoopDialog(self, existing=node)
            if dlg.result:
                dlg.result['children'] = node['children']
                parent_list[i] = dlg.result
        else:
            dlg = BlockDialog(self, node['type'], existing=node)
            if dlg.result:
                parent_list[i] = dlg.result
        self._refresh_list()
        self.listbox.selection_set(idx)

    def _delete_selected(self):
        sel = self._selected_indices()
        if not sel:
            return
        # delete from the deepest / last so earlier indices stay valid
        for s in reversed(sel):
            parent_list, i, _ = self._rows[s]
            node = parent_list[i]
            if is_loop(node) and node['children']:
                if not messagebox.askyesno(
                        'Delete loop?',
                        f'Delete loop and all {len(_expand_sequence(node["children"]))} '
                        f'expanded blocks inside it?'):
                    continue
            parent_list.pop(i)
        self._refresh_list()
        if self._rows:
            self.listbox.selection_set(min(sel[0], len(self._rows) - 1))

    def _move_up(self):
        sel = self._selected_indices()
        if not sel:
            return
        if len(sel) > 1:
            messagebox.showinfo('Select one node',
                                'Select a single node to move (multi-select reordering '
                                'is not supported).')
            return
        idx = sel[0]
        parent_list, i, _ = self._rows[idx]
        if i == 0:
            return
        parent_list[i], parent_list[i - 1] = parent_list[i - 1], parent_list[i]
        self._refresh_list()
        # reselect same node (it moved up one row)
        self.listbox.selection_set(idx - 1)
        self.listbox.see(idx - 1)

    def _move_down(self):
        sel = self._selected_indices()
        if not sel:
            return
        if len(sel) > 1:
            messagebox.showinfo('Select one node',
                                'Select a single node to move (multi-select reordering '
                                'is not supported).')
            return
        idx = sel[0]
        parent_list, i, _ = self._rows[idx]
        if i >= len(parent_list) - 1:
            return
        parent_list[i], parent_list[i + 1] = parent_list[i + 1], parent_list[i]
        self._refresh_list()
        self.listbox.selection_set(idx + 1)
        self.listbox.see(idx + 1)

    def _clear_all(self):
        if not self.sequence:
            return
        if messagebox.askyesno('Clear all', 'Remove all nodes from the sequence?'):
            self.sequence.clear()
            self._refresh_list()

    # ── help window ──────────────────────────────────────────────

    def _show_help(self):
        win = tk.Toplevel(self)
        win.title('RH / RV / Rt Sequence Builder — Guide')
        win.geometry('780x680')
        win.minsize(620, 500)
        win.transient(self)

        # Header
        hdr = tk.Frame(win, bg='#2b2b2b')
        hdr.pack(fill='x')
        tk.Label(hdr, text='📖  Usage Guide',
                 bg='#2b2b2b', fg='white',
                 font=('Arial', 14, 'bold'), pady=10).pack()

        # Scrollable text body
        body = ttk.Frame(win)
        body.pack(fill='both', expand=True, padx=10, pady=10)
        sb = ttk.Scrollbar(body, orient='vertical')
        txt = tk.Text(body, wrap='word', font=('Consolas', 10),
                      yscrollcommand=sb.set, relief='flat',
                      padx=12, pady=10, spacing1=2, spacing2=4)
        sb.config(command=txt.yview)
        txt.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Tag styles
        txt.tag_config('h1', font=('Arial', 13, 'bold'),
                       foreground='#2b2b2b', spacing3=6)
        txt.tag_config('h2', font=('Arial', 11, 'bold'),
                       foreground='#3a7abf', spacing3=4, spacing1=4)
        txt.tag_config('b',  font=('Arial', 10, 'bold'))
        txt.tag_config('mono', font=('Consolas', 10),
                       background='#f4f4f4', lmargin1=16, lmargin2=16)
        txt.tag_config('note', foreground='#b07d00', lmargin1=16, lmargin2=16)
        txt.tag_config('p', lmargin1=8, lmargin2=8, spacing3=4)

        def h1(s): txt.insert('end', s + '\n', 'h1')
        def h2(s): txt.insert('end', s + '\n', 'h2')
        def p(s=''): txt.insert('end', s + '\n', 'p')
        def b(s): txt.insert('end', s + '\n', 'b')
        def mono(s): txt.insert('end', s + '\n', 'mono')
        def note(s): txt.insert('end', s + '\n', 'note')

        h1('RH / RV / Rt Sequence Builder — Guide')
        p('Build a custom measurement sequence as a tree of blocks and '
          'loops. Click ⚡ Generate File to write the flat sequence file '
          'your sequencer procedure reads. The file format never contains '
          'loop syntax — loops are unrolled at generation time.')
        p()

        h2('1. Blocks (measurement steps)')
        p('Click ＋ Add RH / RV / Rt to append a measurement step. '
          'Double-click a block to edit it. Del removes the selection. '
          '↑ / ↓ move the selected node within its current level.')
        b('Block types:')
        p('• RH — Move Magnet: set target field, sweep rate, delay.')
        p('• RV — Voltage Sweep: ramp a gate SMU (Gate_1 / Gate_2 / smua / '
          'smub) to a target with a given step size.')
        p('• Rt — Wait / Acquire: acquire for N seconds at fixed V and H.')
        p()

        h2('2. Loops (repeat with different setpoints)')
        p('Select one or more contiguous sibling blocks, then click '
          '🔁 Wrap in Loop. A dialog asks:')
        p('• Sweep parameter — Field (T) or Voltage (V).')
        p('• Gate SMU to sweep — only when sweeping Voltage. This is what '
          'lets you nest two different gates without them clashing.')
        p('• Values — Linspace (start, end, #points) or Explicit list '
          '(comma-separated).')
        p()
        p('The selected blocks collapse into one purple loop row. '
          'Children appear indented underneath. Double-click a loop row to '
          'edit its parameter / values.')
        p()
        b('How loops override their children:')
        p('• Field loop → sets field_t on every child that has it (RH, Rt).')
        p('• Voltage loop → sets voltage_v only on RV blocks whose SMU '
          'matches the loop SMU. Rt keeps whatever voltage you typed by '
          'hand, on purpose (avoids ambiguity about which gate it tracks).')
        note('Note: the block values you see inside a loop are just '
             'placeholders — they get overwritten per iteration when you '
             'generate the file.')
        p()

        h2('3. Nesting (outer loop around inner loop)')
        p('Build the inner sequence first, wrap it in an inner loop, then '
          'select that loop and wrap it in an outer loop. Overrides '
          'accumulate: every active loop reaches the leaves at the same '
          'time.')
        p()

        h2('4. Worked examples')

        b('Example A — Gate scan at several fields')
        p('Goal: for each magnetic field, run one gate sweep.')
        p('Steps:')
        p('  1. Add:  RH  →  Rt  →  RV(Gate_1, V=-5)  →  RV(Gate_1, V=5)')
        p('  2. Select all four → Wrap in Loop → Field (T), values [0, 0.5, 1].')
        p('Resulting tree:')
        mono('🔁 Loop: Field (T) ∈ [0, 0.5, 1]   (3 pts)')
        mono('   RH   (field_t overwritten each pass)')
        mono('   Rt')
        mono('   RV  Gate_1   V=-5  step=10mV')
        mono('   RV  Gate_1   V=5   step=10mV')
        p('Expanded total: 3 fields × 4 blocks = 12 blocks written.')
        p()

        b('Example B — Field scan at several gate values')
        p('Goal: for each gate voltage, run one field sweep.')
        p('Steps:')
        p('  1. Add:  RH(0→1T)  →  Rt  →  RH(1→0T)  →  Rt')
        p('  2. Select all four → Wrap in Loop → Field (T), values [0, 1].')
        p('  3. Select the new loop → Wrap in Loop → Voltage (V),')
        p('     SMU = Gate_1, values [-5, 0, 5].')
        p('Resulting tree:')
        mono('🔁 Loop: Voltage (V) ∈ [-5, 0, 5]   [SMU \'Gate_1\']')
        mono('   🔁 Loop: Field (T) ∈ [0, 1]')
        mono('      RH   (0 → 1 T)')
        mono('      Rt')
        mono('      RH   (1 → 0 T)')
        mono('      Rt')
        note('The RH blocks don\'t have an SMU, so the outer Voltage loop '
             'only affects them if you add RV blocks. In this example the '
             'outer loop is only meaningful if there is an RV(Gate_1) inside '
             'that should move between gate values — add one as the first '
             'child of the inner loop if you need the gate ramped.')
        p()

        b('Example C — 2D gate map (two gates nested)')
        p('Goal: sweep Gate_2 over a range at each Gate_1 value.')
        p('Steps:')
        p('  1. Add:  RV(Gate_1)  →  RV(Gate_2, V=-5)  →  RV(Gate_2, V=5)')
        p('  2. Select the two RV(Gate_2) blocks → Wrap in Loop →')
        p('     Voltage (V), SMU = Gate_2, values [-5, 5].')
        p('  3. Select everything → Wrap in Loop →')
        p('     Voltage (V), SMU = Gate_1, values [0, 1, 2, 3, 4, 5].')
        p('Resulting tree:')
        mono('🔁 Outer: Voltage ∈ [0, 1, 2, 3, 4, 5]  [SMU \'Gate_1\']')
        mono('   RV  Gate_1  step=10mV')
        mono('   🔁 Inner: Voltage ∈ [-5, 5]  [SMU \'Gate_2\']')
        mono('      RV  Gate_2  step=10mV')
        mono('      RV  Gate_2  step=10mV')
        p('Expanded total: 6 outer × 2 inner × (1 + 2) blocks = 36 blocks.')
        p()
        b('Two kinds of "step" — keep them distinct:')
        p('• Outer-loop setpoints = the loop values (where Gate_1 goes). '
          'Change by editing the outer loop.')
        p('• Ramp granularity between setpoints = step_mv on the RV(Gate_1) '
          'block. Change by editing that block.')
        note('First-iteration tip: set the RV(Gate_1) block\'s placeholder '
             'voltage_v equal to the first outer setpoint so the first ramp '
             'is zero (instrument starts from a known state).')
        p()

        h2('5. Rules & gotchas')
        p('• Same-SMU nested (Gate_1 inside Gate_1) = inner shadows outer — '
          'physically meaningless. Use two different SMUs to nest.')
        p('• Voltage loops never touch Rt voltages. Set Rt voltages by hand.')
        p('• Sidebar counts show the expanded (unrolled) totals — what will '
          'actually be written to the file.')
        p('• "Open Loop" dissolves a loop: its children stay in the parent, '
          'the loop wrapper is removed.')
        p('• Delete on a non-empty loop asks for confirmation and removes '
          'the whole subtree.')

        txt.config(state='disabled')

        # Close button
        bf = ttk.Frame(win, padding=(10, 8))
        bf.pack(fill='x')
        ttk.Button(bf, text='Close', command=win.destroy).pack(side='right')

        # Center on parent
        win.update_idletasks()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")

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
        expanded = _expand_sequence(self.sequence)
        if not expanded:
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
                for block in expanded:
                    write_block(f, block['type'], block_to_file_params(block))

            counts = {'RH': 0, 'RV': 0, 'Rt': 0}
            for b in expanded:
                counts[b['type']] += 1

            messagebox.showinfo(
                'Done',
                f"Sequence written successfully!\n\n"
                f"File:   {filepath}\n"
                f"Blocks: {len(expanded)}  "
                f"(RH: {counts['RH']}, RV: {counts['RV']}, Rt: {counts['Rt']})"
            )
        except Exception as e:
            messagebox.showerror('Write error', str(e))


# ─────────────────────────────────────────────────────────────────
#   Self-check: exercise the pure expansion logic (no GUI).
# ─────────────────────────────────────────────────────────────────

def _self_check():
    # field loop wrapping RH + RV(Gate_1) + RV(Gate_2)
    field_loop = {
        'type': 'LOOP', 'param': 'field_t', 'param_label': 'Field (T)',
        'smu': None, 'values': [0.0, 1.0],
        'children': [
            {'type': 'RH', 'field_t': -99, 'sweep_rate': 0.1, 'acq_delay': 1,
             'use_magnet': "'True'"},
            {'type': 'RV', 'smu': "'Gate_1'", 'voltage_v': -99, 'step_mv': 10,
             'acq_delay': 1, 'use_magnet': "'False'"},
            {'type': 'RV', 'smu': "'Gate_2'", 'voltage_v': 3, 'step_mv': 10,
             'acq_delay': 1, 'use_magnet': "'False'"},
        ],
    }
    out = _expand_sequence([field_loop])
    assert len(out) == 6, len(out)
    # field overridden on RH
    assert out[0]['field_t'] == 0.0 and out[3]['field_t'] == 1.0
    # Gate_1 voltage untouched (no voltage loop present)
    assert out[1]['voltage_v'] == -99 and out[2]['voltage_v'] == 3

    # gate-in-gate: outer Gate_1 loop, inner Gate_2 loop
    inner = {
        'type': 'LOOP', 'param': 'voltage_v', 'param_label': 'Voltage (V)',
        'smu': "'Gate_2'", 'values': [-1.0, 1.0],
        'children': [
            {'type': 'RV', 'smu': "'Gate_1'", 'voltage_v': -99, 'step_mv': 10,
             'acq_delay': 1, 'use_magnet': "'False'"},
            {'type': 'RV', 'smu': "'Gate_2'", 'voltage_v': -99, 'step_mv': 10,
             'acq_delay': 1, 'use_magnet': "'False'"},
        ],
    }
    outer = {
        'type': 'LOOP', 'param': 'voltage_v', 'param_label': 'Voltage (V)',
        'smu': "'Gate_1'", 'values': [0.0, 5.0],
        'children': [inner],
    }
    out = _expand_sequence([outer])
    # 2 outer × 2 inner × 2 children = 8
    assert len(out) == 8, len(out)
    # Each block: Gate_1 value tracks outer, Gate_2 tracks inner.
    for b in out:
        if b['smu'] == "'Gate_1'":
            assert b['voltage_v'] in (0.0, 5.0)
        else:
            assert b['voltage_v'] in (-1.0, 1.0)
    print('self-check OK')


if __name__ == '__main__':
    _self_check()
    app = SequenceBuilder()
    app.mainloop()
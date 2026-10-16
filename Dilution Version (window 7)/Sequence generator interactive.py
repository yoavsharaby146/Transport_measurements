"""
Dilution SEQUENCE GENERATOR — interactive console
=================================================
Standalone sibling of the Scripts-folder sequence generators, but for the
Dilution version: it builds a sequence step by step in the console and
saves a JSON file loadable by Sequence_GUI.py via "Load sequence (JSON)"
(format: {'base_dir': ..., 'sequence': [...]}).

Steps supported: Rt / RV / R_AUX / RH / Wait / Loop (nestable).
Every prompt shows its default — press Enter to accept.
Placeholders: any field may contain {V}, replaced by the current loop
value on each iteration (e.g. target_voltage = {V}, Subfolder = gate {V}V).

Usage:
    python "Sequence generator interactive.py"            # window (default)
    python "Sequence generator interactive.py" --console  # terminal mode
    python "Sequence generator interactive.py" --self-check
"""

import json
import os
import sys

DEFAULT_SAVE_DIR = r'C:\Users\USER\Desktop\Data\YoavSharaby'

# (key, label, default) — mirrors the main() signatures of the procedures
STEP_FIELDS = {
    'Rt': [
        ('title', 'Title', 'Rt'),
        ('acq_delay', 'Acquisition delay (s)', '1'),
        ('acq_length', 'Acquisition length (s)', '3600'),
    ],
    'RV': [
        ('title', 'Title', 'RV'),
        ('target_voltage', 'Target voltage (V)', '0.5'),
        ('step_size', 'Step size (mV)', '5'),
        ('acq_delay', 'Acquisition delay (s)', '1'),
        ('smu', 'SMU', 'Gate_1'),
    ],
    'R_AUX': [
        ('title', 'Title', 'AUX sweep'),
        ('target_AUX_voltage', 'Target AUX voltage (V)', '0'),
        ('step_size', 'Step size (mV)', '1'),
        ('acq_delay', 'Acquisition delay (s)', '1'),
        ('aux', 'Aux output (1-4)', '1'),
    ],
    'RH': [
        ('title', 'Title', 'RH'),
        ('target_field', 'Target field (T)', '0.5'),
        ('step_size', 'Step size (mT)', '5'),
        ('ramp_rate', 'Ramp rate (T/min)', '0.01'),
        ('axis', 'Axis (bx/by/bz)', 'bz'),
        ('acq_delay', 'Acquisition delay (s)', '10'),
    ],
    'Wait': [
        ('seconds', 'Seconds', '10'),
    ],
}

COMMON_FIELDS = [
    ('Resistor', 'Resistor / gain', 'Gain 3'),
    ('Contacts', 'Contacts', 'SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49-50'),
]

HELP = """\
Commands:
  rt / rv / aux / rh / w   add Rt / RV / R_AUX / RH / Wait step
  loop                     start a Loop (values: 'linspace(a,b,n)' or '1, 2, 3')
  end                      close the innermost open Loop
  t                        quick templates (gate hysteresis, AUX vs gate, ...)
  p                        print the sequence
  s                        save to JSON (loadable by Sequence_GUI.py)
  q                        quit without saving"""


# ---------------------------------------------------------------------------
# Pure helpers (no I/O) — testable
# ---------------------------------------------------------------------------
def ask_fields(fields, get_input):
    """Prompt for (key, label, default) triples; Enter accepts default."""
    params = {}
    for key, label, default in fields:
        raw = get_input('  %s [%s]: ' % (label, default)).strip()
        params[key] = raw if raw else default
    return params


def build_step(kind, get_input):
    """Return a step dict for a procedure / Wait step."""
    if kind == 'Wait':
        return {'type': 'Wait',
                'params': ask_fields(STEP_FIELDS['Wait'], get_input)}
    fields = STEP_FIELDS[kind] + COMMON_FIELDS + \
        [('Subfolder', 'Subfolder (optional, may contain {V})', '')]
    params = ask_fields(fields, get_input)
    return {'type': kind, 'params': params}


def parse_loop_values(raw):
    """Same semantics as Sequence_GUI.parse_values — no Qt import needed."""
    import re
    raw = str(raw).strip()
    if not raw:
        return []
    m = re.fullmatch(r'linspace\(([-+0-9.eE]+),([-+0-9.eE]+),([-+0-9.eE]+)\)',
                     raw.replace(' ', ''))
    if m:
        import numpy as np
        start, stop, num = float(m.group(1)), float(m.group(2)), int(m.group(3))
        return [float(v) for v in np.linspace(start, stop, num)]
    return [float(v) for v in raw.split(',')]


def _deepest_open_loop(steps):
    """Innermost Loop carrying the _open flag, or None."""
    for s in reversed(steps):
        if s['type'] == 'Loop':
            if s.get('_open'):
                inner = _deepest_open_loop(s['children'])
                return inner or s
    return None


def add_step(sequence, step):
    """Append to the innermost open Loop, or to the top level."""
    loop = _deepest_open_loop(sequence)
    (loop['children'] if loop else sequence).append(step)


def finalize(sequence):
    """Deep copy with loop 'values' resolved to float lists, flags removed."""
    import copy
    out = copy.deepcopy(sequence)

    def walk(steps):
        for s in steps:
            if s['type'] == 'Loop':
                s['values'] = parse_loop_values(s['values'])
                s.pop('_open', None)
                walk(s['children'])
    walk(out)
    return out


def save_json(sequence, base_dir, path):
    data = {'base_dir': base_dir, 'sequence': finalize(sequence)}
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return data


def print_tree(sequence):
    """Indented console view of the sequence tree."""
    def walk(steps, indent):
        for s in steps:
            if s['type'] == 'Loop':
                vals = s['values'] if isinstance(s['values'], str) \
                    else ', '.join('%g' % v for v in s['values'])
                print('%sLoop over [%s] (%d children)'
                      % (indent, vals, len(s['children'])))
                walk(s['children'], indent + '    ')
            elif s['type'] == 'Wait':
                print('%sWait %s s' % (indent, s['params'].get('seconds')))
            else:
                bits = ['%s=%s' % (k, s['params'][k])
                        for k in ('target_voltage', 'target_AUX_voltage',
                                  'target_field', 'acq_length')
                        if k in s['params']]
                sub = s['params'].get('Subfolder', '')
                if sub:
                    bits.append('sub=%s' % sub)
                print('%s%s  %s' % (indent, s['type'], '  '.join(bits)))
    walk(sequence, '')


# ---------------------------------------------------------------------------
# Quick templates — pure builders shared by console + GUI
# ---------------------------------------------------------------------------
def build_gate_hysteresis(p):
    """RV to +V, -V, back to 0. Keys: target_voltage, step_size,
    acq_delay, smu."""
    v = str(p['target_voltage']).lstrip('+')

    def rv(target, sub):
        return {'type': 'RV', 'params': {
            'title': 'RV', 'target_voltage': target,
            'step_size': p['step_size'], 'acq_delay': p['acq_delay'],
            'smu': p['smu'], 'Resistor': COMMON_FIELDS[0][2],
            'Contacts': COMMON_FIELDS[1][2], 'Subfolder': sub}}
    return [rv('+' + v, 'hyst +%sV' % v),
            rv('-' + v, 'hyst -%sV' % v),
            rv('0', 'hyst 0V')]


def build_aux_vs_gate(p):
    """Loop over gate values; each: set gate, then AUX +A -> -A -> +A."""
    return [{'type': 'Loop',
             'values': 'linspace(%s,%s,%s)' % (p['gate_start'],
                                               p['gate_stop'],
                                               p['gate_steps']),
             'children': [
                 {'type': 'RV', 'params': {
                     'title': 'Gate set', 'target_voltage': '{V}',
                     'step_size': p['gate_step_size'],
                     'acq_delay': p['acq_delay'], 'smu': p['smu'],
                     'Resistor': COMMON_FIELDS[0][2],
                     'Contacts': COMMON_FIELDS[1][2],
                     'Subfolder': 'gate {V}V'}},
                 _aux_sweep_step(p, p['aux_high']),
                 _aux_sweep_step(p, p['aux_low']),
                 _aux_sweep_step(p, p['aux_high']),
             ]}]


def _aux_sweep_step(p, target):
    return {'type': 'R_AUX', 'params': {
        'title': 'AUX sweep', 'target_AUX_voltage': target,
        'step_size': p['step_size'], 'acq_delay': p['acq_delay'],
        'aux': p['aux'], 'Resistor': COMMON_FIELDS[0][2],
        'Contacts': COMMON_FIELDS[1][2], 'Subfolder': 'gate {V}V'}}


def build_aux_hysteresis(p):
    """AUX +A, -A, back to +A at the current operating point."""
    a = str(p['aux_high']).lstrip('+')

    def step(target, sub):
        return {'type': 'R_AUX', 'params': {
            'title': 'AUX sweep', 'target_AUX_voltage': target,
            'step_size': p['step_size'], 'acq_delay': p['acq_delay'],
            'aux': p['aux'], 'Resistor': COMMON_FIELDS[0][2],
            'Contacts': COMMON_FIELDS[1][2], 'Subfolder': sub}}
    return [step('+' + a, 'AUX hyst +%sV' % a),
            step('-' + a, 'AUX hyst -%sV' % a),
            step('+' + a, 'AUX hyst +%sV' % a)]


TEMPLATES = [
    ('Gate hysteresis RV +V/-V/0', build_gate_hysteresis,
     [('target_voltage', 'Target voltage V', '4'),
      ('step_size', 'Step size mV', '5'),
      ('acq_delay', 'Acq delay s', '1'),
      ('smu', 'SMU', 'Gate_1')]),
    ('AUX hysteresis vs gate (loop)', build_aux_vs_gate,
     [('gate_start', 'Gate start', '-1'),
      ('gate_stop', 'Gate stop', '1'),
      ('gate_steps', 'Gate steps', '51'),
      ('aux_high', 'Aux high V', '0.5'),
      ('aux_low', 'Aux low V', '-0.5'),
      ('step_size', 'Aux step mV', '1'),
      ('gate_step_size', 'Gate step mV', '1000'),
      ('acq_delay', 'Acq delay s', '1'),
      ('aux', 'Aux output 1-4', '1'),
      ('smu', 'SMU', 'Gate_1')]),
    ('AUX hysteresis at point', build_aux_hysteresis,
     [('aux_high', 'Aux amplitude V', '4'),
      ('step_size', 'Aux step mV', '20'),
      ('acq_delay', 'Acq delay s', '4'),
      ('aux', 'Aux output 1-4', '1')]),
]


def template_menu(sequence, get_input, echo):
    echo('templates:')
    for i, (name, _b, _f) in enumerate(TEMPLATES, 1):
        echo('  %d) %s' % (i, name))
    t = get_input('template number: ').strip()
    if not t.isdigit() or not 1 <= int(t) <= len(TEMPLATES):
        echo('unknown template')
        return
    name, builder, fields = TEMPLATES[int(t) - 1]
    p = ask_fields(fields, get_input)
    steps = builder(p)
    sequence.extend(steps)
    echo('%s added (%d top-level steps)' % (name, len(steps)))



# ---------------------------------------------------------------------------
# Interactive session
# ---------------------------------------------------------------------------
def run(get_input=input, echo=print):
    sequence = []
    base_dir = get_input('Base save dir [%s]: ' % DEFAULT_SAVE_DIR).strip() \
        or DEFAULT_SAVE_DIR
    echo(HELP)
    while True:
        cmd = get_input('\ncommand (h=help): ').strip().lower()
        if cmd in ('h', 'help'):
            echo(HELP)
        elif cmd in ('rt', 'rv', 'aux', 'rh', 'w'):
            kind = {'rt': 'Rt', 'rv': 'RV', 'aux': 'R_AUX',
                    'rh': 'RH', 'w': 'Wait'}[cmd]
            add_step(sequence, build_step(kind, get_input))
            echo('added %s' % kind)
        elif cmd == 'loop':
            raw = get_input('  Loop values '
                            '(linspace(start,stop,n) or 1, 2, 3): ')
            sequence.append({'type': 'Loop', 'values': raw.strip(),
                             'children': [], '_open': True})
            echo('loop opened — add children now, "end" to close')
        elif cmd == 'end':
            loop = _deepest_open_loop(sequence)
            if loop:
                loop.pop('_open')
                echo('loop closed (%d children)' % len(loop['children']))
            else:
                echo('no open loop')
        elif cmd == 't':
            template_menu(sequence, get_input, echo)
        elif cmd == 'p':
            print_tree(finalize(sequence))
        elif cmd == 's':
            default = os.path.join(base_dir or '.', 'sequence.json')
            path = get_input('Save to [%s]: ' % default).strip() or default
            save_json(sequence, base_dir, path)
            echo('saved %s — load it with "Load sequence (JSON)" '
                 'in Sequence_GUI.py' % path)
        elif cmd in ('q', 'quit', 'exit'):
            return sequence
        else:
            echo('unknown command — h for help')


# ---------------------------------------------------------------------------
# Self-check — scripted session, no real input, no instruments
# ---------------------------------------------------------------------------
def _self_check():
    answers = iter([
        DEFAULT_SAVE_DIR,                  # base dir
        't', '2',                          # template: AUX vs gate
        '-1', '1', '5',                    # gate start/stop/steps
        '0.5', '-0.5', '1', '1000',        # aux high/low, aux step, gate step
        '1', '1', 'Gate_1',                # delay, aux out, smu
        'w', '120',                        # Wait 120 s (top level)
        'loop', 'linspace(0.5,-0.5,3)',    # second loop
        'aux', '', '0.2', '1', '0.5', '2',  # R_AUX inside it (title default)
        'Gain 1', 'SRS830_1 18-38', '',    # common + subfolder
        'end',                             # close loop
        'p', 's', '',                      # print, save to default path
        'q',
    ])
    saved = {}

    def fake_save(sequence, base_dir, path):
        saved['data'] = {'base_dir': base_dir,
                         'sequence': finalize(sequence)}
        return saved['data']

    globals()['save_json'] = fake_save
    try:
        run(get_input=lambda prompt='': next(answers), echo=lambda m='': None)
    finally:
        globals()['save_json'] = fake_save

    data = saved['data']
    seq = data['sequence']
    assert seq[0]['type'] == 'Loop' and len(seq[0]['children']) == 4
    assert seq[0]['values'] == [-1.0, -0.5, 0.0, 0.5, 1.0]
    assert seq[1] == {'type': 'Wait', 'params': {'seconds': '120'}}
    assert seq[2]['type'] == 'Loop' and len(seq[2]['children']) == 1
    assert seq[2]['values'] == [0.5, 0.0, -0.5]
    assert seq[2]['children'][0]['params']['target_AUX_voltage'] == '0.2'
    assert '_open' not in json.dumps(data), 'internal flag leaked to JSON'
    # cross-check with the sequencer's own expander (needs PyQt5)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from Sequence_GUI import expand
        runs = expand(data['sequence'], data['base_dir'])
        assert len(runs) == 5 * 4 + 1 + 3, len(runs)
        print('expand() cross-check OK: %d runs' % len(runs))
    except ImportError:
        print('PyQt5 unavailable — skipped expand() cross-check')
    # JSON round trip
    assert data == json.loads(json.dumps(data))
    print('self-check OK')


# ---------------------------------------------------------------------------
# GUI (tkinter) — same builders, window front end
# ---------------------------------------------------------------------------
def step_summary(step):
    """One-line summary string for tree/list display."""
    if step['type'] == 'Loop':
        vals = step['values'] if isinstance(step['values'], str) \
            else ', '.join('%g' % v for v in step['values'])
        return 'over [%s]  (%d children)' % (vals, len(step['children']))
    if step['type'] == 'Wait':
        return 'wait %s s' % step['params'].get('seconds')
    p = step['params']
    bits = ['%s=%s' % (k, p[k]) for k in
            ('target_voltage', 'target_AUX_voltage', 'target_field',
             'acq_length') if k in p]
    if p.get('Subfolder'):
        bits.append('sub=%s' % p['Subfolder'])
    return '  '.join(bits)


def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    sequence = []
    iid_to_step = {}
    counter = [0]

    root = tk.Tk()
    root.title('Dilution sequence generator')

    # ---------------- helpers ----------------
    def containing_list(step):
        """List that directly holds `step` (top level or a loop's children)."""
        def walk(steps):
            for s in steps:
                if s is step:
                    return steps
                if s['type'] == 'Loop':
                    res = walk(s['children'])
                    if res is not None:
                        return res
            return None
        return walk(sequence) or sequence

    def rebuild_tree():
        tree.delete(*tree.get_children())
        iid_to_step.clear()

        def insert(steps, parent=''):
            for s in steps:
                counter[0] += 1
                iid = 's%d' % counter[0]
                iid_to_step[iid] = s
                label = s['type'] + (' (loop)' if s['type'] == 'Loop' else '')
                item = tree.insert(parent, 'end', iid, text=label,
                                   values=(step_summary(s),))
                if s['type'] == 'Loop':
                    insert(s['children'], item)
        insert(sequence)

    def selected_step():
        sel = tree.selection()
        return iid_to_step[sel[0]] if sel else None

    def form_dialog(title, fields):
        """Modal field-entry dialog; returns dict or None on cancel."""
        dlg = tk.Toplevel(root)
        dlg.title(title)
        dlg.transient(root)
        dlg.grab_set()
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill='both', expand=True)
        entries = {}
        for row, (key, label, default) in enumerate(fields):
            ttk.Label(frm, text=label + ':').grid(
                row=row, column=0, sticky='e', padx=4, pady=2)
            var = tk.StringVar(value=str(default))
            ent = ttk.Entry(frm, textvariable=var, width=32)
            ent.grid(row=row, column=1, padx=4, pady=2)
            entries[key] = var
            if row == 0:
                ent.focus_set()
        result = []

        def ok(event=None):
            result.append({key: entries[key].get().strip() or default
                           for key, _label, default in fields})
            dlg.destroy()

        def cancel(event=None):
            dlg.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=8)
        ttk.Button(btns, text='OK', command=ok).pack(side='left', padx=4)
        ttk.Button(btns, text='Cancel', command=cancel).pack(side='left')
        dlg.bind('<Return>', ok)
        dlg.bind('<Escape>', cancel)
        root.wait_window(dlg)
        return result[0] if result else None

    def procedure_fields(kind):
        return STEP_FIELDS[kind] + COMMON_FIELDS + \
            [('Subfolder', 'Subfolder (optional, {V} allowed)', '')]

    def select_step(step):
        for iid, s in iid_to_step.items():
            if s is step:
                tree.selection_set(iid)
                break

    # ---------------- actions ----------------
    def _placement(sel, into_loop):
        """(target_list, insert_index) for a new step, or None + warning."""
        if sel is None:
            return sequence, len(sequence)
        if into_loop:
            if sel['type'] != 'Loop':
                sel = _owning_loop(sequence, sel)
                if sel is None:
                    messagebox.showwarning(
                        'No loop selected',
                        'Select a Loop step (or a step inside one) '
                        'to add into it.')
                    return None
            return sel['children'], len(sel['children'])
        lst = containing_list(sel)
        return lst, lst.index(sel) + 1

    def _owning_loop(steps, target):
        """Innermost Loop whose children contain target, else None."""
        for s in steps:
            if s['type'] == 'Loop':
                if target in s['children']:
                    return s
                res = _owning_loop(s['children'], target)
                if res is not None:
                    return res
        return None

    def add_procedure(kind, into_loop=False):
        fields = STEP_FIELDS[kind] if kind == 'Wait' else procedure_fields(kind)
        params = form_dialog('Add %s' % kind, fields)
        if params is None:
            return
        place = _placement(selected_step(), into_loop)
        if place is None:
            return
        target_list, idx = place
        target_list.insert(idx, {'type': kind, 'params': params})
        rebuild_tree()
        select_step(target_list[idx])

    def add_loop(into_loop=False):
        params = form_dialog('Add Loop', [
            ('values', 'Values (linspace(a,b,n) or 1, 2, 3)',
             'linspace(-1,1,11)')])
        if params is None:
            return
        place = _placement(selected_step(), into_loop)
        if place is None:
            return
        target_list, idx = place
        target_list.insert(
            idx, {'type': 'Loop', 'values': params['values'], 'children': []})
        rebuild_tree()
        select_step(target_list[idx])

    def add_into_loop():
        kind = into_combo.get()
        if kind == 'Loop':
            add_loop(into_loop=True)
        else:
            add_procedure(kind, into_loop=True)

    def add_template():
        menu = tk.Menu(root, tearoff=0)

        def make_go(builder, fields, name):
            def go():
                p = form_dialog('Template: %s' % name, fields)
                if p is None:
                    return
                sequence.extend(builder(p))
                rebuild_tree()
            return go

        for name, builder, fields in TEMPLATES:
            menu.add_command(label=name, command=make_go(builder, fields, name))
        menu.tk_popup(*root.winfo_pointerxy())

    def delete_selected():
        sel = selected_step()
        if sel is None:
            return
        containing_list(sel).remove(sel)
        rebuild_tree()

    def move_selected(delta):
        sel = selected_step()
        if sel is None:
            return
        lst = containing_list(sel)
        i = lst.index(sel)
        j = i + delta
        if 0 <= j < len(lst):
            lst[i], lst[j] = lst[j], lst[i]
            rebuild_tree()
            select_step(sel)

    def save():
        if not sequence:
            messagebox.showinfo('Nothing to save', 'Sequence is empty.')
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.json', filetypes=[('Sequence JSON', '*.json')],
            initialfile='sequence.json')
        if not path:
            return
        try:
            save_json(sequence, dir_var.get().strip(), path)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Save failed', str(exc))
            return
        messagebox.showinfo(
            'Saved', path + '\n\nLoad it in Sequence_GUI.py via '
                            '"Load sequence (JSON)".')

    # ---------------- layout ----------------
    top = ttk.Frame(root, padding=6)
    top.pack(fill='x')
    ttk.Label(top, text='Base save dir:').pack(side='left')
    dir_var = tk.StringVar(value=DEFAULT_SAVE_DIR)
    ttk.Entry(top, textvariable=dir_var, width=52).pack(side='left', padx=4)

    left = ttk.Frame(root, padding=(10, 4))
    left.pack(side='left', fill='y')
    for kind in ('Rt', 'RV', 'R_AUX', 'RH', 'Wait'):
        ttk.Button(left, text='Add %s' % kind,
                   command=lambda k=kind: add_procedure(k)).pack(
            fill='x', pady=2)
    ttk.Button(left, text='Add Loop', command=lambda: add_loop()).pack(
        fill='x', pady=2)
    ttk.Separator(left).pack(fill='x', pady=6)
    into_row = ttk.Frame(left)
    into_row.pack(fill='x', pady=2)
    into_combo = ttk.Combobox(
        into_row, state='readonly', width=8,
        values=('Rt', 'RV', 'R_AUX', 'RH', 'Wait', 'Loop'))
    into_combo.set('RV')
    into_combo.pack(side='left', fill='x', expand=True)
    ttk.Button(into_row, text='Add into\nselected loop',
               command=add_into_loop).pack(side='left', padx=(4, 0))
    ttk.Separator(left).pack(fill='x', pady=6)
    ttk.Button(left, text='Templates...', command=add_template).pack(
        fill='x', pady=2)
    ttk.Separator(left).pack(fill='x', pady=6)
    ttk.Button(left, text='Up',
               command=lambda: move_selected(-1)).pack(fill='x', pady=2)
    ttk.Button(left, text='Down',
               command=lambda: move_selected(1)).pack(fill='x', pady=2)
    ttk.Button(left, text='Delete', command=delete_selected).pack(
        fill='x', pady=2)
    ttk.Separator(left).pack(fill='x', pady=6)
    ttk.Button(left, text='Save sequence (JSON)', command=save).pack(
        fill='x', pady=2)
    ttk.Label(left, text='Add: inserts after the selected step\n'
                         '(same level, never inside).\n'
                         'Select a Loop + use the combobox\n'
                         'to add inside it.',
              foreground='gray', justify='left').pack(pady=8)

    right = ttk.Frame(root, padding=(0, 4, 10, 8))
    right.pack(side='left', fill='both', expand=True)
    tree = ttk.Treeview(right, columns=('summary',), show='tree headings',
                        selectmode='browse')
    tree.heading('#0', text='Step')
    tree.heading('summary', text='Summary')
    tree.column('#0', width=160)
    tree.column('summary', width=520)
    scroll = ttk.Scrollbar(right, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')

    rebuild_tree()
    root.mainloop()


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        _self_check()
    elif '--console' in sys.argv:
        run()
    else:
        run_gui()



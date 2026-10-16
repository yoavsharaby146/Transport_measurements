"""Headless-ish driver test for the tkinter generator window.

Patches Tk.mainloop so run_gui() builds the window and returns; then
invokes button commands directly, fills dialogs, saves, reloads, and
cross-checks with Sequence_GUI.expand().
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog
import tkinter.messagebox

tk.Tk.mainloop = lambda self, *a, **k: None          # build, don't block
tkinter.messagebox.showinfo = staticmethod(lambda *a, **k: print('[info]', a))
tkinter.messagebox.showerror = staticmethod(lambda *a, **k: print('[error]', a))

_import_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'Sequence generator interactive.py')
import importlib.util
spec = importlib.util.spec_from_file_location('seqgen', _import_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TMP = os.path.join(tempfile.gettempdir(), 'gui_gen_test_sequence.json')
tkinter.filedialog.asksaveasfilename = staticmethod(lambda **k: TMP)

mod.run_gui()

root = tk._default_root
assert root is not None and root.winfo_exists()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def button(text):
    hits = [w for w in walk(root)
            if isinstance(w, ttk.Button) and str(w['text']) == text]
    assert len(hits) == 1, (text, len(hits))
    return hits[0]


def schedule_dialog_fill(values, delay_ms=50):
    """form_dialog blocks inside wait_window, so queue the fill via after()."""
    def fill():
        for toplevel in [w for w in walk(root)
                         if isinstance(w, tk.Toplevel) and w.winfo_exists()]:
            entries = [w for w in walk(toplevel) if isinstance(w, ttk.Entry)]
            oks = [w for w in walk(toplevel)
                   if isinstance(w, ttk.Button) and str(w['text']) == 'OK']
            if not entries or not oks:
                continue
            for ent, val in zip(entries, values):
                ent.delete(0, 'end')
                ent.insert(0, val)
            oks[0].invoke()
            return
        raise AssertionError('no dialog appeared to fill')
    root.after(delay_ms, fill)


tree = None


def get_tree():
    global tree
    if tree is None:
        tree = [w for w in walk(root) if isinstance(w, ttk.Treeview)][0]
    return tree


def loop_iid():
    hits = [i for i in get_tree().get_children('')
            if 'loop' in get_tree().item(i, 'text').lower()]
    assert len(hits) == 1
    return hits[0]


# --- add a Loop (values: linspace(-1,1,5)); nothing selected -> top level ---
schedule_dialog_fill(['linspace(-1,1,5)'])
button('Add Loop').invoke()
assert len(get_tree().get_children('')) == 1
assert 'loop' in get_tree().item(loop_iid(), 'text').lower()

# --- plain Add with loop selected goes AFTER the loop, not inside ---
assert list(get_tree().selection()) == [loop_iid()]   # auto-select still on
schedule_dialog_fill(['5'])
button('Add Wait').invoke()
assert len(get_tree().get_children('')) == 2, 'plain Add must not nest'
assert len(get_tree().get_children(loop_iid())) == 0
top_labels = [get_tree().item(i, 'text') for i in get_tree().get_children('')]
assert top_labels == ['Loop (loop)', 'Wait'], top_labels

# --- combobox + "Add into selected loop" nests inside ---
get_tree().selection_set(loop_iid())


def add_into(kind, values):
    combo = [w for w in walk(root) if isinstance(w, ttk.Combobox)][0]
    combo.set(kind)
    schedule_dialog_fill(values)
    button('Add into\nselected loop').invoke()


add_into('RV', ['', '{V}', '1000', '0.5', 'Gate_1', 'Gain 3', 'SRS830_1',
                'gate {V}V'])
add_into('Rt', ['', '2', '60', 'Gain 3', 'SRS830_1', 'rt {V}V'])
add_into('Wait', ['30'])
add_into('Loop', ['linspace(0.5,-0.5,3)'])   # nested loop inside the loop

kids = get_tree().get_children(loop_iid())
assert len(kids) == 4, 'children: %d' % len(kids)
labels = [get_tree().item(k, 'text') for k in kids]
assert labels == ['RV', 'Rt', 'Wait', 'Loop (loop)'], labels

# --- save and cross-check ---
button('Save sequence (JSON)').invoke()
data = json.load(open(TMP))
seq = data['sequence']
assert seq[0]['type'] == 'Loop' and len(seq[0]['children']) == 4
assert seq[0]['values'] == [-1.0, -0.5, 0.0, 0.5, 1.0]
child_types = [c['type'] for c in seq[0]['children']]
assert child_types == ['RV', 'Rt', 'Wait', 'Loop'], child_types
assert seq[0]['children'][0]['params']['target_voltage'] == '{V}'
assert seq[0]['children'][1]['params']['Subfolder'] == 'rt {V}V'
assert seq[0]['children'][2]['params'] == {'seconds': '30'}
nested = seq[0]['children'][3]
assert nested['values'] == [0.5, 0.0, -0.5]
assert seq[1] == {'type': 'Wait', 'params': {'seconds': '5'}}

from Sequence_GUI import expand
runs = expand(data['sequence'], data['base_dir'])
# outer loop: RV + Rt + Wait per value = 15; nested loop empty = 0; top Wait = 1
assert len(runs) == 5 * 3 + 1, len(runs)

os.remove(TMP)
root.destroy()
print('GUI WINDOW TEST PASSED: build, nest, save, reload,', len(runs), 'runs')

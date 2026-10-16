"""Headless (offscreen) test of the Sequence_GUI loop + template workflow."""
import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)
from Sequence_GUI import SequenceWindow, expand, TemplateDialog
win = SequenceWindow()

# --- user step 1: create a Loop step via the editor ---
win.type_combo.setCurrentText('Loop')
win._fields['values'].setText('linspace(-1,1,51)')
win.add_btn.click()

assert win.tree.topLevelItemCount() == 1
loop_item = win.tree.topLevelItem(0)
loop = loop_item._step
assert loop['type'] == 'Loop' and loop['children'] == []

# --- user step 2: select the loop, add an RV child into it ---
win.tree.setCurrentItem(loop_item)
app.processEvents()          # let itemSelectionChanged -> load_selected run

win.type_combo.setCurrentText('RV')
win._fields['target_voltage'].setText('{V}')
win.add_loop_btn.click()

assert len(loop['children']) == 1, 'child NOT appended to loop dict'
assert loop_item.childCount() == 1, 'child NOT shown in tree'

# --- user step 3: add a second child (selected via the RV child) ---
win.tree.setCurrentItem(loop_item.child(0))
app.processEvents()
win.type_combo.setCurrentText('Wait')
win._fields['seconds'].setText('2')
win.add_loop_btn.click()
assert len(loop['children']) == 2

# --- user step 4: edit loop values via Apply (fallback path) ---
win.tree.setCurrentItem(loop_item)
app.processEvents()
win._fields['values'].setText('0.5, -0.5')
win.apply_btn.click()
assert loop['values'] == [0.5, -0.5], loop['values']

# --- round trip: tree -> expand ---
runs = win.tree_to_sequence()
flat = expand(runs, r'C:\data')
print('flat runs:', [(r[0], r[2] if r[0] == 'call' else r[1]) for r in flat])

# --- template wizard: build steps and insert into the tree ---
dlg = TemplateDialog(win)
dlg.combo.setCurrentText('AUX hysteresis vs Gate (Loop)')
app.processEvents()               # rebuild_form ran via signal
dlg._fields['gate_steps'].setText('5')
steps = dlg.build_steps()
assert len(steps) == 1 and steps[0]['type'] == 'Loop'
assert len(steps[0]['values']) == 5 and len(steps[0]['children']) == 4

win.tree.clear()
for s in steps:                   # open_templates insertion logic (exec_ blocks headless)
    win.make_item(s)
win.refresh_summaries()
assert win.tree.topLevelItemCount() == 1
assert win.tree.topLevelItem(0).childCount() == 4, 'children missing in tree'
assert len(win.tree.topLevelItem(0)._step['children']) == 4
flat2 = expand(win.tree_to_sequence(), r'C:\data')
assert len(flat2) == 20, len(flat2)

# template switch rebuilds the form
dlg.combo.setCurrentText('RH field sweep')
app.processEvents()
assert 'target_field' in dlg._fields and 'gate_start' not in dlg._fields

print('ALL GUI LOOP + TEMPLATE CHECKS PASSED')


"""
Sequence GUI for the Dilution (window 7) measurement procedures.

Build a sequence of measurement steps (Rt / RV / R_AUX / RH / Wait), optionally
wrapped in a Loop step that repeats a group of steps over a list of values
(e.g. gate voltages). Any parameter field or the per-step Subfolder may contain
the placeholder {V}, which is replaced by the current loop value on each
iteration (this reproduces the 'AUX_hyst {target_gate_voltage}V' pattern from
Main.py).

Run:      python Sequence_GUI.py
Check:    python Sequence_GUI.py --self-check   (no instruments touched)
"""

import os
import sys
import re
import json
import copy
import importlib
import logging

# make sure sibling modules (procedures / Instruments) import regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt, QTimer, QEventLoop
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QComboBox, QFormLayout, QVBoxLayout,
    QHBoxLayout, QLineEdit, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QDialog, QCheckBox, QGridLayout, QSpinBox
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Procedure registry — mirrors the main() signatures of the procedure modules.
# entries are (name, type, default)
# ---------------------------------------------------------------------------
PROCEDURES = {
    'Rt': {
        'module': 'Rt_procedure',
        'params': [
            ('title', str, 'Rt'),
            ('acq_delay', float, 1),
            ('acq_length', int, 3600),
        ],
    },
    'RV': {
        'module': 'RV_procedure',
        'params': [
            ('title', str, 'RV'),
            ('target_voltage', float, 0.5),
            ('step_size', float, 5),
            ('acq_delay', float, 1),
            ('smu', str, 'Gate_1'),
        ],
    },
    'R_AUX': {
        'module': 'R_AUX_procedure',
        'params': [
            ('title', str, 'AUX sweep'),
            ('target_AUX_voltage', float, 0),
            ('step_size', float, 1),
            ('acq_delay', float, 1),
            ('aux', int, 1),
        ],
    },
    'RH': {
        'module': 'RH_procedure',
        'params': [
            ('title', str, 'RH'),
            ('target_field', float, 0.5),
            ('step_size', int, 5),
            ('ramp_rate', float, 0.001),
            ('axis', str, 'bz'),
            ('acq_delay', float, 10),
        ],
    },
}
COMMON_PARAMS = [
    ('Resistor', str, 'Gain 3'),
    ('Contacts', str, 'SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49-50'),
]
STEP_TYPES = list(PROCEDURES) + ['Wait', 'Loop']

DEFAULT_SAVE_DIR = r'C:\Users\USER\Desktop\Data\YoavSharaby'

# pymeasure status codes differ across versions (0.15: 0=Finished;
# 0.9: 3=Finished) — resolve names dynamically instead of hardcoding
def _status_name(status):
    try:
        from pymeasure.experiment.procedure import Procedure
        codes = getattr(Procedure, 'STATUS_CODES', None) or \
            getattr(Procedure, 'STATUS_STRINGS', {})
        return str(codes.get(int(status), 'status %s' % status))
    except Exception:
        return 'status %s' % status


def execute_manager(manager):
    """Run one procedure manager without nested QApplication.exec_().

    The procedures' own main.run() calls app.exec_(), which only works
    standalone (closing the plot window quits a lone app). Inside this GUI
    that loop would never return properly, so we drive the worker ourselves:
    start worker, show window, poll; closing the window stops the measurement.
    """
    worker = manager.worker
    window = manager.window
    worker.start()
    window.show()
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(200)

    def check():
        if not window.isVisible():
            worker.stop()  # user closed the plot window -> stop measuring
        if not worker.is_alive():
            poll.stop()
            loop.quit()

    poll.timeout.connect(check)
    poll.start(200)
    loop.exec_()
    if window.isVisible():
        window.close()



# ---------------------------------------------------------------------------
# Pure logic (no Qt, no instruments) — testable
# ---------------------------------------------------------------------------
_LINSPACE_RE = re.compile(
    r'linspace\(([-+0-9.eE]+),([-+0-9.eE]+),([-+0-9.eE]+)\)', re.IGNORECASE)


def substitute(value, context):
    """Replace {V}-style placeholders in a string using the loop context."""
    if isinstance(value, str) and context:
        for key, val in context.items():
            value = value.replace('{%s}' % key, str(val))
    return value


def convert(value, typ, where):
    try:
        return typ(value)
    except (TypeError, ValueError):
        raise ValueError("%s: cannot interpret '%s' as %s"
                         % (where, value, typ.__name__))


def parse_values(text):
    """Parse a loop-values string.

    Accepts either a comma list ('0.5, -0.5, 0') or
    'linspace(start, stop, num)'.
    """
    text = str(text).strip()
    if not text:
        return []
    m = _LINSPACE_RE.fullmatch(text.replace(' ', ''))
    if m:
        import numpy as np
        start, stop, num = float(m.group(1)), float(m.group(2)), int(m.group(3))
        return [float(v) for v in np.linspace(start, stop, num)]
    try:
        return [float(v) for v in text.split(',')]
    except ValueError:
        raise ValueError("Loop values: cannot parse '%s' "
                         "(use '0.5, -0.5' or 'linspace(0.5,-0.5,11)')" % text)


def expand(sequence, base_dir):
    """Flatten a sequence into concrete runnable steps.

    Returns a list of tuples:
        ('wait', seconds)
        ('call', module_name, step_type, kwargs)
    kwargs are ready for `module.main(**kwargs)`. Pure function.
    """
    runs = []

    def do_step(step, ctx):
        typ = step.get('type')
        if typ == 'Loop':
            for v in step.get('values', []):
                child_ctx = dict(ctx)
                child_ctx['V'] = v
                for child in step.get('children', []):
                    do_step(child, child_ctx)
        elif typ == 'Wait':
            sec = convert(substitute(step['params']['seconds'], ctx),
                          float, 'Wait step')
            runs.append(('wait', sec))
        elif typ in PROCEDURES:
            spec = PROCEDURES[typ]
            kwargs = {}
            for name, t, default in spec['params'] + COMMON_PARAMS:
                raw = step['params'].get(name, default)
                kwargs[name] = convert(substitute(raw, ctx), t,
                                       "%s '%s'" % (typ, name))
            sub = substitute(step['params'].get('Subfolder', ''), ctx).strip()
            kwargs['save_dir'] = os.path.join(base_dir, sub) if sub else base_dir
            runs.append(('call', spec['module'], typ, kwargs))
        else:
            raise ValueError('Unknown step type: %r' % typ)

    for step in sequence:
        do_step(step, {})
    return runs


# ---------------------------------------------------------------------------
# Wait dialog (sleep with live countdown and skip)
# ---------------------------------------------------------------------------
class WaitDialog(QDialog):
    def __init__(self, seconds, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Waiting')
        self.remaining = int(round(float(seconds)))
        self.label = QLabel('Waiting %d s...' % self.remaining, self)
        skip_btn = QPushButton('Skip', self)
        skip_btn.clicked.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(skip_btn)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.timer.stop()
            self.accept()
        else:
            self.label.setText('Waiting %d s...' % self.remaining)

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class SequenceWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dilution measurement sequencer')
        self.resize(1150, 650)
        self._stop = False
        self._editing_item = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)

        # ---------------- left: step editor ----------------
        left = QVBoxLayout()
        left.addWidget(QLabel('Step editor'))
        self.type_combo = QComboBox()
        self.type_combo.addItems(STEP_TYPES)
        self.type_combo.currentTextChanged.connect(self.rebuild_form)
        left.addWidget(self.type_combo)

        self.form = QFormLayout()
        left.addLayout(self.form)
        self.rebuild_form(self.type_combo.currentText())

        self.add_btn = QPushButton('Add to sequence')
        self.add_btn.clicked.connect(self.add_step)
        left.addWidget(self.add_btn)

        self.add_loop_btn = QPushButton('Add into selected loop')
        self.add_loop_btn.clicked.connect(lambda: self.add_step(into_loop=True))
        left.addWidget(self.add_loop_btn)

        self.apply_btn = QPushButton('Apply edit to selected')
        self.apply_btn.clicked.connect(self.apply_edit)
        left.addWidget(self.apply_btn)
        outer.addLayout(left, 1)

        # ---------------- right: sequence tree ----------------
        right = QVBoxLayout()
        right.addWidget(QLabel('Sequence (runs top to bottom)'))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Step', 'Summary'])
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemSelectionChanged.connect(self.load_selected)
        right.addWidget(self.tree)

        btns = QHBoxLayout()
        for text, slot in (('Up', lambda: self.move_step(-1)),
                           ('Down', lambda: self.move_step(1)),
                           ('Duplicate', self.duplicate_step),
                           ('Delete', self.delete_step)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        right.addLayout(btns)

        # ---------------- bottom: dir + run + save/load ----------------
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel('Save dir:'))
        self.dir_edit = QLineEdit(DEFAULT_SAVE_DIR)
        bottom.addWidget(self.dir_edit, 2)
        browse = QPushButton('Browse...')
        browse.clicked.connect(self.browse_dir)
        bottom.addWidget(browse)
        right.addLayout(bottom)

        run_btn = QPushButton('Run sequence')
        run_btn.setStyleSheet('font-weight: bold;')
        run_btn.clicked.connect(self.run_sequence)
        right.addWidget(run_btn)

        self.instruments_btn = QPushButton('Instruments...')
        self.instruments_btn.clicked.connect(self.open_instruments_dialog)
        right.addWidget(self.instruments_btn)

        self.stop_btn = QPushButton('Stop after current step')
        self.stop_btn.clicked.connect(self.stop_run)
        right.addWidget(self.stop_btn)

        file_btns = QHBoxLayout()
        save = QPushButton('Save sequence (JSON)')
        save.clicked.connect(self.save_json)
        load = QPushButton('Load sequence (JSON)')
        load.clicked.connect(self.load_json)
        file_btns.addWidget(save)
        file_btns.addWidget(load)
        right.addLayout(file_btns)

        self.status = QLabel('Ready.')
        right.addWidget(self.status)

        outer.addLayout(right, 2)

    # ------------- step editor form -------------
    def rebuild_form(self, step_type):
        # clear previous rows
        while self.form.count():
            item = self.form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields = {}

        def add_field(name, default):
            edit = QLineEdit(str(default))
            edit.setMinimumWidth(220)
            self._fields[name] = edit
            self.form.addRow(name + ':', edit)

        if step_type == 'Loop':
            add_field('values', 'linspace(0.5,-0.5,11)')
            hint = QLabel('Children may use {V} in any field or Subfolder,\n'
                          "e.g. target_voltage = {V}, Subfolder = hyst {V}V")
            self.form.addRow('', hint)
        elif step_type == 'Wait':
            add_field('seconds', 10)
        else:
            for name, _t, default in PROCEDURES[step_type]['params']:
                add_field(name, default)
            for name, _t, default in COMMON_PARAMS:
                add_field(name, default)
            add_field('Subfolder (optional)', '')

    def read_form(self):
        """Return a fresh step dict from the editor (or raise ValueError)."""
        step_type = self.type_combo.currentText()
        if step_type == 'Loop':
            return {'type': 'Loop',
                    'values': parse_values(self._fields['values'].text()),
                    'children': []}
        params = {name: edit.text()
                  for name, edit in self._fields.items()
                  if name != 'Subfolder (optional)'}
        if step_type != 'Wait':
            params['Subfolder'] = self._fields['Subfolder (optional)'].text()
        return {'type': step_type, 'params': params}

    # ------------- tree handling -------------
    def summary(self, step):
        if step['type'] == 'Loop':
            vals = step.get('values', [])
            preview = ', '.join(str(v) for v in vals[:3])
            more = ', ...' if len(vals) > 3 else ''
            return 'Loop over [%s%s] (%d children)' % (
                preview, more, len(step.get('children', [])))
        if step['type'] == 'Wait':
            return 'wait %s s' % step['params'].get('seconds', '')
        p = step['params']
        bits = []
        for key in ('target_voltage', 'target_AUX_voltage', 'target_field',
                    'acq_length'):
            if key in p:
                bits.append('%s=%s' % (key, p[key]))
        sub = p.get('Subfolder', '')
        if sub:
            bits.append('sub=%s' % sub)
        return ' '.join(bits)

    def make_item(self, step, parent=None):
        item = QTreeWidgetItem(parent or self.tree,
                               [step['type'], self.summary(step)])
        item.setData(0, Qt.UserRole, step)
        if step['type'] == 'Loop':
            for child in step.get('children', []):
                self.make_item(child, item)
        return item

    def add_step(self, into_loop=False):
        try:
            step = self.read_form()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        if into_loop:
            target = self.selected_loop()
            if target is None:
                QMessageBox.information(
                    self, 'No loop selected',
                    'Select a Loop step (or one of its children) first.')
                return
            target.data(0, Qt.UserRole)['children'].append(step)
            self.make_item(step, target)
            target.setExpanded(True)
        else:
            self.make_item(step)
        self.refresh_summaries()

    def selected_loop(self):
        """Tree item of the Loop owning the current selection, or None."""
        item = self.tree.currentItem()
        while item is not None:
            if item.data(0, Qt.UserRole)['type'] == 'Loop':
                return item
            item = item.parent()
        return None

    def selected_step_item(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        if item.data(0, Qt.UserRole)['type'] == 'Loop':
            return None  # loops are edited via their values field
        return item

    def load_selected(self):
        item = self.tree.currentItem()
        if item is None:
            return
        step = item.data(0, Qt.UserRole)
        self._editing_item = item
        if self.type_combo.currentText() != step['type']:
            self.type_combo.setCurrentText(step['type'])
            # rebuild_form ran via signal; fields are fresh now
        if step['type'] == 'Loop':
            self._fields['values'].setText(
                ', '.join(str(v) for v in step.get('values', [])))
        elif step['type'] == 'Wait':
            self._fields['seconds'].setText(str(step['params']['seconds']))
        else:
            for name, edit in self._fields.items():
                key = 'Subfolder' if name == 'Subfolder (optional)' else name
                if key in step['params']:
                    edit.setText(str(step['params'][key]))

    def apply_edit(self):
        item = self._editing_item or self.selected_step_item()
        if item is None:
            # maybe a loop is selected directly — update its values
            loop_item = self.tree.currentItem()
            if loop_item is not None and \
                    loop_item.data(0, Qt.UserRole)['type'] == 'Loop':
                try:
                    loop_item.data(0, Qt.UserRole)['values'] = \
                        parse_values(self._fields['values'].text())
                except ValueError as e:
                    QMessageBox.warning(self, 'Invalid input', str(e))
                    return
                self.refresh_summaries()
                return
            QMessageBox.information(self, 'Nothing selected',
                                    'Select a step to edit first.')
            return
        try:
            new_step = self.read_form()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        old = item.data(0, Qt.UserRole)
        if old['type'] == new_step['type']:
            old['params'] = new_step['params']
        else:
            # type changed: replace the item in place, keep position
            parent = item.parent() or self.tree.invisibleRootItem()
            is_top = parent is self.tree.invisibleRootItem()
            idx = parent.indexOfChild(item)
            if is_top:
                self.tree.takeTopLevelItem(idx)
            else:
                parent.removeChild(item)
            self.make_item(new_step, None if is_top else parent)
            if is_top:
                moved = self.tree.takeTopLevelItem(
                    self.tree.topLevelItemCount() - 1)
                self.tree.insertTopLevelItem(idx, moved)
            else:
                moved = parent.takeChild(parent.childCount() - 1)
                parent.insertChild(idx, moved)
            self._editing_item = moved
        self.refresh_summaries()

    def _insert_after(self, item, new_step):
        """Insert new_step right below item in the same parent."""
        parent = item.parent() or self.tree.invisibleRootItem()
        is_top = parent is self.tree.invisibleRootItem()
        idx = parent.indexOfChild(item) + 1
        self.make_item(new_step, None if is_top else parent)
        if is_top:
            moved = self.tree.takeTopLevelItem(
                self.tree.topLevelItemCount() - 1)
            self.tree.insertTopLevelItem(idx, moved)
        else:
            moved = parent.takeChild(parent.childCount() - 1)
            parent.insertChild(idx, moved)
        self.tree.setCurrentItem(moved)
        return moved

    def move_step(self, delta):
        item = self.tree.currentItem()
        if item is None:
            return
        parent = item.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(item)
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= parent.childCount():
            return
        if parent is self.tree.invisibleRootItem():
            item = self.tree.takeTopLevelItem(idx)
            self.tree.insertTopLevelItem(new_idx, item)
        else:
            item = parent.takeChild(idx)
            parent.insertChild(new_idx, item)
        self.tree.setCurrentItem(item)

    def duplicate_step(self):
        item = self.selected_step_item()
        if item is None:
            return
        self._insert_after(item, copy.deepcopy(item.data(0, Qt.UserRole)))
        self.refresh_summaries()

    def delete_step(self):
        item = self.tree.currentItem()
        if item is None:
            return
        parent = item.parent() or self.tree.invisibleRootItem()
        if parent is self.tree.invisibleRootItem():
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        else:
            parent.removeChild(item)
        self._editing_item = None

    def refresh_summaries(self):
        def walk(item):
            item.setText(1, self.summary(item.data(0, Qt.UserRole)))
            for i in range(item.childCount()):
                walk(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

    def tree_to_sequence(self):
        return [self.tree.topLevelItem(i).data(0, Qt.UserRole)
                for i in range(self.tree.topLevelItemCount())]

    # ------------- dir / save / load -------------
    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, 'Choose save directory',
                                             self.dir_edit.text() or '')
        if d:
            self.dir_edit.setText(d)

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save sequence', '',
                                              'Sequence JSON (*.json)')
        if not path:
            return
        with open(path, 'w') as f:
            json.dump({'base_dir': self.dir_edit.text(),
                       'sequence': self.tree_to_sequence()}, f, indent=2)
        self.status.setText('Saved %s' % path)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load sequence', '',
                                              'Sequence JSON (*.json)')
        if not path:
            return
        with open(path, 'r') as f:
            data = json.load(f)
        self.tree.clear()
        self._editing_item = None
        for step in data.get('sequence', []):
            self.make_item(step)
        if data.get('base_dir'):
            self.dir_edit.setText(data['base_dir'])
        self.status.setText('Loaded %s' % path)

    # ------------- instruments dialog -------------
    def open_instruments_dialog(self):
        import instruments_config as icfg
        settings = icfg.load_settings()

        dlg = QDialog(self)
        dlg.setWindowTitle('Instruments (instruments.json)')
        grid = QGridLayout(dlg)
        grid.addWidget(QLabel('Use'), 0, 0)
        grid.addWidget(QLabel('Device'), 0, 1)

        rows = []
        combos = []  # VISA-address dropdowns (filled by Scan)
        for row, (key, label, addr_key) in enumerate(icfg.DEVICE_LAYOUT, 1):
            cb = QCheckBox()
            cb.setChecked(bool(settings.get('use_' + key)))
            if key == 'dilution':
                addr = QLineEdit(str(settings.get(addr_key, '')))
            else:
                addr = QComboBox()
                addr.setEditable(True)
                addr.setCurrentText(str(settings.get(addr_key, '')))
                combos.append(addr)
            rows.append((key, addr_key, cb, addr))
            grid.addWidget(cb, row, 0)
            grid.addWidget(QLabel(label), row, 1)
            grid.addWidget(addr, row, 2)

        def scan_visa():
            """Fill every VISA dropdown with the addresses pyvisa finds."""
            try:
                import pyvisa
                rm = pyvisa.ResourceManager()
                found = [str(r) for r in rm.list_resources()]
            except Exception as exc:
                QMessageBox.warning(dlg, 'VISA scan failed',
                                    'Could not list VISA resources:\n%s' % exc)
                return
            for combo in combos:
                current = combo.currentText()
                combo.clear()
                combo.addItems(found)
                combo.setCurrentText(current)  # keep manual entry
            scan_btn.setText('Scan VISA (%d found)' % len(found))

        scan_btn = QPushButton('Scan VISA')
        scan_btn.clicked.connect(scan_visa)
        grid.addWidget(scan_btn, 0, 2)

        # dilution port spinner next to the IP
        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        port_spin.setValue(int(settings.get('dilution_port', 33576)))
        grid.addWidget(QLabel('port:'), len(icfg.DEVICE_LAYOUT) + 1, 1)
        grid.addWidget(port_spin, len(icfg.DEVICE_LAYOUT) + 1, 2)

        magnet_cb = QCheckBox('Record Bx/By/Bz (magnet readout each point)')
        magnet_cb.setChecked(bool(settings.get('use_magnet', True)))
        grid.addWidget(magnet_cb, len(icfg.DEVICE_LAYOUT) + 2, 0, 1, 3)

        note = QLabel('Disabled or failed devices are skipped: no columns,\n'
                      'no reads — the measurement adjusts automatically.')
        grid.addWidget(note, len(icfg.DEVICE_LAYOUT) + 3, 0, 1, 3)

        save_btn = QPushButton('Save & Connect')
        cancel_btn = QPushButton('Cancel')
        grid.addWidget(save_btn, len(icfg.DEVICE_LAYOUT) + 4, 0, 1, 2)
        grid.addWidget(cancel_btn, len(icfg.DEVICE_LAYOUT) + 4, 2)
        cancel_btn.clicked.connect(dlg.reject)

        def save_and_connect():
            for key, addr_key, cb, addr in rows:
                settings['use_' + key] = cb.isChecked()
                settings[addr_key] = addr.currentText() \
                    if hasattr(addr, 'currentText') else addr.text()
                settings[addr_key] = settings[addr_key].strip()
            settings['dilution_port'] = port_spin.value()
            settings['use_magnet'] = magnet_cb.isChecked()
            icfg.save_settings(settings)
            dlg.accept()
            try:
                statuses = icfg.reload()
            except Exception as exc:
                QMessageBox.critical(self, 'Connection error', str(exc))
                return
            ok = [n for n, v in statuses.items() if v]
            bad = [n for n, v in statuses.items() if not v
                   and settings.get('use_' + n.lower())]
            msg = 'Connected: %s' % (', '.join(ok) if ok else 'none')
            if bad:
                msg += '\nFailed: %s (columns for these will be absent)' \
                    % ', '.join(bad)
            QMessageBox.information(self, 'Instrument status', msg)
            self.status.setText('Instruments: %d connected' % len(ok))

        save_btn.clicked.connect(save_and_connect)
        dlg.resize(560, 400)
        dlg.exec_()

    # ------------- running -------------
    def stop_run(self):
        self._stop = True
        self.status.setText('Stopping after current step...')

    def run_sequence(self):
        base_dir = self.dir_edit.text().strip()
        if not base_dir:
            QMessageBox.warning(self, 'No save dir',
                                'Choose a save directory.')
            return
        try:
            runs = expand(self.tree_to_sequence(), base_dir)
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid sequence', str(e))
            return
        if not runs:
            QMessageBox.information(self, 'Empty sequence',
                                    'Add some steps first.')
            return
        ret = QMessageBox.question(
            self, 'Run sequence',
            'Run %d steps (%d measurements, %d waits)?' % (
                len(runs),
                sum(1 for r in runs if r[0] == 'call'),
                sum(1 for r in runs if r[0] == 'wait')),
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        # connect instruments once (per instruments.json); columns and
        # startup()/getmeas() adjust to whatever is actually connected
        try:
            import instruments_config as icfg
            statuses = icfg.connect_all()
            n_ok = sum(1 for v in statuses.values() if v)
        except Exception as exc:
            QMessageBox.critical(self, 'Instrument connection failed',
                                 str(exc))
            return
        if n_ok == 0:
            ret = QMessageBox.warning(
                self, 'No instruments connected',
                'No instruments are connected — measurements will fail.\n'
                'Open Instruments... to configure devices. Start anyway?',
                QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return

        self._stop = False
        total = len(runs)
        for i, run in enumerate(runs, 1):
            if self._stop:
                break
            if run[0] == 'wait':
                self.status.setText('Step %d/%d: wait %g s'
                                    % (i, total, run[1]))
                WaitDialog(run[1], self).exec_()
            else:
                _tag, module_name, step_type, kwargs = run
                self.status.setText('Step %d/%d: %s -> %s'
                                    % (i, total, step_type, kwargs['save_dir']))
                QApplication.processEvents()
                failed = False
                try:
                    mod = importlib.import_module(module_name)
                    manager = mod.main(**kwargs)
                    execute_manager(manager)
                    status = _status_name(getattr(manager.procedure,
                                                  'status', None))
                    if status.lower() != 'finished':
                        # worker thread death auto-closes the plot window;
                        # only visible via the procedure status
                        failed = True
                        reason = status
                except Exception as exc:
                    failed = True
                    reason = str(exc)
                    log.exception('Step %d (%s) raised', i, step_type)
                if failed:
                    ret = QMessageBox.critical(
                        self, 'Step failed',
                        'Step %d (%s) %s.\nSee console for the traceback.\n\n'
                        'Continue with next step?' % (i, step_type, reason),
                        QMessageBox.Yes | QMessageBox.No)
                    if ret != QMessageBox.Yes:
                        break

        self.status.setText('Stopped.' if self._stop else 'Done.')
        self._stop = False

    def closeEvent(self, event):
        # release shared instrument connections on exit (best effort)
        try:
            import instruments_config as icfg
            icfg.close_all()
        except Exception:
            pass
        super().closeEvent(event)


def launch():
    # surface pymeasure worker tracebacks (procedures use NullHandler,
    # so without this a crashed worker closes its window silently)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s: %(message)s')
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    win = SequenceWindow()
    win.show()
    sys.exit(app.exec_())


# ---------------------------------------------------------------------------
# Self-check — runnable without instruments or a display
# ---------------------------------------------------------------------------
def _self_check():
    seq = [
        {'type': 'Loop', 'values': [0.5, -0.5], 'children': [
            {'type': 'RV', 'params': {'target_voltage': '{V}',
                                      'Subfolder': 'hyst {V}V'}},
            {'type': 'Wait', 'params': {'seconds': '2'}},
        ]},
        {'type': 'Rt', 'params': {'acq_length': '60'}},
    ]
    runs = expand(seq, r'C:\data')
    assert len(runs) == 5, runs
    assert runs[0][0] == 'call' and runs[0][1] == 'RV_procedure'
    assert runs[0][3]['target_voltage'] == 0.5
    assert runs[0][3]['save_dir'] == r'C:\data\hyst 0.5V'
    assert runs[1] == ('wait', 2.0)
    assert runs[2][3]['target_voltage'] == -0.5
    assert runs[2][3]['save_dir'] == r'C:\data\hyst -0.5V'
    assert runs[3] == ('wait', 2.0)
    assert runs[4][0] == 'call' and runs[4][1] == 'Rt_procedure'
    assert runs[4][3]['acq_length'] == 60
    assert runs[4][3]['save_dir'] == r'C:\data'
    # defaults pulled from registry for unspecified params
    assert runs[4][3]['Resistor'] == COMMON_PARAMS[0][2]
    # values parsing
    import numpy as np
    assert parse_values('0.5, -0.5, 0') == [0.5, -0.5, 0.0]
    assert parse_values('linspace(0.5,-0.5,11)') == \
        [float(v) for v in np.linspace(0.5, -0.5, 11)]
    assert len(parse_values('linspace(1,2,5)')) == 5
    # JSON round trip of a sequence
    rt = json.loads(json.dumps(seq))
    assert expand(rt, r'C:\data') == runs
    print('self-check OK')


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        _self_check()
    else:
        launch()







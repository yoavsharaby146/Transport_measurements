"""
temperature_control.py

Standalone tool that controls a LabVIEW temperature-control program through
its on-screen front panel. Two control backends, chosen automatically:

  "uia"    - Windows UI Automation via pywinauto. If the LabVIEW program
             exposes named controls ("Target Temperature", "P", ...) they are
             read/written directly. Most reliable.
  "coords" - Fallback: anchored screen coordinates + OCR. The LabVIEW window
             is located by title on every run, controls are clicked at
             fixed offsets from the window origin (so the window may move),
             and current values are read back with Tesseract OCR.

Usage:
    python temperature_control.py inspect
    python temperature_control.py calibrate
    python temperature_control.py read
    python temperature_control.py set target 300      (Set Point, K)
    python temperature_control.py set ramp 5          (Ramp Rate, K/min)
    python temperature_control.py set pid 50 10 2     (P I D)
    python temperature_control.py set output 50       (Heater Output, %)
    python temperature_control.py heater high         (Heater Range ring)
    python temperature_control.py apply all           (press Set Values)
    python temperature_control.py selftest

'read' also returns 'temp': the actual temperature from the read-only
'Temperature State' indicator. If the window is minimized, the coords
backend restores it automatically (UIA works even while minimized).

Panel layout handled (Temperature Control tab):
    PID Control group: Set Point [K], Ramp Rate [K/min], P/I/D,
                       Heater Range ring (off/low/medium/high),
                       "Set Values" button.
    Manual Heater Control group: Heater Output [%], "Set Values" button.
    LabVIEW buffers typed edits until "Set Values" is pressed - every
    write is followed by the matching group's Set Values click, then a
    read-back verification.

First-time setup on the measurement PC:
    1. pip install pywinauto pyautogui pytesseract Pillow
    2. Install Tesseract (UB Mannheim build) or set TESSERACT_CMD env var
    3. Set WINDOW_TITLE below to match the LabVIEW window
    4. Run "inspect". If controls are found, config switches to uia mode.
       If not, run "calibrate" and click each field when prompted.

Config is saved next to this file as temperature_control_config.json.
"""

import json
import os
import re
import sys
import time

# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

# Exact window title, or a constant part of it (substring match, case-sensitive).
WINDOW_TITLE = "ICE Lemon & Magnet Control"
# ICE - Temperature Control
#ICE Lemon & Magnet Control
# Field definitions shared by both backends.
# Regexes match UIA control names from the LabVIEW front panel
# ("Set Point", "Ramp Rate", "P/I/D", "Heater Output", "Heater Range").
FIELD_NAMES = ["target", "ramp", "P", "I", "D", "output"]

FIELD_UIA_RE = {
    "target": r"(?i)set\s*point|setpoint",
    "ramp": r"(?i)ramp",
    "P": r"(?i)^p$|\bp\s*value\b|\bproportional\b",
    "I": r"(?i)^i$|\bi\s*value\b|\bintegral\b",
    "D": r"(?i)^d$|\bd\s*value\b|\bderivative\b",
    "output": r"(?i)heater\s*output",
    "range": r"(?i)heater\s*range",
    "temp": r"(?i)^temperature$",
}

# Read-only indicators (in "Temperature State" group): included in read_all()
# but never written. 'temp' is the actual measured temperature.
READ_ONLY_FIELDS = ["temp"]

# Which "Set Values" button applies each field
# (PID Control group vs Manual Heater Control group on the
# Temperature Control tab). LabVIEW buffers edits until the button is pressed.
FIELD_GROUP = {
    "target": "pid", "ramp": "pid", "P": "pid", "I": "pid", "D": "pid",
    "output": "manual",
}

HEATER_OPTIONS = ["off", "low", "medium", "high"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "temperature_control_config.json")
INSPECT_PATH = os.path.join(SCRIPT_DIR, "inspect_output.txt")

# Default OCR box (pixels) around a calibrated click point when reading a value.
READ_BOX = (160, 30)  # width, height

# Tesseract executable: auto-detect common install paths, else env var.
_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


# ---------------------------------------------------------------------------
# Config handling
# ---------------------------------------------------------------------------

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    print("Saved config -> %s" % CONFIG_PATH)


def require_config():
    cfg = load_config()
    if not cfg.get("mode"):
        sys.exit("No config found. Run 'inspect' or 'calibrate' first.")
    return cfg


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def find_window():
    """Return hwnd of the LabVIEW window by title, restoring it if minimized.

    Minimized windows report (-32000, -32000) as position: clicks and
    screenshots would hit wrong pixels. The coords backend needs the window
    on screen, so it is restored automatically. (UIA mode reads/writes
    controls even while minimized.)
    """
    import win32gui
    import win32con

    matches = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and WINDOW_TITLE in title:
                matches.append(hwnd)

    win32gui.EnumWindows(cb, None)
    if not matches:
        sys.exit("Window containing '%s' not found. Is the LabVIEW "
                 "program open?" % WINDOW_TITLE)
    hwnd = matches[0]
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)
    return hwnd


def find_window_rect():
    """Return (left, top, right, bottom) of the LabVIEW window by title."""
    import win32gui

    return win32gui.GetWindowRect(find_window())


def focus_window():
    """Bring the LabVIEW window to the foreground."""
    import win32gui

    try:
        win32gui.SetForegroundWindow(find_window())
    except win32gui.error:
        pass  # already foreground or blocked; clicks usually still work
    time.sleep(0.3)


def setup_tesseract():
    import pytesseract

    if os.environ.get("TESSERACT_CMD"):
        return pytesseract
    for path in _TESSERACT_CANDIDATES:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return pytesseract
    return pytesseract  # rely on PATH; OCR calls will raise if missing


def ocr_region(box, digits=False):
    """OCR a screen region box=(left, top, right, bottom). Returns str."""
    from PIL import ImageGrab

    pytesseract = setup_tesseract()
    img = ImageGrab.grab(bbox=box)
    config = "--psm 7"
    if digits:
        config += " -c tessedit_char_whitelist=0123456789.-"
    text = pytesseract.image_to_string(img, config=config)
    return text.strip()


def parse_number(text):
    """Extract first float from OCR text. Raises ValueError if none found."""
    m = re.search(r"[-+]?\d*\.?\d+", text.replace(",", "."))
    if not m:
        raise ValueError("no number in OCR text: %r" % text)
    return float(m.group())


# ---------------------------------------------------------------------------
# UIA backend (pywinauto)
# ---------------------------------------------------------------------------

def _uia_window():
    from pywinauto import Application

    app = Application(backend="uia").connect(
        title_re=".*%s.*" % re.escape(WINDOW_TITLE), timeout=5)
    return app.top_window()


def uia_select_tab(win):
    """Make sure the 'Temperature Control' tab is the active one."""
    try:
        tab = win.window_control(title_re="(?i)temperature control",
                                 control_type="TabItem", search_depth=15)
        if tab.exists(timeout=1):
            tab.select()
            time.sleep(0.2)
    except Exception:
        pass


def uia_find_apply_button(win, group):
    """Find the 'Set Values' button of the PID or Manual control group."""
    best = None
    try:
        for btn in win.descendants(control_type="Button"):
            if not re.search(r"(?i)set\s*values", btn.window_text() or ""):
                continue
            names = []
            cur = btn
            for _ in range(20):
                try:
                    cur = cur.parent()
                except Exception:
                    break
                names.append(cur.element_info.name or "")
            path = "|".join(names)
            if re.search(r"(?i)\bpid\b", path) and group == "pid":
                return btn
            if re.search(r"(?i)manual", path) and group == "manual":
                return btn
            best = best or btn  # fallback if groups not visible in UIA tree
    except Exception:
        pass
    return best


def uia_apply(win, group):
    """Press the group's 'Set Values' button (applies buffered edits)."""
    btn = uia_find_apply_button(win, group)
    if btn is None:
        raise RuntimeError(
            "Could not find 'Set Values' button for %s group" % group)
    try:
        btn.invoke()
    except Exception:
        btn.click_input()
    time.sleep(0.4)


def uia_find_field(win, field):
    """Find the UIA control for a field by name regex. None if not found."""
    try:
        desc = win.window_control(title_re=FIELD_UIA_RE[field], search_depth=15)
        if desc.exists(timeout=1):
            return desc
    except Exception:
        pass
    # LabVIEW often nests the value in an Edit child next to the label.
    try:
        for edit in win.descendants(control_type="Edit"):
            name = (edit.window_text() or "") + "|" + (edit.element_info.name or "")
            parent = edit.parent().element_info.name or ""
            if re.search(FIELD_UIA_RE[field], name + "|" + parent, re.IGNORECASE):
                return edit
    except Exception:
        pass
    return None


def uia_read(win, field):
    uia_select_tab(win)
    ctl = uia_find_field(win, field)
    if ctl is None:
        raise RuntimeError("UIA control for '%s' not found" % field)
    return ctl.get_value()


def uia_write(win, field, value):
    uia_select_tab(win)
    ctl = uia_find_field(win, field)
    if ctl is None:
        raise RuntimeError("UIA control for '%s' not found" % field)
    ctl.set_value(value)
    time.sleep(0.2)
    uia_apply(win, FIELD_GROUP[field])
    return uia_read(win, field)


def uia_read_heater(win):
    uia_select_tab(win)
    try:
        rng = win.window_control(title_re=FIELD_UIA_RE["range"],
                                 search_depth=15)
        if rng.exists(timeout=1):
            try:
                texts = rng.texts()
                if texts and texts[0].strip():
                    return texts[0].strip().lower()
            except Exception:
                pass
            try:
                sel = rng.get_selection()
                if sel:
                    return (sel[0].window_text() or "").strip().lower()
            except Exception:
                pass
    except Exception:
        pass
    raise RuntimeError("Could not determine heater range via UIA")


def uia_set_heater(win, option):
    uia_select_tab(win)
    option = option.lower()
    if option not in HEATER_OPTIONS:
        raise ValueError("heater option must be one of %s" % HEATER_OPTIONS)
    try:
        rng = win.window_control(title_re=FIELD_UIA_RE["range"],
                                 search_depth=15)
        if rng.exists(timeout=1):
            try:
                rng.select(option)
                time.sleep(0.3)
                uia_apply(win, "pid")
                return uia_read_heater(win)
            except Exception:
                pass
    except Exception:
        pass
    raise RuntimeError("Could not set heater range '%s' via UIA" % option)


# ---------------------------------------------------------------------------
# Coordinate + OCR backend
# ---------------------------------------------------------------------------

def _click(absolute_xy, clicks=1):
    import pyautogui

    pyautogui.click(absolute_xy[0], absolute_xy[1], clicks=clicks)
    time.sleep(0.4)


# Window-relative config keys holding the two "Set Values" buttons.
GROUP_POSITION_KEY = {"pid": "set_values_pid", "manual": "set_values_manual"}


def _coords_prepare(cfg):
    """Focus window and make sure the 'Temperature Control' tab is active."""
    focus_window()
    if "tab" in cfg:
        left, top, _, _ = find_window_rect()
        x_off, y_off = cfg["tab"]
        _click((left + x_off, top + y_off))


def _coords_apply(cfg, group):
    """Press the group's 'Set Values' button (applies buffered edits)."""
    key = GROUP_POSITION_KEY[group]
    if key not in cfg:
        print("WARNING: %s not calibrated - value typed but NOT applied"
              % key)
        return
    left, top, _, _ = find_window_rect()
    sx, sy = cfg[key]
    _click((left + sx, top + sy))


def _to_screen(cfg, field):
    """Convert a stored window-relative offset to absolute screen coords."""
    left, top, _, _ = find_window_rect()
    x_off, y_off = cfg["fields"][field] if field in cfg.get("fields", {}) \
        else cfg[field]
    return (left + x_off, top + y_off)


def coords_read_field(cfg, field):
    x, y = _to_screen(cfg, field)
    w, h = READ_BOX
    box = (x - w // 2, y - h // 2, x + w // 2, y + h // 2)
    return parse_number(ocr_region(box, digits=True))


def coords_write_field(cfg, field, value):
    import pyautogui

    x, y = _to_screen(cfg, field)
    _click((x, y))
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.typewrite(str(value), interval=0.02)
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(0.3)
    # LabVIEW buffers edits until the group's "Set Values" is pressed.
    _coords_apply(cfg, FIELD_GROUP[field])
    time.sleep(0.3)
    return coords_read_field(cfg, field)


def coords_read_heater(cfg):
    x, y = _to_screen(cfg, "heater")
    w, h = (260, READ_BOX[1])  # wide enough for OCR of "medium"
    box = (x - w // 2, y - h // 2, x + w // 2, y + h // 2)
    text = ocr_region(box).lower()
    for opt in HEATER_OPTIONS:
        if opt in text:
            return opt
    raise ValueError("no heater option in OCR text: %r" % text)


def coords_set_heater(cfg, option):
    option = option.lower()
    if option not in HEATER_OPTIONS:
        raise ValueError("heater option must be one of %s" % HEATER_OPTIONS)

    if cfg.get("heater_style") == "direct":
        # Radio-style: one recorded position per option, just click it.
        if option not in cfg.get("heater_options", {}):
            raise RuntimeError("no calibrated position for '%s'" % option)
        left, top, _, _ = find_window_rect()
        x_off, y_off = cfg["heater_options"][option]
        _click((left + x_off, top + y_off))
        time.sleep(0.5)
        _coords_apply(cfg, "pid")
        time.sleep(0.3)
        return coords_read_heater(cfg)

    # Dropdown/ring style: click selector, OCR the opened menu, click option.
    from PIL import ImageGrab

    pytesseract = setup_tesseract()
    x, y = _to_screen(cfg, "heater")
    _click((x, y))
    time.sleep(0.5)
    box = (x - 60, y, x + 260, y + 260)
    img = ImageGrab.grab(bbox=box)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    for i, word in enumerate(data["text"]):
        if word.strip().lower() == option:
            wx = box[0] + data["left"][i] + data["width"][i] // 2
            wy = box[1] + data["top"][i] + data["height"][i] // 2
            _click((wx, wy))
            time.sleep(0.5)
            _coords_apply(cfg, "pid")
            time.sleep(0.3)
            return coords_read_heater(cfg)
    raise RuntimeError("Option '%s' not found in opened heater menu" % option)


# ---------------------------------------------------------------------------
# Public read/write API (dispatches on config mode)
# ---------------------------------------------------------------------------

def read_field(cfg, field):
    if cfg["mode"] == "uia":
        return uia_read(_uia_window(), field)
    _coords_prepare(cfg)
    return coords_read_field(cfg, field)


def write_field(cfg, field, value):
    if field in READ_ONLY_FIELDS:
        raise ValueError("'%s' is a read-only indicator, cannot be written"
                         % field)
    if cfg["mode"] == "uia":
        return uia_write(_uia_window(), field, value)
    _coords_prepare(cfg)
    return coords_write_field(cfg, field, value)


def read_heater(cfg):
    if cfg["mode"] == "uia":
        return uia_read_heater(_uia_window())
    _coords_prepare(cfg)
    return coords_read_heater(cfg)


def set_heater_output(cfg, option):
    if cfg["mode"] == "uia":
        return uia_set_heater(_uia_window(), option)
    _coords_prepare(cfg)
    return coords_set_heater(cfg, option)


def read_all(cfg):
    result = {}
    for field in FIELD_NAMES + READ_ONLY_FIELDS:
        try:
            result[field] = read_field(cfg, field)
        except Exception as exc:
            result[field] = "ERROR: %s" % exc
    try:
        result["heater"] = read_heater(cfg)
    except Exception as exc:
        result["heater"] = "ERROR: %s" % exc
    return result


# ---------------------------------------------------------------------------
# inspect mode
# ---------------------------------------------------------------------------

def cmd_inspect():
    """Try UIA. If named controls are found, save uia-mode config."""
    from pywinauto import Application

    app = Application(backend="uia").connect(
        title_re=".*%s.*" % re.escape(WINDOW_TITLE), timeout=5)
    win = app.top_window()

    with open(INSPECT_PATH, "w", encoding="utf-8") as f:
        for ctl in win.descendants():
            f.write("%s | window_text='%s' | name='%s'\n" % (
                ctl.friendly_class_name(),
                ctl.window_text() or "",
                ctl.element_info.name or ""))
    print("Wrote control dump -> %s" % INSPECT_PATH)

    found = [field for field in FIELD_NAMES + READ_ONLY_FIELDS
             if uia_find_field(win, field) is not None]

    if found:
        cfg = load_config()
        cfg["mode"] = "uia"
        cfg["window_title"] = WINDOW_TITLE
        save_config(cfg)
        print("UIA controls found for: %s" % ", ".join(found))
        print("Config switched to uia mode. Try: python %s read"
              % os.path.basename(__file__))
    else:
        print("No named UIA controls found for numeric fields.")
        print("LabVIEW front panel is likely opaque to UI Automation.")
        print("Next step: run 'calibrate' to use the coordinate+OCR backend.")


# ---------------------------------------------------------------------------
# calibrate mode (coordinate backend)
# ---------------------------------------------------------------------------

def _prompt_position(label):
    """Ask user to hover the mouse over a control, press Enter, read pos."""
    import pyautogui

    input("Move the mouse over the %s, then press Enter..." % label)
    return pyautogui.position()


def cmd_calibrate():
    cfg = load_config()
    print("Calibrating against window: %s" % WINDOW_TITLE)
    print("Open the 'Temperature Control' tab first. Keep the LabVIEW "
          "window in its normal position and do not move it while "
          "clicking.\n")

    left, top, _, _ = find_window_rect()
    tab = _prompt_position("'Temperature Control' tab header")
    labels = {"target": "'Set Point' box (295.000 K)",
              "ramp": "'Ramp Rate' box (K/min)",
              "P": "'P' box",
              "I": "'I' box",
              "D": "'D' box",
              "output": "'Heater Output' % box (Manual Heater Control)"}
    fields = {}
    for field in FIELD_NAMES:
        pos = _prompt_position(labels[field])
        fields[field] = [pos.x - left, pos.y - top]

    temp_pos = _prompt_position(
        "'Temperature' display in the 'Temperature State' group "
        "(the actual temperature reading)")
    fields["temp"] = [temp_pos.x - left, temp_pos.y - top]

    pid_apply = _prompt_position("'Set Values' button under 'PID Control'")
    manual_apply = _prompt_position(
        "'Set Values' button under 'Manual Heater Control'")
    heater_pos = _prompt_position(
        "'Heater Range' ring selector (shows High/Low/Medium/Off)")

    cfg.update({
        "mode": "coords",
        "window_title": WINDOW_TITLE,
        "tab": [tab.x - left, tab.y - top],
        "fields": fields,
        "set_values_pid": [pid_apply.x - left, pid_apply.y - top],
        "set_values_manual": [manual_apply.x - left, manual_apply.y - top],
        "heater": [heater_pos.x - left, heater_pos.y - top],
        "heater_style": "dropdown",
    })

    save_config(cfg)
    print("\nCalibration done. Verify with: python %s read"
          % os.path.basename(__file__))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = ("Usage:\n"
         "  inspect    dump UIA controls, try uia mode\n"
         "  calibrate  record field positions (coordinate mode)\n"
         "  read       read all values\n"
         "  set target|ramp|P|I|D|output <value> | set pid <P> <I> <D>\n"
         "  heater off|low|medium|high     (Heater Range ring)\n"
         "  apply pid|manual|all           (press 'Set Values' only)\n"
         "  selftest")


def cmd_read():
    cfg = require_config()
    print(json.dumps(read_all(cfg), indent=2))


def _set_and_report(cfg, field, value_str):
    value = float(value_str)
    print("Setting %s = %s ..." % (field, value))
    readback = write_field(cfg, field, value)
    print("  read back: %s" % readback)
    try:
        if abs(float(readback) - value) > 1e-6 * max(1.0, abs(value)):
            print("  WARNING: readback does not match requested value!")
    except (TypeError, ValueError):
        print("  WARNING: could not verify readback (%r)" % readback)


def cmd_set(args):
    cfg = require_config()
    if not args:
        sys.exit("Usage: set target 300 | set ramp 5 | set P 50 | "
                 "set pid 50 10 2")
    what = args[0].lower()
    if what == "pid":
        if len(args) != 4:
            sys.exit("Usage: set pid <P> <I> <D>")
        for field, value in zip(["P", "I", "D"], args[1:]):
            _set_and_report(cfg, field, value)
        return
    if what not in FIELD_NAMES:
        sys.exit("Unknown field '%s'. Use: %s or pid" % (what, FIELD_NAMES))
    if len(args) != 2:
        sys.exit("Usage: set %s <value>" % what)
    _set_and_report(cfg, what, args[1])


def cmd_heater(args):
    cfg = require_config()
    if not args or args[0].lower() not in HEATER_OPTIONS:
        sys.exit("Usage: heater <off|low|medium|high>")
    option = args[0].lower()
    print("Setting heater range = %s ..." % option)
    readback = set_heater_output(cfg, option)
    print("  read back: %s" % readback)
    if str(readback).lower() != option:
        print("  WARNING: readback does not match requested option!")


def cmd_apply(args):
    """Press 'Set Values' without writing any field."""
    cfg = require_config()
    group = args[0].lower() if args else "pid"
    if group not in ("pid", "manual", "all"):
        sys.exit("Usage: apply pid|manual|all")
    groups = ["pid", "manual"] if group == "all" else [group]
    if cfg["mode"] == "uia":
        win = _uia_window()
        uia_select_tab(win)
        for g in groups:
            uia_apply(win, g)
        print("Applied: %s" % ", ".join(groups))
        return
    _coords_prepare(cfg)
    left, top, _, _ = find_window_rect()
    for g in groups:
        key = GROUP_POSITION_KEY[g]
        if key not in cfg:
            sys.exit("%s not calibrated - run 'calibrate' first" % key)
        sx, sy = cfg[key]
        _click((left + sx, top + sy))
    print("Applied: %s" % ", ".join(groups))


def cmd_selftest():
    """No-GUI checks for the pure parsing logic."""
    assert parse_number("300.5 K") == 300.5
    assert parse_number("  -12 ") == -12.0
    assert parse_number("1,5") == 1.5
    try:
        parse_number("no digits here")
        raise AssertionError("parse_number should have failed")
    except ValueError:
        pass
    assert re.search(FIELD_UIA_RE["target"], "Set Point")
    assert re.search(FIELD_UIA_RE["target"], "Setpoint (K)")
    assert re.search(FIELD_UIA_RE["ramp"], "Ramp Rate [K/min]")
    assert re.search(FIELD_UIA_RE["P"], "P")
    assert re.search(FIELD_UIA_RE["P"], "P value")
    assert re.search(FIELD_UIA_RE["I"], "I")
    assert re.search(FIELD_UIA_RE["D"], "D")
    assert re.search(FIELD_UIA_RE["output"], "Heater Output")
    assert re.search(FIELD_UIA_RE["range"], "Heater Range")
    assert re.search(FIELD_UIA_RE["temp"], "Temperature")
    assert not re.search(FIELD_UIA_RE["temp"], "Set Point")
    assert not re.search(FIELD_UIA_RE["temp"], "Temperature Control")
    assert not re.search(FIELD_UIA_RE["target"], "Ramp Rate")
    assert not re.search(FIELD_UIA_RE["output"], "Heater Range")
    assert not re.search(FIELD_UIA_RE["range"], "Heater Output")
    assert FIELD_GROUP["target"] == "pid"
    assert FIELD_GROUP["output"] == "manual"
    assert GROUP_POSITION_KEY["pid"] == "set_values_pid"
    print("selftest OK")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "selftest":
        cmd_selftest()
        return
    if WINDOW_TITLE == "PUT-LABVIEW-WINDOW-TITLE-HERE":
        print("Edit WINDOW_TITLE at the top of this script first.")
        print(USAGE)
        return

    args = sys.argv[2:]
    if cmd == "inspect":
        cmd_inspect()
    elif cmd == "calibrate":
        cmd_calibrate()
    elif cmd == "read":
        cmd_read()
    elif cmd == "set":
        cmd_set(args)
    elif cmd == "heater":
        cmd_heater(args)
    elif cmd == "apply":
        cmd_apply(args)
    else:
        print(USAGE)


if __name__ == "__main__":
    main()







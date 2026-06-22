"""
CSV Cross-File Column Math Tool
--------------------------------
Load multiple CSV files, reference columns as f1.col, f2.col, etc.,
define computed columns via math expressions, copy raw columns,
and export the result to a new CSV.

Requirements: Python 3.8+ (tkinter is included in the standard library)
Run: python csv_column_math.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import math
import os
import re


# ── palette ──────────────────────────────────────────────────────────────────
FILE_COLORS = [
    {"bg": "#DBEAFE", "fg": "#1E40AF", "tag": "f1"},  # blue
    {"bg": "#DCFCE7", "fg": "#166534", "tag": "f2"},  # green
    {"bg": "#EDE9FE", "fg": "#5B21B6", "tag": "f3"},  # purple
    {"bg": "#FEF3C7", "fg": "#92400E", "tag": "f4"},  # amber
    {"bg": "#FFE4E6", "fg": "#9F1239", "tag": "f5"},  # rose
]


# ── data model ────────────────────────────────────────────────────────────────
class CSVFile:
    def __init__(self, path, alias):
        self.path = path
        self.name = os.path.basename(path)
        self.alias = alias
        self.headers = []
        self.rows = []   # list of dicts {col: float}
        self._load()

    def _load(self):
        with open(self.path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.headers = reader.fieldnames or []
            for row in reader:
                parsed = {}
                for h in self.headers:
                    try:
                        parsed[h] = float(row[h])
                    except (ValueError, TypeError):
                        parsed[h] = float("nan")
                self.rows.append(parsed)


class AppState:
    def __init__(self):
        self.files: list[CSVFile] = []
        self.copy_cols: list[tuple] = []   # list of (alias, col)
        self.ops: list[dict] = []          # list of {"name": str, "expr": str}

    def add_file(self, path):
        alias = f"f{len(self.files) + 1}"
        self.files.append(CSVFile(path, alias))

    def remove_file(self, idx):
        self.files.pop(idx)
        # re-alias
        for i, f in enumerate(self.files):
            f.alias = f"f{i + 1}"
        # clean copy cols that referenced removed file
        valid = {(f.alias, h) for f in self.files for h in f.headers}
        self.copy_cols = [c for c in self.copy_cols if c in valid]

    def eval_expr(self, expr: str, row_by_alias: dict) -> float:
        """Evaluate a formula expression for one row."""
        js = expr
        # replace f1.col, f2.col, etc.
        for f in self.files:
            for h in f.headers:
                val = row_by_alias.get(f.alias, {}).get(h, float("nan"))
                js = js.replace(f"{f.alias}.{h}", str(val))
        # replace bare col names → first file values
        if self.files:
            for h in self.files[0].headers:
                pattern = r'(?<![a-zA-Z0-9_\.])' + re.escape(h) + r'(?![a-zA-Z0-9_\.])'
                val = row_by_alias.get(self.files[0].alias, {}).get(h, float("nan"))
                js = re.sub(pattern, str(val), js)
        try:
            allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
            allowed["abs"] = abs
            return float(eval(js, {"__builtins__": {}}, allowed))  # noqa: S307
        except Exception:
            return float("nan")

    def build_output(self):
        if not self.files:
            return [], []
        n_rows = min(len(f.rows) for f in self.files)
        out_headers = [f"{a}.{c}" for a, c in self.copy_cols] + \
                      [op["name"] or op["expr"] or f"col_{i}" for i, op in enumerate(self.ops)]
        out_rows = []
        for i in range(n_rows):
            row_by_alias = {f.alias: f.rows[i] for f in self.files}
            row = {}
            for alias, col in self.copy_cols:
                row[f"{alias}.{col}"] = row_by_alias.get(alias, {}).get(col, float("nan"))
            for j, op in enumerate(self.ops):
                h = op["name"] or op["expr"] or f"col_{j}"
                row[h] = self.eval_expr(op["expr"], row_by_alias) if op["expr"].strip() else ""
            out_rows.append(row)
        return out_headers, out_rows


def fmt(v):
    if v == "" or v is None:
        return ""
    try:
        f = float(v)
        if math.isnan(f):
            return "error"
        return str(int(f)) if f == int(f) else f"{f:.6g}"
    except (ValueError, TypeError):
        return str(v)


# ── main GUI ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV Column Math")
        self.geometry("900x720")
        self.minsize(700, 560)
        self.configure(bg="#F8F8F7")
        self.state = AppState()
        self._build_ui()

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        style.configure("TLabel", background="#F8F8F7", foreground="#1A1A18")
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#1A1A18")
        style.configure("Hint.TLabel", background="#FFFFFF", foreground="#6B6B68", font=("", 9))
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#6B6B68",
                        font=("", 9, "bold"))
        style.configure("TButton", padding=(8, 4))

        main = tk.Frame(self, bg="#F8F8F7")
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # scrollable canvas (vertical + horizontal)
        self.canvas = tk.Canvas(main, bg="#F8F8F7", highlightthickness=0)
        vsb = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(main, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self.canvas, bg="#F8F8F7")
        self.scroll_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        # vertical scroll (mouse wheel)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))
        self.canvas.bind("<Button-4>",   lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>",   lambda e: self.canvas.yview_scroll(1,  "units"))
        # horizontal scroll (Shift + mouse wheel, or drag the bottom scrollbar)
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-1*(e.delta//120), "units"))
        self.canvas.bind("<Shift-Button-4>",   lambda e: self.canvas.xview_scroll(-1, "units"))
        self.canvas.bind("<Shift-Button-5>",   lambda e: self.canvas.xview_scroll(1,  "units"))

        sf = self.scroll_frame
        self._section_files(sf)
        self._section_refs(sf)
        self._section_copy(sf)
        self._section_ops(sf)
        self._section_preview(sf)

    def _card(self, parent, title):
        outer = tk.Frame(parent, bg="#E5E5E2", padx=1, pady=1)
        outer.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(outer, bg="#FFFFFF", padx=14, pady=12)
        inner.pack(fill="both")
        tk.Label(inner, text=title.upper(), bg="#FFFFFF", fg="#9B9B98",
                 font=("", 8, "bold")).pack(anchor="w", pady=(0, 8))
        return inner

    def _scrollable(self, parent, height=160):
        """Create a fixed-height scrollable sub-area (vertical + horizontal
        scrollbars) and return the inner content frame. Keeps the window from
        stretching infinitely wide when there are many columns."""
        outer = tk.Frame(parent, bg="#FFFFFF")
        outer.pack(fill="x")
        canvas = tk.Canvas(outer, bg="#FFFFFF", highlightthickness=0, height=height)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg="#FFFFFF")
        inner.canvas = canvas
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        return inner

    def _bind_wheel(self, widget, canvas):
        """Recursively bind mouse-wheel scrolling to a widget and its children,
        so scrolling works while hovering over labels/checkboxes inside the area."""
        widget.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        widget.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        widget.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        for child in widget.winfo_children():
            self._bind_wheel(child, canvas)

    # ── section 1: files ──────────────────────────────────────────────────────
    def _section_files(self, parent):
        card = self._card(parent, "1 — load csv files")

        btn_frame = tk.Frame(card, bg="#FFFFFF")
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="＋ Add CSV files…", command=self._add_files).pack(side="left")
        self.row_warn_lbl = tk.Label(btn_frame, text="", bg="#FFFFFF", fg="#92400E", font=("", 9))
        self.row_warn_lbl.pack(side="left", padx=(12, 0))

        self.file_list_frame = tk.Frame(card, bg="#FFFFFF")
        self.file_list_frame.pack(fill="x", pady=(8, 0))

    def _add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("CSV files", "*.csv")])
        for p in paths:
            if len(self.state.files) >= 5:
                messagebox.showwarning("Limit", "Maximum 5 files supported.")
                break
            try:
                self.state.add_file(p)
            except Exception as e:
                messagebox.showerror("Error loading file", str(e))
        self._refresh()

    def _render_files(self):
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        for i, f in enumerate(self.state.files):
            c = FILE_COLORS[i % len(FILE_COLORS)]
            row = tk.Frame(self.file_list_frame, bg="#F4F4F2", pady=4, padx=8)
            row.pack(fill="x", pady=2)
            alias_lbl = tk.Label(row, text=f.alias, bg=c["bg"], fg=c["fg"],
                                 font=("", 9, "bold"), padx=6, pady=2)
            alias_lbl.pack(side="left")
            tk.Label(row, text=f"  {f.name}", bg="#F4F4F2", fg="#3A3A38",
                     font=("", 10)).pack(side="left")
            info = f"  ({len(f.rows)} rows)"
            tk.Label(row, text=info, bg="#F4F4F2", fg="#8A8A88",
                     font=("", 9)).pack(side="left")
            idx = i
            ttk.Button(row, text="✕", width=3,
                       command=lambda ix=idx: self._remove_file(ix)).pack(side="left")

        # row count warning
        if len(self.state.files) >= 2:
            counts = [len(f.rows) for f in self.state.files]
            if len(set(counts)) > 1:
                self.row_warn_lbl.config(
                    text=f"⚠ Row counts differ: {counts} — will use min ({min(counts)})")
            else:
                self.row_warn_lbl.config(
                    text=f"✓ All files have {counts[0]} rows", fg="#166534")
        else:
            self.row_warn_lbl.config(text="")

    def _remove_file(self, idx):
        self.state.remove_file(idx)
        self._refresh()

    # ── section 2: refs ───────────────────────────────────────────────────────
    def _section_refs(self, parent):
        self.refs_card = self._card(parent, "2 — column references  (click to insert into formula)")
        tk.Label(self.refs_card, text="Use  f1.colname + f2.colname  syntax in formulas. "
                 "Plain names like  a+b  reference file 1.",
                 bg="#FFFFFF", fg="#9B9B98", font=("", 9), wraplength=760,
                 justify="left").pack(anchor="w", pady=(0, 6))
        self.refs_inner = self._scrollable(self.refs_card, height=160)

    def _render_refs(self):
        for w in self.refs_inner.winfo_children():
            w.destroy()
        if not self.state.files:
            tk.Label(self.refs_inner, text="No files loaded yet.",
                     bg="#FFFFFF", fg="#9B9B98", font=("", 9)).pack(anchor="w")
            return
        columns = tk.Frame(self.refs_inner, bg="#FFFFFF")
        columns.pack(fill="x", anchor="nw")
        for fi, f in enumerate(self.state.files):
            c = FILE_COLORS[fi % len(FILE_COLORS)]
            col = tk.Frame(columns, bg="#FFFFFF", padx=10)
            col.pack(side="left", anchor="n")
            tk.Label(col, text=f.alias, bg=c["bg"], fg=c["fg"],
                     font=("", 9, "bold"), padx=6, pady=2).pack(anchor="w", pady=(0, 4))
            for h in f.headers:
                ref = f"{f.alias}.{h}"
                lbl = tk.Label(col, text=ref, bg=c["bg"], fg=c["fg"],
                               font=("", 9, "bold"), padx=6, pady=2,
                               cursor="hand2", relief="flat")
                lbl.pack(anchor="w", pady=1)
                lbl.bind("<Button-1>", lambda e, r=ref: self._insert_ref(r))
        self._bind_wheel(self.refs_inner, self.refs_inner.canvas)

    def _insert_ref(self, ref):
        if self._focused_expr:
            try:
                w = self._focused_expr
                pos = w.index(tk.INSERT)
                w.insert(pos, ref)
                w.focus()
            except Exception:
                pass

    # ── section 3: copy cols ──────────────────────────────────────────────────
    def _section_copy(self, parent):
        self.copy_card = self._card(parent, "3 — copy columns to output  (raw values, no formula)")
        self.copy_inner = self._scrollable(self.copy_card, height=160)

    def _render_copy(self):
        for w in self.copy_inner.winfo_children():
            w.destroy()
        self._copy_vars = {}
        if not self.state.files:
            tk.Label(self.copy_inner, text="No files loaded yet.",
                     bg="#FFFFFF", fg="#9B9B98", font=("", 9)).pack(anchor="w")
            return
        columns = tk.Frame(self.copy_inner, bg="#FFFFFF")
        columns.pack(fill="x", anchor="nw")
        for fi, f in enumerate(self.state.files):
            c = FILE_COLORS[fi % len(FILE_COLORS)]
            col = tk.Frame(columns, bg="#FFFFFF", padx=10)
            col.pack(side="left", anchor="n")
            tk.Label(col, text=f.alias, bg=c["bg"], fg=c["fg"],
                     font=("", 9, "bold"), padx=6, pady=2).pack(anchor="w", pady=(0, 4))
            for h in f.headers:
                key = (f.alias, h)
                var = tk.BooleanVar(value=key in self.state.copy_cols)
                self._copy_vars[key] = var
                cb = tk.Checkbutton(col, text=h, variable=var,
                                    bg="#FFFFFF", fg=c["fg"],
                                    selectcolor=c["bg"], activebackground="#FFFFFF",
                                    font=("", 9), command=self._on_copy_change)
                cb.pack(anchor="w", pady=1)
        self._bind_wheel(self.copy_inner, self.copy_inner.canvas)

    def _on_copy_change(self):
        self.state.copy_cols = [k for k, v in self._copy_vars.items() if v.get()]
        self._render_preview()

    # ── section 4: ops ────────────────────────────────────────────────────────
    def _section_ops(self, parent):
        card = self._card(parent, "4 — computed columns")
        self.ops_frame = tk.Frame(card, bg="#FFFFFF")
        self.ops_frame.pack(fill="x")
        self._focused_expr = None
        btns = tk.Frame(card, bg="#FFFFFF")
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="＋ Add formula column",
                   command=self._add_op).pack(side="left")
        ttk.Button(btns, text="📥 Load formulas from .txt…",
                   command=self._load_formulas).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="💾 Save formulas to .txt…",
                   command=self._save_formulas).pack(side="left", padx=(8, 0))
        tk.Label(btns, text="format:  name<TAB>expression  (one per line)",
                 bg="#FFFFFF", fg="#9B9B98", font=("", 8)).pack(side="left", padx=(10, 0))

    def _render_ops(self):
        for w in self.ops_frame.winfo_children():
            w.destroy()
        self._op_entries = []
        for i, op in enumerate(self.state.ops):
            row = tk.Frame(self.ops_frame, bg="#FFFFFF")
            row.pack(fill="x", pady=3)

            tk.Label(row, text="name", bg="#FFFFFF", fg="#9B9B98",
                     font=("", 9)).pack(side="left")
            name_var = tk.StringVar(value=op["name"])
            name_ent = ttk.Entry(row, textvariable=name_var, width=14)
            name_ent.pack(side="left", padx=(4, 0))

            tk.Label(row, text="  =", bg="#FFFFFF", fg="#9B9B98",
                     font=("", 9)).pack(side="left")
            expr_var = tk.StringVar(value=op["expr"])
            expr_ent = ttk.Entry(row, textvariable=expr_var, width=38)
            expr_ent.pack(side="left", padx=(4, 0), fill="x", expand=True)
            expr_ent.bind("<FocusIn>", lambda e, w=expr_ent: self._set_focus(w))

            idx = i
            name_var.trace_add("write", lambda *a, ix=idx, v=name_var: self._update_op(ix, "name", v.get()))
            expr_var.trace_add("write", lambda *a, ix=idx, v=expr_var: self._update_op(ix, "expr", v.get()))

            ttk.Button(row, text="✕", width=3,
                       command=lambda ix=idx: self._remove_op(ix)).pack(side="left", padx=(6, 0))
            self._op_entries.append((name_ent, expr_ent))

    def _set_focus(self, widget):
        self._focused_expr = widget

    def _add_op(self):
        self.state.ops.append({"name": "", "expr": ""})
        self._render_ops()

    def _remove_op(self, idx):
        self.state.ops.pop(idx)
        self._render_ops()
        self._render_preview()

    def _update_op(self, idx, key, val):
        if idx < len(self.state.ops):
            self.state.ops[idx][key] = val
            self._render_preview()

    # ── load / save formulas from a .txt file ──────────────────────────────────
    def _parse_formula_text(self, text):
        """Parse formula lines: 'name<TAB>expression', one per line.
        Blank lines and lines starting with '#' are skipped.
        Falls back to splitting on 2+ spaces when no tab is present."""
        ops = []
        for raw in text.splitlines():
            line = raw.rstrip("\r")
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            name, expr = "", s
            if "\t" in line:
                name, expr = line.split("\t", 1)
                name, expr = name.strip(), expr.strip()
            else:
                parts = re.split(r"[ \t]{2,}", s, maxsplit=1)
                if len(parts) == 2:
                    name, expr = parts[0].strip(), parts[1].strip()
            ops.append({"name": name, "expr": expr})
        return ops

    def _load_formulas(self):
        path = filedialog.askopenfilename(
            title="Load formulas from text file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            return
        new_ops = self._parse_formula_text(text)
        if not new_ops:
            messagebox.showinfo(
                "No formulas",
                "No valid formula lines found in the file.\n"
                "Expected format:  name<TAB>expression  (one per line)")
            return
        choice = messagebox.askyesnocancel(
            "Load formulas",
            f"Loaded {len(new_ops)} formula(s) from:\n{os.path.basename(path)}\n\n"
            "Yes    = Replace existing formulas\n"
            "No     = Append to existing formulas\n"
            "Cancel = Abort")
        if choice is None:
            return
        if choice:
            self.state.ops = new_ops
        else:
            self.state.ops.extend(new_ops)
        self._focused_expr = None
        self._render_ops()
        self._render_preview()

    def _save_formulas(self):
        if not self.state.ops:
            messagebox.showinfo("No formulas", "There are no formula columns to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save formulas to text file",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="formulas.txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for op in self.state.ops:
                    f.write(f"{op['name']}\t{op['expr']}\n")
        except Exception as e:
            messagebox.showerror("Error writing file", str(e))
            return
        messagebox.showinfo(
            "Saved",
            f"Saved {len(self.state.ops)} formula(s) to:\n{os.path.basename(path)}")

    # ── section 5: preview & export ───────────────────────────────────────────
    def _section_preview(self, parent):
        card = self._card(parent, "5 — preview & export")
        self.preview_frame = tk.Frame(card, bg="#FFFFFF")
        self.preview_frame.pack(fill="both", expand=True)
        btn_row = tk.Frame(card, bg="#FFFFFF")
        btn_row.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_row, text="⬇ Export CSV…",
                   command=self._export).pack(side="left")
        self.export_msg = tk.Label(btn_row, text="", bg="#FFFFFF", fg="#166534", font=("", 9))
        self.export_msg.pack(side="left", padx=10)

    def _render_preview(self):
        for w in self.preview_frame.winfo_children():
            w.destroy()
        headers, rows = self.state.build_output()
        if not headers:
            tk.Label(self.preview_frame,
                     text="Select copy columns or add formulas above.",
                     bg="#FFFFFF", fg="#9B9B98", font=("", 10)).pack(anchor="w")
            return

        preview = rows[:20]

        # treeview
        tree = ttk.Treeview(self.preview_frame, columns=headers, show="headings",
                            height=min(len(preview), 12))
        for h in headers:
            tree.heading(h, text=h)
            tree.column(h, width=max(80, len(h)*9), anchor="center")
        for row in preview:
            tree.insert("", "end", values=[fmt(row.get(h, "")) for h in headers])

        vsb = ttk.Scrollbar(self.preview_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(self.preview_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        if len(rows) > 20:
            tk.Label(self.preview_frame,
                     text=f"Showing 20 of {len(rows)} rows",
                     bg="#FFFFFF", fg="#9B9B98", font=("", 9)).pack(anchor="w", pady=4)

    def _export(self):
        headers, rows = self.state.build_output()
        if not headers:
            messagebox.showinfo("Nothing to export", "Add copy columns or computed columns first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="output.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({h: fmt(row.get(h, "")) for h in headers})
        self.export_msg.config(text=f"✓ Exported {len(rows)} rows → {os.path.basename(path)}")
        self.after(4000, lambda: self.export_msg.config(text=""))

    # ── refresh all panels ────────────────────────────────────────────────────
    def _refresh(self):
        self._render_files()
        self._render_refs()
        self._render_copy()
        self._render_ops()
        self._render_preview()


if __name__ == "__main__":
    app = App()
    app.mainloop()
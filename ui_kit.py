"""Look and feel: colors (light + dark), fonts, small widgets, date picker, table,
timetable grid and the dashboard layout (top bar + sidebar + pages) used by all screens."""
import calendar
import io
import json
import os
import queue
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
import weakref
from datetime import date
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

import academic
import fonts
from textfmt import fmt_code, has_bengali, subject_of

# ------------------------------------------------------------------ colors: (light, dark)
PRIMARY = ("#55B9C8", "#65C5D1")
PRIMARY_HOVER = ("#45A9B8", "#55B5C1")
SECONDARY = ("#91D5DF", "#397F8D")
MINT = ("#D7F5E8", "#244B48")
BG = ("#F5FAFC", "#101C24")
SURFACE = ("#FFFFFF", "#192A34")
SIDEBAR = ("#EAF4F7", "#14232D")
TEXT = ("#243746", "#E7F1F4")
BORDER = ("#DCE9ED", "#30434D")
MUTED = ("#5F7584", "#9DB3BE")            # softer text (derived from Text)
ON_PRIMARY = ("#173042", "#0B1A22")       # text on the primary color
SUCCESS_BG, SUCCESS_FG = ("#E3F5EA", "#244B38"), ("#1E6B47", "#8FDDB0")
WARNING_BG, WARNING_FG = ("#FFF3D6", "#554322"), ("#7A5A12", "#F0D28A")
ERROR_BG, ERROR_FG = ("#FCE8E8", "#542F35"), ("#A33A3A", "#F2AEB5")
INFO_BG, INFO_FG = ("#E4F2FA", "#244253"), ("#1F5F85", "#9BD0EA")

CHIP_KINDS = {
    "info": (INFO_BG, INFO_FG), "success": (SUCCESS_BG, SUCCESS_FG),
    "warning": (WARNING_BG, WARNING_FG), "error": (ERROR_BG, ERROR_FG),
    "mint": (MINT, TEXT), "primary": (PRIMARY, ON_PRIMARY), "muted": (SIDEBAR, MUTED),
}
CELL_TONES = [MINT, INFO_BG, SUCCESS_BG, WARNING_BG, ERROR_BG, SECONDARY]

PREFS_FILE = Path(__file__).parent / "prefs.json"


def load_mode():
    try:
        return json.loads(PREFS_FILE.read_text()).get("mode", "light")
    except Exception:
        return "light"


def current(color):
    """The plain color for the mode that is on now (for widgets that cannot take two colors)."""
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def set_mode(mode):
    ctk.set_appearance_mode(mode)
    try:
        PREFS_FILE.write_text(json.dumps({"mode": mode}))
    except Exception:
        pass
    apply_tree_style()


ctk.set_default_color_theme("blue")
ctk.set_appearance_mode(load_mode())

# ------------------------------------------------------------------ fonts
_FONT_CACHE = {}


def font(size=14, bold=False, text=None):
    """DM Sans for English, Hind Siliguri for Bangla. bold = 600 (700 for big headings)."""
    fam = fonts.find_families()
    bn = has_bengali(text)
    key = (size, bold, bn)
    if key not in _FONT_CACHE:
        if bold and size >= 24:
            f = ctk.CTkFont(family=fam["bn" if bn else "en"], size=size, weight="bold")
        elif bold:
            name = fam["bn_semi" if bn else "en_semi"]
            base = fam["bn" if bn else "en"]
            f = ctk.CTkFont(family=name, size=size, weight="bold" if name == base else "normal")
        else:
            f = ctk.CTkFont(family=fam["bn" if bn else "en"], size=size)
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]


# ------------------------------------------------------------------ basic widgets
class Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", SURFACE)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", BORDER)
        kw.setdefault("corner_radius", 14)
        super().__init__(parent, **kw)


def label(parent, text, size=14, bold=False, color=TEXT, **kw):
    return ctk.CTkLabel(parent, text=text, font=font(size, bold, text), text_color=color, **kw)


def set_text(lbl, text, color=None):
    """Change a label's text and pick the right font for Bangla text."""
    lbl.configure(text=text, font=font(lbl._font.cget("size") if hasattr(lbl, "_font") else 14, False, text))
    if color is not None:
        lbl.configure(text_color=color)


def message(parent, **kw):
    return ctk.CTkLabel(parent, text="", font=font(13), text_color=MUTED, **kw)


def show_msg(lbl, text, ok=True):
    lbl.configure(text=text, text_color=SUCCESS_FG if ok else ERROR_FG)


def button(parent, text, command=None, kind="primary", width=None, height=38, **kw):
    kinds = {
        "primary": dict(fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=ON_PRIMARY),
        "secondary": dict(fg_color=SIDEBAR, hover_color=BORDER, text_color=TEXT,
                          border_width=1, border_color=BORDER),
        "danger": dict(fg_color=ERROR_BG, hover_color=BORDER, text_color=ERROR_FG),
        "success": dict(fg_color=SUCCESS_BG, hover_color=BORDER, text_color=SUCCESS_FG),
    }
    opts = dict(kinds[kind])
    opts.update(kw)
    if width:
        opts["width"] = width
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=10,
                         font=font(14, True), **opts)


def entry(parent, text="", placeholder="", width=None, **kw):
    e = ctk.CTkEntry(parent, height=38, corner_radius=10, fg_color=BG, border_color=BORDER,
                     text_color=TEXT, placeholder_text_color=MUTED, placeholder_text=placeholder,
                     font=font(14), **({"width": width} if width else {}), **kw)
    if text:
        e.insert(0, text)
    return e


def combo(parent, values, width=260, command=None):
    return ctk.CTkComboBox(parent, values=values or [""], width=width, height=38, command=command,
                           corner_radius=10, fg_color=BG, border_color=BORDER, button_color=PRIMARY,
                           button_hover_color=PRIMARY_HOVER, dropdown_fg_color=SURFACE,
                           dropdown_hover_color=SIDEBAR, text_color=TEXT, dropdown_text_color=TEXT,
                           font=font(14), dropdown_font=font(14))


def chip(parent, text, kind="info"):
    bg, fg = CHIP_KINDS[kind]
    return ctk.CTkLabel(parent, text=text, fg_color=bg, text_color=fg, corner_radius=8, height=28,
                        font=font(12, True, text), padx=10)


def stat_card(parent, title, value, tone=PRIMARY):
    box = Card(parent)
    ctk.CTkFrame(box, fg_color=tone, width=5, height=10, corner_radius=3).pack(
        side="left", fill="y", padx=(10, 0), pady=14)
    inner = ctk.CTkFrame(box, fg_color="transparent")
    inner.pack(side="left", padx=14, pady=10)
    value_label = label(inner, str(value), 22, True)
    value_label.pack(anchor="w")
    label(inner, title, 12, False, MUTED).pack(anchor="w")
    box.value_label = value_label
    return box


def date_block(parent, d, done=False):
    block = ctk.CTkFrame(parent, fg_color=SIDEBAR if done else PRIMARY, corner_radius=12,
                         width=86, height=86)
    block.grid_propagate(False)
    block.pack_propagate(False)
    color = MUTED if done else ON_PRIMARY
    label(block, d.strftime("%d"), 26, True, color).pack(pady=(8, 0))
    label(block, d.strftime("%b").upper(), 12, True, color).pack()
    label(block, d.strftime("%a"), 11, False, color).pack()
    return block


def status_for(d, next_date):
    if d < date.today():
        return "DONE"
    return "NEXT" if d == next_date else ""


def section_head(parent, title, subtitle=""):
    """Section heading (20px, 600). Returns (frame, right) - put buttons in `right`."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(0, 8))
    left = ctk.CTkFrame(row, fg_color="transparent")
    left.pack(side="left")
    label(left, title, 20, True).pack(anchor="w")
    if subtitle:
        label(left, subtitle, 13, False, MUTED).pack(anchor="w")
    right = ctk.CTkFrame(row, fg_color="transparent", width=1, height=1)   # grows with its buttons
    right.pack(side="right")
    return row, right


def scroll(parent, **kw):
    return ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=BORDER,
                                  scrollbar_button_hover_color=SECONDARY, **kw)


# ------------------------------------------------------------------ date picker
class CalendarPopup(ctk.CTkToplevel):
    """Pop-up calendar. Years from (this year - 20) to (this year + 5)."""

    def __init__(self, anchor, start, on_pick):
        super().__init__(anchor)
        self.on_pick = on_pick
        today = date.today()
        self.first_year, self.last_year = today.year - 20, today.year + 5
        start = start or today
        self.year = min(max(start.year, self.first_year), self.last_year)
        self.month = start.month
        self.selected = start if start else None
        self.title("Select date")
        self.configure(fg_color=SURFACE)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        anchor.update_idletasks()
        self._pos = f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height() + 4}"
        self.geometry(self._pos)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 6))
        button(head, "<", self.prev_month, "secondary", width=36, height=34).pack(side="left")
        self.month_box = combo(head, list(calendar.month_name)[1:], 120, lambda v: self.pick_month(v))
        self.month_box.configure(height=34)
        self.month_box.pack(side="left", padx=6)
        self.year_box = combo(head, [str(y) for y in range(self.first_year, self.last_year + 1)], 86,
                              lambda v: self.pick_year(v))
        self.year_box.configure(height=34)
        self.year_box.pack(side="left")
        button(head, ">", self.next_month, "secondary", width=36, height=34).pack(side="left", padx=(6, 0))
        self.grid_area = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_area.pack(padx=12, pady=(0, 6))
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=12, pady=(0, 12))
        button(foot, "Today", lambda: self.choose(date.today()), "secondary", width=80, height=32).pack(
            side="left")
        button(foot, "Close", self.destroy, "secondary", width=80, height=32).pack(side="right")
        self.render()
        self.after(80, self.grab)
        self.after(220, lambda: self.geometry(self._pos))    # CTk resets the size after start

    def grab(self):
        try:
            self.geometry(self._pos)
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def render(self):
        self.month_box.set(calendar.month_name[self.month])
        self.year_box.set(str(self.year))
        for w in self.grid_area.winfo_children():
            w.destroy()
        for c, name in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
            label(self.grid_area, name, 12, True, MUTED, width=40).grid(row=0, column=c, pady=(0, 4))
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.year, self.month)
        today = date.today()
        for r, week in enumerate(weeks, start=1):
            for c, d in enumerate(week):
                other = d.month != self.month
                is_sel = self.selected == d
                if is_sel:
                    colors = dict(fg_color=PRIMARY, text_color=ON_PRIMARY, hover_color=PRIMARY_HOVER)
                elif d == today:
                    colors = dict(fg_color=MINT, text_color=TEXT, hover_color=SECONDARY)
                else:
                    colors = dict(fg_color="transparent", text_color=MUTED if other else TEXT,
                                  hover_color=SIDEBAR)
                ctk.CTkButton(self.grid_area, text=str(d.day), width=40, height=34, corner_radius=8,
                              font=font(13, is_sel), command=lambda x=d: self.choose(x), **colors).grid(
                    row=r, column=c, padx=1, pady=1)

    def choose(self, d):
        if not (self.first_year <= d.year <= self.last_year):
            return
        self.on_pick(d)
        self.destroy()

    def pick_month(self, name):
        self.month = list(calendar.month_name).index(name)
        self.render()

    def pick_year(self, text):
        self.year = int(text)
        self.render()

    def prev_month(self):
        if self.year == self.first_year and self.month == 1:
            return
        self.month, self.year = (12, self.year - 1) if self.month == 1 else (self.month - 1, self.year)
        self.render()

    def next_month(self):
        if self.year == self.last_year and self.month == 12:
            return
        self.month, self.year = (1, self.year + 1) if self.month == 12 else (self.month + 1, self.year)
        self.render()


class DateField(ctk.CTkFrame):
    """A button that opens the pop-up calendar. get() gives 'YYYY-MM-DD' or ''."""

    def __init__(self, parent, placeholder="Select date", width=200, value=None):
        super().__init__(parent, fg_color="transparent")
        self.value = None
        self.placeholder = placeholder
        self.btn = ctk.CTkButton(self, text=placeholder, width=width, height=38, anchor="w",
                                 corner_radius=10, fg_color=BG, hover_color=SIDEBAR, border_width=1,
                                 border_color=BORDER, text_color=MUTED, font=font(14), command=self.open)
        self.btn.pack(fill="x")
        if value:
            self.set(value)

    def open(self):
        old = getattr(self, "popup", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        self.popup = CalendarPopup(self.btn, self.value, self.set)

    def set(self, d):
        self.value = d
        if d:
            self.btn.configure(text=d.strftime("%d %b %Y"), text_color=TEXT)
        else:
            self.btn.configure(text=self.placeholder, text_color=MUTED)

    def get(self):
        return self.value.isoformat() if self.value else ""


# ------------------------------------------------------------------ table (fast, for many rows)
_TABLES = []
_TREE_FONTS = []


def apply_tree_style():
    try:
        style = ttk.Style()
        fam = fonts.find_families()
        body = tkfont.Font(family=fam["en"], size=-13)
        head = tkfont.Font(family=fam["en_semi"], size=-13)
        _TREE_FONTS[:] = [body, head]
        style.configure("ER.Treeview", background=current(SURFACE), fieldbackground=current(SURFACE),
                        foreground=current(TEXT), rowheight=30, borderwidth=0, font=body)
        style.configure("ER.Treeview.Heading", background=current(SIDEBAR), foreground=current(TEXT),
                        relief="flat", font=head, padding=(8, 6))
        style.map("ER.Treeview", background=[("selected", current(PRIMARY))],
                  foreground=[("selected", current(ON_PRIMARY))])
        style.map("ER.Treeview.Heading", background=[("active", current(BORDER))])
        for name in ("ER.Vertical.TScrollbar", "ER.Horizontal.TScrollbar"):
            style.configure(name, background=current(BORDER), troughcolor=current(SURFACE),
                            bordercolor=current(SURFACE), arrowcolor=current(MUTED))
        for ref in list(_TABLES):
            t = ref()
            if t is None:
                _TABLES.remove(ref)
            else:
                t.tree.tag_configure("odd", background=current(BG))
    except Exception:
        pass


class DataTable(ctk.CTkFrame):
    """columns = [(key, heading, width, anchor)]"""

    def __init__(self, parent, columns, height=12, selectmode="extended"):
        super().__init__(parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=12)
        try:
            ttk.Style().theme_use("clam")
        except Exception:
            pass
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings",
                                 style="ER.Treeview", selectmode=selectmode, height=height)
        last = len(columns) - 1
        for i, (key, text, width, anchor) in enumerate(columns):
            self.tree.heading(key, text=text, anchor=anchor)
            self.tree.column(key, width=width, minwidth=40, anchor=anchor, stretch=(i == last))
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style="ER.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview,
                            style="ER.Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        vsb.grid(row=0, column=1, sticky="ns", pady=(6, 0), padx=(0, 4))
        hsb.grid(row=1, column=0, sticky="ew", padx=(6, 0), pady=(0, 4))
        _TABLES.append(weakref.ref(self))
        apply_tree_style()

    def set_rows(self, rows):
        """rows = [(iid, [values...])]"""
        self.tree.delete(*self.tree.get_children())
        for i, (iid, values) in enumerate(rows):
            self.tree.insert("", "end", iid=str(iid), values=values, tags=("odd",) if i % 2 else ())
        self.tree.tag_configure("odd", background=current(BG))

    def selected(self):
        return list(self.tree.selection())


# ------------------------------------------------------------------ weekly timetable
FULL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def tone_for(code):
    key = subject_of(code) or str(code)
    return CELL_TONES[sum(ord(c) for c in key) % len(CELL_TONES)]


class TimetableGrid(ctk.CTkFrame):
    """items = [{'day','period','start','end','code',...}]. lines_fn(item) -> list of text lines.
    breaks = [(name, 'HH:MM', 'HH:MM')] are shown as bars between the periods."""

    def __init__(self, parent, periods, days, items, lines_fn, breaks=()):
        super().__init__(parent, fg_color="transparent")
        periods = list(periods)
        known = {p[0] for p in periods}
        for it in items:
            if it["period"] not in known:
                periods.append((it["period"], it["start"], it["end"]))
                known.add(it["period"])
        used = list(days)
        for it in items:
            if it["day"] not in used:
                used.append(it["day"])
        order = [d for d in academic.WEEK_ORDER if d in used]
        by = {(it["day"], it["period"]): it for it in items}
        entries = [("p", p[1], p) for p in periods] + [("b", b[1], b) for b in breaks]
        entries.sort(key=lambda e: e[1])

        self.grid_columnconfigure(0, minsize=100)
        for c, d in enumerate(order, start=1):
            self.grid_columnconfigure(c, weight=1, uniform="tt")
            label(self, FULL_DAYS[d], 13, True, TEXT, fg_color=SIDEBAR, corner_radius=8, height=32).grid(
                row=0, column=c, sticky="ew", padx=3, pady=(0, 4))
        for r, (kind, _, e) in enumerate(entries, start=1):
            if kind == "b":
                label(self, f"{e[0]}      {e[1]} - {e[2]}", 12, True, MUTED, fg_color=MINT,
                      corner_radius=8, height=26).grid(row=r, column=0, columnspan=len(order) + 1,
                                                       sticky="ew", padx=3, pady=3)
                continue
            no, start, end = e
            lab = ctk.CTkFrame(self, fg_color="transparent")
            lab.grid(row=r, column=0, sticky="nsew", padx=(0, 4), pady=3)
            label(lab, f"Period {no}", 13, True).pack(anchor="w", pady=(12, 0))
            label(lab, f"{start}-{end}", 12, False, MUTED).pack(anchor="w")
            for c, d in enumerate(order, start=1):
                it = by.get((d, no))
                if it:
                    cell = ctk.CTkFrame(self, fg_color=tone_for(it["code"]), corner_radius=10, height=92,
                                        border_width=1, border_color=BORDER)
                    cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
                    cell.pack_propagate(False)
                    for i, text in enumerate(lines_fn(it)):
                        label(cell, text, 13 if i == 0 else 12, i == 0,
                              TEXT if i == 0 else MUTED).pack(anchor="w", padx=10,
                                                              pady=(8 if i == 0 else 1, 0))
                else:
                    ctk.CTkFrame(self, fg_color=BG, corner_radius=10, height=92, border_width=1,
                                 border_color=BORDER).grid(row=r, column=c, sticky="nsew", padx=3, pady=3)


# ------------------------------------------------------------------ PDF save helper
AUTO_OPEN = True


def save_pdf(parent, default_name, builder):
    """Ask where to save, build the PDF. Returns (ok, message) or None if cancelled."""
    path = filedialog.asksaveasfilename(parent=parent, title="Save PDF", defaultextension=".pdf",
                                        initialfile=default_name, filetypes=[("PDF file", "*.pdf")])
    if not path:
        return None
    try:
        builder(path)
    except PermissionError:
        return False, "Could not save. Close the file if it is open in another program."
    except Exception as e:
        return False, f"Could not create the PDF: {e}"
    if AUTO_OPEN:
        try:
            if hasattr(os, "startfile"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
    return True, f"Saved: {path}"


# ------------------------------------------------------------------ background log helpers
class QueueWriter(io.TextIOBase):
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(s)
        return len(s)

    def flush(self):
        pass


DONE = object()


# ------------------------------------------------------------------ dashboard layout
class Dashboard(ctk.CTkFrame):
    def __init__(self, app, role_label, name):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        self.current_page = None
        top = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=64)
        top.pack(fill="x")
        top.pack_propagate(False)
        label(top, "Exam Routine", 20, True).pack(side="left", padx=(24, 12))
        chip(top, role_label.upper(), "primary").pack(side="left")
        button(top, "Logout", app.logout, "secondary", width=90, height=34).pack(side="right", padx=24)
        label(top, name, 14, True, MUTED).pack(side="right", padx=(0, 6))
        self.mode_switch = ctk.CTkSwitch(top, text="Dark mode", font=font(13), text_color=MUTED,
                                         progress_color=PRIMARY, button_color=SECONDARY,
                                         button_hover_color=PRIMARY_HOVER, width=44,
                                         command=lambda: app.set_theme("dark" if self.mode_switch.get() else "light"))
        if ctk.get_appearance_mode() == "Dark":
            self.mode_switch.select()
        self.mode_switch.pack(side="right", padx=16)
        ctk.CTkFrame(self, fg_color=BORDER, height=1, corner_radius=0).pack(fill="x")
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.pack(fill="both", expand=True)
        self.sidebar = ctk.CTkFrame(main, fg_color=SIDEBAR, corner_radius=0, width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkFrame(main, fg_color=BORDER, width=1, corner_radius=0).pack(side="left", fill="y")
        self.body = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        self.body.pack(side="left", fill="both", expand=True, padx=26, pady=18)

    # ----- page header and numbers
    def header(self, title, subtitle, refresh_cmd=None):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        label(left, title, 28, True).pack(anchor="w")
        label(left, subtitle, 13, False, MUTED, justify="left").pack(anchor="w")
        if refresh_cmd:
            button(row, "Refresh", refresh_cmd, "secondary", width=96, height=36).pack(side="right")

    def stats_row(self, items):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(14, 8))
        tones = (PRIMARY, SECONDARY, MINT, INFO_FG, WARNING_FG, SUCCESS_FG)
        for i, (title, value, *_) in enumerate(items):
            row.grid_columnconfigure(i, weight=1, uniform="stat")
            stat_card(row, title, value, tones[i % len(tones)]).grid(
                row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))

    # ----- sidebar pages
    def make_pages(self, names):
        for w in self.sidebar.winfo_children():
            w.destroy()
        self.page_area = ctk.CTkFrame(self.body, fg_color="transparent")
        self.page_area.pack(fill="both", expand=True, pady=(6, 0))
        self.pages, self.nav_buttons = {}, {}
        label(self.sidebar, "MENU", 11, True, MUTED).pack(anchor="w", padx=22, pady=(20, 6))
        for n in names:
            self.pages[n] = ctk.CTkFrame(self.page_area, fg_color="transparent")
            b = ctk.CTkButton(self.sidebar, text=n, anchor="w", height=40, corner_radius=10,
                              fg_color="transparent", hover_color=BORDER, text_color=TEXT, font=font(14, True),
                              command=lambda x=n: self.show_page(x))
            b.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[n] = b
        self.show_page(self.current_page if self.current_page in self.pages else names[0])
        return self.pages

    def show_page(self, name):
        self.current_page = name
        for n, frame in self.pages.items():
            frame.pack_forget()
            self.nav_buttons[n].configure(fg_color="transparent", text_color=TEXT)
        self.pages[name].pack(fill="both", expand=True)
        self.nav_buttons[name].configure(fg_color=PRIMARY, text_color=ON_PRIMARY)

    def empty_state(self, parent, text):
        box = Card(parent, corner_radius=16)
        box.pack(fill="x", pady=10)
        label(box, text, 15, False, MUTED, wraplength=640, justify="center").pack(padx=30, pady=46)

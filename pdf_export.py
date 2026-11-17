"""PDF downloads: exam routine, class routine, student exam routine, teacher exam duty.

Fonts: DM Sans for English, Hind Siliguri for Bangla (both in the fonts folder).
"""
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

import academic
from textfmt import fmt_code, has_bengali

FONTS = Path(__file__).parent / "fonts"
INK = (36, 55, 70)            # text  #243746
PRIMARY = (85, 185, 200)      # primary #55B9C8
SECONDARY = (145, 213, 223)   # secondary #91D5DF
MINT = (215, 245, 232)        # mint #D7F5E8
SIDEBAR = (234, 244, 247)     # sidebar #EAF4F7
BORDER = (220, 233, 237)      # border #DCE9ED
MUTED = (110, 130, 142)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Doc(FPDF):
    def __init__(self, title, subtitle="", landscape=True):
        super().__init__(orientation="L" if landscape else "P", unit="mm", format="A4")
        self.doc_title, self.doc_subtitle = title, subtitle
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(True, margin=14)
        self.add_font("DM Sans", "", str(FONTS / "DMSans-Regular.ttf"))
        self.add_font("DM Sans", "B", str(FONTS / "DMSans-Bold.ttf"))
        self.add_font("DM Sans SemiBold", "", str(FONTS / "DMSans-SemiBold.ttf"))
        self.add_font("Hind Siliguri", "", str(FONTS / "HindSiliguri-Regular.ttf"))
        self.add_font("Hind Siliguri", "B", str(FONTS / "HindSiliguri-Bold.ttf"))
        try:
            self.set_text_shaping(True)       # joins Bangla letters correctly (needs uharfbuzz)
        except Exception:
            pass
        self.alias_nb_pages()
        self.add_page()

    # ---- page parts
    def header(self):
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, self.w, 3, style="F")
        self.set_xy(10, 7)
        self.set_font("DM Sans", "", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 4, "Exam Routine System", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DM Sans", "B", 18)
        self.set_text_color(*INK)
        self.cell(0, 9, self.doc_title, new_x="LMARGIN", new_y="NEXT")
        if self.doc_subtitle:
            self.set_font("Hind Siliguri" if has_bengali(self.doc_subtitle) else "DM Sans", "", 10)
            self.set_text_color(*MUTED)
            self.multi_cell(0, 5, self.doc_subtitle, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-10)
        self.set_font("DM Sans", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}", align="L")
        self.set_x(-40)
        self.cell(30, 5, f"Page {self.page_no()} / {{nb}}", align="R")

    # ---- helpers
    def section(self, text):
        self.ln(2)
        self.set_font("DM Sans SemiBold", "", 13)
        self.set_text_color(*INK)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")

    def face(self, text, bold=False, fill=None, color=INK, size=9):
        fam = "Hind Siliguri" if has_bengali(text) else "DM Sans"
        return FontFace(family=fam, emphasis="BOLD" if bold else None, size_pt=size,
                        color=color, fill_color=fill)

    def data_table(self, headers, rows, widths, aligns=None, size=9):
        """One table. rows = list of lists of text. Header repeats on every page."""
        aligns = aligns or ["L"] * len(headers)
        head = FontFace(family="DM Sans", emphasis="BOLD", size_pt=size, color=INK, fill_color=SECONDARY)
        with self.table(col_widths=widths, text_align=tuple(aligns), headings_style=head,
                        line_height=5.2, borders_layout="SINGLE_TOP_LINE",
                        cell_fill_color=SIDEBAR, cell_fill_mode="ROWS", width=sum(widths)) as table:
            r = table.row()
            for h in headers:
                r.cell(h)
            for row in rows:
                r = table.row()
                for text in row:
                    text = str(text)
                    r.cell(text, style=self.face(text, size=size))


def _d(d):
    return d.strftime("%d %b %Y")


def _meta(*parts):
    return "   |   ".join(p for p in parts if p)


# ------------------------------------------------------------------ exam routine (admin)
def exam_routine_pdf(path, rows, subtitle=""):
    doc = Doc("Exam Routine", subtitle or f"{len(rows)} room allotments")
    sched = OrderedDict()
    for r in rows:
        key = (r["date"], r["start"], r["end"], r["code"])
        e = sched.setdefault(key, dict(r=r, students=0, rooms=0))
        e["students"] += r["students"]
        e["rooms"] += 1
    doc.section("1. Exam schedule")
    doc.data_table(["Date", "Day", "Time", "Course", "Class", "Students", "Rooms"],
                   [[_d(k[0]), k[0].strftime("%a"), f"{k[1]} - {k[2]}", fmt_code(k[3]),
                     fmt_code(v["r"]["klass"]), v["students"], v["rooms"]] for k, v in sched.items()],
                   [34, 20, 40, 34, 34, 24, 20], ["L", "L", "L", "L", "L", "R", "R"])
    doc.section("2. Rooms, seats and teachers")
    doc.data_table(["Date", "Time", "Course", "Room", "Seats", "Students", "Teachers"],
                   [[_d(r["date"]), f"{r['start']} - {r['end']}", fmt_code(r["code"]), r["room"],
                     f"{r['first']} - {r['last']}", r["students"], r["teachers"]] for r in rows],
                   [28, 32, 24, 20, 24, 20, 129], ["L", "L", "L", "L", "L", "R", "L"], size=8)
    doc.output(path)


# ------------------------------------------------------------------ class routine (timetable)
def class_routine_pdf(path, title, subtitle, items, periods, breaks, days, lines_fn):
    """items = [{'day','period',...}]. lines_fn(item) -> list of text lines for a cell."""
    doc = Doc(title, subtitle)
    periods = list(periods)
    known = {p[0] for p in periods}
    for it in items:
        if it["period"] not in known:
            periods.append((it["period"], it["start"], it["end"]))
            known.add(it["period"])
    periods.sort()
    used = list(days)
    for it in items:
        if it["day"] not in used:
            used.append(it["day"])
    order = [d for d in academic.WEEK_ORDER if d in used]
    by = {(it["day"], it["period"]): it for it in items}

    entries = [("p", p[1], p) for p in periods] + [("b", b[1], b) for b in breaks]
    entries.sort(key=lambda e: e[1])
    ncols = len(order) + 1
    width = 277
    first = 26
    widths = [first] + [(width - first) / len(order)] * len(order)
    head = FontFace(family="DM Sans", emphasis="BOLD", size_pt=10, color=INK, fill_color=SECONDARY)
    with doc.table(col_widths=widths, headings_style=head, line_height=4.6, text_align="C",
                   borders_layout="ALL", width=width) as table:
        r = table.row()
        r.cell("Period")
        for d in order:
            r.cell(DAYS[d])
        for kind, _, e in entries:
            r = table.row()
            if kind == "b":
                r.cell(f"{e[0]}   {e[1]} - {e[2]}", colspan=ncols,
                       style=FontFace(family="DM Sans", emphasis="BOLD", size_pt=8.5, color=MUTED,
                                      fill_color=MINT))
                continue
            no, start, end = e
            r.cell(f"Period {no}\n{start}-{end}",
                   style=FontFace(family="DM Sans", emphasis="BOLD", size_pt=8.5, color=INK,
                                  fill_color=SIDEBAR))
            for d in order:
                it = by.get((d, no))
                if not it:
                    r.cell("")
                    continue
                lines = lines_fn(it)
                text = "\n".join(lines)
                r.cell(text, style=doc.face(text, size=8.5, fill=(255, 255, 255)))
    doc.output(path)


# ------------------------------------------------------------------ student exam routine
def student_exam_pdf(path, name, student_id, klass, section, semester, exams):
    doc = Doc("My Exam Routine", _meta(f"{name}", f"ID {student_id}", fmt_code(klass),
                                       f"Section {section}", semester))
    doc.data_table(["Date", "Day", "Time", "Course", "Course name", "Room", "Seat"],
                   [[_d(e["date"]), e["date"].strftime("%a"), f"{e['start']} - {e['end']}",
                     fmt_code(e["code"]), e["course"], f"{e['building']}-{e['room']}", e["seat"]]
                    for e in exams],
                   [30, 18, 34, 26, 90, 26, 20], ["L", "L", "L", "L", "L", "L", "R"], size=10)
    doc.output(path)


# ------------------------------------------------------------------ teacher exam duty
def duty_pdf(path, name, code, major, duties):
    doc = Doc("My Exam Duty", _meta(name, f"ID {code}", f"Major {major}" if major else ""))
    doc.data_table(["Date", "Day", "Time", "Course", "Course name", "Room", "Students", "With"],
                   [[_d(x["date"]), x["date"].strftime("%a"), f"{x['start']} - {x['end']}",
                     fmt_code(x["code"]), x["course"], f"{x['building']}-{x['room']}",
                     x["students"], x["partners"]] for x in duties],
                   [28, 14, 30, 22, 52, 22, 20, 89], ["L", "L", "L", "L", "L", "L", "R", "L"], size=9)
    doc.output(path)

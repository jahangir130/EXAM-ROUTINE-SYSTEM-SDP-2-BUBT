"""Student dashboard: class routine, exam routine, courses and marks (PDF download for routines)."""
from collections import defaultdict
from datetime import date

import customtkinter as ctk

import academic
import pdf_export
import queries
import ui_kit
from db import get_connection
from textfmt import fmt_code
from ui_kit import (BG, BORDER, CHIP_KINDS, ERROR_FG, MUTED, ON_PRIMARY, PRIMARY, SECONDARY, SIDEBAR,
                    SUCCESS_FG, TEXT, Card, Dashboard, TimetableGrid, button, chip, date_block, label,
                    message, scroll, section_head, show_msg, status_for)


class StudentFrame(Dashboard):
    def __init__(self, app, student_id, name):
        super().__init__(app, "Student", name)
        self.student_id = student_id
        self.name = name
        self.render()

    # ---------------------------------------------------------------- data
    def load(self):
        conn = get_connection()
        try:
            d = dict(info=queries.student_info(conn, self.student_id),
                     exams=queries.student_exams(conn, self.student_id),
                     sem=academic.active_semester(conn),
                     settings=academic.get_settings(conn))
            sid = d["sem"]["id"] if d["sem"] else 0
            d["courses"] = academic.student_courses(conn, self.student_id, sid)
            d["timetable"] = academic.student_timetable(conn, self.student_id, sid) if sid else []
            d["marks"] = academic.student_marks(conn, self.student_id, sid) if sid else {}
        finally:
            conn.close()
        return d

    def subtitle(self, d, with_semester=True):
        i = d["info"]
        parts = [f"ID {self.student_id}", fmt_code(i["dept"]), f"Section {i['section']}"]
        if with_semester and d["sem"]:
            parts.append(d["sem"]["name"])
        return "   |   ".join(parts)

    # -------------------------------------------------------------- screen
    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        d = self.load()
        self.d = d
        exams, sem = d["exams"], d["sem"]
        sub = self.subtitle(d, False) + f"   |   Intake {d['info']['intake']}"
        sub += ("\nSemester: " + academic.semester_text(sem)) if sem else "\nNo active semester yet"
        self.header(f"Hello, {self.name}", sub, self.render)
        upcoming = [e["date"] for e in exams if e["date"] >= date.today()]
        next_date = min(upcoming) if upcoming else None
        self.stats_row([
            ("Courses", len(d["courses"]), 0),
            ("Exams", len(exams), 0),
            ("Next exam", next_date.strftime("%d %b %Y") if next_date else "-", 0),
            ("Classes per week", len(d["timetable"]), 0),
        ])
        pages = self.make_pages(["Class routine", "Exam routine", "My courses", "Marks"])
        self.class_page(pages["Class routine"])
        self.exam_page(pages["Exam routine"], next_date)
        self.courses_page(pages["My courses"])
        self.marks_page(pages["Marks"])

    # ---------------------------------------------------------- pdf helpers
    def download(self, default_name, builder, msg_label):
        res = ui_kit.save_pdf(self, default_name, builder)
        if res:
            show_msg(msg_label, res[1], res[0])

    # ---------------------------------------------------------------- pages
    def class_page(self, page):
        d = self.d
        _, right = section_head(page, "Weekly class routine")
        msg = message(page)
        if d["timetable"]:
            s = d["settings"]

            def build(path):
                pdf_export.class_routine_pdf(
                    path, "My Class Routine", f"{self.name}   |   " + self.subtitle(d), d["timetable"],
                    academic.class_periods(s), academic.class_breaks(s), academic.parse_days(s["class_days"]),
                    lambda it: [fmt_code(it["code"]), it["teacher"], f"Room {it['room']}"])

            button(right, "Download PDF", lambda: self.download(
                f"class_routine_{self.student_id}.pdf", build, msg), "primary", width=150).pack()
        msg.pack(anchor="w")
        box = scroll(page)
        box.pack(fill="both", expand=True)
        if not d["timetable"]:
            self.empty_state(box, "Your class routine is not published yet.\n"
                                  "The admin will publish it after assigning teachers.")
            return
        s = d["settings"]
        TimetableGrid(box, academic.class_periods(s), academic.parse_days(s["class_days"]), d["timetable"],
                      lambda it: [fmt_code(it["code"]), it["teacher"], f"Room {it['room']}"],
                      academic.class_breaks(s)).pack(fill="x", padx=2, pady=2)

    def exam_page(self, page, next_date):
        d, exams = self.d, self.d["exams"]
        _, right = section_head(page, "Exam routine")
        msg = message(page)
        if exams:
            def build(path):
                pdf_export.student_exam_pdf(path, self.name, self.student_id, d["info"]["dept"],
                                            d["info"]["section"], d["sem"]["name"] if d["sem"] else "", exams)

            button(right, "Download PDF", lambda: self.download(
                f"exam_routine_{self.student_id}.pdf", build, msg), "primary", width=150).pack()
        msg.pack(anchor="w")
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not exams:
            self.empty_state(lst, "Your exam routine is not published yet.\n"
                                  "Please check again after the admin generates the routine.")
            return
        for e in exams:
            status = status_for(e["date"], next_date)
            done = status == "DONE"
            item = Card(lst)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            date_block(item, e["date"], done).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            top = ctk.CTkFrame(mid, fg_color="transparent")
            top.pack(anchor="w")
            label(top, fmt_code(e["code"]), 20, True, MUTED if done else TEXT).pack(side="left")
            if status:
                chip(top, status, "success" if status == "NEXT" else "muted").pack(side="left", padx=10)
            label(mid, e["course"], 14, False, MUTED).pack(anchor="w")
            label(mid, f"{e['start']} - {e['end']}", 14, True, TEXT).pack(anchor="w", pady=(4, 0))
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            chip(right, f"Room {e['building']}-{e['room']}", "info").pack(pady=3, anchor="e")
            chip(right, f"Seat {e['seat']}", "primary").pack(pady=3, anchor="e")

    def courses_page(self, page):
        d = self.d
        section_head(page, "My courses")
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not d["courses"]:
            self.empty_state(lst, "No courses found for you.")
            return
        slots = defaultdict(list)
        for t in d["timetable"]:
            slots[t["code"]].append(t)
        for c in d["courses"]:
            item = Card(lst)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            label(item, fmt_code(c["code"]), 18, True, ON_PRIMARY, fg_color=PRIMARY, corner_radius=12,
                  width=100, height=64).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            label(mid, c["course"], 16, True).pack(anchor="w")
            label(mid, ("Teacher: " + c["teacher"]) if c["teacher"] else "Teacher not assigned yet",
                  14, False, MUTED).pack(anchor="w")
            rows = slots.get(c["code"], [])
            when = "   |   ".join(f"{academic.WEEKDAY_NAMES[r['day']]} {r['start']}-{r['end']} "
                                  f"(Room {r['room']})" for r in rows)
            label(mid, when or "Class time not published yet", 13, True, MUTED, wraplength=620,
                  justify="left").pack(anchor="w", pady=(4, 0))
            chip(item, f"{len(rows)} class/week", "mint").grid(row=0, column=2, padx=18)

    def marks_page(self, page):
        d = self.d
        section_head(page, "Marks")
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not d["sem"]:
            self.empty_state(lst, "No active semester yet.")
            return
        mx = float(d["settings"]["max_marks"])
        got = [(c, d["marks"].get(c["course_id"])) for c in d["courses"]]
        done = [m for _, m in got if m is not None]
        text = (f"Published: {len(done)} of {len(got)} courses"
                + (f"   |   Average: {sum(done) / len(done):.1f} / {mx:g}" if done else ""))
        label(lst, text, 14, True, MUTED).pack(anchor="w", pady=(0, 6))
        for c, m in got:
            item = Card(lst)
            item.pack(fill="x", pady=5)
            item.grid_columnconfigure(1, weight=1)
            label(item, fmt_code(c["code"]), 16, True, width=100).grid(row=0, column=0, padx=(14, 6), pady=16)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            label(mid, c["course"], 14, True).pack(anchor="w")
            label(mid, ("Teacher: " + c["teacher"]) if c["teacher"] else "Teacher not assigned",
                  13, False, MUTED).pack(anchor="w")
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            if m is None:
                chip(right, "Not published yet", "muted").pack()
            else:
                letter = academic.grade_for(m, mx)
                label(right, f"{m:g} / {mx:g}", 20, True).pack(side="left", padx=(0, 12))
                chip(right, letter, "success" if letter != "F" else "error").pack(side="left")

"""Teacher dashboard: courses, class routine, marks entry, exam routine and duty (PDF downloads)."""
from datetime import date

import customtkinter as ctk

import academic
import pdf_export
import queries
import ui_kit
from db import get_connection
from textfmt import fmt_code
from ui_kit import (BG, BORDER, ERROR_FG, MUTED, ON_PRIMARY, PRIMARY, SUCCESS_FG, TEXT, Card, Dashboard,
                    TimetableGrid, button, chip, date_block, entry, label, message, scroll, section_head,
                    show_msg, status_for, combo)


class TeacherFrame(Dashboard):
    def __init__(self, app, teacher_id, name):
        super().__init__(app, "Teacher", name)
        self.teacher_id = int(teacher_id)
        self.name = name
        self.render()

    def load(self):
        conn = get_connection()
        try:
            d = dict(info=queries.teacher_info(conn, self.teacher_id),
                     duties=queries.teacher_duties(conn, self.teacher_id),
                     sem=academic.active_semester(conn),
                     settings=academic.get_settings(conn))
            sid = d["sem"]["id"] if d["sem"] else 0
            d["assign"] = academic.teacher_assignments(conn, self.teacher_id, sid) if sid else []
            d["timetable"] = academic.teacher_timetable(conn, self.teacher_id, sid) if sid else []
            d["exam_rooms"] = {a["id"]: academic.assignment_exam_rooms(conn, a["course_id"], a["section"])
                               for a in d["assign"]}
        finally:
            conn.close()
        return d

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        d = self.load()
        self.d = d
        info, sem = d["info"], d["sem"]
        self.title_name = f"{self.name} ({info['major']})" if info["major"] else self.name
        sub = (f"Teacher ID {info['code']}   |   {info['rank'].title()}   |   Major {info['major'] or '-'}"
               f"   |   {info['dept']}")
        sub += ("\nSemester: " + academic.semester_text(sem)) if sem else "\nNo active semester yet"
        self.header(f"Hello, {self.title_name}", sub, self.render)
        self.stats_row([
            ("My courses", len(d["assign"]), 0),
            ("Students", sum(a["size"] for a in d["assign"]), 0),
            ("Classes per week", len(d["timetable"]), 0),
            ("Exam duties", len(d["duties"]), 0),
        ])
        pages = self.make_pages(["My courses", "Class routine", "Marks", "Exam routine", "Exam duty"])
        self.courses_page(pages["My courses"])
        self.class_page(pages["Class routine"])
        self.marks_page(pages["Marks"])
        self.exam_page(pages["Exam routine"])
        self.duty_page(pages["Exam duty"])

    def download(self, default_name, builder, msg_label):
        res = ui_kit.save_pdf(self, default_name, builder)
        if res:
            show_msg(msg_label, res[1], res[0])

    # ---------------------------------------------------------------- pages
    def courses_page(self, page):
        d = self.d
        section_head(page, "My courses", "Courses are given by your major: "
                     + (d["info"]["major"] or "-"))
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not d["assign"]:
            self.empty_state(lst, "No course is assigned to you in this semester yet.\n"
                                  "The admin assigns courses to teachers.")
            return
        for a in d["assign"]:
            rows = [t for t in d["timetable"] if t["assignment"] == a["id"]]
            item = Card(lst)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            label(item, fmt_code(a["code"]), 18, True, ON_PRIMARY, fg_color=PRIMARY, corner_radius=12,
                  width=100, height=64).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            label(mid, a["course"], 16, True).pack(anchor="w")
            label(mid, f"Class: {fmt_code(a['klass']) or '-'}   |   Section {a['section']}   |   "
                       f"{a['size']} students", 14, False, MUTED).pack(anchor="w")
            when = "   |   ".join(f"{academic.WEEKDAY_NAMES[r['day']]} {r['start']}-{r['end']} "
                                  f"(Room {r['room']})" for r in rows)
            label(mid, when or "Class time not published yet", 13, True, MUTED, wraplength=620,
                  justify="left").pack(anchor="w", pady=(4, 0))
            chip(item, f"{len(rows)} class/week", "mint").grid(row=0, column=2, padx=18)

    def class_page(self, page):
        d = self.d
        _, right = section_head(page, "Weekly class routine")
        msg = message(page)
        s = d["settings"]
        lines = lambda it: [f"{fmt_code(it['code'])}  Sec {it['section']}", f"Room {it['room']}"]
        if d["timetable"]:
            def build(path):
                pdf_export.class_routine_pdf(
                    path, "My Class Routine",
                    f"{self.title_name}   |   ID {d['info']['code']}   |   "
                    f"{d['sem']['name'] if d['sem'] else ''}", d["timetable"],
                    academic.class_periods(s), academic.class_breaks(s), academic.parse_days(s["class_days"]),
                    lines)

            button(right, "Download PDF", lambda: self.download(
                f"class_routine_{d['info']['code']}.pdf", build, msg), "primary", width=150).pack()
        msg.pack(anchor="w")
        box = scroll(page)
        box.pack(fill="both", expand=True)
        if not d["timetable"]:
            self.empty_state(box, "Your class routine is not published yet.")
            return
        TimetableGrid(box, academic.class_periods(s), academic.parse_days(s["class_days"]), d["timetable"],
                      lines, academic.class_breaks(s)).pack(fill="x", padx=2, pady=2)

    # ----- marks entry -----
    def marks_page(self, page):
        d = self.d
        section_head(page, "Marks entry")
        if not d["assign"] or not d["sem"]:
            self.empty_state(scroll(page), "No course is assigned to you yet, so there are no "
                                           "students to give marks.")
            return
        self.max_marks = float(d["settings"]["max_marks"])
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        self.assign_map = {f"{fmt_code(a['code'])} - {a['course']}  |  Section {a['section']}": a
                           for a in d["assign"]}
        self.pick = combo(top, list(self.assign_map), 430, lambda v: self.load_roster())
        self.pick.pack(side="left")
        label(top, f"Marks out of {self.max_marks:g}", 14, True, MUTED).pack(side="left", padx=14)
        button(top, "Save marks", self.save_marks, "success", width=130).pack(side="right")
        self.marks_msg = message(page)
        self.marks_msg.pack(anchor="w")
        self.roster_box = scroll(page)
        self.roster_box.pack(fill="both", expand=True)
        self.entries = []
        self.pick.set(list(self.assign_map)[0])
        self.load_roster()

    def current_assignment(self):
        return self.assign_map.get(self.pick.get())

    def load_roster(self):
        for w in self.roster_box.winfo_children():
            w.destroy()
        self.entries = []
        self.marks_msg.configure(text="")
        a = self.current_assignment()
        if not a:
            return
        conn = get_connection()
        try:
            roster = academic.marks_roster(conn, self.d["sem"]["id"], a["course_id"], a["section"])
        finally:
            conn.close()
        head = ctk.CTkFrame(self.roster_box, fg_color="transparent")
        head.pack(fill="x", padx=8)
        for text, w in (("Student ID", 110), ("Name", 260), ("Marks", 100), ("Grade", 60)):
            label(head, text, 12, True, MUTED, width=w, anchor="w").pack(side="left", padx=(0, 8))
        for r in roster:
            row = Card(self.roster_box, corner_radius=10)
            row.pack(fill="x", pady=3, padx=4)
            label(row, r["student_id"], 14, True, width=110, anchor="w").pack(side="left", padx=(12, 8), pady=6)
            label(row, r["name"], 14, False, MUTED, width=260, anchor="w").pack(side="left", padx=(0, 8))
            ent = entry(row, placeholder="-", width=100)
            ent.configure(height=32)
            if r["marks"] is not None:
                ent.insert(0, f"{r['marks']:g}")
            ent.pack(side="left", padx=(0, 8))
            grade = label(row, "", 14, True, SUCCESS_FG, width=60, anchor="w")
            grade.pack(side="left")
            ent.bind("<KeyRelease>", lambda e, en=ent, g=grade: self.preview_grade(en, g))
            self.preview_grade(ent, grade)
            self.entries.append((r["student_id"], ent))

    def preview_grade(self, entry_widget, lbl):
        text = entry_widget.get().strip()
        try:
            value = float(text)
            if text == "" or value < 0 or value > self.max_marks:
                raise ValueError
            letter = academic.grade_for(value, self.max_marks)
            lbl.configure(text=letter, text_color=SUCCESS_FG if letter != "F" else ERROR_FG)
        except ValueError:
            lbl.configure(text="")

    def save_marks(self):
        a = self.current_assignment()
        if not a:
            return
        conn = get_connection()
        try:
            ok, msg = academic.save_marks(conn, self.d["sem"]["id"], self.teacher_id, a["id"],
                                          [(sid, e.get()) for sid, e in self.entries], self.max_marks)
        finally:
            conn.close()
        show_msg(self.marks_msg, msg, ok)

    # ----- exam routine of my sections -----
    def exam_page(self, page):
        d = self.d
        section_head(page, "Exam routine of my sections")
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not d["assign"]:
            self.empty_state(lst, "No course is assigned to you yet.")
            return
        for a in d["assign"]:
            card = Card(lst)
            card.pack(fill="x", pady=6)
            label(card, f"{fmt_code(a['code'])}  -  {a['course']}   (Section {a['section']})", 16, True).pack(
                anchor="w", padx=18, pady=(14, 4))
            rows = d["exam_rooms"].get(a["id"], [])
            if not rows:
                label(card, "Exam routine is not published yet.", 14, False, MUTED).pack(
                    anchor="w", padx=18, pady=(0, 14))
            for r in rows:
                line = ctk.CTkFrame(card, fg_color="transparent")
                line.pack(fill="x", padx=18, pady=(0, 10))
                label(line, r["date"].strftime("%a, %d %b %Y"), 14, True, TEXT, width=160, anchor="w").pack(
                    side="left")
                label(line, f"{r['start']} - {r['end']}", 14, False, MUTED, width=120, anchor="w").pack(
                    side="left")
                chip(line, f"Room {r['room']}", "primary").pack(side="left", padx=6)
                chip(line, f"Seats {r['first']}-{r['last']}  ({r['students']} students)", "info").pack(
                    side="left", padx=6)

    # ----- invigilation duty -----
    def duty_page(self, page):
        d = self.d
        duties = d["duties"]
        _, right = section_head(page, "Exam duty")
        msg = message(page)
        if duties:
            def build(path):
                pdf_export.duty_pdf(path, self.name, d["info"]["code"], d["info"]["major"], duties)

            button(right, "Download PDF", lambda: self.download(
                f"exam_duty_{d['info']['code']}.pdf", build, msg), "primary", width=150).pack()
        msg.pack(anchor="w")
        lst = scroll(page)
        lst.pack(fill="both", expand=True)
        if not duties:
            self.empty_state(lst, "No exam duty has been assigned to you yet.")
            return
        upcoming = [x["date"] for x in duties if x["date"] >= date.today()]
        next_date = min(upcoming) if upcoming else None
        for x in duties:
            status = status_for(x["date"], next_date)
            done = status == "DONE"
            item = Card(lst)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            date_block(item, x["date"], done).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            top = ctk.CTkFrame(mid, fg_color="transparent")
            top.pack(anchor="w")
            label(top, fmt_code(x["code"]), 20, True, MUTED if done else TEXT).pack(side="left")
            if status:
                chip(top, status, "success" if status == "NEXT" else "muted").pack(side="left", padx=10)
            label(mid, x["course"], 14, False, MUTED).pack(anchor="w")
            label(mid, f"{x['start']} - {x['end']}     With: {x['partners']}", 14, True).pack(
                anchor="w", pady=(4, 0))
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            chip(right, f"Room {x['building']}-{x['room']}", "primary").pack(pady=3, anchor="e")
            chip(right, f"{x['students']} students", "info").pack(pady=3, anchor="e")

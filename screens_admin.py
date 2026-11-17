"""Admin panel: routine tools (with the full exam routine and PDF), semesters (calendar),
teacher courses, time settings (HH:MM, breaks), class routine (with PDF) and teacher IDs."""
import contextlib
import gc
import json
import queue
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import academic
import pdf_export
import queries
import ui_kit
from db import get_connection
from textfmt import fmt_code, raw_code
from ui_kit import (BG, BORDER, DONE, ERROR_FG, MUTED, SUCCESS_FG, TEXT, Card, DataTable, DateField,
                    Dashboard, QueueWriter, TimetableGrid, button, chip, combo, entry, label, message,
                    scroll, section_head, show_msg, stat_card)
import ui_kit as K


class AdminFrame(Dashboard):
    def __init__(self, app):
        super().__init__(app, "Admin", "Administrator")
        self.q = queue.Queue()
        self.busy = False
        self.log_target = None
        self.task_buttons = []
        self.stat_boxes = {}
        self.pray_rows = []
        self.header("Admin panel", "Semesters, teachers, time settings, routines and more.")
        self.build_stats()
        pages = self.make_pages(["Routine tools", "Semesters", "Assign courses", "Time settings",
                                 "Class routine", "Teacher IDs"])
        self.build_tools(pages["Routine tools"])
        self.build_semesters(pages["Semesters"])
        self.build_assign(pages["Assign courses"])
        self.build_settings(pages["Time settings"])
        self.build_class_routine(pages["Class routine"])
        self.build_teachers(pages["Teacher IDs"])
        self.refresh_all()
        self.after(100, self.poll)

    # ------------------------------------------------------------ top stats
    def build_stats(self):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(12, 6))
        spec = (("students", "Students"), ("courses", "Courses"), ("teachers", "Teachers"),
                ("rooms", "Rooms"), ("exams", "Exams"), ("duties", "Duties"))
        tones = (K.PRIMARY, K.SECONDARY, K.INFO_FG, K.WARNING_FG, K.SUCCESS_FG, K.ERROR_FG)
        for i, ((key, title), tone) in enumerate(zip(spec, tones)):
            row.grid_columnconfigure(i, weight=1, uniform="adm")
            box = stat_card(row, title, "0", tone)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            self.stat_boxes[key] = box

    def refresh_all(self):
        try:
            conn = get_connection()
        except Exception:
            return
        try:
            data = queries.counts(conn)
        finally:
            conn.close()
        for key, box in self.stat_boxes.items():
            box.value_label.configure(text=str(data.get(key, 0)))
        self.fill_teachers()
        self.refresh_semesters()
        self.reload_lookup()
        self.refresh_assignments()
        self.reload_preview_boxes()
        self.refresh_exam_table()

    # ----------------------------------------------------- background tasks
    def make_log(self, parent, text):
        box = ctk.CTkTextbox(parent, fg_color=BG, text_color=TEXT, corner_radius=12, border_width=1,
                             border_color=BORDER, font=ctk.CTkFont(family="Courier", size=12), wrap="none")
        box.insert("end", text + "\n")
        box.configure(state="disabled")
        return box

    def log(self, text, box=None):
        box = box or self.log_target
        if box is None:
            return
        box.configure(state="normal")
        box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")

    def poll(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                item = self.q.get_nowait()
                if item is DONE:
                    gc.enable()                    # was paused while the background task ran
                    self.busy = False
                    for b in self.task_buttons:
                        b.configure(state="normal")
                    self.refresh_all()
                    if getattr(self, "after_task", None):
                        self.after_task()
                        self.after_task = None
                else:
                    self.log(item)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def run_task(self, title, fn, log_box, after=None):
        if self.busy:
            return
        self.busy = True
        self.after_task = after
        self.log_target = log_box
        for b in self.task_buttons:
            b.configure(state="disabled")
        self.log(f"\n>>> {title}\n")
        gc.disable()   # Tk objects must not be cleaned up from the worker thread (it can freeze)

        def work():
            try:
                with contextlib.redirect_stdout(QueueWriter(self.q)):
                    fn()
            except Exception as e:
                traceback.print_exc()
                self.q.put(f"\nERROR: {e}\n")
            self.q.put(DONE)

        threading.Thread(target=work, daemon=True).start()

    def download(self, default_name, builder, msg_label):
        res = ui_kit.save_pdf(self, default_name, builder)
        if res:
            show_msg(msg_label, res[1], res[0])

    # ======================================================== Routine tools
    def build_tools(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="t", minsize=270)
        tab.grid_columnconfigure(1, weight=5, uniform="t")
        tab.grid_rowconfigure(0, weight=1)
        left = scroll(tab)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        label(left, "Step 1: Import CSV data", 18, True).pack(anchor="w")
        label(left, "Folder with the students, enrollments, courses, teachers and rooms CSV files.",
              13, False, MUTED, wraplength=225, justify="left").pack(anchor="w", pady=(0, 6))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x")
        self.folder_entry = entry(row, str(Path(__file__).parent / "data"))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        button(row, "Browse", self.browse, "secondary", width=80).pack(side="left", padx=(8, 0))
        self.clear_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left, text="Delete old data first", variable=self.clear_var,
                        font=K.font(13), text_color=MUTED, fg_color=K.PRIMARY, hover_color=K.PRIMARY_HOVER,
                        border_color=BORDER, checkmark_color=K.ON_PRIMARY, checkbox_width=18,
                        checkbox_height=18).pack(anchor="w", pady=(10, 0))
        self.import_btn = button(left, "Import data", self.on_import, "primary", height=42)
        self.import_btn.pack(fill="x", pady=(10, 22))

        label(left, "Step 2: Exam routine", 18, True).pack(anchor="w")
        label(left, "First possible exam date. Exam time and exam days come from Time settings.",
              13, False, MUTED, wraplength=225, justify="left").pack(anchor="w", pady=(0, 6))
        self.exam_start = DateField(left, "Select first exam date", width=260)
        self.exam_start.pack(fill="x")
        from datetime import date
        self.exam_start.set(date.today())
        self.gen_btn = button(left, "Generate exam routine", self.on_generate, "success", height=42)
        self.gen_btn.pack(fill="x", pady=(10, 0))
        self.task_buttons += [self.import_btn, self.gen_btn]

        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.pack(fill="x")
        self.view_log_btn = button(head, "Activity log", lambda: self.show_tools_view("log"), "primary",
                                   width=120, height=34)
        self.view_log_btn.pack(side="left")
        self.view_exam_btn = button(head, "Exam routine", lambda: self.show_tools_view("exam"), "secondary",
                                    width=130, height=34)
        self.view_exam_btn.pack(side="left", padx=8)
        self.exam_pdf_btn = button(head, "Download PDF", self.on_exam_pdf, "primary", width=140, height=34)
        self.exam_pdf_btn.pack(side="right")
        self.exam_msg = message(right)
        self.exam_msg.pack(anchor="w", pady=(4, 0))
        self.tools_log = self.make_log(right, "Ready. Step 1: import data, then Step 2: generate the "
                                              "exam routine.")
        self.exam_table = DataTable(right, [
            ("date", "Date", 120, "w"), ("time", "Time", 100, "w"), ("course", "Course", 70, "w"),
            ("room", "Room", 66, "w"), ("seats", "Seats", 66, "w"), ("students", "Students", 80, "e"),
            ("teachers", "Teachers", 420, "w")], height=14)
        self.show_tools_view("log")

    def show_tools_view(self, which):
        self.tools_log.pack_forget()
        self.exam_table.pack_forget()
        if which == "log":
            self.tools_log.pack(fill="both", expand=True, pady=(6, 0))
            self.view_log_btn.configure(fg_color=K.PRIMARY, text_color=K.ON_PRIMARY)
            self.view_exam_btn.configure(fg_color=K.SIDEBAR, text_color=TEXT)
        else:
            self.exam_table.pack(fill="both", expand=True, pady=(6, 0))
            self.view_exam_btn.configure(fg_color=K.PRIMARY, text_color=K.ON_PRIMARY)
            self.view_log_btn.configure(fg_color=K.SIDEBAR, text_color=TEXT)

    def refresh_exam_table(self):
        conn = get_connection()
        try:
            self.exam_rows = academic.exam_routine_rows(conn)
        finally:
            conn.close()
        self.exam_table.set_rows([
            (i, [r["date"].strftime("%a, %d %b %Y"), f"{r['start']} - {r['end']}", fmt_code(r["code"]),
                 r["room"], f"{r['first']} - {r['last']}", r["students"], r["teachers"]])
            for i, r in enumerate(self.exam_rows)])
        self.exam_pdf_btn.configure(state="normal" if self.exam_rows else "disabled")

    def on_exam_pdf(self):
        rows = self.exam_rows
        if not rows:
            show_msg(self.exam_msg, "No exam routine yet. Generate it first.", False)
            return
        sem = self.active_sem()
        sub = (academic.semester_text(sem) + "   |   " if sem else "") + f"{len(rows)} room allotments"
        self.download("exam_routine.pdf", lambda p: pdf_export.exam_routine_pdf(p, rows, sub), self.exam_msg)

    def browse(self):
        folder = filedialog.askdirectory(title="Choose the folder with the CSV files")
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def on_import(self):
        folder = self.folder_entry.get().strip()
        clear = self.clear_var.get()

        def task():
            import import_csv
            import run_all
            import_csv.DATA = Path(folder)
            data, errors = import_csv.validate()
            if errors:
                print(f"{len(errors)} error(s) found. Nothing was saved:")
                for e in errors:
                    print(" -", e)
                return
            print("CSV files are OK. Saving to MySQL...")
            conn = get_connection(with_database=False)
            try:
                run_all.run_schema(conn)
                if clear:
                    import_csv.clear_all(conn)
                    print("Old data removed.")
                import_csv.save(conn, data)
            finally:
                conn.close()
            print("Import finished.")

        self.show_tools_view("log")
        self.run_task("Import CSV data", task, self.tools_log)

    def on_generate(self):
        start = self.exam_start.value
        if not start:
            self.show_tools_view("log")
            self.log("\nERROR: choose the first exam date\n", self.tools_log)
            return

        def task():
            import allocate_rooms
            import assign_teachers
            import scheduler
            conn = get_connection()
            try:
                st = academic.get_settings(conn)
                academic.apply_exam_slots(conn, st)
            finally:
                conn.close()
            scheduler.START_DATE = start
            scheduler.EXAM_WEEKDAYS = set(academic.parse_days(st["exam_days"]))
            print("Step 1 of 3: scheduling exams")
            scheduler.main()
            print("\nStep 2 of 3: allocating rooms and seats")
            allocate_rooms.main()
            print("\nStep 3 of 3: assigning teachers")
            assign_teachers.main()
            print("\nAll done. The full exam routine is shown in the 'Exam routine' view.")

        self.show_tools_view("log")
        self.run_task("Generate exam routine", task, self.tools_log,
                      after=lambda: self.show_tools_view("exam"))

    # ============================================================= Semesters
    def build_semesters(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="s", minsize=300)
        tab.grid_columnconfigure(1, weight=3, uniform="s")
        tab.grid_rowconfigure(0, weight=1)
        left = Card(tab)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        label(left, "New semester", 20, True).pack(anchor="w", padx=20, pady=(18, 0))
        label(left, "Name and duration (date, month, year).", 13, False, MUTED).pack(anchor="w", padx=20)
        label(left, "SEMESTER NAME", 11, True, MUTED).pack(anchor="w", padx=20, pady=(14, 0))
        self.sem_name = entry(left, placeholder="Spring 2026")
        self.sem_name.pack(fill="x", padx=20, pady=(2, 8))
        label(left, "START DATE", 11, True, MUTED).pack(anchor="w", padx=20)
        self.sem_start = DateField(left, "Select start date")
        self.sem_start.pack(fill="x", padx=20, pady=(2, 8))
        label(left, "END DATE", 11, True, MUTED).pack(anchor="w", padx=20)
        self.sem_end = DateField(left, "Select end date")
        self.sem_end.pack(fill="x", padx=20, pady=(2, 12))
        button(left, "Create semester", self.on_create_semester, "primary", height=42).pack(
            fill="x", padx=20)
        self.sem_msg = message(left, wraplength=300, justify="left")
        self.sem_msg.pack(anchor="w", padx=20, pady=10)
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        section_head(right, "Semesters")
        self.sem_list = scroll(right)
        self.sem_list.pack(fill="both", expand=True)

    def on_create_semester(self):
        conn = get_connection()
        try:
            ok, msg = academic.create_semester(conn, self.sem_name.get(), self.sem_start.get(),
                                               self.sem_end.get())
        finally:
            conn.close()
        show_msg(self.sem_msg, msg, ok)
        if ok:
            self.sem_name.delete(0, "end")
            self.sem_start.set(None)
            self.sem_end.set(None)
            self.refresh_semesters()
            self.refresh_assignments()

    def refresh_semesters(self):
        for w in self.sem_list.winfo_children():
            w.destroy()
        conn = get_connection()
        try:
            sems = academic.list_semesters(conn)
        finally:
            conn.close()
        if not sems:
            label(self.sem_list, "No semester yet. Create the first one on the left.", 14, False, MUTED).pack(
                pady=30)
        for s in sems:
            row = Card(self.sem_list, corner_radius=12)
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
            mid = ctk.CTkFrame(row, fg_color="transparent")
            mid.grid(row=0, column=0, sticky="w", padx=16, pady=12)
            label(mid, s["name"], 16, True).pack(anchor="w")
            label(mid, f"{s['start'].strftime('%d %b %Y')}  to  {s['end'].strftime('%d %b %Y')}", 13,
                  False, MUTED).pack(anchor="w")
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.grid(row=0, column=1, padx=12)
            if s["active"]:
                chip(right, "ACTIVE", "success").pack(side="left", padx=4)
            else:
                button(right, "Set active", lambda i=s["id"]: self.set_active(i), "primary", width=100,
                       height=32).pack(side="left", padx=4)
            button(right, "Delete", lambda i=s["id"], n=s["name"]: self.delete_semester(i, n), "danger",
                   width=80, height=32).pack(side="left", padx=4)

    def set_active(self, sid):
        conn = get_connection()
        try:
            academic.set_active_semester(conn, sid)
        finally:
            conn.close()
        self.refresh_semesters()
        self.refresh_assignments()

    def delete_semester(self, sid, name):
        if not messagebox.askyesno("Delete semester",
                                   f"Delete '{name}' with its teacher courses, class routine and "
                                   f"marks?\nThis cannot be undone."):
            return
        conn = get_connection()
        try:
            academic.delete_semester(conn, sid)
        finally:
            conn.close()
        self.refresh_semesters()
        self.refresh_assignments()

    # ======================================================= Assign courses
    def build_assign(self, tab):
        self.assign_info = label(tab, "", 14, True, MUTED)
        self.assign_info.pack(anchor="w", pady=(0, 6))
        form = ctk.CTkFrame(tab, fg_color="transparent")
        form.pack(fill="x")
        self.course_combo = combo(form, [], 270, lambda v: self.on_course_pick())
        self.course_combo.pack(side="left", padx=(0, 8))
        self.section_combo = combo(form, [], 175)
        self.section_combo.pack(side="left", padx=(0, 8))
        self.teacher_combo = combo(form, [], 300)
        self.teacher_combo.pack(side="left", padx=(0, 8))
        button(form, "Assign", self.on_assign, "success", width=90).pack(side="left")
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", pady=8)
        button(row2, "Auto-assign all unassigned", self.on_auto_assign, "primary", height=36).pack(side="left")
        button(row2, "Remove selected", self.on_remove_selected, "secondary", height=36).pack(
            side="left", padx=8)
        button(row2, "Clear all", self.on_clear_assign, "danger", width=90, height=36).pack(side="left")
        self.assign_search = entry(row2, placeholder="Search teacher, course, section or major", width=300)
        self.assign_search.pack(side="right")
        self.assign_search.bind("<KeyRelease>", lambda e: self.refresh_assignments())
        self.assign_msg = message(tab, wraplength=900, justify="left")
        self.assign_msg.pack(anchor="w")
        self.assign_table = DataTable(tab, [
            ("course", "Course", 90, "w"), ("name", "Course name", 220, "w"), ("section", "Section", 70, "w"),
            ("students", "Students", 80, "e"), ("tcode", "Teacher ID", 90, "w"),
            ("teacher", "Teacher", 240, "w"), ("major", "Major", 70, "w")], height=12)
        self.assign_table.pack(fill="both", expand=True, pady=(4, 0))
        self.teacher_map, self.course_map, self.section_map = {}, {}, {}

    def reload_lookup(self):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cur.fetchall()
        finally:
            conn.close()
        self.course_map = {f"{fmt_code(c[1])} - {c[2]}": c[0] for c in courses}
        self.course_combo.configure(values=list(self.course_map) or [""])
        self.course_combo.set(next(iter(self.course_map), "Choose course"))
        self.on_course_pick()

    def on_course_pick(self):
        cid = self.course_map.get(self.course_combo.get())
        self.section_map, self.teacher_map = {}, {}
        note = ""
        if cid:
            conn = get_connection()
            try:
                secs = academic.sections_for_course(conn, cid)
                teachers, matched = academic.teachers_for_course(conn, cid)
            finally:
                conn.close()
            self.section_map = {f"Section {sec} ({n} students)": sec for sec, n in secs}
            self.teacher_map = {f"{t[1]} - {t[2]} ({t[3] or '-'})": t[0] for t in teachers}
            if not matched:
                note = "No teacher has the matching major for this course, so all teachers are listed."
        self.section_combo.configure(values=list(self.section_map) or [""])
        self.section_combo.set(next(iter(self.section_map), "Section"))
        self.teacher_combo.configure(values=list(self.teacher_map) or [""])
        self.teacher_combo.set(next(iter(self.teacher_map), "Choose teacher"))
        if note:
            show_msg(self.assign_msg, note, False)

    def active_sem(self):
        conn = get_connection()
        try:
            return academic.active_semester(conn)
        finally:
            conn.close()

    def on_assign(self):
        sem = self.active_sem()
        tid = self.teacher_map.get(self.teacher_combo.get())
        cid = self.course_map.get(self.course_combo.get())
        sec = self.section_map.get(self.section_combo.get())
        if not sem:
            show_msg(self.assign_msg, "Create and activate a semester first.", False)
            return
        if not (tid and cid and sec):
            show_msg(self.assign_msg, "Choose a course, a section and a teacher.", False)
            return
        conn = get_connection()
        try:
            academic.add_assignment(conn, sem["id"], tid, cid, sec)
        finally:
            conn.close()
        show_msg(self.assign_msg, "Assigned. Generate the class routine again to update times.")
        self.refresh_assignments()

    def on_auto_assign(self):
        sem = self.active_sem()
        if not sem:
            show_msg(self.assign_msg, "Create and activate a semester first.", False)
            return
        conn = get_connection()
        try:
            n, unmatched = academic.auto_assign(conn, sem["id"])
        finally:
            conn.close()
        text = f"Assigned {n} course section(s). Every teacher got courses of their own major."
        if unmatched:
            text += f" {unmatched} had no teacher with the matching major, so any teacher was used."
        show_msg(self.assign_msg, text, unmatched == 0)
        self.refresh_assignments()

    def on_remove_selected(self):
        ids = self.assign_table.selected()
        if not ids:
            show_msg(self.assign_msg, "Select one or more rows in the table first.", False)
            return
        conn = get_connection()
        try:
            for i in ids:
                academic.remove_assignment(conn, int(i))
        finally:
            conn.close()
        show_msg(self.assign_msg, f"Removed {len(ids)} assignment(s).")
        self.refresh_assignments()

    def on_clear_assign(self):
        sem = self.active_sem()
        if not sem or not messagebox.askyesno("Clear", "Remove ALL teacher course assignments of "
                                                       "this semester?"):
            return
        conn = get_connection()
        try:
            academic.clear_assignments(conn, sem["id"])
        finally:
            conn.close()
        show_msg(self.assign_msg, "All assignments removed.")
        self.refresh_assignments()

    def refresh_assignments(self):
        conn = get_connection()
        try:
            sem = academic.active_semester(conn)
            rows = academic.list_assignments(conn, sem["id"], self.assign_search.get()) if sem else []
        finally:
            conn.close()
        self.assign_info.configure(
            text=(f"Active semester: {academic.semester_text(sem)}      |      {len(rows)} course sections")
            if sem else "No active semester. Create one in the Semesters tab.")
        self.assign_table.set_rows([
            (r["id"], [fmt_code(r["code"]), r["course"], r["section"], r["size"], r["teacher_code"],
                       r["teacher"], r["major"]]) for r in rows])

    # ========================================================= Time settings
    def build_settings(self, tab):
        box = scroll(tab)
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(0, weight=1, uniform="c")
        box.grid_columnconfigure(1, weight=1, uniform="c")
        self.set_entries, self.day_vars = {}, {}
        s = self.current_settings()

        def card(col, title, subtitle):
            c = Card(box)
            c.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)
            label(c, title, 20, True).pack(anchor="w", padx=18, pady=(16, 0))
            label(c, subtitle, 13, False, MUTED).pack(anchor="w", padx=18, pady=(0, 8))
            return c

        def field(c, key, text, hint, convert=None):
            label(c, text, 11, True, MUTED).pack(anchor="w", padx=18)
            e = entry(c, convert(s[key]) if convert else s[key], hint)
            e.pack(fill="x", padx=18, pady=(2, 8))
            self.set_entries[key] = e

        def days(c, kind, title):
            label(c, title, 11, True, MUTED).pack(anchor="w", padx=18, pady=(4, 2))
            grid = ctk.CTkFrame(c, fg_color="transparent")
            grid.pack(fill="x", padx=14, pady=(0, 14))
            chosen = academic.parse_days(s[kind + "_days"])
            for i, d in enumerate(academic.WEEK_ORDER):        # Sunday ... Saturday, all 7 days
                var = ctk.BooleanVar(value=d in chosen)
                self.day_vars[(kind, d)] = var
                ctk.CTkCheckBox(grid, text=K.FULL_DAYS[d], variable=var, width=110, font=K.font(13),
                                text_color=TEXT, fg_color=K.PRIMARY, hover_color=K.PRIMARY_HOVER,
                                border_color=BORDER, checkmark_color=K.ON_PRIMARY, checkbox_width=18,
                                checkbox_height=18).grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="w")

        ex = card(0, "Exam time", "Set by the admin. The exam routine follows this.")
        field(ex, "exam_start", "FIRST EXAM STARTS AT (HH:MM)", "09:00")
        field(ex, "exam_duration", "EXAM DURATION (HH:MM)", "02:00", academic.to_hhmm)
        field(ex, "exam_gap", "GAP BETWEEN EXAMS (HH:MM)", "00:30", academic.to_hhmm)
        field(ex, "exam_slots", "EXAM TIME SLOTS PER DAY", "4")
        days(ex, "exam", "EXAM DAYS")

        cl = card(1, "Class time", "Set by the admin. The class routine follows this.")
        field(cl, "class_start", "FIRST CLASS STARTS AT (HH:MM)", "08:30")
        field(cl, "class_duration", "CLASS DURATION (HH:MM)", "00:45", academic.to_hhmm)
        field(cl, "class_gap", "GAP BETWEEN CLASSES (HH:MM)", "00:05", academic.to_hhmm)
        field(cl, "class_periods", "CLASS PERIODS PER DAY", "6")
        field(cl, "classes_per_week", "CLASSES PER WEEK FOR EACH COURSE", "2")
        field(cl, "max_marks", "TOTAL MARKS FOR MARKS ENTRY", "100")
        days(cl, "class", "CLASS DAYS")

        # ---- breaks
        br = Card(box)
        br.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=8)
        label(br, "Breaks in the class day", 20, True).pack(anchor="w", padx=18, pady=(16, 0))
        label(br, "Start time and length, both HH:MM. Leave the start empty to skip a break. "
                  "Classes are placed around the breaks.", 13, False, MUTED, wraplength=900,
              justify="left").pack(anchor="w", padx=18, pady=(0, 8))
        items = {}
        try:
            for it in json.loads(s["class_breaks"]):
                items[it["name"]] = it
        except ValueError:
            pass
        self.break_entries = {}
        for name in ("Snacks break", "Lunch break"):
            row = ctk.CTkFrame(br, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=3)
            label(row, name, 14, True, width=140, anchor="w").pack(side="left")
            label(row, "Start", 12, False, MUTED).pack(side="left", padx=(8, 4))
            a = entry(row, items.get(name, {}).get("start", ""), "HH:MM", width=90)
            a.pack(side="left")
            label(row, "Length", 12, False, MUTED).pack(side="left", padx=(12, 4))
            b = entry(row, academic.to_hhmm(items[name]["dur"]) if name in items else "", "HH:MM", width=90)
            b.pack(side="left")
            self.break_entries[name] = (a, b)
        label(br, "PRAYER BREAKS (up to 5)", 11, True, MUTED).pack(anchor="w", padx=18, pady=(10, 2))
        self.pray_box = ctk.CTkFrame(br, fg_color="transparent", width=1, height=1)
        self.pray_box.pack(fill="x", padx=18)
        self.pray_add_btn = button(br, "Add prayer break", self.add_prayer, "secondary", width=170, height=34)
        self.pray_add_btn.pack(anchor="w", padx=18, pady=(8, 16))       # made first: add_prayer needs it
        for it in items.values():
            if it["name"].startswith("Prayer"):
                self.add_prayer(it["start"], academic.to_hhmm(it["dur"]))
        self.update_pray_button()

        bottom = ctk.CTkFrame(box, fg_color="transparent")
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        button(bottom, "Save settings", self.on_save_settings, "success", width=200, height=42).pack(anchor="w")
        self.settings_msg = message(bottom, wraplength=900, justify="left")
        self.settings_msg.pack(anchor="w", pady=(8, 0))
        self.settings_preview = label(bottom, "", 13, False, MUTED, wraplength=900, justify="left")
        self.settings_preview.pack(anchor="w", pady=(4, 0))
        self.show_preview(s)

    def add_prayer(self, start="", length=""):
        if len(self.pray_rows) >= 5:
            return
        row = ctk.CTkFrame(self.pray_box, fg_color="transparent")
        row.pack(fill="x", pady=3)
        n = len(self.pray_rows) + 1
        lab = label(row, f"Prayer {n}", 14, True, width=80, anchor="w")
        lab.pack(side="left")
        label(row, "Start", 12, False, MUTED).pack(side="left", padx=(8, 4))
        a = entry(row, start, "HH:MM", width=90)
        a.pack(side="left")
        label(row, "Length", 12, False, MUTED).pack(side="left", padx=(12, 4))
        b = entry(row, length or "00:15", "HH:MM", width=90)
        b.pack(side="left")
        rec = (row, a, b)
        button(row, "Remove", lambda r=rec: self.remove_prayer(r), "danger", width=80, height=32).pack(
            side="left", padx=12)
        self.pray_rows.append(rec)
        self.update_pray_button()

    def remove_prayer(self, rec):
        rec[0].destroy()
        self.pray_rows.remove(rec)
        self.update_pray_button()

    def update_pray_button(self):
        if not hasattr(self, "pray_add_btn"):
            return
        left = 5 - len(self.pray_rows)
        self.pray_add_btn.configure(state="normal" if left else "disabled",
                                    text=f"Add prayer break ({left} left)" if left else "Maximum 5 reached")

    def current_settings(self):
        conn = get_connection()
        try:
            return academic.get_settings(conn)
        finally:
            conn.close()

    def show_preview(self, s):
        try:
            ex = " | ".join(f"{a}-{b}" for _, a, b in academic.make_periods(
                s["exam_start"], s["exam_duration"], s["exam_gap"], s["exam_slots"]))
            cl = " | ".join(f"{a}-{b}" for _, a, b in academic.class_periods(s))
            br = " | ".join(f"{n} {a}-{b}" for n, a, b in academic.class_breaks(s)) or "none"
            self.settings_preview.configure(
                text=f"Exam slots: {ex}\nClass periods: {cl}\nBreaks: {br}")
        except (ValueError, KeyError):
            pass

    def on_save_settings(self):
        vals = {k: e.get().strip() for k, e in self.set_entries.items()}
        for kind in ("exam", "class"):
            chosen = [d for d in academic.WEEK_ORDER if self.day_vars[(kind, d)].get()]
            vals[kind + "_days"] = ",".join(str(d) for d in chosen)
        try:
            for key in ("exam_slots", "class_periods", "classes_per_week"):
                if int(vals[key]) <= 0:
                    raise ValueError(f"{key.replace('_', ' ')} must be a positive number")
            for key in ("exam_duration", "class_duration"):
                vals[key] = academic.fmt_hhmm(academic.parse_duration(vals[key]))
                if academic.parse_duration(vals[key]) <= 0:
                    raise ValueError(f"{key.replace('_', ' ')} must be more than 00:00")
            for key in ("exam_gap", "class_gap"):
                vals[key] = academic.fmt_hhmm(academic.parse_duration(vals[key]))
            if float(vals["max_marks"]) <= 0:
                raise ValueError("total marks must be positive")
            if not vals["exam_days"] or not vals["class_days"]:
                raise ValueError("choose at least one exam day and one class day")
            snacks, lunch = self.break_entries["Snacks break"], self.break_entries["Lunch break"]
            breaks = academic.build_breaks(
                snacks[0].get(), snacks[1].get(), lunch[0].get(), lunch[1].get(),
                [(a.get(), b.get()) for _, a, b in self.pray_rows])
            vals["class_breaks"] = json.dumps(breaks)
            academic.make_periods(vals["exam_start"], vals["exam_duration"], vals["exam_gap"],
                                  vals["exam_slots"])
            academic.class_periods(vals)
        except (ValueError, KeyError) as e:
            show_msg(self.settings_msg, f"Please check: {e}", False)
            return
        conn = get_connection()
        try:
            academic.set_settings(conn, vals)
            _, cleared = academic.apply_exam_slots(conn, academic.get_settings(conn))
        finally:
            conn.close()
        msg = "Settings saved. Generate the exam routine and the class routine again to use them."
        if cleared:
            msg += " (The old exam routine was removed because exam slots were reduced.)"
        show_msg(self.settings_msg, msg)
        self.show_preview(vals)

    # ======================================================== Class routine
    def build_class_routine(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="r", minsize=250)
        tab.grid_columnconfigure(1, weight=6, uniform="r")
        tab.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        label(left, "Generate class routine", 18, True).pack(anchor="w")
        label(left, "Uses the active semester, teacher courses, class time, breaks and rooms. "
                    "No teacher, student or room clash.", 13, False, MUTED, wraplength=250,
              justify="left").pack(anchor="w", pady=(0, 8))
        self.class_btn = button(left, "Generate class routine", self.on_class_routine, "success", height=42)
        self.class_btn.pack(fill="x")
        self.task_buttons.append(self.class_btn)
        self.class_log = self.make_log(left, "Ready.")
        self.class_log.pack(fill="both", expand=True, pady=(10, 0))

        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        _, bar = section_head(right, "Show a section")
        row = ctk.CTkFrame(right, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        self.pv_class = combo(row, [], 150, lambda v: self.on_pv_class())
        self.pv_class.pack(side="left")
        self.pv_section = combo(row, [], 130)
        self.pv_section.pack(side="left", padx=8)
        button(row, "Show", self.show_preview_grid, "primary", width=90).pack(side="left")
        self.pv_pdf = button(row, "Download PDF", self.on_class_pdf, "primary", width=150)
        self.pv_pdf.pack(side="right")
        self.pv_msg = message(right)
        self.pv_msg.pack(anchor="w")
        self.pv_area = scroll(right)
        self.pv_area.pack(fill="both", expand=True)
        self.pv_data, self.pv_items = {}, []

    def on_class_routine(self):
        import class_scheduler

        def task():
            conn = get_connection()
            try:
                sem = academic.active_semester(conn)
                if not sem:
                    print("No active semester. Create one in the Semesters tab.")
                    return
                print("Semester:", academic.semester_text(sem))
                print(class_scheduler.generate(conn, sem["id"])[2])
            finally:
                conn.close()

        self.run_task("Generate class routine", task, self.class_log)

    def reload_preview_boxes(self):
        conn = get_connection()
        try:
            self.pv_data = academic.class_and_sections(conn)
        finally:
            conn.close()
        names = [fmt_code(k) for k in self.pv_data]
        self.pv_class.configure(values=names or [""])
        self.pv_class.set(names[0] if names else "Class")
        self.on_pv_class()

    def on_pv_class(self):
        secs = self.pv_data.get(raw_code(self.pv_class.get()), [])
        self.pv_section.configure(values=[f"Section {s}" for s in secs] or [""])
        self.pv_section.set(f"Section {secs[0]}" if secs else "Section")

    def show_preview_grid(self):
        for w in self.pv_area.winfo_children():
            w.destroy()
        self.pv_items = []
        conn = get_connection()
        try:
            sem = academic.active_semester(conn)
            if not sem:
                show_msg(self.pv_msg, "No active semester.", False)
                return
            self.pv_class_raw = raw_code(self.pv_class.get())
            self.pv_section_raw = self.pv_section.get().replace("Section ", "")
            items = academic.section_timetable(conn, self.pv_class_raw, self.pv_section_raw, sem["id"])
            self.pv_settings = academic.get_settings(conn)
            self.pv_sem = sem
        finally:
            conn.close()
        if not items:
            show_msg(self.pv_msg, "No class routine for this section yet. Generate it first.", False)
            return
        self.pv_items = items
        show_msg(self.pv_msg, f"{fmt_code(self.pv_class_raw)}  |  Section {self.pv_section_raw}  |  "
                              f"{len(items)} classes per week")
        st = self.pv_settings
        TimetableGrid(self.pv_area, academic.class_periods(st), academic.parse_days(st["class_days"]), items,
                      lambda it: [fmt_code(it["code"]), it["teacher"], f"Room {it['room']}"],
                      academic.class_breaks(st)).pack(fill="x", padx=2)

    def on_class_pdf(self):
        if not self.pv_items:
            show_msg(self.pv_msg, "Choose a class and section and press Show first.", False)
            return
        st, items = self.pv_settings, self.pv_items
        title = f"Class Routine - {fmt_code(self.pv_class_raw)}, Section {self.pv_section_raw}"

        def build(path):
            pdf_export.class_routine_pdf(
                path, title, academic.semester_text(self.pv_sem), items, academic.class_periods(st),
                academic.class_breaks(st), academic.parse_days(st["class_days"]),
                lambda it: [fmt_code(it["code"]), it["teacher"], f"Room {it['room']}"])

        self.download(f"class_routine_{self.pv_class_raw}_{self.pv_section_raw}.pdf", build, self.pv_msg)

    # ============================================================ Teacher IDs
    def build_teachers(self, tab):
        section_head(tab, "Teacher IDs", "The ID is the first letters of the name, like FBI for "
                                         "Ferdaush Bin Islam. Teachers use it to register and login.")
        self.teacher_table = DataTable(tab, [
            ("code", "Teacher ID", 100, "w"), ("name", "Name", 280, "w"), ("major", "Major", 80, "w"),
            ("rank", "Rank", 90, "w"), ("dept", "Department", 140, "w")], height=14)
        self.teacher_table.pack(fill="both", expand=True)

    def fill_teachers(self):
        conn = get_connection()
        try:
            rows = queries.teacher_list(conn)
        finally:
            conn.close()
        self.teacher_table.set_rows([(r[0], [r[1], r[2], r[3], r[4], r[5]]) for r in rows])

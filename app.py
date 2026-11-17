"""Exam Routine System - desktop app (CustomTkinter).

Run:  python app.py
Screens: Login/Register (student, teacher, admin), student dashboard,
         teacher dashboard, admin panel.
"""
import contextlib
import io

import customtkinter as ctk

import academic
import allocate_rooms
import auth
import fonts
import ui_kit
from db import get_connection
from screens_admin import AdminFrame
from screens_student import StudentFrame
from screens_teacher import TeacherFrame
from ui_kit import (BG, BORDER, ERROR_FG, MUTED, ON_PRIMARY, PRIMARY, PRIMARY_HOVER, SIDEBAR, SUCCESS_FG,
                    SURFACE, TEXT, Card, button, chip, entry, font, label)


class Seg(ctk.CTkFrame):
    """Small switch between a few choices (Student / Teacher / Admin, Login / Register)."""

    def __init__(self, parent, values, command, height=36):
        super().__init__(parent, fg_color=SIDEBAR, corner_radius=10)
        self.command, self.buttons, self.value = command, {}, values[0]
        for v in values:
            b = ctk.CTkButton(self, text=v, height=height - 6, corner_radius=8, font=font(13, True),
                              fg_color="transparent", hover_color=BORDER, text_color=TEXT,
                              command=lambda x=v: self.pick(x))
            b.pack(side="left", expand=True, fill="x", padx=3, pady=3)
            self.buttons[v] = b
        self.set(values[0])

    def set(self, value):
        self.value = value
        for v, b in self.buttons.items():
            if v == value:
                b.configure(fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=ON_PRIMARY)
            else:
                b.configure(fg_color="transparent", hover_color=BORDER, text_color=TEXT)

    def pick(self, value):
        self.set(value)
        self.command(value)


# ---------- Login / Register ----------
class LoginFrame(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        self.role = "student"
        self.mode = "Login"
        self.grid_columnconfigure(0, weight=5, uniform="cols")
        self.grid_columnconfigure(1, weight=6, uniform="cols")
        self.grid_rowconfigure(0, weight=1)
        self.build_brand()
        self.build_form()
        self.refresh_labels()

    def build_brand(self):
        brand = ctk.CTkFrame(self, fg_color=PRIMARY, corner_radius=0)
        brand.grid(row=0, column=0, sticky="nsew")
        inner = ctk.CTkFrame(brand, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        label(inner, "EXAM", 52, True, ON_PRIMARY).pack(anchor="w")
        label(inner, "ROUTINE", 52, True, ON_PRIMARY).pack(anchor="w")
        label(inner, "Smart exam and class scheduling\nfor students and teachers.", 16, False,
              ON_PRIMARY, justify="left").pack(anchor="w", pady=(10, 28))
        for line in ("Your class and exam routine in one place",
                     "Teachers enter marks and see their duty",
                     "No clash for any student, teacher or room"):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(anchor="w", pady=5)
            ctk.CTkFrame(row, fg_color=SURFACE, width=10, height=10, corner_radius=5).pack(
                side="left", padx=(0, 12))
            label(row, line, 14, False, ON_PRIMARY).pack(side="left")

    def build_form(self):
        side = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        side.grid(row=0, column=1, sticky="nsew")
        self.mode_switch = ctk.CTkSwitch(side, text="Dark mode", font=font(13), text_color=MUTED,
                                         progress_color=PRIMARY, button_color=ui_kit.SECONDARY,
                                         button_hover_color=PRIMARY_HOVER,
                                         command=lambda: self.app.set_theme(
                                             "dark" if self.mode_switch.get() else "light"))
        if ctk.get_appearance_mode() == "Dark":
            self.mode_switch.select()
        self.mode_switch.place(relx=0.97, y=18, anchor="ne")
        card = Card(side, corner_radius=20, width=420)
        card.place(relx=0.5, rely=0.5, anchor="center")
        pad = dict(padx=34, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        self.title = label(card, "", 28, True)
        self.title.grid(row=0, column=0, padx=34, pady=(30, 0), sticky="w")
        self.subtitle = label(card, "", 13, False, MUTED, wraplength=350, justify="left")
        self.subtitle.grid(row=1, column=0, padx=34, pady=(2, 14), sticky="w")

        self.role_seg = Seg(card, ["Student", "Teacher", "Admin"], self.on_role)
        self.role_seg.grid(row=2, column=0, pady=(0, 8), **pad)
        self.mode_seg = Seg(card, ["Login", "Register"], self.on_mode, height=32)
        self.mode_seg.grid(row=3, column=0, pady=(0, 14), **pad)

        self.id_label = label(card, "", 12, True, MUTED)
        self.id_label.grid(row=4, column=0, padx=34, sticky="w")
        self.id_entry = entry(card)
        self.id_entry.configure(height=44)
        self.id_entry.grid(row=5, column=0, pady=(2, 10), **pad)

        label(card, "Password", 12, True, MUTED).grid(row=6, column=0, padx=34, sticky="w")
        self.pw_entry = entry(card, show="*")
        self.pw_entry.configure(height=44)
        self.pw_entry.grid(row=7, column=0, pady=(2, 10), **pad)

        self.confirm_label = label(card, "Confirm password", 12, True, MUTED)
        self.confirm_label.grid(row=8, column=0, padx=34, sticky="w")
        self.confirm_entry = entry(card, show="*", placeholder="Type the password again")
        self.confirm_entry.configure(height=44)
        self.confirm_entry.grid(row=9, column=0, pady=(2, 10), **pad)

        self.show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(card, text="Show password", variable=self.show_var, command=self.toggle_show,
                        font=font(13), text_color=MUTED, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                        border_color=BORDER, checkmark_color=ON_PRIMARY, checkbox_width=18,
                        checkbox_height=18).grid(row=10, column=0, pady=(0, 14), **pad)

        self.submit = button(card, "", self.on_submit, "primary", height=46)
        self.submit.grid(row=11, column=0, pady=(0, 8), **pad)

        self.message = ctk.CTkLabel(card, text="", font=font(13), wraplength=350, justify="left")
        self.message.grid(row=12, column=0, padx=34, pady=(0, 26), sticky="w")

        for w in (self.id_entry, self.pw_entry, self.confirm_entry):
            w.bind("<Return>", lambda e: self.on_submit())

    # ----- behaviour -----
    def on_role(self, value):
        self.role = value.lower()
        self.set_message("")
        self.refresh_labels()

    def on_mode(self, value):
        self.mode = value
        self.set_message("")
        self.refresh_labels()

    def toggle_show(self):
        ch = "" if self.show_var.get() else "*"
        self.pw_entry.configure(show=ch)
        self.confirm_entry.configure(show=ch)

    def set_message(self, text, good=False):
        self.message.configure(text=text, text_color=SUCCESS_FG if good else ERROR_FG)

    def refresh_labels(self):
        register = self.mode == "Register"
        self.title.configure(text="Create account" if register else "Welcome back")
        hints = {
            "student": "Use your student ID from the university list.",
            "teacher": "Use your teacher ID: the first letters of your name, like FBI for "
                       "Ferdaush Bin Islam.",
            "admin": "First-time setup: choose an admin password." if register
                     else "Login with the admin password.",
        }
        self.subtitle.configure(text=hints[self.role])
        if self.role == "admin":
            self.id_label.grid_remove()
            self.id_entry.grid_remove()
        else:
            self.id_label.grid()
            self.id_entry.grid()
            self.id_label.configure(text="STUDENT ID" if self.role == "student" else "TEACHER ID")
            self.id_entry.configure(placeholder_text="Enter your ID" if self.role == "student"
                                    else "Example: FBI")
        if register:
            self.confirm_label.grid()
            self.confirm_entry.grid()
            self.pw_entry.configure(placeholder_text=f"At least {auth.MIN_PASSWORD_LENGTH} characters")
        else:
            self.confirm_label.grid_remove()
            self.confirm_entry.grid_remove()
            self.pw_entry.configure(placeholder_text="Enter your password")
        self.submit.configure(text="Create account" if register else "Login")

    def on_submit(self):
        user_id = self.id_entry.get().strip()
        pw = self.pw_entry.get()
        confirm = self.confirm_entry.get()
        try:
            conn = get_connection()
        except Exception:
            self.set_message("Cannot connect to MySQL. Start MySQL in XAMPP and try again.")
            return
        try:
            if self.mode == "Register":
                ok, msg = auth.register(conn, self.role, user_id, pw, confirm)
                self.set_message(msg, good=ok)
                if ok:
                    self.mode_seg.set("Login")
                    self.mode = "Login"
                    self.refresh_labels()
                    self.confirm_entry.delete(0, "end")
                    self.pw_entry.delete(0, "end")
                    self.set_message(msg, good=True)
            else:
                ok, msg, name, uid = auth.login(conn, self.role, user_id, pw)
                if ok:
                    self.app.open_dashboard(self.role, uid, name)
                else:
                    self.set_message(msg)
        finally:
            conn.close()


# ---------- Error screen ----------
class ErrorFrame(ctk.CTkFrame):
    def __init__(self, app, message):
        super().__init__(app, fg_color=BG, corner_radius=0)
        box = Card(self, corner_radius=20)
        box.place(relx=0.5, rely=0.5, anchor="center")
        label(box, "Cannot connect to MySQL", 24, True, ERROR_FG).pack(padx=50, pady=(34, 6))
        label(box, "1. Open XAMPP Control Panel and Start MySQL\n2. Check the password in config.py\n"
                   "3. Press Retry", 14, False, MUTED, justify="left").pack(padx=50, pady=6)
        label(box, message[:200], 11, False, MUTED, wraplength=420).pack(padx=50, pady=6)
        button(box, "Retry", app.start, "primary", width=160, height=42).pack(pady=(10, 34))


# ---------- Main window ----------
class App(ctk.CTk):
    def __init__(self):
        fonts.register_fonts()
        super().__init__()
        self.title("Exam Routine System")
        self.geometry("1180x760")
        self.minsize(1040, 680)
        self.configure(fg_color=BG)
        self.current = None
        self.start()

    def show(self, frame):
        if self.current is not None:
            self.current.destroy()
        self.current = frame
        frame.pack(fill="both", expand=True)

    def set_theme(self, mode):
        ui_kit.set_mode(mode)

    def bootstrap(self):
        """Make sure the database and all tables exist (safe to run every time)."""
        import run_all
        with contextlib.redirect_stdout(io.StringIO()):
            conn = get_connection(with_database=False)
            try:
                run_all.run_schema(conn)
            finally:
                conn.close()
        conn = get_connection()
        try:
            conn.cursor().execute(allocate_rooms.CREATE_SEAT_PLAN)
            auth.ensure_tables(conn)
            academic.ensure_tables(conn)
        finally:
            conn.close()

    def start(self):
        try:
            self.bootstrap()
            self.show(LoginFrame(self))
        except Exception as e:
            self.show(ErrorFrame(self, str(e)))

    def open_dashboard(self, role, user_id, name):
        if role == "student":
            self.show(StudentFrame(self, user_id, name))
        elif role == "teacher":
            self.show(TeacherFrame(self, user_id, name))
        else:
            self.show(AdminFrame(self))

    def logout(self):
        self.show(LoginFrame(self))


if __name__ == "__main__":
    App().mainloop()

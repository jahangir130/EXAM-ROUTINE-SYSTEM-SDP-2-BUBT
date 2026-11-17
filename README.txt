EXAM ROUTINE SYSTEM
===================

1. Start MySQL in XAMPP Control Panel.
2. Install the libraries (once):
       python -m pip install -r requirements.txt
3. Run the app:
       python app.py

Fonts: DM Sans (English) and Hind Siliguri (Bangla) are in the fonts folder and are loaded
by the program itself on Windows. Light mode is the default; use the "Dark mode" switch.

Order of work for the admin (first time):
  1. Admin > Register (set admin password) > Login.
  2. Routine tools:  Import data (choose data/ or demo_school/ folder).
  3. Semesters:      Create a semester (name, start date, end date from the calendar).
  4. Time settings:  Exam time and duration (HH:MM), exam days, class time, class days,
                     classes per week, snacks / lunch / prayer breaks (HH:MM), total marks.
  5. Assign courses: "Auto-assign all unassigned" gives every course section to a teacher
                     whose MAJOR matches the course subject (BAN 10 -> major BAN).
                     You can also assign or remove one by one.
  6. Class routine:  Generate class routine, then choose class + section and Download PDF.
  7. Routine tools:  Generate exam routine. The full routine is shown and can be downloaded as PDF.
  8. Teacher IDs:    Every teacher ID is made from the initials of the name
                     (Ferdaush Bin Islam = FBI, FBI2 if two teachers have the same initials).

Teachers: Teacher > Register (first time only) with the teacher ID (like FBI) and a password.
  My courses, Class routine (PDF), Marks, Exam routine, Exam duty (PDF).
Students: Student > Register (first time only) with the student ID and a password.
  Class routine (PDF), Exam routine (PDF), My courses, Marks.

teachers.csv columns: name, dept, rank_type, major   (major = subject code like BAN, ENG, MAT).
If major is missing, the first 3 letters of dept are used.

If your MySQL has a password, write it in config.py (DB_PASSWORD = "your password").

Data sets included:
  data/         small demo (50 students, 6 courses)
  demo_school/  classes 6 to 10, 10 sections per class, 70 students per section,
                8 subjects per class, 80 junior + 50 senior teachers, 30 rooms
Keep "Delete old data first" ticked when you import a different data set.

Command-line tools (optional): run_all.py, conflict_checker.py, scheduler.py,
allocate_rooms.py, assign_teachers.py, class_scheduler.py

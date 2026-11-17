"""Small text helpers shared by the screens and the PDF files."""
import re

_CODE = re.compile(r"^([A-Za-z]+)\s*(\d+)$")


def fmt_code(code):
    """BAN10 -> 'BAN 10', Class6 -> 'Class 6', CSE101 -> 'CSE 101'. Other text is unchanged."""
    code = str(code or "")
    m = _CODE.match(code.strip())
    return f"{m.group(1)} {m.group(2)}" if m else code


def raw_code(text):
    """'BAN 10' -> 'BAN10' (back to the stored value)."""
    return str(text or "").replace(" ", "")


def has_bengali(text):
    return any("\u0980" <= ch <= "\u09ff" for ch in str(text or ""))


def subject_of(course_code):
    """BAN10 -> 'BAN' (the letters before the class or level number)."""
    m = re.match(r"^([A-Za-z]+)", str(course_code or "").strip())
    return m.group(1).upper() if m else ""

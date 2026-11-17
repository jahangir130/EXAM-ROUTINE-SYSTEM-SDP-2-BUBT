"""Bundled fonts: DM Sans (English) and Hind Siliguri (Bangla).

register_fonts() makes the files in the fonts folder usable by this program only
(Windows). On other systems install the .ttf files once. find_families() tells which
fonts are really available, so the program still works if a font is missing.
"""
import subprocess
import sys
import tkinter.font as tkfont
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"
_FAMILIES = None


def register_fonts():
    files = sorted(FONT_DIR.glob("*.ttf"))
    try:
        if sys.platform.startswith("win"):
            import ctypes
            for f in files:                                   # FR_PRIVATE = only for this program
                ctypes.windll.gdi32.AddFontResourceExW(str(f), 0x10, 0)
        elif sys.platform.startswith("linux"):
            target = Path.home() / ".local" / "share" / "fonts" / "exam-routine"
            if not (target / files[0].name).exists():
                target.mkdir(parents=True, exist_ok=True)
                for f in files:
                    (target / f.name).write_bytes(f.read_bytes())
                subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=30)
    except Exception:
        pass


def find_families():
    """Pick the font names to use (needs the Tk window to exist)."""
    global _FAMILIES
    if _FAMILIES is None:
        have = set(tkfont.families())
        english = "DM Sans" if "DM Sans" in have else ("Segoe UI" if "Segoe UI" in have else "Helvetica")
        semibold = "DM Sans SemiBold" if "DM Sans SemiBold" in have else english
        bangla = next((f for f in ("Hind Siliguri", "Noto Sans Bengali", "Nirmala UI", "Vrinda")
                       if f in have), english)
        bangla_semibold = "Hind Siliguri SemiBold" if "Hind Siliguri SemiBold" in have else bangla
        _FAMILIES = dict(en=english, en_semi=semibold, bn=bangla, bn_semi=bangla_semibold)
    return _FAMILIES

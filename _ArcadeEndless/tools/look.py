"""The Arcade Endless app's look: Age of Darkness colours, the game's own fonts and art (read from the installed
game by game_art, nothing shipped), on ttk's "clam" theme. Without Pillow or the fonts it falls back to plain
fonts and a banner without pictures.

    look.prepare()        before tk.Tk(): sharp text on high-DPI screens, game fonts for this process
    lk = look.Look(root)  styles; lk.px(n) scales pixel sizes; lk.fonts / lk.c hold fonts and colours
    look.Banner(parent, lk, height)   the header: Nightmare horde art, logo, title, credit, install status
"""
import tkinter as tk
from tkinter import ttk

import game_art

UI = "Achilles/Content/UI/"
FONT_FILES = ("Cinzel-Medium", "CormorantSC-Medium", "Jost-Medium", "Jost-SemiBold", "Jost-Bold")
LOGO = UI + "Textures/Logos/Aod_logo_TEX"
BANNER = UI + "Textures/Backgrounds/UI_Background_Nightmares"
TORCH = UI + "Textures/Backgrounds/UI_Background_Loading_TEX"


class C:  # colours: the game's night, Veil green and torch fire
    bg = "#090c0d"
    panel = "#10171a"
    panel2 = "#162125"
    line = "#25373c"
    entry = "#0b1214"
    text = "#d9e1e3"
    muted = "#7a8d92"
    veil = "#45d8a7"
    veil_dark = "#1b6a57"
    veil_hover = "#24886f"
    fire = "#f3b65c"
    blood = "#ec6a57"
    final = "#ffa384"
    surge_bg = "#2a2312"
    death_bg = "#2c1513"
    final_bg = "#45160f"
    stripe = "#131c1f"
    quiet = "#43555a"
    warn = "#ff5b4c"
    danger = "#5a1d18"
    danger_hover = "#7a2820"


_fonts_loaded = False


def prepare():
    """Call before tk.Tk()."""
    global _fonts_loaded
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    _fonts_loaded = all([game_art.load_private_font(UI + "Fonts/" + f) for f in FONT_FILES])


class Look:
    def __init__(self, root):
        self.root = root
        self.c = C
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        serif, sc, sans, semi = (("Cinzel Medium", "Cormorant SC Medium", "Jost Medium", "Jost SemiBold") if _fonts_loaded
                                 else ("Georgia", "Georgia", "Segoe UI", "Segoe UI Semibold"))
        self.fonts = {"title": (serif, 30), "subtitle": (sc, 15), "section": (serif, 12), "tab": (serif, 10),
                      "button": (serif, 10), "body": (sans, 10), "small": (sans, 9), "bold": (semi, 10),
                      "table": (sans, 10), "table_head": (semi, 9), "final": (semi, 10), "status": (semi, 9)}
        self.images = {}
        try:
            self.images = {"logo": game_art.texture(LOGO), "banner": game_art.texture(BANNER), "torch": game_art.texture(TORCH)}
        except Exception:
            pass
        self.style()
        self.icon()
        self.dark_title_bar()

    def px(self, n):
        return int(round(n * self.scale))

    def style(self):
        f, s = self.fonts, ttk.Style(self.root)
        s.theme_use("clam")
        self.root.configure(background=C.bg)
        s.configure(".", background=C.panel, foreground=C.text, fieldbackground=C.entry, bordercolor=C.line,
                    lightcolor=C.panel2, darkcolor=C.panel, troughcolor=C.entry, focuscolor=C.veil, insertcolor=C.text,
                    selectbackground=C.veil_dark, selectforeground="#ffffff", font=f["body"])
        s.configure("TFrame", background=C.panel)
        s.configure("Bar.TFrame", background=C.bg)
        s.configure("TLabel", background=C.panel, foreground=C.text)
        s.configure("Bar.TLabel", background=C.bg, foreground=C.muted, font=f["status"])
        s.configure("Muted.TLabel", foreground=C.muted, font=f["small"])
        s.configure("Section.TLabel", foreground=C.veil, font=f["section"])
        s.configure("Value.TLabel", foreground=C.veil, font=f["bold"])
        s.configure("Notice.TLabel", background=C.bg, foreground=C.veil, font=f["bold"])  # "Installed", on the window background
        s.configure("Summary.TLabel", foreground=C.text, font=f["body"])
        s.configure("TSeparator", background=C.line)

        s.configure("TNotebook", background=C.panel, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=C.panel2, foreground=C.muted, padding=(self.px(14), self.px(6)),
                    font=f["tab"], borderwidth=0, lightcolor=C.panel2, bordercolor=C.line)
        s.map("TNotebook.Tab", background=[("selected", C.panel)], foreground=[("selected", C.veil)],
              lightcolor=[("selected", C.veil)])
        # the two mods' tabs at the top of the window: bigger, on the window background
        s.configure("Mods.TNotebook", background=C.bg, borderwidth=0, tabmargins=(self.px(16), 0, self.px(16), 0))
        s.configure("Mods.TNotebook.Tab", background=C.panel2, foreground=C.muted, padding=(self.px(22), self.px(9)),
                    font=f["section"], borderwidth=0, lightcolor=C.panel2, bordercolor=C.line)
        s.map("Mods.TNotebook.Tab", background=[("selected", C.panel)], foreground=[("selected", C.veil)],
              lightcolor=[("selected", C.veil)])

        s.configure("TButton", background=C.panel2, foreground=C.text, bordercolor=C.line, lightcolor=C.panel2,
                    darkcolor=C.panel2, padding=(self.px(14), self.px(7)), font=f["button"], focusthickness=0)
        s.map("TButton", background=[("pressed", C.line), ("active", C.line)])
        s.configure("Accent.TButton", background=C.veil_dark, foreground="#ffffff", bordercolor=C.veil,
                    lightcolor=C.veil_dark, darkcolor=C.veil_dark, padding=(self.px(20), self.px(9)))
        s.map("Accent.TButton", background=[("pressed", C.veil_hover), ("active", C.veil_hover)])
        s.configure("Danger.TButton", background=C.danger, foreground="#ffd9d3", bordercolor="#8a3328",
                    lightcolor=C.danger, darkcolor=C.danger)
        s.map("Danger.TButton", background=[("pressed", C.danger_hover), ("active", C.danger_hover)])
        s.configure("Small.TButton", padding=(self.px(8), self.px(4)), font=f["small"])

        s.configure("TCheckbutton", background=C.panel, foreground=C.text, indicatorbackground=C.entry,
                    indicatorforeground=C.veil, indicatormargin=(0, 0, self.px(6), 0))
        s.map("TCheckbutton", background=[("active", C.panel)], indicatorbackground=[("selected", C.veil_dark)])
        s.configure("Horizontal.TScale", background=C.veil, troughcolor=C.entry, bordercolor=C.line,
                    lightcolor=C.veil, darkcolor=C.veil_dark, gripcount=0, sliderthickness=self.px(14), troughrelief="flat")
        s.map("Horizontal.TScale", background=[("active", "#7ff0c8")], bordercolor=[("active", C.veil_dark)])
        for w in ("TCombobox", "TSpinbox", "TEntry"):
            s.configure(w, fieldbackground=C.entry, background=C.panel2, foreground=C.text, arrowcolor=C.veil,
                        bordercolor=C.line, lightcolor=C.entry, darkcolor=C.entry, padding=self.px(3))
            s.map(w, fieldbackground=[("disabled", C.panel), ("readonly", C.entry)],
                  foreground=[("disabled", C.quiet), ("readonly", C.text)], arrowcolor=[("disabled", C.line)],
                  bordercolor=[("focus", C.veil_dark)], selectbackground=[("readonly", C.entry)])
        self.root.option_add("*TCombobox*Listbox.background", C.entry)
        self.root.option_add("*TCombobox*Listbox.foreground", C.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", C.veil_dark)
        self.root.option_add("*TCombobox*Listbox.font", f["body"])

        s.configure("Treeview", background=C.panel, fieldbackground=C.panel, foreground=C.text, rowheight=self.px(25),
                    font=f["table"], bordercolor=C.line, lightcolor=C.panel, darkcolor=C.panel)
        s.map("Treeview", background=[("selected", C.veil_dark)], foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=C.panel2, foreground=C.veil, font=f["table_head"], relief="flat",
                    padding=(self.px(4), self.px(7)), bordercolor=C.line, lightcolor=C.panel2, darkcolor=C.panel2)
        s.map("Treeview.Heading", background=[("active", C.line)])
        s.configure("Vertical.TScrollbar", background=C.panel2, troughcolor=C.panel, bordercolor=C.panel,
                    lightcolor=C.panel2, darkcolor=C.panel2, arrowcolor=C.muted, gripcount=0)
        s.map("Vertical.TScrollbar", background=[("active", C.line)])

    def table_tags(self, tree):
        f = self.fonts
        tree.tag_configure("odd", background=C.stripe)
        tree.tag_configure("surge", background=C.surge_bg, foreground=C.fire)
        tree.tag_configure("death", background=C.death_bg, foreground=C.blood)
        tree.tag_configure("final", background=C.final_bg, foreground=C.final, font=f["final"])
        tree.tag_configure("quiet", foreground=C.quiet)

    def dark_title_bar(self, window=None):
        """Windows 10/11: dark title bar on window (default: the main one), coloured like the window where Windows 11
        allows it."""
        window = window or self.root
        try:
            import ctypes
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
            r, g, b = (int(C.bg[i:i + 2], 16) for i in (1, 3, 5))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(r | g << 8 | b << 16)), 4)  # DWMWA_CAPTION_COLOR
        except Exception:
            pass

    def icon(self):
        try:
            from PIL import ImageTk
            torch = self.images["torch"]
            w, h = torch.size
            crop = torch.crop((int(w * 0.36), int(h * 0.18), int(w * 0.64), int(h * 0.46))).resize((64, 64))
            self._icon = ImageTk.PhotoImage(crop)
            self.root.iconphoto(True, self._icon)
        except Exception:
            pass


class Banner(tk.Canvas):
    """Nightmare horde art fading into the window, the game's logo, the mod's title and credit, and the install status."""

    def __init__(self, parent, look, height):
        super().__init__(parent, height=look.px(height), highlightthickness=0, background=C.bg)
        self.look, self.h = look, look.px(height)
        self.status = [("MOD PAK", "not installed", False), ("GAME EXE", "not patched", False)]
        self._img = None
        self._size = None
        self.bind("<Configure>", lambda e: self.redraw())

    def set_status(self, rows):
        """rows: [(label, text, ok)]"""
        self.status = rows
        self.redraw(force=True)

    def picture(self, w, h):
        from PIL import Image, ImageDraw, ImageTk
        src = self.look.images["banner"].convert("RGB")
        scale = max(w / src.width, h / src.height)
        im = src.resize((max(w, int(src.width * scale)), max(h, int(src.height * scale))), Image.LANCZOS)
        top = int((im.height - h) * 0.35)
        im = im.crop((0, top, w, top + h)).convert("RGBA")
        shade = Image.new("RGBA", (w, h))
        d = ImageDraw.Draw(shade)
        bg = tuple(int(C.bg[i:i + 2], 16) for i in (1, 3, 5))
        for x in range(w):  # dark on the left (logo, title) and right (status), the horde visible between
            t = x / max(1, w - 1)
            a = int(235 - 150 * min(1.0, t / 0.55)) if t < 0.55 else int(85 + 120 * max(0.0, (t - 0.7) / 0.3))
            d.line([(x, 0), (x, h)], fill=bg + (max(0, min(255, a)),))
        im.alpha_composite(shade)
        fade = Image.new("RGBA", (w, h))
        d = ImageDraw.Draw(fade)
        for y in range(h):  # melt into the window at the bottom
            t = max(0.0, (y - h * 0.55) / (h * 0.45))
            d.line([(0, y), (w, y)], fill=bg + (int(255 * t * t),))
        im.alpha_composite(fade)
        logo = self.look.images["logo"]
        lh = int(h * 0.78)
        logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
        im.alpha_composite(logo, (self.look.px(18), int(h * 0.08)))
        return ImageTk.PhotoImage(im), logo.width

    def redraw(self, force=False):
        w, h = self.winfo_width(), self.h
        if w < 2 or (not force and self._size == w):
            return
        self._size = w
        self.delete("all")
        f, px = self.look.fonts, self.look.px
        x = px(24)
        if "banner" in self.look.images:
            try:
                self._img, logo_w = self.picture(w, h)
                self.create_image(0, 0, image=self._img, anchor="nw")
                x = px(18) + logo_w + px(18)
            except Exception:
                pass
        if x == px(24):  # no art: the name in text
            self.create_text(x, h * 0.36, text="AGE OF DARKNESS", font=f["section"], fill=C.muted, anchor="w")
            x += px(4)
        for dx, colour in ((2, "#000000"), (0, "#eaf3f2")):
            self.create_text(x + px(dx), h * 0.40 + px(dx), text="ARCADE ENDLESS", font=f["title"], fill=colour, anchor="w")
        self.create_text(x + px(2), h * 0.66, text="The night never ends.  Neither do they.", font=f["subtitle"],
                         fill=C.veil, anchor="w")
        self.create_text(x + px(3), h * 0.87, text="CREATED BY LUNAR", font=f["status"], fill=C.muted, anchor="w")
        y = h * 0.30
        for label, text, ok in self.status:
            colour = C.veil if ok else C.muted
            self.create_text(w - px(24), y, text=f"{label}   {text}", font=f["status"], fill=colour, anchor="e")
            self.create_text(w - px(24) - self.measure(f"{label}   {text}", f["status"]) - px(10), y, text="●" if ok else "○",
                             font=f["status"], fill=colour, anchor="e")
            y += px(24)

    def measure(self, text, font):
        import tkinter.font as tkfont
        return tkfont.Font(root=self, font=font).measure(text)

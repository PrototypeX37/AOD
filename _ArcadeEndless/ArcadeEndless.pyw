"""Arcade Endless: pick how hard the run is, see and edit what every night brings, and install it. Double-click to run.

Needs Python 3 with tkinter (the python.org installer includes it). Building only reads the game's own pak.
"Build & install" writes dist\\ArcadeEndless_P.pak, validates it, copies it into Paks\\~mods and applies the exe
patch; "Remove" undoes both. For multiplayer only the host needs this app: friends copy the host's pak into
their ~mods and run tools\\exe_patch.ps1, then compare match codes. The NightmarePOC tab installs and removes that
optional second mod the same way, on its own; its Customise window sets the Nightmares' costs and the heroes' stats.
"""
import contextlib
import io
import math
import os
import shutil
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import build_endless as be  # noqa: E402
import exe_patch  # noqa: E402
import home  # noqa: E402
import look  # noqa: E402
import nightmare  # noqa: E402
import schedule  # noqa: E402
import validate_endless as ve  # noqa: E402

INSTALLED = exe_patch.MOD_PAK
INSTALLED_SETTINGS = os.path.join(home.DIST, "installed_settings.txt")  # "<settings code> <match code>"
# the game's own names for its difficulties (Main_ST string table), in DIFFICULTIES order
DIFFICULTY_LABELS = dict(zip(("Forgiving", "Easy", "Normal", "Veteran", "Horrific", "Nightmare"), be.DIFFICULTY_FIELDS))
SLIDERS = [  # settings field, label, low, high, step
    ("pester", "Pester wave size", 0.25, 4.0, 0.05),
    ("surge", "Surge night size (Crushers 1.5x this)", 1.0, 5.0, 0.1),
    ("death_night_growth", "Death Night growth (0 = base game sizes)", 0.0, 3.0, 0.05),
    ("elites", "Elite bosses on Death Nights (0 = none)", 0.0, 5.0, 0.25),
]
MIX_STEP = 0.05
ROW_TAGS = {"Surge": "surge", "Quiet": "quiet", "First day": "quiet", "Final Night": "final"}  # "Death Night N" -> "death"
EDITED = "*"
ELITE_SHORT = {"Crawler": "Crawler", "Axeman": "Axe", "Spearman": "Spear", "Wraith": "Wraith", "Spitter": "Spit",
               "Crusher": "Crush", "Festerling": "Fest"}  # the Elites column has room for the Final Night's five
# self.edits keys: ("P", day, unit) for pester/surge nights (both modes); ("N", mode, night, difficulty, unit)
# for Death Nights (night 1-5) and the Final Night (0)


def quietly(fn, *args):
    """(fn's result, or the exception it raised, and everything it printed). exe_patch reports problems as SystemExit."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            return fn(*args), out.getvalue()
        except (Exception, SystemExit) as ex:
            return ex, out.getvalue()


def failed(result):
    return isinstance(result, BaseException)


class App:
    def __init__(self, root):
        self.root = root
        self.loading = False
        self.pending = None
        self.editor = None
        self.edits = {}
        self.rows = {}
        self.look = look.Look(root)
        px = self.look.px
        root.title("Arcade Endless: Age of Darkness")
        w, h = min(px(1500), root.winfo_screenwidth() - 40), min(px(950), root.winfo_screenheight() - 80)
        root.geometry(f"{w}x{h}")
        root.minsize(min(px(1180), w), min(px(720), h))
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)
        self.banner = look.Banner(root, self.look, 150)
        self.banner.grid(row=0, column=0, columnspan=2, sticky="we")
        self.warning_bar = tk.Frame(root, background=look.C.danger, highlightthickness=1, highlightbackground=look.C.warn)
        self.warning_bar.grid(row=1, column=0, columnspan=2, sticky="we", padx=px(16), pady=(0, px(12)))
        self.limit_warning = tk.StringVar()
        bar_text = tk.Label(self.warning_bar, textvariable=self.limit_warning, fg="#ffe3de", bg=look.C.danger,
                            font=self.look.fonts["bold"], justify="left", anchor="w", padx=px(14), pady=px(10))
        bar_text.pack(fill="x")
        self.warning_bar.bind("<Configure>", lambda e: bar_text.configure(wraplength=max(px(200), e.width - px(40))))
        self.nm = nightmare.installed_settings() or nightmare.defaults()  # NightmarePOC's settings for its next install
        self.build_settings_panel(self.card(root, "How hard", 0))
        self.build_nights_panel(self.card(root, "Every night", 1))
        self.build_install_bar(ttk.Frame(root, style="Bar.TFrame", padding=(px(16), 0, px(16), px(14))))
        self.load(self.installed_settings() or be.PRESETS["Hard"])
        self.update_status()

    # ------------------------------------------------------------------ layout
    def card(self, root, title, column):
        px = self.look.px
        f = ttk.Frame(root, padding=px(14))
        f.grid(row=2, column=column, sticky="nsw" if column == 0 else "nsew",
               padx=(px(16), px(10)) if column == 0 else (0, px(16)), pady=(0, px(12)))
        ttk.Label(f, text=title.upper(), style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(8)))
        body = ttk.Frame(f)
        body.grid(row=1, column=0, columnspan=3, sticky="nsew")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        return body

    def build_settings_panel(self, f):
        px = self.look.px
        self.preset = tk.StringVar()
        ttk.Label(f, text="Preset").grid(row=0, column=0, sticky="w")
        box = ttk.Combobox(f, textvariable=self.preset, values=list(be.PRESETS) + ["Custom"], state="readonly", width=14)
        box.grid(row=0, column=1, sticky="w", pady=(0, px(10)))
        box.bind("<<ComboboxSelected>>", lambda _: self.preset.get() in be.PRESETS and self.load(be.PRESETS[self.preset.get()]))

        tabs = ttk.Notebook(f)
        tabs.grid(row=1, column=0, columnspan=2, sticky="nwe")
        general, mix, limits, extra = (ttk.Frame(tabs, padding=px(10)) for _ in range(4))
        tabs.add(general, text="Difficulty")
        tabs.add(mix, text="Unit mix")
        tabs.add(limits, text="Limits")
        tabs.add(extra, text="NightmarePOC")
        self.build_nightmare_tab(extra)

        self.vars = {}
        lo, hi = be.FINAL_NIGHT_RANGE
        row = self.spin(general, 0, "final_night_day", f"Final Night on day ({lo + 1}-{hi + 1})", lo + 1, hi + 1)  # in-game day
        for name, label, lo, hi, step in SLIDERS:
            row = self.slider(general, row, self.vars, name, label, lo, hi, step)
        row = self.spin(general, row, "surge_every", f"Surge every N nights from day {be.SURGE_FROM + 1} (0 = off)", 0, 10)
        self.vars["tiers"] = tk.BooleanVar()
        ttk.Checkbutton(general, text="Higher tiers on later Death Nights", variable=self.vars["tiers"],
                        command=self.changed).grid(row=row, column=0, columnspan=3, sticky="w", pady=(px(8), 0))

        ttk.Label(limits, text="Safety caps. A night over its cap is scaled down to fit.\nRaise them at your own risk.",
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        row = self.spin(limits, 1, "night_cap", f"Death Night cap (units)\nthe game's biggest night: {be.BASE_NIGHT_CAP:,}",
                        1000, be.CAP_MAX, step=1000, width=8)
        self.spin(limits, row, "pester_cap", f"Pester night cap (units)\nsafe: {be.PESTER_NIGHT_CAP:,}",
                  100, be.CAP_MAX, step=500, width=8)

        ttk.Label(mix, text="How many of each unit come on pester and surge\nnights, x the preset's numbers. 0 = none of them.",
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(6)))
        self.mix = {}
        row = 1
        for unit in be.UNITS:
            v = self.mix[unit] = tk.DoubleVar()
            ttk.Label(mix, text=unit).grid(row=row, column=0, sticky="w", pady=px(5))
            ttk.Scale(mix, from_=0.0, to=5.0, variable=v, length=px(170),
                      command=lambda _, v=v: (v.set(round(round(v.get() / MIX_STEP) * MIX_STEP, 2)), self.changed())
                      ).grid(row=row, column=1, sticky="w", padx=px(8))
            ttk.Label(mix, textvariable=v, width=5, style="Value.TLabel").grid(row=row, column=2, sticky="e")
            row += 1
        ttk.Button(mix, text="All x1", style="Small.TButton", command=lambda: self.set_mix((1.0,) * len(be.UNITS))
                   ).grid(row=row, column=0, sticky="w", pady=(px(12), 0))

        ttk.Label(f, text="Settings code").grid(row=2, column=0, sticky="w", pady=(px(14), px(2)))
        self.code = tk.StringVar()
        codes = ttk.Frame(f)
        codes.grid(row=3, column=0, columnspan=2, sticky="we")
        codes.columnconfigure(0, weight=1)
        ttk.Entry(codes, textvariable=self.code, width=30, state="readonly").grid(row=0, column=0, sticky="we")
        ttk.Button(codes, text="Copy", style="Small.TButton", command=self.copy_code).grid(row=0, column=1, padx=(px(6), 0))
        self.paste = tk.StringVar()
        ttk.Entry(codes, textvariable=self.paste, width=30).grid(row=1, column=0, sticky="we", pady=(px(6), 0))
        ttk.Button(codes, text="Load", style="Small.TButton", command=self.load_code).grid(row=1, column=1, padx=(px(6), 0), pady=(px(6), 0))
        ttk.Label(f, text="Holds every setting and edit: a friend who loads it gets your exact run.",
                  style="Muted.TLabel", wraplength=px(330)).grid(row=4, column=0, columnspan=2, sticky="w", pady=(px(4), 0))

    def build_nightmare_tab(self, f):
        px = self.look.px
        ttk.Label(f, text="Optional: a second mod by Lunar", style="Value.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, style="Muted.TLabel", justify="left", wraplength=px(300), text=(
            "Separate from Arcade Endless: install, play or remove either one on its own. In Survival and multiplayer "
            "(the campaign is untouched):\n"
            "\u2022 The Volatists can train 8 Nightmares, from Crawlers to Crushers, at the Barracks and Siege Workshop.\n"
            "\u2022 Heroes can be made stronger or weaker. By default they keep the game's own stats.\n"
            "\u2022 The main menu's hidden Editor button comes back: the developers' own map and mission editor, rough "
            "edges included.\n\n"
            "Customise sets each Nightmare's cost (by default no population or food) and each hero's stats. Install "
            "builds it from your game's own files into Paks\\~mods; the game exe isn't touched. Not yet tested in-game. "
            "In multiplayer every player needs the same pak (compare match codes). Remove it between matches, not "
            "mid-save.")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(6), px(10)))
        self.nightmare_status = tk.StringVar()
        ttk.Label(f, textvariable=self.nightmare_status, wraplength=px(300), justify="left"
                  ).grid(row=2, column=0, columnspan=2, sticky="w")
        state = "normal" if nightmare.AVAILABLE else "disabled"
        ttk.Button(f, text="Customise...", state=state, command=lambda: NightmareWindow(self)
                   ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(10), 0))
        ttk.Button(f, text="Remove", style="Danger.TButton", state=state, command=self.remove_nightmare
                   ).grid(row=4, column=0, sticky="w", padx=(0, px(8)), pady=(px(8), 0))
        ttk.Button(f, text="Install NightmarePOC", style="Accent.TButton", state=state, command=self.install_nightmare
                   ).grid(row=4, column=1, sticky="e", pady=(px(8), 0))

    def spin(self, f, row, name, label, lo, hi, step=1, width=6):
        px = self.look.px
        v = self.vars[name] = tk.IntVar()
        ttk.Label(f, text=label).grid(row=row, column=0, columnspan=2, sticky="w", pady=(px(8), 0))
        s = ttk.Spinbox(f, from_=lo, to=hi, increment=step, textvariable=v, width=width, command=self.changed)
        s.grid(row=row, column=2, sticky="e", pady=(px(8), 0))
        s.bind("<KeyRelease>", lambda _: self.changed())
        return row + 1

    def slider(self, f, row, store, name, label, lo, hi, step):
        px = self.look.px
        v = store[name] = tk.DoubleVar()
        ttk.Label(f, text=label).grid(row=row, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
        ttk.Scale(f, from_=lo, to=hi, variable=v, length=px(230),
                  command=lambda _: (v.set(round(round(v.get() / step) * step, 2)), self.changed())
                  ).grid(row=row + 1, column=0, columnspan=2, sticky="w")
        ttk.Label(f, textvariable=v, width=5, style="Value.TLabel").grid(row=row + 1, column=2, sticky="e")
        return row + 2

    def build_nights_panel(self, f):
        px = self.look.px
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        top = ttk.Frame(f)
        top.grid(row=0, column=0, columnspan=2, sticky="we")
        top.columnconfigure(4, weight=1)
        self.mode = tk.StringVar(value="Survival")
        self.difficulty = tk.StringVar(value="Normal")
        for col, (label, var, values) in enumerate((("Mode", self.mode, be.MODES), ("Difficulty", self.difficulty, list(DIFFICULTY_LABELS)))):
            ttk.Label(top, text=label).grid(row=0, column=2 * col, padx=(0 if col == 0 else px(16), px(6)))
            c = ttk.Combobox(top, textvariable=var, values=list(values), state="readonly", width=12)
            c.grid(row=0, column=2 * col + 1)
            c.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.edit_info = tk.StringVar()
        ttk.Label(top, textvariable=self.edit_info, style="Value.TLabel").grid(row=0, column=5, padx=(px(12), px(8)))
        ttk.Button(top, text="Reset all edits", style="Small.TButton", command=lambda: self.reset(lambda k: True)).grid(row=0, column=6)
        self.summary = tk.StringVar()
        ttk.Label(f, textvariable=self.summary, wraplength=px(860), justify="left", style="Summary.TLabel"
                  ).grid(row=1, column=0, columnspan=2, sticky="w", pady=px(10))

        cols = ("day", "night", "total") + be.UNITS + ("tier", "elites")
        self.tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = {"day": 40, "night": 124, "total": 64, "tier": 42, "elites": 180, "Festerling": 86, "Spearman": 80, "Crawler": 72}
        head = tkfont.Font(root=self.root, font=self.look.fonts["table_head"])
        for c in cols:  # never narrower than the header text, at any screen scaling
            self.tree.heading(c, text=c.upper())
            width = max(px(widths.get(c, 64)), head.measure(c.upper()) + px(20))
            self.tree.column(c, width=width, minwidth=width if c != "elites" else px(120),
                             anchor="w" if c in ("night", "elites") else "e", stretch=c == "elites")
        self.look.table_tags(self.tree)
        self.tree.bind("<Double-1>", self.start_edit)
        self.tree.bind("<Button-3>", self.context_menu)
        self.tree.bind("<MouseWheel>", lambda _: self.close_editor(), add="+")
        bar = ttk.Scrollbar(f, orient="vertical", command=lambda *a: (self.close_editor(), self.tree.yview(*a)))
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.grid(row=2, column=0, sticky="nsew")
        bar.grid(row=2, column=1, sticky="ns")
        ttk.Label(f, style="Muted.TLabel", wraplength=px(860), justify="left", text=(
            "Counts are what spawns at the difficulty shown. Days match the in-game day counter. The game multiplies "
            "pester waves by its difficulty (Forgiving x0.2, Easy x0.5, Normal x0.8, Veteran x1, Horrific x1.2, Nightmare "
            "x1.5; with Custom difficulty, your Death Night choice) and rounds down. Double-click a unit's count to set what "
            f"spawns ({EDITED} = your edit; clear the box to undo it); right-click a row to reset edits. A pester edit is "
            "exact for the difficulty shown and scales with the others; a Death Night edit is for that mode and difficulty "
            "only. Quiet = the night after a Death Night, when the game sends no wave. Hardship's bosses aren't counted. "
            "With Custom difficulty, Duration picks the Death Night days.")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(8), 0))

    def build_install_bar(self, f):
        px = self.look.px
        f.grid(row=3, column=0, columnspan=2, sticky="we")
        f.columnconfigure(0, weight=1)
        self.status = tk.StringVar()
        ttk.Label(f, textvariable=self.status, style="Bar.TLabel", justify="left").grid(row=0, column=0, sticky="w")
        buttons = ttk.Frame(f, style="Bar.TFrame")
        buttons.grid(row=0, column=1, sticky="e")
        ttk.Button(buttons, text="Open mods folder", command=self.open_mods).grid(row=0, column=0, padx=px(5))
        ttk.Button(buttons, text="Remove", style="Danger.TButton", command=self.remove).grid(row=0, column=1, padx=px(5))
        ttk.Button(buttons, text="Build & install", style="Accent.TButton", command=self.install).grid(row=0, column=2, padx=(px(5), 0))

    # ------------------------------------------------------------------ settings
    def load(self, s):
        self.loading = True
        for f in ("surge_every", "tiers", "night_cap", "pester_cap") + tuple(x[0] for x in SLIDERS):
            self.vars[f].set(getattr(s, f))
        self.vars["final_night_day"].set(s.final_night_day + 1)  # the spinbox shows the in-game day
        for unit, x in zip(be.UNITS, s.mix):
            self.mix[unit].set(x)
        self.edits = {("P", day, unit): n for day, unit, n in s.pester_edits}
        self.edits.update({("N", *e[:4]): e[4] for e in s.night_edits})
        self.loading = False
        self.changed()

    def set_mix(self, mix):
        for unit, x in zip(be.UNITS, mix):
            self.mix[unit].set(x)
        self.changed()

    def settings(self):
        """The settings on screen, or raise ValueError with what's wrong."""
        try:
            kw = {name: v.get() for name, v in self.vars.items()}
            kw["final_night_day"] -= 1
            kw["mix"] = tuple(self.mix[u].get() for u in be.UNITS)
            kw["pester_edits"] = [(k[1], k[2], n) for k, n in self.edits.items() if k[0] == "P"]
            kw["night_edits"] = [(*k[1:], n) for k, n in self.edits.items() if k[0] == "N"]
            return be.Settings(**kw).checked()
        except (tk.TclError, AssertionError, TypeError) as ex:
            raise ValueError(str(ex) or "check the numbers") from ex

    def changed(self):
        if self.loading:
            return
        if self.pending:
            self.root.after_cancel(self.pending)
        self.pending = self.root.after(150, self.refresh)

    def refresh(self):
        self.pending = None
        self.close_editor()
        try:
            s = self.settings()
        except ValueError as ex:
            self.summary.set(f"Invalid settings: {ex}")
            return
        self.preset.set(next((n for n, p in be.PRESETS.items() if p == s), "Custom"))
        self.code.set(s.code())
        warnings = s.over_limits()
        self.limit_warning.set("⚠  ABOVE THE GAME'S LIMITS.   " + "  ".join(warnings) + "  The game has never run nights this big: "
                               "expect heavy lag, and it may freeze or crash. Untested; use at your own risk." if warnings else "")
        if warnings:
            self.warning_bar.grid()
        else:
            self.warning_bar.grid_remove()
        self.edit_info.set(f"{len(self.edits)} edit{'s' if len(self.edits) != 1 else ''}")
        b, log = quietly(be.build, s)
        if failed(b):
            self.summary.set(f"Build failed: {b}")
            return
        mode, difficulty = self.mode.get(), DIFFICULTY_LABELS[self.difficulty.get()]
        self.multiplier = b.pester_multipliers[difficulty]
        nights = schedule.schedule(b, mode, difficulty)
        top = self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for n in nights:
            tag = ROW_TAGS.get(n.kind, "death" if n.kind.startswith("Death") else "odd" if n.day % 2 else "")
            elites = ", ".join(f"{c} {ELITE_SHORT[e.split(' ', 1)[1]]}" for e, c in n.elites.items())  # the column says "elite"
            units = [f"{n.units[u]:,}{EDITED}" if u in n.edited else (f"{n.units[u]:,}" if n.units[u] else "") for u in be.UNITS]
            kind = n.kind + (" (capped)" if n.capped else "")
            iid = self.tree.insert("", "end", tags=(tag,), values=(n.game_day, kind, f"{n.total:,}", *units,
                                                                    n.tier if n.editable else "", elites))
            self.rows[iid] = n
        self.tree.yview_moveto(top)
        pester = [n.total for n in nights if n.kind in ("Pester", "Surge")]
        majors = [n for n in nights if n.kind.startswith("Death")]
        surges = f"every {s.surge_every} nights from day {be.SURGE_FROM + 1}" if s.surge_every else "off"
        capped = sum(n.capped for n in nights)
        self.summary.set(
            f"{self.difficulty.get()}: pester waves x{self.multiplier / 1024:.1f}. Death Nights on days "
            f"{', '.join(str(n.game_day) for n in majors)}; Final Night on day {nights[-1].game_day} ({nights[-1].total:,} units). "
            f"Surge nights {surges}. Biggest pester night {max(pester):,} units (cap {s.pester_cap:,} before the multiplier); "
            f"biggest Death Night {max(n.total for n in majors):,}."
            + (f" {capped} night{'s' if capped != 1 else ''} scaled down to fit a safety cap." if capped else "")
            )
        self.update_status()

    def copy_code(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.code.get())

    def load_code(self):
        try:
            self.load(be.Settings.from_code(self.paste.get()))
        except (ValueError, AssertionError, TypeError) as ex:
            messagebox.showerror("Arcade Endless", f"That isn't a valid settings code ({ex}).")

    # ------------------------------------------------------------------ editing counts
    def edit_key(self, night, unit):
        if night.kind in ("Pester", "Surge"):
            return ("P", night.day, unit)
        return ("N", self.mode.get(), night.night, DIFFICULTY_LABELS[self.difficulty.get()], unit)

    def night_keys(self, night):
        """Predicate: is an edit key one of this night's cells?"""
        probe = self.edit_key(night, None)[:-1]
        return lambda k: k[:-1] == probe

    def cell_at(self, event):
        """(row id, "#n", column name) under the mouse. Found from the cells' own boxes: identify_column's idea of
        the column edges is a few pixels off from where the cells are drawn."""
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify_region(event.x, event.y) != "cell":
            return None
        for i, name in enumerate(self.tree["columns"]):
            box = self.tree.bbox(iid, name)
            if box and box[0] <= event.x < box[0] + box[2]:
                return iid, f"#{i + 1}", name
        return None

    def close_editor(self):
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.destroy()
        self.editor = None

    def start_edit(self, event):
        cell = self.cell_at(event)
        if not cell or cell[2] not in be.UNITS:
            return
        iid, col, unit = cell
        night = self.rows[iid]
        if not night.editable:
            return messagebox.showinfo("Arcade Endless", "The game sends no wave on the first day or the night after a Death "
                                       "Night, so there's nothing to edit.")
        self.close_editor()
        x, y, w, h = self.tree.bbox(iid, col)
        var = tk.StringVar(value=str(night.units[unit]))
        entry = self.editor = ttk.Entry(self.tree, textvariable=var, justify="right")
        entry.place(x=x, y=y, width=max(w, 70), height=h)
        entry.focus_set()
        entry.select_range(0, "end")
        done = []

        def commit(_=None):
            if done:
                return
            done.append(True)
            text = var.get().strip().replace(",", "").rstrip(EDITED)
            self.close_editor()
            if text and not text.isdigit():
                return messagebox.showerror("Arcade Endless", "Type a whole number of units (0 or more), or clear the box to undo the edit.")
            warning = self.set_count(night, unit, int(text) if text else None)
            if warning:
                messagebox.showwarning("Arcade Endless", warning)
            self.changed()
        entry.bind("<Return>", commit)
        entry.bind("<KP_Enter>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda _: (done.append(True), self.close_editor()))

    def set_count(self, night, unit, n):
        """Make `unit` spawn n on `night` at the difficulty shown (None undoes the edit). Returns a warning or None.

        Pester edits are stored before the game's difficulty multiplier, as the smallest count that spawns n here."""
        key = self.edit_key(night, unit)
        if n is None:
            self.edits.pop(key, None)
            return None
        if key[0] == "N":
            self.edits[key] = min(n, be.CAP_MAX)
            return f"{n:,} is more than a night can take; using {be.CAP_MAX:,}." if n > be.CAP_MAX else None
        try:
            cap = self.settings().pester_cap
        except ValueError:
            cap = be.PESTER_NIGHT_CAP
        count = be.count_for(n, self.multiplier)
        self.edits[key] = min(count, cap)
        if count > cap:
            return (f"At this difficulty one pester night can spawn at most {be.spawned(cap, self.multiplier):,} {unit}s "
                    f"(the pester night cap is {cap:,} before the game's x{self.multiplier / 1024:.1f}). Using that. Raise "
                    "the cap on the Limits tab for more.")
        return None

    def context_menu(self, event):
        cell = self.cell_at(event)
        if not cell:
            return
        iid, _, column = cell
        night = self.rows[iid]
        menu = tk.Menu(self.root, tearoff=0)
        if column in be.UNITS and self.edit_key(night, column) in self.edits:
            key = self.edit_key(night, column)
            menu.add_command(label=f"Reset {column} on this night", command=lambda: self.reset(lambda k: k == key))
        if night.editable and any(map(self.night_keys(night), self.edits)):
            menu.add_command(label=f"Reset this night's edits (day {night.day})", command=lambda: self.reset(self.night_keys(night)))
        if self.edits:
            menu.add_command(label=f"Reset all {len(self.edits)} edits", command=lambda: self.reset(lambda k: True))
        if menu.index("end") is not None:
            menu.tk_popup(event.x_root, event.y_root)

    def reset(self, which):
        self.edits = {k: n for k, n in self.edits.items() if not which(k)}
        self.changed()

    # ------------------------------------------------------------------ install
    def installed_settings(self):
        """The settings of the pak in ~mods, if this app installed it."""
        try:
            code, match = open(INSTALLED_SETTINGS).read().split()
            return be.Settings.from_code(code) if os.path.exists(INSTALLED) and exe_patch.match_code(INSTALLED) == match else None
        except (OSError, ValueError, AssertionError):
            return None

    def update_status(self):
        site = quietly(exe_patch.find_site, open(exe_patch.EXE, "rb").read())[0] if not hasattr(self, "exe_state") else self.exe_state
        self.exe_state = site
        exe = "unrecognised exe" if failed(site) else ("not patched" if site[1] is None else f"patched ({site[1]} days of waves)")
        if not os.path.exists(INSTALLED):
            mod = "not installed"
        else:
            s = self.installed_settings()
            match = exe_patch.match_code(INSTALLED)
            try:
                same = s is not None and s == self.settings()
            except ValueError:
                same = False
            mod = f"installed, match code {match}" + (" (these settings)" if same else " (other settings)" if s else " (settings unknown)")
        backup = "saved" if os.path.exists(exe_patch.backup_path()) else "none yet (installing makes one)"
        nm_ok = os.path.exists(nightmare.INSTALLED)
        nm = f"installed, match code {exe_patch.match_code(nightmare.INSTALLED)}" if nm_ok else "not installed"
        if nm_ok and nightmare.AVAILABLE:
            s = nightmare.installed_settings()
            nm += " (these settings)" if s is not None and s == self.nm else " (other settings)" if s else " (settings unknown)"
        self.status.set(f"Mod pak: {mod}.   Game exe: {exe}.   Exe backup: {backup}.   NightmarePOC: {nm}.")
        self.nightmare_status.set(f"Settings: {nightmare.describe(self.nm)}.\nNightmarePOC: {nm}." if nightmare.AVAILABLE else
                                  f"Not available: NightmarePOC's tools aren't in this copy of the app ({nightmare.TOOLS}).")
        pak_ok = os.path.exists(INSTALLED)
        self.banner.set_status([("MOD PAK", f"match {exe_patch.match_code(INSTALLED)}" if pak_ok else "not installed", pak_ok),
                                ("GAME EXE", f"patched, {site[1]} days" if not failed(site) and site[1] else "not patched",
                                 not failed(site) and bool(site[1])),
                                ("NIGHTMAREPOC", f"match {exe_patch.match_code(nightmare.INSTALLED)}" if nm_ok else "not installed", nm_ok)])

    def install(self):
        try:
            s = self.settings()
        except ValueError as ex:
            return messagebox.showerror("Arcade Endless", f"Invalid settings: {ex}")
        warnings = s.over_limits()
        if warnings and not messagebox.askyesno(
                "Arcade Endless: above the game's limits",
                "WARNING: these settings go past the game's limits:\n\n" + "\n".join("- " + w for w in warnings)
                + "\n\nThe game has never been run with nights this big. It may lag badly, freeze or crash, and multiplayer "
                "games may fall out of sync. Nobody has tested this.\n\nInstall anyway?", icon="warning", default="no"):
            return
        if not messagebox.askokcancel("Arcade Endless", "Build the pak for these settings, copy it into Paks\\~mods and "
                                      "patch the game exe?\n\nClose the game first."):
            return
        self.root.config(cursor="watch")
        self.root.update()
        try:
            result, log = quietly(be.main, s, be.OUT_PAK)
            if failed(result):
                return messagebox.showerror("Arcade Endless", f"Build failed: {result}\n\n{log[-1500:]}")
            result, log = quietly(ve.main, be.OUT_PAK)
            if result != 0:
                fails = "\n".join(line for line in log.splitlines() if "FAIL" in line)
                hint = ("\n\nAn older NightmarePOC is in ~mods: install it again from the NightmarePOC tab to update it."
                        if "NightmarePOC" in fails else "")
                return messagebox.showerror("Arcade Endless", f"Validation failed, nothing installed:\n\n{fails or result}{hint}")
            try:
                os.makedirs(os.path.dirname(INSTALLED), exist_ok=True)
                shutil.copyfile(be.OUT_PAK, INSTALLED)
            except OSError as ex:
                return messagebox.showerror("Arcade Endless", f"Couldn't copy the pak into ~mods ({ex}). Close the game and try again.")
            result, log = quietly(exe_patch.main, ["", "install"])
            if failed(result):
                messagebox.showerror("Arcade Endless", f"The pak is installed but the exe patch failed:\n\n{result}")
            match = exe_patch.match_code(INSTALLED)
            with open(INSTALLED_SETTINGS, "w") as f:
                f.write(f"{s.code()} {match}\n")
            del self.exe_state
            self.update_status()
            if not failed(result):
                messagebox.showinfo("Arcade Endless", f"Installed. Match code {match}.\n\nMultiplayer: send friends "
                                    f"{INSTALLED}\nThey copy it into their Paks\\~mods, run tools\\exe_patch.ps1 install, "
                                    f"and 'exe_patch.ps1 status' should show match code {match}.")
        finally:
            self.root.config(cursor="")

    def remove(self):
        if not messagebox.askokcancel("Arcade Endless", "Delete the mod pak from ~mods and restore the original game exe?"):
            return
        try:
            if os.path.exists(INSTALLED):
                os.remove(INSTALLED)
        except OSError as ex:
            return messagebox.showerror("Arcade Endless", f"Couldn't delete the pak ({ex}). Close the game and try again.")
        result, _ = quietly(exe_patch.main, ["", "remove"])
        if failed(result) and os.path.exists(exe_patch.backup_path()) and messagebox.askyesno(
                "Arcade Endless", f"Putting the original 6 bytes back failed:\n\n{result}\n\nCopy the full backup of the original exe "
                f"back instead?\n\n{exe_patch.backup_path()}"):
            result, _ = quietly(exe_patch.main, ["", "restore"])
        if os.path.exists(INSTALLED_SETTINGS):
            os.remove(INSTALLED_SETTINGS)
        del self.exe_state
        self.update_status()
        if failed(result):
            messagebox.showerror("Arcade Endless", f"The pak is removed but restoring the exe failed:\n\n{result}\n\n"
                                 "Steam's 'Verify integrity of game files' also puts the original exe back.")

    def install_nightmare(self):
        s = self.nm
        if not messagebox.askokcancel("Arcade Endless", f"Build NightmarePOC with {nightmare.describe(s)} from your game's own "
                                      "files and copy it into Paks\\~mods?\n\nClose the game first."):
            return
        self.root.config(cursor="watch")
        self.root.update()
        try:
            result, log = quietly(nightmare.build, s)
            if failed(result):
                return messagebox.showerror("Arcade Endless", f"NightmarePOC build failed: {result}\n\n{log[-1500:]}")
            result, log = quietly(nightmare.check, s)
            if result != 0:
                fails = "\n".join(line for line in log.splitlines() if "FAIL" in line)
                return messagebox.showerror("Arcade Endless", f"NightmarePOC validation failed, nothing installed:\n\n{fails or result}")
            try:
                os.makedirs(os.path.dirname(nightmare.INSTALLED), exist_ok=True)
                shutil.copyfile(nightmare.OUT_PAK, nightmare.INSTALLED)
            except OSError as ex:
                return messagebox.showerror("Arcade Endless", f"Couldn't copy NightmarePOC into ~mods ({ex}). Close the game and try again.")
            match = exe_patch.match_code(nightmare.INSTALLED)
            with open(nightmare.INSTALLED_SETTINGS, "w") as f:
                f.write(f"{s.code()} {match}\n")
            self.update_status()
            messagebox.showinfo("Arcade Endless", f"NightmarePOC installed. Match code {match}.\n\nPick the Volatists to train "
                                f"Nightmares.\n\nMultiplayer: every player needs the same NightmarePOC. Send them your "
                                f"settings code from Customise (or {nightmare.INSTALLED}); they install it and should see "
                                f"match code {match}.")
        finally:
            self.root.config(cursor="")

    def remove_nightmare(self):
        if not messagebox.askokcancel("Arcade Endless", "Delete NightmarePOC from ~mods?\n\nRemove it between matches: a save "
                                      "with Nightmares you trained hasn't been tested without it."):
            return
        try:
            if os.path.exists(nightmare.INSTALLED):
                os.remove(nightmare.INSTALLED)
        except OSError as ex:
            return messagebox.showerror("Arcade Endless", f"Couldn't delete NightmarePOC ({ex}). Close the game and try again.")
        if os.path.exists(nightmare.INSTALLED_SETTINGS):
            os.remove(nightmare.INSTALLED_SETTINGS)
        self.update_status()

    def open_mods(self):
        folder = os.path.dirname(INSTALLED)
        os.startfile(folder if os.path.isdir(folder) else os.path.dirname(folder))


UNIT_WORDS = {"villagers": "population", "seconds": "train time"}
HERO_WORDS = {"regen": "health regen", "melee": "melee damage", "special": "special damage", "ranged": "ranged damage",
              "shred": "armour shred", "speed": "move speed", "revive": "revive time"}


class NightmareWindow:
    """Customise NightmarePOC: what each Nightmare costs and each hero's stats. OK keeps them for the next install."""

    def __init__(self, app, show=True):
        self.app = app
        bm = nightmare.build_mod
        px = self.px = app.look.px
        w = self.win = tk.Toplevel(app.root)
        if not show:
            w.withdraw()
        w.title("Customise NightmarePOC")
        w.configure(background=look.C.panel)
        w.transient(app.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        f = ttk.Frame(w, padding=px(18))
        f.pack(fill="both", expand=True)
        self.units, self.heroes = {}, {}

        ttk.Label(f, text="NIGHTMARE UNITS", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(f, style="Muted.TLabel", text="What each Nightmare costs the Volatists. Population is how many villagers "
                  "a unit uses; 0 = none.").grid(row=1, column=0, sticky="w", pady=(px(2), px(6)))
        grid = ttk.Frame(f)
        grid.grid(row=2, column=0, sticky="w")
        for c, text in enumerate(("Unit", "Trained at", "Gold", "Wood", "Stone", "Iron", "Food", "Population",
                                  "Train time (s)", "Upkeep (gold)")):
            ttk.Label(grid, text=text, style="Value.TLabel").grid(row=0, column=c, sticky="w", padx=px(4), pady=(0, px(4)))
        for r, unit in enumerate(bm.UNIT_ORDER, 1):
            ttk.Label(grid, text=nightmare.unit_label(unit)).grid(row=r, column=0, sticky="w", padx=px(4))
            ttk.Label(grid, text=nightmare.trained_at(unit), style="Muted.TLabel").grid(row=r, column=1, sticky="w", padx=px(4))
            for c, field in enumerate(bm.UNIT_FIELDS, 2):
                lo, hi = (1 if field == "seconds" else 0), bm.UNIT_MAX.get(field, bm.RESOURCE_MAX)
                self.units[(unit, field)] = self.spinbox(grid, r, c, lo, hi, 5 if field in bm.RESOURCES[:4] else 1)

        ttk.Label(f, text="HEROES", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(px(18), 0))
        ttk.Label(f, style="Muted.TLabel", justify="left", wraplength=px(900), text=(
            f"Each hero's own stats at level {nightmare.build_mod.HERO_LEVEL}, the top level. Change one and every level "
            "changes in proportion; armour is set to the same value at every level. Damage over time scales with its "
            "attack's damage, and ranged damage is per shot. Shred is the hero's main armour shred; their other attacks' "
            "shred scales with it. Greyed out: the hero has no such attack. Other abilities keep the game's numbers."
            )).grid(row=4, column=0, sticky="w", pady=(px(2), px(6)))
        grid = ttk.Frame(f)
        grid.grid(row=5, column=0, sticky="w")
        for c, text in enumerate(("Hero", "Health", "Regen", "Armour", "Melee dmg", "Special dmg", "Ranged dmg", "Shred",
                                  "Move speed", "Revive (s)")):
            ttk.Label(grid, text=text, style="Value.TLabel").grid(row=0, column=c, sticky="w", padx=px(4), pady=(0, px(4)))
        game = nightmare.game_values()
        for r, hero in enumerate(bm.HEROES, 1):
            ttk.Label(grid, text=hero).grid(row=r, column=0, sticky="w", padx=px(4))
            for c, field in enumerate(bm.HERO_FIELDS, 1):
                g = game[hero][field]
                lo, hi = self.hero_range(hero, field)
                step = 1 if field == "armour" or not g else 10 ** (math.floor(math.log10(g)) - 1)
                self.heroes[(hero, field)] = self.spinbox(grid, r, c, lo, hi, step, enabled=g is not None)

        self.error = tk.StringVar()
        tk.Label(f, textvariable=self.error, fg=look.C.blood, bg=look.C.panel, font=app.look.fonts["bold"]
                 ).grid(row=6, column=0, sticky="w", pady=(px(10), 0))
        codes = ttk.Frame(f)
        codes.grid(row=7, column=0, sticky="we", pady=(px(6), 0))
        codes.columnconfigure(1, weight=1)
        self.code, self.paste = tk.StringVar(), tk.StringVar()
        ttk.Label(codes, text="Settings code").grid(row=0, column=0, sticky="w", padx=(0, px(8)))
        ttk.Entry(codes, textvariable=self.code, state="readonly").grid(row=0, column=1, sticky="we")
        ttk.Button(codes, text="Copy", style="Small.TButton", command=self.copy_code).grid(row=0, column=2, padx=(px(6), 0))
        ttk.Entry(codes, textvariable=self.paste).grid(row=1, column=1, sticky="we", pady=(px(6), 0))
        ttk.Button(codes, text="Load", style="Small.TButton", command=self.load_code).grid(row=1, column=2, padx=(px(6), 0), pady=(px(6), 0))
        buttons = ttk.Frame(f)
        buttons.grid(row=8, column=0, sticky="we", pady=(px(14), 0))
        buttons.columnconfigure(2, weight=1)
        ttk.Button(buttons, text="Reset all", command=lambda: self.load(nightmare.defaults())).grid(row=0, column=0, padx=(0, px(8)))
        ttk.Button(buttons, text="Reset heroes", command=self.game_heroes).grid(row=0, column=1)
        ttk.Button(buttons, text="Cancel", command=self.close).grid(row=0, column=3, padx=px(8))
        ttk.Button(buttons, text="OK", style="Accent.TButton", command=self.ok).grid(row=0, column=4)

        self.load(app.nm)
        for v in list(self.units.values()) + list(self.heroes.values()):
            v.trace_add("write", lambda *_: self.show_code())
        self.show_code()
        app.look.dark_title_bar(w)
        if show:
            w.geometry(f"+{app.root.winfo_rootx() + px(40)}+{app.root.winfo_rooty() + px(40)}")
            try:
                w.grab_set()
            except tk.TclError:
                pass

    def spinbox(self, parent, row, column, lo, hi, step, enabled=True):
        v = tk.StringVar()
        ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=v, width=8,
                    state="normal" if enabled else "disabled").grid(row=row, column=column, sticky="w", padx=self.px(4), pady=self.px(2))
        return v

    def load(self, s):
        bm = nightmare.build_mod
        for unit in bm.UNIT_ORDER:
            for field, x in s.unit(unit).items():
                self.units[(unit, field)].set(str(x))
        for hero in bm.HEROES:
            for field, x in s.hero(hero).items():
                self.heroes[(hero, field)].set(nightmare.shown(hero, field, x))

    def game_heroes(self):
        bm = nightmare.build_mod
        for hero in bm.HEROES:
            for field, x in zip(bm.HERO_FIELDS, bm.GAME_HERO):
                self.heroes[(hero, field)].set(nightmare.shown(hero, field, x))

    @staticmethod
    def hero_range(hero, field):
        """The values a hero stat's box takes: what Settings allows, in the stat's own units."""
        bm = nightmare.build_mod
        game = nightmare.game_values()[hero][field]
        if field == "armour":
            return 0.0, bm.ARMOUR_MAX
        return (game * bm.MULT_RANGE[0], game * bm.MULT_RANGE[1]) if game else (0.0, 1.0)

    def read(self):
        """The settings in the window, or ValueError naming the first bad box."""
        bm = nightmare.build_mod
        units = []
        for unit in bm.UNIT_ORDER:
            row = []
            for field in bm.UNIT_FIELDS:
                try:
                    x = float(self.units[(unit, field)].get())
                    if x != int(x):
                        raise ValueError
                except ValueError:
                    raise ValueError(f"{nightmare.unit_label(unit)} {UNIT_WORDS.get(field, field)}: type a whole number") from None
                row.append(int(x))
            units.append(tuple(row))
        heroes = []
        for hero in bm.HEROES:
            row = []
            for field in bm.HERO_FIELDS:
                text = self.heroes[(hero, field)].get().strip()
                lo, hi = self.hero_range(hero, field)
                try:
                    if text and not lo - 1e-9 <= float(text) <= hi + 1e-9:
                        raise ValueError
                    row.append(nightmare.setting(hero, field, text))
                except ValueError:
                    raise ValueError(f"{hero} {HERO_WORDS.get(field, field)}: type a number from {lo:.4g} to {hi:.4g}") from None
            heroes.append(tuple(row))
        return bm.Settings(tuple(units), tuple(heroes)).checked()

    def show_code(self):
        try:
            self.code.set(self.read().code())
            self.error.set("")
        except ValueError as ex:
            self.code.set("")
            self.error.set(str(ex))

    def copy_code(self):
        self.win.clipboard_clear()
        self.win.clipboard_append(self.code.get())

    def load_code(self):
        try:
            self.load(nightmare.build_mod.Settings.from_code(self.paste.get()))
        except ValueError as ex:
            messagebox.showerror("Arcade Endless", f"Can't load that code: {ex}", parent=self.win)

    def ok(self):
        try:
            self.app.nm = self.read()
        except ValueError as ex:
            return messagebox.showerror("Arcade Endless", str(ex), parent=self.win)
        self.app.update_status()
        self.close()

    def close(self):
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()


def selftest():
    """Builds the window hidden, fills the table for every preset, mode and difficulty, and checks that edits and the
    unit mix land in the right cells; installs nothing."""
    look.prepare()
    root = tk.Tk()
    root.withdraw()
    app = App(root)

    def row(game_day):
        iid = app.tree.get_children()[game_day - 1]
        return dict(zip(app.tree["columns"], app.tree.item(iid)["values"]))

    def night(game_day):
        return app.rows[app.tree.get_children()[game_day - 1]]
    for preset in be.PRESETS.values():
        app.load(preset)
        for mode in be.MODES:
            for label in DIFFICULTY_LABELS:
                app.mode.set(mode)
                app.difficulty.set(label)
                app.refresh()
                rows = app.tree.get_children()
                assert len(rows) == be.FINAL_NIGHT_DAY + 1 and app.preset.get() != "Custom", (preset, mode, label)  # + the first day
                assert app.tree.item(rows[-1])["values"][1].startswith("Final Night")
        print(f"{preset.code()}: ok, {app.summary.get()}")
    app.load(be.PRESETS["Hard"])
    app.mode.set("Survival")
    app.difficulty.set("Normal")
    app.refresh()
    assert row(1)["night"] == "First day" and row(2)["night"] == "Pester" and row(7)["night"] == "Death Night 1", (row(1), row(7))
    app.set_count(night(22), "Crusher", 40)
    app.set_count(night(7), "Crusher", 12)
    app.mix["Crawler"].set(0.0)
    app.refresh()
    assert row(22)["Crusher"] == f"40{EDITED}" and row(22)["Crawler"] == "" and row(7)["Crusher"] == f"12{EDITED}", (row(22), row(7))
    assert app.preset.get() == "Custom" and be.Settings.from_code(app.code.get()) == app.settings()
    app.difficulty.set("Forgiving")
    app.refresh()
    app.set_count(night(3), "Crusher", 1)  # 0.2x: needs a count of 5
    app.refresh()
    assert row(3)["Crusher"] == f"1{EDITED}" and app.edits[("P", 2, "Crusher")] == 5, (row(3), app.edits)
    app.difficulty.set("Normal")
    app.refresh()
    app.reset(app.night_keys(night(7)))
    app.refresh()
    assert row(7)["Crusher"] == "" and len(app.edits) == 2
    print("edits and unit mix: ok,", app.edit_info.get(), "left")
    assert nightmare.AVAILABLE, "NightmarePOC's builder isn't packed in"
    win = NightmareWindow(app, show=False)
    assert win.read() == app.nm
    defaults = nightmare.defaults()
    win.load(defaults)
    assert win.read() == defaults and win.code.get() == defaults.code()
    win.units[("Crawler", "food")].set("5")
    win.units[("Crawler", "villagers")].set("1")
    game = nightmare.game_values()
    assert win.heroes[("Vizargo", "health")].get() == f"{game['Vizargo']['health']:g}"  # the real value, the game's own
    win.heroes[("Vizargo", "health")].set(f"{game['Vizargo']['health'] * 2:g}")
    win.heroes[("Cyrus", "ranged")].set(f"{game['Cyrus']['ranged'] * 1.5:g}")
    win.heroes[("Aelis", "armour")].set("7")
    custom = win.read()
    assert (custom.unit("Crawler")["food"], custom.unit("Crawler")["villagers"], custom.hero("Vizargo")["health"],
            custom.hero("Cyrus")["ranged"], custom.hero("Aelis")["armour"]) == (5, 1, 2.0, 1.5, 7.0), custom
    win.game_heroes()
    assert win.read().heroes == defaults.heroes == (nightmare.build_mod.GAME_HERO,) * len(nightmare.build_mod.HEROES)
    win.load(custom)
    assert win.read() == custom
    assert nightmare.build_mod.Settings.from_code(win.code.get()) == custom
    win.units[("Crawler", "gold")].set("lots")
    assert win.code.get() == "" and "Crawler gold" in win.error.get(), win.error.get()
    win.close()
    print("NightmarePOC window: ok,", nightmare.describe(custom))
    out = os.path.join(home.DIST, "selftest", "NightmarePOC_P.pak")  # the validator wants the real file name
    for name, settings in (("defaults", defaults), ("custom", custom)):
        result, log = quietly(nightmare.build, settings, out)
        assert not failed(result), (result, log[-1500:])
        result, log = quietly(nightmare.check, settings, out)
        assert result == 0, [line for line in log.splitlines() if "FAIL" in line]
        print(f"NightmarePOC {name}: builds and validates, match code {exe_patch.match_code(out)}")
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    installed = exe_patch.match_code(nightmare.INSTALLED) if os.path.exists(nightmare.INSTALLED) else "not installed"
    print(f"NightmarePOC installed: {installed}")
    print("status:", app.status.get())
    root.destroy()


def no_game():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Arcade Endless", "Can't find Age of Darkness: Final Stand here.\n\nPut ArcadeEndless.exe in the game's "
                         "folder, or a folder inside it (for example ...\\steamapps\\common\\Age of Darkness - Final Stand"
                         f"\\_ArcadeEndless), and run it from there.\n\nLooked for:\n{os.path.join(home.GAME, home.GAME_PAK)}")
    root.destroy()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # a packed, windowed exe has no console: write the results to dist\selftest.log instead
        if sys.stdout is None:
            os.makedirs(home.DIST, exist_ok=True)
        # line-buffered and closed before exiting: Tk's teardown can end the process before Python flushes files
        log = open(os.path.join(home.DIST, "selftest.log"), "w", encoding="utf-8", buffering=1) if sys.stdout is None else None
        with contextlib.redirect_stdout(log or sys.stdout):
            try:
                selftest()
                code = 0
            except Exception:
                import traceback
                traceback.print_exc(file=sys.stdout)
                code = 1
        if log:
            log.close()
        sys.exit(code)
    elif not home.FOUND:
        no_game()
    else:
        look.prepare()
        root = tk.Tk()
        App(root)
        root.mainloop()

"""Build dist/ArcadeEndless_P.pak from the installed game's own pak (read-only).

Arcade Endless: a Survival or multiplayer run lasts until the Final Night on day FINAL_NIGHT_DAY (normally
day 18-33), and it keeps getting harder: every night without a Death Night brings a pester wave that grows
day by day, with surge nights on top, and each Death Night is bigger, higher-tier and brings elite bosses.

Changes, all data-only; the campaign keeps the game's own curves and waves:
  1. Pester waves: seven new curves (MOD_DIR/AE_Pester_*) with one flat step per day (PESTER), and every
     SURGE_EVERY-th night from SURGE_FROM a surge (SURGE_MULT, Crushers SURGE_CRUSHER_MULT).
     WaveConstants_BP and MPWaveConstants_BP import them instead of /Game/Curves/Pester_*.
  2. Death Night days: DEATH_NIGHT_DAYS, and the Final Night on FINAL_NIGHT_DAY for every difficulty.
     UWaveConstants::PostLoad rebuilds the day map from DT_WaveDays, and that table can't move the Final Night
     (ParseData always puts it 2 days after Death Night 5), so MajorWaveDayTable is cleared: ParseData returns
     early and the game uses the stored ParsedDifficultyToMajorWaveDay, which is rewritten.
  3. Death Nights and the Final Night: more units (DEATH_NIGHT_MULT / FINAL_NIGHT_MULT), at least tier
     DEATH_NIGHT_TIER / FINAL_NIGHT_TIER, plus elite bosses for everyone (ELITES; normally only Hardship gets
     them). No night spawns more units than the biggest one the base game already has. Hardship bosses unchanged.
  4. Main menu: the credit (tools/menu_credit.py) in place of the old Early Access title. NightmarePOC ships the
     same credit in its Menu_UI, and with both installed the game uses NightmarePOC's.

Pester waves always spawn tier 1 (__generate_pester_waves hardcodes it) and only the seven curve types.

The game only creates pester waves for days 1-44 (a hardcoded 45-day duration). tools/exe_patch.py raises that
to exe_patch.PATCH_DAYS; without it, the nights after day 44 bring no pester waves.
"""
import base64
import copy
import hashlib
import json
import math
import os
import struct
import sys
import zlib
from dataclasses import dataclass, fields

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exe_patch  # noqa: E402
import home  # noqa: E402
import menu_credit  # noqa: E402
import pak  # noqa: E402
import ue_pkg as ue  # noqa: E402

GAME = home.GAME
BASE_PAK = os.path.join(GAME, home.GAME_PAK)
OUT_PAK = os.path.join(home.DIST, "ArcadeEndless_P.pak")

MODES = ("Survival", "Multiplayer")
WAVE_CONSTANTS = {"Survival": "Achilles/Content/Code/WaveConstants_BP",
                  "Multiplayer": "Achilles/Content/Code/MultiplayerConstants/MPWaveConstants_BP"}
CURVE_DIR = "Achilles/Content/Curves"
DIFFICULTY_CONSTANTS = "Achilles/Content/DataAssets/DifficultyModifiers/DifficultyModifierConstants"
MOD_DIR = "/Game/Mods/ArcadeEndless"

PESTER_LAST_DAY = exe_patch.PATCH_DAYS - 1   # the patched game generates pester waves for days 1..PATCH_DAYS-1
# Days of the Death Nights that have waves, per difficulty (as in the base game, a little later when easier).
# Multiplayer has three; its map entries for Death Nights 4 and 5 have no waves and stay 4 and 2 days before the
# Final Night, where the base game has them.
DEATH_NIGHT_DAYS = {
    "Survival": {"VERY_EASY": (7, 16, 27, 40, 55), "EASY": (7, 16, 27, 40, 55),
                 "MEDIUM": (6, 14, 24, 36, 50), "HARD": (6, 14, 24, 36, 50),
                 "VERY_HARD": (5, 12, 21, 32, 45), "UNBEATABLE": (5, 12, 21, 32, 45)},
    "Multiplayer": {"VERY_EASY": (8, 19, 35), "EASY": (7, 18, 33), "MEDIUM": (6, 16, 30),
                    "HARD": (6, 15, 29), "VERY_HARD": (6, 15, 28), "UNBEATABLE": (5, 14, 27)},
}
# The "Hard" preset; the other presets and the settings app scale these (see configure).
# Unit counts of the regular spawns, capped so no night outgrows the base game's biggest (Survival Death
# Night 5 on Unbeatable, ~22k).
HARD_DEATH_NIGHT_MULT = {"Survival": (1.0, 1.25, 1.5, 1.75, 2.0), "Multiplayer": (1.0, 1.5, 2.0)}
HARD_FINAL_NIGHT_MULT = {"Survival": 2.0, "Multiplayer": 4.0}  # base Final Night = a copy of DN4 (Survival) / DN2 (MP)
# Lowest tier of the regular spawns. Regular horde units only have stats for tiers 1-4 (5+ have 0 health) and
# the base game never uses 4, so 3 is the top.
HARD_DEATH_NIGHT_TIER = {"Survival": (1, 2, 3, 3, 3), "Multiplayer": (1, 2, 3)}
HARD_FINAL_NIGHT_TIER = 3
MAX_TIER = 3
# Elite bosses (same stats at every tier) added to the regular spawns: (elite, counts very easy..unbeatable).
ELITE_TYPES = {"crawler": 16, "axeman": 17, "spearman": 18, "wraith": 21, "spitter": 22, "crusher": 23, "festerling": 55}
_DN2 = [("crawler", (0, 0, 1, 1, 1, 2))]
_DN3 = [("axeman", (1, 1, 2, 2, 3, 3)), ("crusher", (0, 1, 1, 2, 2, 3))]
_DN4 = [("crusher", (1, 2, 3, 4, 5, 6)), ("spitter", (1, 1, 2, 2, 3, 4)), ("wraith", (1, 1, 2, 2, 3, 4))]
_DN5 = [("crusher", (2, 3, 5, 6, 8, 10)), ("spitter", (1, 2, 3, 4, 5, 6)), ("wraith", (1, 2, 3, 4, 5, 6)),
        ("spearman", (1, 2, 3, 4, 5, 6))]
_FINAL = [("crusher", (4, 6, 10, 12, 16, 20)), ("spitter", (2, 4, 6, 8, 10, 12)), ("wraith", (2, 4, 6, 8, 10, 12)),
          ("axeman", (2, 4, 6, 8, 10, 12)), ("festerling", (1, 2, 3, 4, 5, 6))]
HARD_ELITES = {"Survival": ([], _DN2, _DN3, _DN4, _DN5), "Multiplayer": ([], _DN3, _DN5)}
HARD_FINAL_ELITES = _FINAL
# The horde's regular units: their pester curve (/Game/Curves/Pester_<curve>_Spawn) and AGENT_TYPE::ENEMY_AGENT_TYPE_<n>
UNITS = ("Crawler", "Axeman", "Spearman", "Festerling", "Wraith", "Spitter", "Crusher")
CURVES = {"Crawler": "Crawler", "Axeman": "Axemen", "Spearman": "Spearmen", "Festerling": "Festerling",
          "Wraith": "Wraith", "Spitter": "Spitter", "Crusher": "Crusher"}
ENEMY_TYPES = {"Crawler": 0, "Axeman": 1, "Spearman": 2, "Wraith": 5, "Spitter": 6, "Crusher": 7, "Festerling": 9}
# Pester units per night from `start` on: base + linear*n + quadratic*n^2, n = day - start.
# Custom difficulty's "harassment wave" multiplier still scales these.
PESTER = {  # unit: (start day, base, linear, quadratic)
    "Crawler": (1, 8, 2.5, 0.035),
    "Axeman": (3, 2, 0.6, 0.008),
    "Spearman": (4, 2, 0.5, 0.007),
    "Festerling": (8, 1, 0.15, 0.002),
    "Wraith": (10, 1, 0.15, 0.002),
    "Spitter": (12, 1, 0.15, 0.002),
    "Crusher": (12, 1, 0.08, 0.0025),
}
# Safety caps; Settings.pester_cap / night_cap may raise them (the app warns). A night over its cap has every
# count scaled down together to fit.
# Pester waves seem to spawn all at once (their spawn group has no spread-out time, unlike Death Nights).
PESTER_NIGHT_CAP = 6000
# The base game's biggest night (Survival Death Night 5 on Unbeatable); build() checks the game data still says so.
BASE_NIGHT_CAP = 21951
CAP_MAX = 100_000  # the most any cap or edit may ask for
SURGE_FROM = 20  # first possible surge night; none if it's a Death Night or the day after one
DIFFICULTY_FIELDS = ("very_easy", "easy", "medium", "hard", "very_hard", "unbeatable")


def _rows(edits):
    return tuple(sorted(tuple(e) for e in edits))


@dataclass(frozen=True)
class Settings:
    final_night_day: int = 180    # FINAL_NIGHT_RANGE
    pester: float = 1.0           # pester wave size, x the PESTER table
    surge_every: int = 5          # a surge every N nights from SURGE_FROM; 0 = no surges
    surge: float = 2.0            # surge night size (Crushers get 1.5x this)
    death_night_growth: float = 1.0  # 0 = base-game sizes, 1 = the Hard table, 2 = twice the growth...
    tiers: bool = True            # later Death Nights use higher tiers (HARD_DEATH_NIGHT_TIER)
    elites: float = 1.0           # elite bosses, x the Hard table; 0 = none
    mix: tuple = (1.0,) * len(UNITS)  # pester and surge nights: x per unit, UNITS order
    pester_edits: tuple = ()      # ((day, unit, count), ...): exact counts on pester/surge nights, both modes
    night_edits: tuple = ()       # ((mode, night, difficulty field, unit, count), ...): night 1-5 Death Night, 0 Final
    pester_cap: int = PESTER_NIGHT_CAP  # most units in one pester night
    night_cap: int = BASE_NIGHT_CAP     # most units in one Death Night or the Final Night

    def __post_init__(self):  # one canonical form, so equal settings compare and encode equal
        object.__setattr__(self, "mix", tuple(float(x) for x in self.mix))
        object.__setattr__(self, "pester_edits", _rows(self.pester_edits))
        object.__setattr__(self, "night_edits", _rows(self.night_edits))

    def code(self):
        """Text that rebuilds exactly these settings (and so the same pak)."""
        data = json.dumps([getattr(self, f.name) for f in fields(self)], separators=(",", ":"))
        return "AE2-" + base64.urlsafe_b64encode(zlib.compress(data.encode(), 9)).decode().rstrip("=")

    @staticmethod
    def from_code(text):
        try:
            raw = text.strip()
            assert raw.startswith("AE2-")
            data = json.loads(zlib.decompress(base64.urlsafe_b64decode(raw[4:] + "=" * (-len(raw[4:]) % 4))))
            assert len(data) <= len(fields(Settings))  # codes from before a field existed get its default
            return Settings(*data).checked()
        except Exception as ex:
            raise ValueError("not an Arcade Endless settings code") from ex

    def checked(self):
        lo, hi = FINAL_NIGHT_RANGE
        assert lo <= self.final_night_day <= hi, f"Final Night day must be {lo}-{hi}"
        assert 0 < self.pester <= 4 and 0 <= self.surge_every <= 10 and 1 <= self.surge <= 5
        assert 0 <= self.death_night_growth <= 3 and 0 <= self.elites <= 5
        assert len(self.mix) == len(UNITS) and all(0 <= x <= 5 for x in self.mix), "unit mix must be 0-5"
        assert 100 <= self.pester_cap <= CAP_MAX and 1000 <= self.night_cap <= CAP_MAX, f"caps must be at most {CAP_MAX:,}"
        for day, unit, n in self.pester_edits:
            assert 1 <= day <= PESTER_LAST_DAY and unit in UNITS and 0 <= n <= self.pester_cap, (day, unit, n)
        for mode, night, d, unit, n in self.night_edits:
            assert mode in MODES and 0 <= night <= len(HARD_DEATH_NIGHT_MULT[mode]) and d in DIFFICULTY_FIELDS, (mode, night, d)
            assert unit in UNITS and 0 <= n <= CAP_MAX, (unit, n)
        assert len({e[:2] for e in self.pester_edits}) == len(self.pester_edits), "two edits for one pester cell"
        assert len({e[:4] for e in self.night_edits}) == len(self.night_edits), "two edits for one Death Night cell"
        return self

    def over_limits(self):
        """Warnings for caps raised past what the game is known to handle (empty if none)."""
        out = []
        if self.night_cap > BASE_NIGHT_CAP:
            out.append(f"Death Night cap {self.night_cap:,} is above the game's biggest night ({BASE_NIGHT_CAP:,} units).")
        if self.pester_cap > PESTER_NIGHT_CAP:
            out.append(f"Pester night cap {self.pester_cap:,} is above {PESTER_NIGHT_CAP:,}; pester waves seem to spawn all at once.")
        return out


def heavy_mix(x):
    """Unit mix with Festerlings, Wraiths, Spitters and Crushers at x."""
    return tuple(x if u in ("Festerling", "Wraith", "Spitter", "Crusher") else 1.0 for u in UNITS)


# after every Death Night (day 55 at the latest, + the day after) and before the last pester day and the MP
# no-wave entries' room (4 days)
FINAL_NIGHT_RANGE = (60, PESTER_LAST_DAY - 4)
PRESETS = {
    "Tough": Settings(pester=0.6, mix=heavy_mix(0.6), surge_every=7, surge=1.5, death_night_growth=0.5, tiers=False, elites=0.5),
    "Hard": Settings(),
    "Brutal": Settings(pester=1.5, mix=heavy_mix(1.5), surge_every=4, surge=2.5, death_night_growth=1.5, elites=2.0),
    "Apocalypse": Settings(pester=2.0, mix=heavy_mix(2.5), surge_every=3, surge=3.0, death_night_growth=2.0, elites=3.0),
}


def configure(s):
    """Set the module's tables from player settings; every build and validation step reads them."""
    global SETTINGS, FINAL_NIGHT_DAY, SURGE_EVERY, SURGE_MULT, SURGE_CRUSHER_MULT, DEATH_NIGHT_MULT, FINAL_NIGHT_MULT
    global DEATH_NIGHT_TIER, FINAL_NIGHT_TIER, ELITES, FINAL_ELITES, PESTER_EDITS, NIGHT_EDITS, PESTER_CAP, NIGHT_CAP
    SETTINGS = s.checked()
    FINAL_NIGHT_DAY = s.final_night_day
    PESTER_CAP, NIGHT_CAP = s.pester_cap, s.night_cap
    SURGE_EVERY, SURGE_MULT, SURGE_CRUSHER_MULT = s.surge_every, s.surge, s.surge * 1.5
    grow = lambda m: 1.0 + s.death_night_growth * (m - 1.0)  # noqa: E731
    DEATH_NIGHT_MULT = {m: tuple(grow(x) for x in v) for m, v in HARD_DEATH_NIGHT_MULT.items()}
    FINAL_NIGHT_MULT = {m: grow(v) for m, v in HARD_FINAL_NIGHT_MULT.items()}
    DEATH_NIGHT_TIER = HARD_DEATH_NIGHT_TIER if s.tiers else {m: (1,) * len(v) for m, v in HARD_DEATH_NIGHT_TIER.items()}
    FINAL_NIGHT_TIER = HARD_FINAL_NIGHT_TIER if s.tiers else 1

    def more(elites):
        out = [(e, tuple(round_half_up(c * s.elites) for c in counts)) for e, counts in elites]
        return [(e, c) for e, c in out if any(c)]
    ELITES = {m: tuple(more(night) for night in v) for m, v in HARD_ELITES.items()}
    FINAL_ELITES = more(HARD_FINAL_ELITES)
    PESTER_EDITS = {(day, unit): n for day, unit, n in s.pester_edits}
    NIGHT_EDITS = {}  # (mode, night): {difficulty field: {unit: count}}
    for mode, night, d, unit, n in s.night_edits:
        NIGHT_EDITS.setdefault((mode, night), {}).setdefault(d, {})[unit] = n


FINAL_NIGHT = "DeathNight::Final_Night"
INNER_TAG = 8 + 8 + 4 + 4 + 8 + 16 + 1  # array-of-struct inner FPropertyTag: name, type, size, index, struct, guid, flag
RICH_CURVE_KEY = struct.Struct("<BBB6f")  # InterpMode, TangentMode, TangentWeightMode, Time, Value, 4 tangents
RCIM_CONSTANT = 1


def game_to_pak(path):
    return "Achilles/Content/" + path[len("/Game/"):]


def round_half_up(x):
    return int(math.floor(x + 0.5))


class Builder:
    def __init__(self):
        self.base = pak.PakReader(BASE_PAK)
        self.out = {}

    def load_base(self, path):
        return ue.Package(self.base.read(path + ".uasset"), self.base.read(path + ".uexp"))

    def save(self, path, pkg):
        uasset, uexp = pkg.write()
        again = ue.Package(uasset, uexp)              # must re-parse...
        assert again.write() == (uasset, uexp), path   # ...and round-trip exactly
        self.out[path + ".uasset"] = uasset
        self.out[path + ".uexp"] = uexp
        return again


def rename(pkg, old, new):
    i = pkg.names.index(old)
    pkg.names[i] = new
    pkg.name_hashes[i] = ue.name_hashes(new)


def curve_path(unit):
    return f"{MOD_DIR}/AE_Pester_{CURVES[unit]}_Spawn"


# ---------------------------------------------------------------------------- tagged-property containers
def read_struct_array(pkg, prop):
    """ArrayProperty<StructProperty> of a tagged struct -> (inner tag bytes, [element props])."""
    v = prop.value
    (n,) = struct.unpack_from("<i", v, 0)
    tag, o = v[4:4 + INNER_TAG], 4 + INNER_TAG
    elems = []
    for _ in range(n):
        props, o = ue.read_props(pkg, v, o)
        elems.append(props)
    assert o == len(v)
    return tag, elems


def write_struct_array(pkg, prop, tag, elems):
    data = b"".join(ue.write_props(pkg, e) for e in elems)
    prop.value = struct.pack("<i", len(elems)) + tag[:16] + struct.pack("<i", len(data)) + tag[20:] + data


def read_map(pkg, prop, value_reader):
    """MapProperty with FName-encoded (enum) keys -> [(key name ref, value)]."""
    v = prop.value
    removed, n = struct.unpack_from("<ii", v, 0)
    assert removed == 0
    o, out = 8, []
    for _ in range(n):
        key = struct.unpack_from("<ii", v, o)
        val, o = value_reader(v, o + 8)
        out.append((key, val))
    assert o == len(v)
    return out


def write_map(prop, entries, value_writer):
    prop.value = struct.pack("<ii", 0, len(entries)) + b"".join(struct.pack("<ii", *k) + value_writer(x) for k, x in entries)


def struct_reader(pkg):
    return lambda v, o: ue.read_props(pkg, v, o)


def int_reader(v, o):
    return struct.unpack_from("<i", v, o)[0], o + 4


def named(pkg, props):
    return {pkg.name(p.name): p for p in props}


def get_int(p):
    return struct.unpack("<i", p.value)[0]


def set_int(p, x):
    p.value = struct.pack("<i", x)


def cdo_props(pkg):
    cdo = next(e for e in pkg.exports if pkg.name(e.object_name).startswith("Default__"))
    props, end = ue.read_props(pkg, cdo.data)
    return cdo, props, end


# ---------------------------------------------------------------------------- 1. pester curves
def is_surge(day):
    return SURGE_EVERY > 0 and day >= SURGE_FROM and (day - SURGE_FROM) % SURGE_EVERY == 0


def pester_base(unit, day):
    """The PESTER table's count, before settings and surges."""
    start, base, linear, quadratic = PESTER[unit]
    n = day - start
    return 0 if n < 0 else base + linear * n + quadratic * n * n


def distribute(total, weights):
    """total split in proportion to weights (all to the first if they're all 0); leftovers to the largest remainders."""
    if sum(weights) == 0:
        return [total] + [0] * (len(weights) - 1)
    shares = [divmod(total * w, sum(weights)) for w in weights]
    out = [q for q, _ in shares]
    for i in sorted(range(len(weights)), key=lambda i: -shares[i][1])[:total - sum(out)]:
        out[i] += 1
    return out


def pester_raw(day):
    """{unit: count} of one pester night before PESTER_CAP: size, unit mix and surge, or the player's edit."""
    counts = {}
    for unit, mix in zip(UNITS, SETTINGS.mix):
        v = pester_base(unit, day) * SETTINGS.pester * mix
        if is_surge(day):
            v *= SURGE_CRUSHER_MULT if unit == "Crusher" else SURGE_MULT
        counts[unit] = PESTER_EDITS.get((day, unit), round_half_up(v))
    return counts


def pester_night(day):
    """{unit: count} of one pester night: pester_raw scaled down together to exactly PESTER_CAP if over."""
    counts = pester_raw(day)
    if sum(counts.values()) <= PESTER_CAP:
        return counts
    return dict(zip(counts, distribute(PESTER_CAP, list(counts.values()))))


def pester_value(unit, day):
    return pester_night(day)[unit]


def pester_multipliers(b):
    """{difficulty field: multiplier} the game applies to every pester count, in fixed point (x1024).

    When you press Play (UGameSettingsUI::PlayPressed, and the multiplayer one) the game looks the Death Night
    difficulty up in DifficultyModifierConstants.spawn_multipliers_for_density_setting and stores
    roundf(x * 1024) as FLevelData.harassment_wave_multiplier; __generate_pester_waves multiplies by it.
    """
    pkg = b.load_base(DIFFICULTY_CONSTANTS)
    props, _ = ue.read_props(pkg, pkg.exports[0].data)
    table = read_map(pkg, named(pkg, props)["spawn_multipliers_for_density_setting"],
                     lambda v, o: (struct.unpack_from("<f", v, o)[0], o + 4))
    return {pkg.name(k).split("::")[1].lower(): round_half_up(x * 1024) for k, x in table}  # x*1024 is exact in float


def spawned(count, multiplier):
    """Units the game spawns from a pester count at a fixed-point multiplier (rounded down)."""
    return count * multiplier >> 10


def count_for(units, multiplier):
    """The smallest pester count the game turns into at least `units` units at this multiplier."""
    return -(-units * 1024 // multiplier)


def pester_keys(unit):
    """Constant-interpolation steps centred on each whole day, so V(day) is exact wherever the game samples it.

    The game bakes 8 samples per key (first..last key time) and reads the curve in looping mode: day t maps to
    t mod (last - first), so the first key must sit at 0 and the last day's step must end after PESTER_LAST_DAY.
    """
    keys = [(0.0, pester_value(unit, 0))]
    keys += [(d - 0.5, pester_value(unit, d)) for d in range(1, PESTER_LAST_DAY + 1)]
    keys.append((PESTER_LAST_DAY + 0.5, pester_value(unit, PESTER_LAST_DAY)))
    return keys


def build_curves(b):
    for unit in UNITS:
        src = f"{CURVE_DIR}/Pester_{CURVES[unit]}_Spawn"
        pkg = b.load_base(src)
        rename(pkg, "/Game/" + src[len("Achilles/Content/"):], curve_path(unit))
        rename(pkg, f"Pester_{CURVES[unit]}_Spawn", curve_path(unit).rsplit("/", 1)[1])
        pkg.s["guid"] = hashlib.md5(curve_path(unit).encode()).digest()
        e = pkg.exports[0]
        props, end = ue.read_props(pkg, e.data)
        (fc,) = props
        sub, sub_end = ue.read_props(pkg, fc.value)
        assert [pkg.name(s.name) for s in sub] == ["Keys"], src
        keys = pester_keys(unit)
        data = b"".join(RICH_CURVE_KEY.pack(RCIM_CONSTANT, 0, 0, t, float(v), 0, 0, 0, 0) for t, v in keys)
        tag = sub[0].value[4:4 + INNER_TAG]
        sub[0].value = struct.pack("<i", len(keys)) + tag[:16] + struct.pack("<i", len(data)) + tag[20:] + data
        fc.value = ue.write_props(pkg, sub) + fc.value[sub_end:]
        e.data = ue.write_props(pkg, props) + e.data[end:]
        b.save(game_to_pak(curve_path(unit)), pkg)
        sample = ", ".join(f"d{d}={pester_value(unit, d)}" for d in (10, 51, 101, PESTER_LAST_DAY))
        print(f"  {curve_path(unit).rsplit('/', 1)[1]}: {len(keys)} keys, {sample}")


# ---------------------------------------------------------------------------- 2. + 3. Death Nights
def night_days(mode, difficulty, nights):
    """{night enum name: day} for one difficulty, in the map's own key order."""
    waves = DEATH_NIGHT_DAYS[mode][difficulty]
    extra = [n for i, n in enumerate(nights) if i >= len(waves) and n != FINAL_NIGHT]
    out = {}
    for i, n in enumerate(nights):
        if n == FINAL_NIGHT:
            out[n] = FINAL_NIGHT_DAY
        elif i < len(waves):
            out[n] = waves[i]
        else:
            out[n] = FINAL_NIGHT_DAY - 2 * (len(extra) - extra.index(n))
    days = [out[n] for n in nights]
    assert all(b2 - a >= 2 for a, b2 in zip(days, days[1:])) and days[-1] == FINAL_NIGHT_DAY < PESTER_LAST_DAY, (mode, difficulty, days)
    return out


def night_totals(pkg, night, keys=("Spawns", "HardshipGrimCommandSpawns")):
    """{difficulty field: units} of a WaveInfo's spawns (regular spawns plus Hardship bosses by default)."""
    out = {}
    for g in read_struct_array(pkg, named(pkg, night)["Groups"])[1]:
        for key in keys:
            if key in named(pkg, g):
                for s in read_struct_array(pkg, named(pkg, g)[key])[1]:
                    for _, per in read_map(pkg, named(pkg, s)["AmountWithDifficultyTiers"], struct_reader(pkg)):
                        for p in per:
                            out[pkg.name(p.name)] = out.get(pkg.name(p.name), 0) + get_int(p)
    return out


def final_wave(pkg, props):
    """(FinalStandWave props, its Wave prop, the Wave's WaveInfo props)"""
    final, _ = ue.read_props(pkg, named(pkg, props)["FinalStandWave"].value)
    wave = named(pkg, final)["Wave"]
    return final, wave, ue.read_props(pkg, wave.value)[0]


def base_night_cap(b):
    """The most units any base-game Death Night or Final Night spawns, over every mode and difficulty."""
    cap = 0
    for mode in MODES:
        pkg = b.load_base(WAVE_CONSTANTS[mode])
        _, props, _ = cdo_props(pkg)
        nights = read_struct_array(pkg, named(pkg, props)["DeathNightWaves"])[1] + [final_wave(pkg, props)[2]]
        cap = max(cap, *(max(night_totals(pkg, n).values()) for n in nights))
    return cap


def tier_name(tier):
    return f"AGENT_TYPE_VARIANT::TIER_{tier}"


def tier_of(name):
    return int(name.rsplit("_", 1)[1])


def enemy_of(pkg, type_prop):
    return int(ue.describe(pkg, type_prop).rsplit("_", 1)[1])


UNIT_OF_ENEMY = {n: u for u, n in ENEMY_TYPES.items()}


def spawn_entry(pkg, template, enemy, tier, counts):
    """A copy of a regular spawn entry that spawns `counts` ({difficulty field: n}) of ENEMY_AGENT_TYPE_<enemy>."""
    entry = [copy.copy(p) for p in template]
    by = named(pkg, entry)
    by["Type"].value = struct.pack("<ii", *pkg.name_ref(f"AGENT_TYPE::ENEMY_AGENT_TYPE_{enemy}"))
    ((_, per),) = read_map(pkg, by["AmountWithDifficultyTiers"], struct_reader(pkg))
    for p in per:
        set_int(p, counts.get(pkg.name(p.name), 0))
    write_map(by["AmountWithDifficultyTiers"], [(pkg.name_ref(tier_name(tier)), per)], lambda x: ue.write_props(pkg, x))
    return entry


def night_amounts(base, units, mult, edits, room):
    """One difficulty's regular-spawn counts: base x mult, edited units' totals spread over their entries in
    proportion to base, then everything floored down together if the night would pass room. (counts, capped)"""
    new = [int(math.floor(b * mult + 1e-6)) for b in base]
    for unit, n in edits.items():
        idx = [i for i, u in enumerate(units) if u == unit]
        for i, v in zip(idx, distribute(n, [base[i] for i in idx])):
            new[i] = v
    if sum(new) <= room:
        return new, False
    f = room / sum(new)
    return [int(math.floor(v * f + 1e-6)) for v in new], True


def patch_night(pkg, night, mult, tier, elites, cap, label, edits):
    """Scale and re-tier a WaveInfo's regular spawns, apply the player's count edits ({difficulty field: {unit: n}};
    a unit the night lacks gets its own entry), fit the cap and add elites, in place. Returns the capped difficulties."""
    before = night_totals(pkg, night)
    bosses = night_totals(pkg, night, ("HardshipGrimCommandSpawns",))
    g_tag, (group,) = read_struct_array(pkg, named(pkg, night)["Groups"])
    s_tag, spawns = read_struct_array(pkg, named(pkg, group)["Spawns"])
    template = next(s for s in spawns
                    if ue.describe(pkg, named(pkg, s)["SpawnTrigger"]) == "SPAWN_GROUP_TRIGGER::LINEAR_TIME_ENTIRE_GROUP")
    tiers = [min(MAX_TIER, max(tier_of(pkg.name(read_map(pkg, named(pkg, s)["AmountWithDifficultyTiers"], struct_reader(pkg))[0][0])), tier))
             for s in spawns]
    night_tier = max(tiers)
    present = {UNIT_OF_ENEMY[enemy_of(pkg, named(pkg, s)["Type"])] for s in spawns}
    for unit in UNITS:
        if unit not in present and any(unit in e for e in edits.values()):
            spawns.append(spawn_entry(pkg, template, ENEMY_TYPES[unit], night_tier, {}))
            tiers.append(night_tier)
    rows = []  # (amount map prop, [per-difficulty props], unit)
    for s in spawns:
        by = named(pkg, s)
        ((_, per),) = read_map(pkg, by["AmountWithDifficultyTiers"], struct_reader(pkg))
        rows.append((by["AmountWithDifficultyTiers"], per, UNIT_OF_ENEMY[enemy_of(pkg, by["Type"])]))
    capped = set()
    for i, d in enumerate(DIFFICULTY_FIELDS):
        cells = [next(p for p in per if pkg.name(p.name) == d) for _, per, _ in rows]
        room = max(0, cap - sum(c[i] for _, c in elites) - bosses.get(d, 0))
        counts, over = night_amounts([get_int(c) for c in cells], [u for _, _, u in rows], mult, edits.get(d, {}), room)
        for c, n in zip(cells, counts):
            set_int(c, n)
        if over:
            capped.add(d)
    for (prop, per, _), t in zip(rows, tiers):
        write_map(prop, [(pkg.name_ref(tier_name(t)), per)], lambda x: ue.write_props(pkg, x))
    spawns += [spawn_entry(pkg, template, ELITE_TYPES[e], 1, dict(zip(DIFFICULTY_FIELDS, c))) for e, c in elites]
    write_struct_array(pkg, named(pkg, group)["Spawns"], s_tag, spawns)
    write_struct_array(pkg, named(pkg, night)["Groups"], g_tag, [group])
    after = night_totals(pkg, night)
    names = ", ".join(e for e, _ in elites) or "none"
    print(f"  {label}: x{mult:g}, tier {tier}+, elites: {names}{', edited' if edits else ''}; medium {before['medium']} -> "
          f"{after['medium']}, unbeatable {before['unbeatable']} -> {after['unbeatable']} units")
    return capped


def patch_wave_constants(b, mode, cap):
    path = WAVE_CONSTANTS[mode]
    pkg = b.load_base(path)
    for unit in UNITS:
        rename(pkg, f"/Game/Curves/Pester_{CURVES[unit]}_Spawn", curve_path(unit))
        rename(pkg, f"Pester_{CURVES[unit]}_Spawn", curve_path(unit).rsplit("/", 1)[1])
    cdo, props, end = cdo_props(pkg)
    by = named(pkg, props)

    set_int(by["MajorWaveDayTable"], 0)  # ParseData returns early; LastMajorWaveDayTable is only compared to it

    m = by["ParsedDifficultyToMajorWaveDay"]
    entries = read_map(pkg, m, struct_reader(pkg))
    for key, parsed in entries:
        days = named(pkg, parsed)["MapDeathNightDay"]
        nd = read_map(pkg, days, int_reader)
        wanted = night_days(mode, pkg.name(key).split("::")[1], [pkg.name(k) for k, _ in nd])
        write_map(days, [(k, wanted[pkg.name(k)]) for k, _ in nd], lambda x: struct.pack("<i", x))
    write_map(m, entries, lambda x: ue.write_props(pkg, x))

    tag, nights = read_struct_array(pkg, by["DeathNightWaves"])
    n = len(next(iter(DEATH_NIGHT_DAYS[mode].values())))
    assert len(nights) == n == len(DEATH_NIGHT_MULT[mode]) == len(DEATH_NIGHT_TIER[mode]) == len(ELITES[mode]), mode
    for k, night in enumerate(nights):
        b.capped[(mode, k + 1)] = patch_night(pkg, night, DEATH_NIGHT_MULT[mode][k], DEATH_NIGHT_TIER[mode][k], ELITES[mode][k],
                                              cap, f"{mode:11} Death Night {k + 1}", NIGHT_EDITS.get((mode, k + 1), {}))
    write_struct_array(pkg, by["DeathNightWaves"], tag, nights)

    final, wave, info = final_wave(pkg, props)
    b.capped[(mode, 0)] = patch_night(pkg, info, FINAL_NIGHT_MULT[mode], FINAL_NIGHT_TIER, FINAL_ELITES, cap,
                                      f"{mode:11} Final Night  ", NIGHT_EDITS.get((mode, 0), {}))
    wave.value = ue.write_props(pkg, info)
    by["FinalStandWave"].value = ue.write_props(pkg, final)

    cdo.data = ue.write_props(pkg, props) + cdo.data[end:]
    b.save(path, pkg)
    print(f"  {mode:11} {path.rsplit('/', 1)[1]}: Medium Death Nights {list(DEATH_NIGHT_DAYS[mode]['MEDIUM'])}, Final Night {FINAL_NIGHT_DAY}")


configure(PRESETS["Hard"])  # the default until a caller picks other settings


def build(settings):
    """All the mod's packages for these settings, in memory: a Builder whose .out maps pak paths to bytes."""
    configure(settings)
    assert FINAL_NIGHT_DAY < PESTER_LAST_DAY < exe_patch.MAX_DAYS
    b = Builder()
    b.capped = {}  # (mode, night: 1-5 Death Night, 0 Final): difficulty fields whose night was scaled down to the cap
    b.pester_multipliers = pester_multipliers(b)
    print(f"Settings {settings.code()}")
    print("Pester curves:")
    build_curves(b)
    assert base_night_cap(b) == BASE_NIGHT_CAP, "the game's Death Night data changed; check BASE_NIGHT_CAP"
    print(f"Death Nights and Final Night (capped at {NIGHT_CAP} units; the base game's biggest night is {BASE_NIGHT_CAP}):")
    for w in settings.over_limits():
        print("  WARNING: " + w)
    for mode in MODES:
        patch_wave_constants(b, mode, NIGHT_CAP)
    print("Main menu:")
    menu = b.load_base(menu_credit.MENU_UI)
    menu_credit.add_credit(menu)
    b.save(menu_credit.MENU_UI, menu)
    print(f"  Menu_UI {menu_credit.LABEL}: {menu_credit.CREDIT!r}")
    return b


def main(settings=PRESETS["Hard"], out=OUT_PAK):
    b = build(settings)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pak.write_pak(out, sorted(b.out.items()), seed=pak.path_hash("arcadeendless_p.pak", 0) & 0xFFFFFFFF)
    print(f"Wrote {os.path.abspath(out)} ({len(b.out)} files, {os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    # python build_endless.py [preset name | settings code]
    arg = sys.argv[1] if len(sys.argv) > 1 else "Hard"
    main(PRESETS[arg] if arg in PRESETS else Settings.from_code(arg))

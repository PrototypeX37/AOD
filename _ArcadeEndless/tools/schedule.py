"""What every night of an Arcade Endless run brings, from day 1 to the Final Night, read back from a build.

  python schedule.py [preset | settings code] [Survival|Multiplayer] [very_easy..unbeatable]   prints a CSV

Pester nights come from build_endless.pester_night (validate_endless proves the game's curve maths gives
exactly those counts), multiplied the way the game does for the difficulty asked for; Death Nights and the Final
Night are read from the built wave constants. Hardship's bosses are left out.

Days: Night.day is the game's own day number, counted from 0; its day counter shows Night.game_day (day + 1).
"""
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_endless as be  # noqa: E402
import ue_pkg as ue  # noqa: E402

UNITS = be.UNITS
ELITE_NAMES = {t: "elite " + n.capitalize() for n, t in be.ELITE_TYPES.items()}


@dataclass
class Night:
    day: int
    kind: str                                   # First day, Pester, Surge, Death Night N, Final Night, Quiet
    night: int = None                           # Death Night number for edits (1-5, 0 = Final Night), else None
    units: dict = field(default_factory=dict)  # UNITS -> count
    tier: int = 1
    elites: dict = field(default_factory=dict)  # elite name -> count
    edited: set = field(default_factory=set)   # units whose count the player set
    capped: bool = False                       # scaled down to its safety cap

    @property
    def game_day(self):
        return self.day + 1  # what the in-game day counter shows

    @property
    def total(self):
        return sum(self.units.values()) + sum(self.elites.values())

    @property
    def editable(self):
        return self.kind not in ("Quiet", "First day")


def wave_night(pkg, info, difficulty, day, kind, number):
    night = Night(day, kind, number, dict.fromkeys(UNITS, 0), tier=0)
    for g in be.read_struct_array(pkg, be.named(pkg, info)["Groups"])[1]:
        for s in be.read_struct_array(pkg, be.named(pkg, g)["Spawns"])[1]:
            by = be.named(pkg, s)
            enemy = be.enemy_of(pkg, by["Type"])
            for key, per in be.read_map(pkg, by["AmountWithDifficultyTiers"], be.struct_reader(pkg)):
                n = next(be.get_int(p) for p in per if pkg.name(p.name) == difficulty)
                if not n:
                    continue
                if enemy in ELITE_NAMES:
                    night.elites[ELITE_NAMES[enemy]] = night.elites.get(ELITE_NAMES[enemy], 0) + n
                else:
                    night.units[be.UNIT_OF_ENEMY[enemy]] += n
                    night.tier = max(night.tier, be.tier_of(pkg.name(key)))
    night.tier = night.tier or 1
    return night


def schedule(b, mode, difficulty):
    """[Night] for days 0..FINAL_NIGHT_DAY of a build (be.build's Builder), one mode, one difficulty field.
    Pester counts are what spawns at that difficulty (the game's multiplier, rounded down)."""
    multiplier = b.pester_multipliers[difficulty]
    path = be.WAVE_CONSTANTS[mode]
    pkg = ue.Package(b.out[path + ".uasset"], b.out[path + ".uexp"])
    _, props, _ = be.cdo_props(pkg)
    waves = be.read_struct_array(pkg, be.named(pkg, props)["DeathNightWaves"])[1]
    days = be.DEATH_NIGHT_DAYS[mode][difficulty.upper()]
    majors = {d: wave_night(pkg, waves[k], difficulty, d, f"Death Night {k + 1}", k + 1) for k, d in enumerate(days)}
    majors[be.FINAL_NIGHT_DAY] = wave_night(pkg, be.final_wave(pkg, props)[2], difficulty, be.FINAL_NIGHT_DAY, "Final Night", 0)
    for n in majors.values():
        n.edited = set(be.NIGHT_EDITS.get((mode, n.night), {}).get(difficulty, {}))
        n.capped = difficulty in b.capped[(mode, n.night)]
    out = [Night(0, "First day", units=dict.fromkeys(UNITS, 0))]  # the game makes pester waves from day 1 (counter: Day 2)
    for day in range(1, be.FINAL_NIGHT_DAY + 1):
        if day in majors:
            out.append(majors[day])
        elif day - 1 in majors:
            out.append(Night(day, "Quiet", units=dict.fromkeys(UNITS, 0)))  # the game sends no pester wave after a major night
        else:
            edited = {u for u in UNITS if (day, u) in be.PESTER_EDITS}
            capped = sum(be.pester_raw(day).values()) > be.PESTER_CAP
            units = {u: be.spawned(c, multiplier) for u, c in be.pester_night(day).items()}
            out.append(Night(day, "Surge" if be.is_surge(day) else "Pester", units=units, edited=edited, capped=capped))
    return out


def main(argv):
    arg = argv[1] if len(argv) > 1 else "Hard"
    settings = be.PRESETS[arg] if arg in be.PRESETS else be.Settings.from_code(arg)
    mode = argv[2] if len(argv) > 2 else "Survival"
    difficulty = argv[3] if len(argv) > 3 else "medium"
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        b = be.build(settings)
    print("day,night,total," + ",".join(UNITS) + ",tier,elites,edited,capped")
    for n in schedule(b, mode, difficulty):
        elites = "; ".join(f"{c} {e}" for e, c in n.elites.items())
        print(f"{n.game_day},{n.kind},{n.total}," + ",".join(str(n.units[u]) for u in UNITS)
              + f",{n.tier},{elites},{' '.join(sorted(n.edited))},{int(n.capped)}")


if __name__ == "__main__":
    main(sys.argv)

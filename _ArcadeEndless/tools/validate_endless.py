"""Independent checks on dist/ArcadeEndless_P.pak against the installed base pak.

Pester counts are checked by re-running the game's own maths: fixed_point_curve's constructor (8 float32 samples
per key, values and times rounded to fixed 22.10) and fixed_point_curve::Eval in looping mode, exactly as
__generate_pester_waves calls it for each day.
"""
import math
from fractions import Fraction
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_endless as be  # noqa: E402
import exe_patch  # noqa: E402
import menu_credit  # noqa: E402
import pak  # noqa: E402
import ue_pkg as ue  # noqa: E402

GAME_DIR = be.GAME
NIGHTMARE_PAKS = [os.path.join(GAME_DIR, "_NightmarePOC", "dist", "NightmarePOC_P.pak"),
                  os.path.join(GAME_DIR, "Achilles", "Content", "Paks", "~mods", "NightmarePOC_P.pak")]
CAMPAIGN_WAVE_CONSTANTS = "Achilles/Content/Code/CampaignConstants/CampaignWaveConstants_BP"
MILESTONE_DAYS = (1, 5, 11, 21, 31, 41, 61, 81, 101, 126, 151, 176)  # normal (non-surge) nights
failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def pkg_from(reader, path):
    return ue.Package(reader.read(path + ".uasset"), reader.read(path + ".uexp"))


def import_paths(pkg):
    return [f"{pkg.name(im.class_name)} {pkg.obj_path(-(i + 1))}" for i, im in enumerate(pkg.imports)]


def renamed_import(x):
    for u in be.UNITS:
        old, new = f"/Game/Curves/Pester_{be.CURVES[u]}_Spawn", be.curve_path(u)
        if x == f"Package {old}":
            return f"Package {new}"
        if x == f"CurveFloat {old}.Pester_{be.CURVES[u]}_Spawn":
            return f"CurveFloat {new}.{new.rsplit('/', 1)[1]}"
    return x


# ---------------------------------------------------------------------------- the game's curve maths
def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def roundf(x):  # C roundf: halves away from zero
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)


def idiv(a, b):  # x64 idiv: truncates toward zero
    q = abs(a) // abs(b)
    q = q if (a >= 0) == (b >= 0) else -q
    return q, a - q * b


def half_round(x):  # cqo; idiv 2; add eax, edx
    q, r = idiv(x, 2)
    return q + r


def sar9(x):  # cqo; and edx, 1FFh; add rax, rdx; sar rax, 9
    return (x + (0x1FF if x < 0 else 0)) >> 9


def curve_keys(pkg):
    props, _ = ue.read_props(pkg, pkg.exports[0].data)
    sub, _ = ue.read_props(pkg, props[0].value)
    v = sub[0].value
    (n,) = struct.unpack_from("<i", v, 0)
    o = 4 + be.INNER_TAG
    keys = [be.RICH_CURVE_KEY.unpack_from(v, o + i * be.RICH_CURVE_KEY.size) for i in range(n)]
    assert o + n * be.RICH_CURVE_KEY.size == len(v)
    return keys


def get_float_value(keys, t):
    """FRichCurve::Eval for constant-interpolation keys (constant pre/post extrapolation)."""
    assert all(k[0] == be.RCIM_CONSTANT for k in keys)
    if t <= keys[0][3]:
        return keys[0][4]
    if t >= keys[-1][3]:
        return keys[-1][4]
    i = max(j for j in range(len(keys)) if keys[j][3] <= t)
    return keys[i][4]


def bake(keys):
    """fixed_point_curve<fixed>::fixed_point_curve(const UCurveFloat*)"""
    samples = len(keys) * 8 - 1
    first, last = keys[0][3], keys[-1][3]
    step = f32(f32(last - first) / f32(samples))
    times, values = [], []
    for i in range(samples):
        t = f32(f32(f32(i) * step) + first)
        values.append(roundf(f32(get_float_value(keys, t) * 1024.0)))
        times.append(roundf(f32(t * 1024.0)))
    times.append(roundf(f32(last * 1024.0)))
    values.append(roundf(f32(keys[-1][4] * 1024.0)))
    return times, values


def evaluate(times, values, t, loop):
    """fixed_point_curve<fixed>::Eval(const fixed&, bool loop)"""
    n = len(times)
    if n == 0:
        return 0
    if n == 1:
        return values[0]
    first, last = times[0], times[-1]
    if loop:
        rng = last - first
        q = half_round(idiv(t << 11, rng)[0])
        q = (q + (0x3FF if q < 0 else 0)) & ~0x3FF
        t = first - half_round(sar9(q * rng)) + t
    t = min(max(t, first), last)
    for i in range(1, n):
        if t < times[i]:
            a = half_round(idiv((t - times[i - 1]) << 11, times[i] - times[i - 1])[0])
            return half_round(sar9(a * (values[i] - values[i - 1]))) + values[i - 1]
    return values[-1]


def game_multiply(value, multiplier):
    """__generate_pester_waves: a curve value times the fixed-point harassment multiplier, floored to whole units."""
    v = half_round(sar9(value * multiplier))
    return (v + (0x3FF if v < 0 else 0)) >> 10


def pester_count(baked, day, multiplier=1024):
    return game_multiply(evaluate(*baked, day << 10, True), multiplier)


# ---------------------------------------------------------------------------- wave-constant walks
def stored_days(pkg, props):
    """{difficulty: [(night, day)]} from ParsedDifficultyToMajorWaveDay, in map order."""
    out = {}
    for key, pp in be.read_map(pkg, be.named(pkg, props)["ParsedDifficultyToMajorWaveDay"], be.struct_reader(pkg)):
        days = be.read_map(pkg, be.named(pkg, pp)["MapDeathNightDay"], be.int_reader)
        out[pkg.name(key).split("::")[1]] = [(pkg.name(k), v) for k, v in days]
    return out


def spawn_rows(pkg, night):
    """(night fields, [(group fields incl. Hardship bosses, [entry])]) of one WaveInfo; entry is a dict."""
    fields = [(pkg.name(p.name), p.value) for p in night if pkg.name(p.name) != "Groups"]
    groups = []
    for g in be.read_struct_array(pkg, be.named(pkg, night)["Groups"])[1]:
        entries = []
        for s in be.read_struct_array(pkg, be.named(pkg, g)["Spawns"])[1]:
            by = be.named(pkg, s)
            ((key, per),) = be.read_map(pkg, by["AmountWithDifficultyTiers"], be.struct_reader(pkg))
            entries.append({"type": ue.describe(pkg, by["Type"]), "trigger": ue.describe(pkg, by["SpawnTrigger"]),
                            "tier": be.tier_of(pkg.name(key)), "amounts": {pkg.name(p.name): be.get_int(p) for p in per},
                            "rest": [(pkg.name(p.name), p.value) for p in s if pkg.name(p.name) not in ("Type", "AmountWithDifficultyTiers")]})
        groups.append(([(pkg.name(p.name), p.value) for p in g if pkg.name(p.name) != "Spawns"], entries))
    return fields, groups


def expected_amounts(base, units, mult, edits, room):
    """The mod's rule for one difficulty, written out on its own: base x mult, floored; an edited unit's total split
    over that unit's entries in proportion to base (all on the first if base is 0), leftovers to the largest
    remainders; then, if the night is over room, every count floored down by room/total. (counts, capped)"""
    out = [math.floor(b * mult + 1e-6) for b in base]
    for unit, n in edits.items():
        idx = [i for i, u in enumerate(units) if u == unit]
        w = [base[i] for i in idx]
        if sum(w) == 0:
            parts = [n] + [0] * (len(idx) - 1)
        else:
            exact = [Fraction(n * x, sum(w)) for x in w]
            parts = [math.floor(e) for e in exact]
            for j in sorted(range(len(idx)), key=lambda j: -(exact[j] - parts[j]))[:n - sum(parts)]:
                parts[j] += 1
        for i, v in zip(idx, parts):
            out[i] = v
    total = sum(out)
    if total <= room:
        return out, False
    return [math.floor(v * room / total + 1e-6) for v in out], True


def check_night(label, bp, bnight, mp, mnight, mult, tier, elites, cap, edits):
    bf, bg = spawn_rows(bp, bnight)
    mf, mg = spawn_rows(mp, mnight)
    check(len(bg) == len(mg) == 1 and bf == mf and bg[0][0] == mg[0][0], f"{label}: one spawn group; timing and Hardship bosses unchanged")
    base_e, mod_e = bg[0][1], mg[0][1]
    unit_of = lambda e: be.UNIT_OF_ENEMY[int(e["type"].rsplit("_", 1)[1])]  # noqa: E731
    present = {unit_of(e) for e in base_e}
    added_units = [u for u in be.UNITS if u not in present and any(u in per for per in edits.values())]
    night_tier = min(be.MAX_TIER, max(max(e["tier"] for e in base_e), tier))
    template = next(e for e in base_e if e["trigger"] == "SPAWN_GROUP_TRIGGER::LINEAR_TIME_ENTIRE_GROUP")
    n, k = len(base_e), len(added_units)
    ok = len(mod_e) == n + k + len(elites)
    ok = ok and all(a["type"] == c["type"] and a["rest"] == c["rest"] and c["tier"] == min(be.MAX_TIER, max(a["tier"], tier))
                    for a, c in zip(base_e, mod_e[:n]))
    ok = ok and all(c["type"] == f"AGENT_TYPE::ENEMY_AGENT_TYPE_{be.ENEMY_TYPES[u]}" and c["tier"] == night_tier and c["rest"] == template["rest"]
                    for u, c in zip(added_units, mod_e[n:n + k]))
    check(ok, f"{label}: spawns kept, at tier {tier} or the base tier if higher (max {be.MAX_TIER})"
              + (f"; new entries for edited {', '.join(added_units)}" if added_units else ""))
    units = [unit_of(e) for e in base_e] + added_units
    bosses = be.night_totals(bp, bnight, ("HardshipGrimCommandSpawns",))
    ok, honoured, capped = True, True, []
    for i, d in enumerate(be.DIFFICULTY_FIELDS):
        room = max(0, cap - sum(c[i] for _, c in elites) - bosses.get(d, 0))
        want, over = expected_amounts([e["amounts"][d] for e in base_e] + [0] * k, units, mult, edits.get(d, {}), room)
        got = [c["amounts"][d] for c in mod_e[:n + k]]
        ok = ok and want == got
        capped += [d] if over else []
        for unit, count in edits.get(d, {}).items():
            honoured = honoured and (over or sum(g for g, u in zip(got, units) if u == unit) == count)
    check(ok, f"{label}: counts x{mult:g}, scaled down only to fit the cap{f' (capped on {len(capped)} of 6 difficulties)' if capped else ''}")
    if edits:
        check(honoured, f"{label}: {sum(len(v) for v in edits.values())} edited count(s) exact (unless the night is capped)")
    new = mod_e[n + k:]
    ok = len(new) == len(elites) and all(
        e["type"] == f"AGENT_TYPE::ENEMY_AGENT_TYPE_{be.ELITE_TYPES[name]}" and e["tier"] == 1 and e["rest"] == template["rest"]
        and e["amounts"] == dict(zip(be.DIFFICULTY_FIELDS, counts)) for e, (name, counts) in zip(new, elites))
    check(ok, f"{label}: elites added for every player: {', '.join(f'{n} {c[2]}' for n, c in elites) or 'none'} (medium)")
    bt, mt = be.night_totals(bp, bnight), be.night_totals(mp, mnight)
    check(max(mt.values()) <= cap, f"{label}: medium {bt['medium']} -> {mt['medium']}, unbeatable {bt['unbeatable']} -> {mt['unbeatable']} units (cap {cap})")


def base_biggest_night(base):
    cap = 0
    for mode in be.MODES:
        pkg = pkg_from(base, be.WAVE_CONSTANTS[mode])
        _, props, _ = be.cdo_props(pkg)
        nights = be.read_struct_array(pkg, be.named(pkg, props)["DeathNightWaves"])[1]
        final, _ = ue.read_props(pkg, be.named(pkg, props)["FinalStandWave"].value)
        nights.append(ue.read_props(pkg, be.named(pkg, final)["Wave"].value)[0])
        cap = max(cap, *(max(be.night_totals(pkg, n).values()) for n in nights))
    return cap


# ---------------------------------------------------------------------------- checks
def main(pak_path=be.OUT_PAK):
    """Check pak_path against the settings build_endless is configured with; 0 if every check passes."""
    failures.clear()
    base = pak.PakReader(be.BASE_PAK)
    mod = pak.PakReader(pak_path)

    print("Pak structure:")
    check(mod.index_ok and mod.phi_ok and mod.fdi_ok, "primary/path-hash/directory index SHA-1s valid")
    check(mod.mount == "../../../", "mount point ../../../")
    check(all(mod.phi.get(pak.path_hash(p, mod.seed)) == loc for p, loc in mod.files.items()), f"path-hash lookup finds all {len(mod.files)} files")
    data = {p: mod.read(p) for p in mod.files}  # read() verifies each entry's SHA-1
    check(True, "every entry's data hash matches its header")

    packages = sorted({p.rsplit(".", 1)[0] for p in mod.files})
    new = {be.game_to_pak(be.curve_path(u)) for u in be.PESTER}
    check(set(packages) == new | set(be.WAVE_CONSTANTS.values()) | {menu_credit.MENU_UI},
          f"exactly {len(new)} new curves + the 2 wave constants + the main menu")
    for path in packages:
        p = pkg_from(mod, path)
        ok = p.write() == (data[path + ".uasset"], data[path + ".uexp"])
        where = "replaces the game's" if path + ".uasset" in base.files else "new, under " + be.MOD_DIR
        check(ok and (path + ".uasset" in base.files or path.startswith(be.game_to_pak(be.MOD_DIR))), f"{path.split('/')[-1]}: round-trips, {where}")

    print("Leaves the campaign and other mods alone:")
    check(not any(p.startswith(be.CURVE_DIR) or p.startswith("Achilles/Content/Datatables/") for p in mod.files),
          "game's own pester curves and wave-day tables untouched (the campaign uses them)")
    camp = pkg_from(base, CAMPAIGN_WAVE_CONSTANTS)
    check(CAMPAIGN_WAVE_CONSTANTS + ".uasset" not in mod.files and any("/Game/Curves/Pester_" in x for x in import_paths(camp)),
          "CampaignWaveConstants_BP not in the pak, still on /Game/Curves/Pester_*")
    menu_files = {menu_credit.MENU_UI + ".uasset", menu_credit.MENU_UI + ".uexp"}
    for np in NIGHTMARE_PAKS:
        if os.path.exists(np):
            other = pak.PakReader(np)
            where = os.path.relpath(np, GAME_DIR)
            check(set(other.files) & set(mod.files) == menu_files, f"shares only Menu_UI with {where}")
            check(menu_credit.credit_of(pkg_from(other, menu_credit.MENU_UI)) == (menu_credit.CREDIT, menu_credit.VISIBILITY),
                  f"{where}'s Menu_UI, which the game uses when both are installed, has the same credit")
    # equal-priority paks mount in descending name order (case-insensitive) and the first mounted wins
    check(menu_credit.WINNER.lower() > os.path.basename(be.OUT_PAK).lower(), f"{menu_credit.WINNER}'s Menu_UI wins when both are installed")

    print("Main menu:")
    menu, old = pkg_from(mod, menu_credit.MENU_UI), pkg_from(base, menu_credit.MENU_UI)
    changed = {menu.name(e.object_name) for eo, e in zip(old.exports, menu.exports) if eo.data != e.data}
    check(changed == {menu_credit.LABEL} and len(menu.imports) == len(old.imports) and len(menu.exports) == len(old.exports),
          f"only {menu_credit.LABEL} changes")
    check(menu_credit.credit_of(menu) == (menu_credit.CREDIT, menu_credit.VISIBILITY), f"{menu_credit.LABEL} shows {menu_credit.CREDIT!r}")

    print("Pester curves (game's bake + looping Eval, harassment multiplier 1.0):")
    baked = {}
    for unit in be.PESTER:
        p = pkg_from(mod, be.game_to_pak(be.curve_path(unit)))
        check(p.obj_path(1) == be.curve_path(unit).rsplit("/", 1)[1] and p.names[0] == be.curve_path(unit), f"{unit}: package renamed to {be.curve_path(unit)}")
        baked[unit] = bake(curve_keys(p))
        counts = [pester_count(baked[unit], d) for d in range(1, be.PESTER_LAST_DAY + 1)]
        expect = [be.pester_value(unit, d) for d in range(1, be.PESTER_LAST_DAY + 1)]
        check(counts == expect, f"{unit}: every day 1-{be.PESTER_LAST_DAY} gives the table's count")
        start = be.PESTER[unit][0]
        check(all(c == 0 for d, c in enumerate(counts[:start - 1], 1) if (d, unit) not in be.PESTER_EDITS),
              f"{unit}: none before day {start} unless edited, {counts[-1]} on day {be.PESTER_LAST_DAY}")
    days = range(1, be.PESTER_LAST_DAY + 1)
    totals = {d: sum(pester_count(baked[u], d) for u in be.UNITS) for d in days}
    edited = {d for d, _ in be.PESTER_EDITS}
    normal = [totals[d] for d in days if not be.is_surge(d) and d not in edited]
    surges = [d for d in days if be.is_surge(d) and not {d, d - 1} & edited]
    check(all(b2 >= a for a, b2 in zip(normal, normal[1:])), f"normal nights never shrink ({normal[0]} -> {normal[-1]} units"
          + (f", {len(edited)} edited nights aside)" if edited else ")"))
    check(all(totals[d] > totals[d - 1] or totals[d] == be.PESTER_CAP or be.is_surge(d - 1) for d in surges),
          f"surge nights (day {be.SURGE_FROM}, then every {be.SURGE_EVERY}) bigger than the normal night"
          f" before, unless at the cap" if be.SURGE_EVERY else "no surge nights")
    check(max(totals.values()) <= be.PESTER_CAP, f"no pester night above {be.PESTER_CAP} units (biggest {max(totals.values())})")
    if be.PESTER_EDITS:
        exact = all(pester_count(baked[u], d) == n for (d, u), n in be.PESTER_EDITS.items()
                    if sum(be.pester_raw(d).values()) <= be.PESTER_CAP)
        check(exact, f"{len(be.PESTER_EDITS)} edited pester count(s) exact in the game's curve maths (unless the night is capped)")
    multipliers = be.pester_multipliers(be.Builder())
    values = {(u, d): evaluate(*baked[u], d << 10, True) for u in be.UNITS for d in days}
    ok = all(game_multiply(values[u, d], m) == be.spawned(be.pester_value(u, d), m)
             for m in multipliers.values() for u in be.UNITS for d in days)
    check(ok, "what the app shows per difficulty = the game's multiply-and-round-down, for every unit, day and difficulty ("
              + ", ".join(f"{d} x{m / 1024:.2f}" for d, m in multipliers.items()) + ")")

    print("Wave constants:")
    biggest = base_biggest_night(base)
    check(biggest == be.BASE_NIGHT_CAP, f"the base game's biggest night is still {be.BASE_NIGHT_CAP} units ({biggest})")
    cap = be.NIGHT_CAP
    major_days = {}
    for mode in be.MODES:
        bp, mp = pkg_from(base, be.WAVE_CONSTANTS[mode]), pkg_from(mod, be.WAVE_CONSTANTS[mode])
        check(import_paths(mp) == [renamed_import(x) for x in import_paths(bp)], f"{mode}: imports identical except the 7 curves -> {be.MOD_DIR}")
        changed = [mp.name(e.object_name) for eo, e in zip(bp.exports, mp.exports) if eo.data != e.data]
        check(len(bp.exports) == len(mp.exports) and len(changed) == 1 and changed[0].startswith("Default__"),
              f"{mode}: only the class defaults export changed ({changed})")
        bcdo, bprops, bend = be.cdo_props(bp)
        mcdo, mprops, mend = be.cdo_props(mp)
        diff = sorted(bp.name(a.name) for a, c in zip(bprops, mprops) if a.value != c.value)
        check(len(bprops) == len(mprops) and bcdo.data[bend:] == mcdo.data[mend:]
              and diff == ["DeathNightWaves", "FinalStandWave", "MajorWaveDayTable", "ParsedDifficultyToMajorWaveDay"],
              f"{mode}: only DeathNightWaves, FinalStandWave, MajorWaveDayTable and the parsed day map differ")
        bb, mb = be.named(bp, bprops), be.named(mp, mprops)
        check(be.get_int(bb["MajorWaveDayTable"]) != 0 and be.get_int(mb["MajorWaveDayTable"]) == 0
              and bb["LastMajorWaveDayTable"].value == mb["LastMajorWaveDayTable"].value,
              f"{mode}: MajorWaveDayTable cleared, so PostLoad's ParseData keeps the stored day map")

        sb, sm = stored_days(bp, bprops), stored_days(mp, mprops)
        check(list(sb) == list(sm) and all([k for k, _ in sb[d]] == [k for k, _ in sm[d]] for d in sb),
              f"{mode}: same difficulties and night keys as the base map")
        n_dn = len(be.DEATH_NIGHT_MULT[mode])
        for d, entries in sm.items():
            days = [v for _, v in entries]
            waved, extra, final = days[:n_dn], days[n_dn:-1], days[-1]
            ok = (entries[-1][0] == be.FINAL_NIGHT and final == be.FINAL_NIGHT_DAY and tuple(waved) == be.DEATH_NIGHT_DAYS[mode][d]
                  and extra == [be.FINAL_NIGHT_DAY - 2 * (len(extra) - i) for i in range(len(extra))]
                  and all(b2 - a >= 2 for a, b2 in zip(days, days[1:])))
            check(ok, f"{mode} {d:10}: Death Nights {waved}{f', no-wave entries {extra}' if extra else ''}, "
                      f"Final Night {final} (was {[v for _, v in sb[d]]})")
            major_days[(mode, d)] = waved + [final]
        check(be.FINAL_NIGHT_DAY < be.PESTER_LAST_DAY < exe_patch.MAX_DAYS,
              f"{mode}: Final Night (day {be.FINAL_NIGHT_DAY}) before the last pester day ({be.PESTER_LAST_DAY}) and the clock's day-199 wrap")

        bn = be.read_struct_array(bp, bb["DeathNightWaves"])[1]
        mn = be.read_struct_array(mp, mb["DeathNightWaves"])[1]
        check(len(bn) == len(mn) == n_dn, f"{mode}: {n_dn} Death Nights, as in the base game")
        for k, (bnight, mnight) in enumerate(zip(bn, mn)):
            check_night(f"{mode} Death Night {k + 1}", bp, bnight, mp, mnight, be.DEATH_NIGHT_MULT[mode][k],
                        be.DEATH_NIGHT_TIER[mode][k], be.ELITES[mode][k], cap, be.NIGHT_EDITS.get((mode, k + 1), {}))
        bfinal, mfinal = be.final_wave(bp, bprops), be.final_wave(mp, mprops)
        check([(bp.name(p.name), p.value) for p in bfinal[0] if bp.name(p.name) != "Wave"]
              == [(mp.name(p.name), p.value) for p in mfinal[0] if mp.name(p.name) != "Wave"],
              f"{mode} Final Night: night-length multipliers unchanged")
        check_night(f"{mode} Final Night", bp, bfinal[2], mp, mfinal[2], be.FINAL_NIGHT_MULT[mode], be.FINAL_NIGHT_TIER, be.FINAL_ELITES,
                    cap, be.NIGHT_EDITS.get((mode, 0), {}))

    print("Pester units per night (multiplier 1.0, all seven types; none on a Death/Final Night or the day after):")
    majors = set(major_days[("Survival", "MEDIUM")])
    for d in MILESTONE_DAYS:
        skip = d in majors or d - 1 in majors
        print(f"         day {d:3}: {'(Survival Medium Death Night or the day after)' if skip else totals[d]:>5}"
              f"  Crushers {pester_count(baked['Crusher'], d):3}{'  (surge)' if be.is_surge(d) else ''}")

    print("Exe patch (needed for pester waves after day 44):")
    _, patched = exe_patch.find_site(open(exe_patch.EXE, "rb").read())
    print(f"         {'NOT patched: pester waves stop after day 44' if patched is None else f'patched: waves for days 1-{patched - 1}'}")

    for w in be.SETTINGS.over_limits():  # the player's choice, so not a failure
        print(f"  WARNING: {w} Untested; the game may lag badly or crash.")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    # python validate_endless.py [preset name | settings code]: the settings dist/ArcadeEndless_P.pak was built with
    arg = sys.argv[1] if len(sys.argv) > 1 else "Hard"
    be.configure(be.PRESETS[arg] if arg in be.PRESETS else be.Settings.from_code(arg))
    sys.exit(main())

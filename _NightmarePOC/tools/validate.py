"""Independent checks on dist/NightmarePOC_P.pak against the installed base pak.

  python validate.py [settings code]: the settings the pak was built with (default: the defaults)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_mod as bm  # noqa: E402
import kismet  # noqa: E402
import menu_credit  # noqa: E402
import pak  # noqa: E402
import ue_pkg as ue  # noqa: E402

VOLATIST_RESEARCH_LIST = "Achilles/Content/Code/FactionConstants/Research/ResearchList_Volatist"
failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def pkg_from(reader, path):
    return ue.Package(reader.read(path + ".uasset"), reader.read(path + ".uexp"))


def props_of(pkg, export):
    props, _ = ue.read_props(pkg, export.data)
    return {pkg.name(x.name): ue.describe(pkg, x) for x in props}


def raw_props(pkg, export):
    props, _ = ue.read_props(pkg, export.data)
    return {pkg.name(x.name): x for x in props}


def effective(pkg, prop):
    """Per-level values of a UFloatVarientValue as the game reads them (mode SAME is the struct default)."""
    sub, _ = ue.read_props(pkg, prop.value)
    get = lambda n, i=0: next((struct.unpack("<f", s.value)[0] for s in sub if pkg.name(s.name) == n and s.array_index == i), None)
    mode = next((ue.describe(pkg, s).split("::")[-1] for s in sub if pkg.name(s.name) == "edit_mode"), "SAME")
    start, inc = get("start_value"), get("increase_value") or 0.0
    if mode == "SAME":
        return [start] * bm.VARIENT_ARRAY_LEN
    if mode == "INCREASE":
        return [None if start is None else start + inc * i for i in range(bm.VARIENT_ARRAY_LEN)]
    return [get("value_array", i) or 0.0 for i in range(bm.VARIENT_ARRAY_LEN)]


def cost_of(text):
    """{resource: amount} from a described ResourceCost, e.g. "{gold=90, wood=10}"."""
    return {k: float(v) for k, v in (x.split("=") for x in text.strip("{}").split(", ") if x)}


def values(pkg, prop):
    """Per-level values of a stat stored as a UFloatVarientValue, or [the plain number]."""
    if prop.type_str == "StructProperty":
        return effective(pkg, prop)
    return [struct.unpack("<f" if prop.type_str == "FloatProperty" else "<i", prop.value)[0]]


def short(vals):
    return f"{[None if v is None else round(v, 3) for v in vals[:3]]}{'...' if len(vals) > 3 else ''}"


def close(new, want):
    return abs(new - want) <= 1e-4 * max(1.0, abs(want))


def check_hero(base, current, mode, hero, h):
    """Every stat HERO_STATS covers, at every level: scaled or set as h says, else byte-for-byte the game's."""
    ac = pkg_from(base, bm.AGENT_CONSTANTS[mode])
    d = props_of(ac, bm.find_export(ac, bm.HEROES[hero])[1])
    changed, untouched = [], []
    for stat, (keys, names) in bm.HERO_STATS.items():
        x = h[stat]
        same = x is None or (stat != "armour" and x == 1)
        for key in keys:
            if key not in d:
                continue
            path = bm.game_to_pak(d[key].split(".")[0])
            po, pn = pkg_from(base, path), current(path)
            ro, rn = raw_props(po, po.exports[0]), raw_props(pn, pn.exports[0])
            for name in names:
                if name not in ro:
                    check(name not in bm.REQUIRED_FIELDS, f"{hero}: {key} has {name}") if name in bm.REQUIRED_FIELDS else None
                    continue
                if same:
                    untouched.append(name in rn and ro[name].value == rn[name].value)
                    continue
                old, new = values(po, ro[name]), values(pn, rn[name])
                if stat == "armour":
                    ok = all(v == x for v in new)
                else:
                    pairs = [(a, c) for a, c in zip(old, new) if a is not None]
                    ok = bool(pairs) and all(c is not None and close(c, a * x) for a, c in pairs)
                    if name == "armour_shred_damage" and pairs and all(a == 0 for a, _ in pairs):
                        ok = all(c > 0 for _, c in pairs)  # shred stored only as start_value: now active in every mode
                changed.append((f"{hero} {stat} {'= ' if stat == 'armour' else 'x'}{x:g}: {key.split('_')[0]}.{name} "
                                f"{short(old)} -> {short(new)}", ok))
    for msg, ok in changed:
        check(ok, msg)
    check(all(untouched), f"{hero}: {'every other stat is' if changed else 'stats are'} the game's own ({len(untouched)} fields)")


def check_hero_projectiles(base, current, mode, s):
    """The projectiles each hero's ranged attack fires take its damage and shred multipliers; all others untouched."""
    ac = pkg_from(base, bm.AGENT_CONSTANTS[mode])
    expected = {}
    for hero, comp in bm.HEROES.items():
        h = s.hero(hero)
        d = props_of(ac, bm.find_export(ac, comp)[1])
        if "ranged_attack_constants" not in d or (h["ranged"], h["shred"]) == (1, 1):
            continue
        rc = pkg_from(base, bm.game_to_pak(d["ranged_attack_constants"].split(".")[0]))
        props, _ = ue.read_props(rc, rc.exports[0].data)
        for p in props:
            if rc.name(p.name) in ("projectile", "siege_projectile"):
                expected[ue.describe(rc, p)] = (hero, h["ranged"], h["shred"])
    po, pn = pkg_from(base, bm.PROJECTILE_CONSTANTS[mode]), current(bm.PROJECTILE_CONSTANTS[mode])
    scaled = 0
    for eo, en in zip(po.exports, pn.exports):
        nm = pn.name(en.object_name).replace("_GEN_VARIABLE", "")
        ro, rn = raw_props(po, eo), raw_props(pn, en)
        t = ue.describe(po, ro["type"]) if "type" in ro else None
        if t not in expected:
            check(eo.data == en.data, f"projectile {nm} untouched") if eo.data != en.data else None
            continue
        hero, damage, shred = expected[t]
        ok = all(close(values(pn, rn[f])[0], values(po, ro[f])[0] * m) for f, m in (("damage", damage), ("armour_shred_damage", shred)) if f in ro)
        check(ok, f"{hero}'s {nm}: damage {values(po, ro['damage'])[0]:g} -> {values(pn, rn['damage'])[0]:g}")
        scaled += 1
    if not expected:
        check(po.write() == pn.write(), "projectiles untouched (no hero ranged damage or shred change)")


def main(pak_path=bm.OUT_PAK, base_pak=bm.BASE_PAK, settings=None):
    """Check pak_path, built for settings (default: the defaults), against base_pak; 0 if every check passes. The
    Arcade Endless app calls this too."""
    failures.clear()
    s = (settings or bm.Settings()).checked()
    print(f"Settings {s.code()}")
    base = pak.PakReader(base_pak)
    mod = pak.PakReader(pak_path)

    def current(path):  # what the game sees: the mod's copy if present, else the base game's
        return pkg_from(mod if path + ".uasset" in mod.files else base, path)

    print("Pak structure:")
    check(mod.index_ok and mod.phi_ok and mod.fdi_ok, "primary/path-hash/directory index SHA-1s valid")
    check(mod.mount == "../../../", "mount point ../../../")
    check(all(mod.phi.get(pak.path_hash(p, mod.seed)) == loc for p, loc in mod.files.items()), f"path-hash lookup finds all {len(mod.files)} files")
    data = {p: mod.read(p) for p in mod.files}  # read() verifies each entry's SHA-1
    check(True, "every entry's data hash matches its header")

    packages = sorted({p.rsplit(".", 1)[0] for p in mod.files})
    print("Packages:")
    for path in packages:
        p = pkg_from(mod, path)
        name = path.split("/")[-1]
        ok = p.write() == (data[path + ".uasset"], data[path + ".uexp"])
        if path + ".uasset" in base.files:
            old = pkg_from(base, path)
            changed = [p.name(e.object_name) for eo, e in zip(old.exports, p.exports) if eo.data != e.data]
            same_shape = len(old.exports) == len(p.exports) and len(old.imports) == len(p.imports)
            check(ok and same_shape, f"{name}: round-trips, same shape as the game's, {len(changed)} export(s) changed")
        else:
            check(ok and path.startswith(bm.game_to_pak(bm.MOD_DIR)), f"{name}: new mod asset, round-trips")

    print("Agent constants: only the borrowed components change")
    for mode in bm.MODES:
        old, new = pkg_from(base, bm.AGENT_CONSTANTS[mode]), pkg_from(mod, bm.AGENT_CONSTANTS[mode])
        changed = {new.name(e.object_name) for eo, e in zip(old.exports, new.exports) if eo.data != e.data}
        check(changed == {u[1] for u in bm.BORROWED_UNITS}, f"{mode}: changed = {sorted(changed)}")

    print("Main menu:")
    menu = pkg_from(mod, bm.MENU_UI)
    for e in menu.exports:
        if menu.obj_name(e.class_index) == "Function":
            kismet.disasm_function(menu, e.data)  # asserts on any size mismatch
    first = kismet.disasm_function(menu, bm.find_export(menu, "Tick")[1].data)[0][2]
    check("EditorButton@MainMenuUI" in first and "SetVisibility(ByteConst(0))" in first, "Tick starts with EditorButton.SetVisibility(Visible)")
    old = pkg_from(base, bm.MENU_UI)
    changed = {menu.name(e.object_name) for eo, e in zip(old.exports, menu.exports) if eo.data != e.data}
    check(changed == {"Tick", menu_credit.LABEL}, f"only Tick and {menu_credit.LABEL} change: {sorted(changed)}")
    check(menu_credit.credit_of(menu) == (menu_credit.CREDIT, menu_credit.VISIBILITY),
          f"{menu_credit.LABEL} shows {menu_credit.CREDIT!r}")
    check(os.path.basename(pak_path) == menu_credit.WINNER, f"pak named {menu_credit.WINNER}, so its Menu_UI wins over Arcade Endless's")

    print("Volatist roster:")
    ul = pkg_from(mod, bm.VOLATIST_UNIT_LIST)
    roster = props_of(ul, ul.exports[0])["enabled_unit_types"].strip("[]").split(", ")
    ours = {"AGENT_TYPE::" + u[2]: u[0] for u in bm.VOLATIST_UNITS + bm.BORROWED_UNITS}
    check(set(ours) <= set(roster), f"all {len(ours)} Nightmares enabled: {sorted(v for v in ours.values())}")
    check(not any("ENEMY_AGENT_TYPE" in r for r in roster), "no enemy agent types in the roster")

    for mode in bm.MODES:
        print(f"{mode}:")
        ac = current(bm.AGENT_CONSTANTS[mode])
        comps = {}
        for e in ac.exports:
            if ac.obj_name(e.class_index) == "PerAgentConstants":
                d = props_of(ac, e)
                comps[d.get("type", "AGENT_TYPE::PLAYER_AGENT_TYPE_0")] = d
        slots, research = {}, {}
        for t in roster:
            pc = current(bm.game_to_pak(comps[t]["player_agent_constants"].split(".")[0]))
            pd = props_of(pc, pc.exports[0])
            slots.setdefault((pd.get("build_location", "BUILDING_TYPE::BARRACKS_T0"), pd.get("button_index", "-1")), []).append(t)
        rl = current(VOLATIST_RESEARCH_LIST)
        visible = set(props_of(rl, rl.exports[0])["enabled_research_types"].strip("[]").split(", "))
        r = current(bm.RESEARCH[mode])
        for e in r.exports:
            if r.obj_name(e.class_index) == "ResearchComponent":
                d = props_of(r, e)
                if d.get("type") in visible:  # research the Volatists never see doesn't take a slot
                    research.setdefault(d.get("research_location"), set()).add(d.get("button_index"))
                check(d.get("unlocks_agent") not in ours, f"research {r.name(e.object_name)} does not lock a Nightmare") if d.get("unlocks_agent") in ours else None
        for t, unit in ours.items():
            d = comps[t]
            check("player_agent_constants" in d and "enemy_constants" not in d, f"{unit}: player constants, no enemy constants (normal player spawn)")
            vc = current(bm.game_to_pak(d["visual_constants"].split(".")[0]))
            vd = props_of(vc, vc.exports[0])
            check("display_training_icon" in vd and "action_mapping_icon" in vd, f"{unit}: training icons")
            pc = current(bm.game_to_pak(d["player_agent_constants"].split(".")[0]))
            pd = props_of(pc, pc.exports[0])
            loc, slot = pd.get("build_location", "BUILDING_TYPE::BARRACKS_T0"), pd["button_index"]
            cost, seconds, upkeep = bm.unit_costs(s, unit)
            check(cost_of(pd["purchase_cost"]) == cost and int(pd["build_time_in_seconds"]) == seconds
                  and cost_of(pd.get("maintenance_cost", "{}")) == ({"gold": upkeep} if upkeep else {}),
                  f"{unit}: costs {pd['purchase_cost']}, {seconds}s, upkeep {upkeep} gold")
            check(len(slots[(loc, slot)]) == 1 and slot not in research.get(loc, set()) and slot not in bm.RESERVED_SLOTS,
                  f"{unit}: {loc.split('::')[1]} slot {slot} not shared with a unit, visible research, or a building action")
        if "visual_constants" in comps.get("AGENT_TYPE::PLAYER_AGENT_TYPE_26", {}):
            src = props_of(ac, bm.find_export(ac, "Nightmare_crawler_const_GEN_VARIABLE")[1])
            check(comps["AGENT_TYPE::PLAYER_AGENT_TYPE_26"]["visual_constants"] == src["visual_constants"], "Crawler uses the horde Crawler's visuals")

        print(f"{mode} heroes:")
        for hero in bm.HEROES:
            check_hero(base, current, mode, hero, s.hero(hero))
        check_hero_projectiles(base, current, mode, s)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(settings=bm.Settings.from_code(sys.argv[1]) if len(sys.argv) > 1 else None))

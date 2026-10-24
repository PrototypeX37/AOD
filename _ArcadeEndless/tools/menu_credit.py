"""Main-menu credit, shared by Arcade Endless and NightmarePOC. Keep both copies (each mod's tools/menu_credit.py) identical.

Both mods ship Menu_UI with this credit, and the game reads just one copy. UE mounts paks of equal priority in
descending name order and the first one mounted wins, so with both installed NightmarePOC_P.pak's Menu_UI (the
credit plus its Editor button) is used; with Arcade Endless alone, Arcade's.
"""
import struct

import ue_pkg as ue

MENU_UI = "Achilles/Content/UI/Blueprints/Menu_UI"
LABEL = "Txt_EarlyAccess"  # the old "Early Access" title over the news panel (bottom right), collapsed since 1.0
CREDIT = "Mod created by Lunar\n(76561198073513480)"
VISIBILITY = "ESlateVisibility::HitTestInvisible"  # shown, but never takes a click
WINNER = "NightmarePOC_P.pak"  # the pak whose Menu_UI the game uses when both are installed


def invariant_text(s):
    """An FText property value holding s as a culture-invariant string (flags CultureInvariant, history None)."""
    return struct.pack("<IBi", 2, 255, 1) + ue.w_fstr(s)


def label(pkg):
    for e in pkg.exports:
        if pkg.name(e.object_name) == LABEL and pkg.obj_name(e.class_index) == "TextBlock":
            return e
    raise KeyError(LABEL)


def label_props(pkg):
    e = label(pkg)
    props, end = ue.read_props(pkg, e.data)
    return e, props, end, {pkg.name(p.name): p for p in props}


def add_credit(pkg):
    """Show the credit in a Menu_UI package, in place of the old Early Access title."""
    e, props, end, by = label_props(pkg)
    assert by["Visibility"].type_str == "EnumProperty", by["Visibility"].type_str
    by["Text"].value = invariant_text(CREDIT)
    by["Visibility"].value = struct.pack("<ii", *pkg.name_ref(VISIBILITY))
    e.data = ue.write_props(pkg, props) + e.data[end:]


def credit_of(pkg):
    """(text, visibility) of the credit label, or text None when it isn't a plain string."""
    _, _, _, by = label_props(pkg)
    v = by["Text"].value
    flags, history, has_string = struct.unpack_from("<IBi", v)
    text = ue.R(v, 9).fstr() if history == 255 and has_string else None
    return text, ue.describe(pkg, by["Visibility"])

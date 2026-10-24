"""Art and fonts read straight out of the installed game's pak, for the Arcade Endless app (nothing is shipped).

texture(path) decodes a cooked UTexture2D's top mip into a PIL image (needs Pillow); font_file(path) writes a
UFontFace's .ufont (a plain TTF/OTF) to a cache file that Windows can load privately for this process.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import home  # noqa: E402
import pak  # noqa: E402
import ue_pkg as ue  # noqa: E402

BASE_PAK = os.path.join(home.GAME, home.GAME_PAK)
CACHE = os.path.join(home.DIST, "cache")
BULK_SEPARATE_FILE = 0x100  # FBulkData flag: payload lives in the .ubulk next to the package
BCN = {"PF_DXT1": 1, "PF_DXT3": 2, "PF_DXT5": 3, "PF_BC4": 4, "PF_BC5": 5, "PF_BC7": 7}
_reader = None


def reader():
    global _reader
    if _reader is None:
        _reader = pak.PakReader(BASE_PAK)
    return _reader


def texture(path):
    """PIL RGBA image of the texture at a pak path without extension (e.g. Achilles/Content/UI/Textures/...)."""
    from PIL import Image
    r = reader()
    pkg = ue.Package(r.read(path + ".uasset"), r.read(path + ".uexp"))
    d = pkg.exports[0].data
    _, o = ue.read_props(pkg, d)
    o += 4 + 4 + 4 + 8 + 8  # object guid flag, strip flags, bCooked, pixel format name, skip offset
    width, height, _ = struct.unpack_from("<iii", d, o)
    rd = ue.R(d, o + 12)
    fmt = rd.fstr()
    _, mips = rd.i32(), rd.i32()
    _, flags, _, size, offset = struct.unpack_from("<iIiiq", d, rd.o)
    if flags & BULK_SEPARATE_FILE:
        data = r.read(path + ".ubulk")[offset:offset + size]
    else:
        data = d[rd.o + 24:rd.o + 24 + size]
    if fmt == "PF_B8G8R8A8":
        return Image.frombytes("RGBA", (width, height), data, "raw", "BGRA")
    if fmt == "PF_G8":
        return Image.frombytes("L", (width, height), data).convert("RGBA")
    if fmt in BCN:
        return Image.frombytes("RGBA", (width, height), data, "bcn", BCN[fmt])
    raise ValueError(f"{path}: pixel format {fmt} not supported")


def font_file(path):
    """Cache-file path of the font at a pak path without extension (e.g. Achilles/Content/UI/Fonts/Cinzel-Medium)."""
    out = os.path.join(CACHE, os.path.basename(path) + ".ttf")
    if not os.path.exists(out):
        os.makedirs(CACHE, exist_ok=True)
        data = reader().read(path + ".ufont")
        assert data[:4] in (b"\0\1\0\0", b"OTTO", b"true"), f"{path}: not a TrueType/OpenType font"
        with open(out, "wb") as f:
            f.write(data)
    return out


def load_private_font(path):
    """Make a game font usable by this process only (Windows); False if that isn't possible."""
    try:
        import ctypes
        FR_PRIVATE = 0x10
        return ctypes.windll.gdi32.AddFontResourceExW(font_file(path), FR_PRIVATE, 0) > 0
    except Exception:
        return False

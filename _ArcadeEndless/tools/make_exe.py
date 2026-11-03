"""Pack the app into _ArcadeEndless\\ArcadeEndless.exe (one file, no console) with PyInstaller.

  python make_exe.py

Needs PyInstaller and Pillow (pip install pyinstaller pillow). The icon is drawn here, an "AE" monogram in the
app's Veil green, so no game art goes into the exe; the app still reads the game's art from the install when it
runs. NightmarePOC's builder and validator (_NightmarePOC\\tools) are packed in too, for the app's optional
NightmarePOC tab. The exe's file details (Properties > Details) carry the credit. Intermediate files go to
_ArcadeEndless\\build\\ and are removed afterwards. It works with the app open: the open copy is renamed to
ArcadeEndless.exe.old.
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import home  # noqa: E402

APP = os.path.join(home.MOD, "ArcadeEndless.pyw")
BUILD = os.path.join(home.MOD, "build")
EXE = os.path.join(home.MOD, "ArcadeEndless.exe")
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
NIGHTMARE_TOOLS = home.NIGHTMARE_TOOLS
SHARED = ("pak.py", "ue_pkg.py", "menu_credit.py", "exe_patches.py")  # in both mods' tools; the exe holds one copy of each
AUTHOR = "Lunar (76561198073513480)"
VERSION_INFO = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=(1, 1, 0, 0), prodvers=(1, 1, 0, 0), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Lunar'),
      StringStruct('FileDescription', 'Arcade Endless for Age of Darkness: Final Stand'),
      StringStruct('FileVersion', '1.1.0.0'),
      StringStruct('InternalName', 'ArcadeEndless'),
      StringStruct('LegalCopyright', 'Created by {AUTHOR}'),
      StringStruct('OriginalFilename', 'ArcadeEndless.exe'),
      StringStruct('ProductName', 'Arcade Endless'),
      StringStruct('ProductVersion', '1.1.0.0')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def draw_icon(path):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import game_art
    n = 256
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((22, 22, n - 22, n - 22), fill=(69, 216, 167, 210))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)
    d.ellipse((30, 30, n - 30, n - 30), fill=(9, 12, 13, 255), outline=(69, 216, 167, 255), width=6)
    try:
        font = ImageFont.truetype(game_art.font_file("Achilles/Content/UI/Fonts/Cinzel-Medium"), 96)
    except Exception:
        font = ImageFont.truetype("georgia.ttf", 96)
    d.text((n / 2, n / 2 + 4), "AE", font=font, fill=(234, 243, 242, 255), anchor="mm")
    im.save(path, sizes=ICON_SIZES)


def replace_exe(new):
    """Move the new exe into place. An open app's exe can't be overwritten, but Windows lets it be renamed."""
    for stale in glob.glob(glob.escape(EXE) + "*.old"):  # left by earlier builds while the app was open
        try:
            os.remove(stale)
        except OSError:
            pass
    try:
        os.replace(new, EXE)
    except PermissionError:
        old = next(p for p in [EXE + ".old"] + [f"{EXE}.{n}.old" for n in range(1, 100)] if not os.path.exists(p))
        os.replace(EXE, old)
        os.replace(new, EXE)
        print(f"The app was open: its exe is now {old}; delete it once the app is closed.")


def main():
    for name in SHARED:
        with open(os.path.join(HERE, name), "rb") as a, open(os.path.join(NIGHTMARE_TOOLS, name), "rb") as b:
            if a.read() != b.read():
                sys.exit(f"tools\\{name} differs between Arcade Endless and NightmarePOC; make them identical first.")
    os.makedirs(BUILD, exist_ok=True)
    icon = os.path.join(BUILD, "ArcadeEndless.ico")
    draw_icon(icon)
    version = os.path.join(BUILD, "version.txt")
    with open(version, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO)
    dist = os.path.join(BUILD, "dist")
    cmd = [sys.executable, "-m", "PyInstaller", APP, "--name", "ArcadeEndless", "--onefile", "--windowed",
           "--icon", icon, "--version-file", version, "--paths", HERE, "--paths", NIGHTMARE_TOOLS, "--distpath", dist, "--workpath", os.path.join(BUILD, "work"),
           "--specpath", BUILD, "--noconfirm", "--clean", "--log-level", "WARN"]
    subprocess.run(cmd, check=True)
    replace_exe(os.path.join(dist, "ArcadeEndless.exe"))
    shutil.rmtree(BUILD, ignore_errors=True)
    print(f"Built {EXE} ({os.path.getsize(EXE) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

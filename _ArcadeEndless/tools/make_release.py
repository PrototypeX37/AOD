"""Pack what players need into two zips in _ArcadeEndless\\release\\:

  ArcadeEndless-<version>.zip         ArcadeEndless.exe + README.txt (README_PLAYERS.txt)
  ArcadeEndless-<version>-python.zip  the same app as Python source (ArcadeEndless.pyw, both mods' tools) + README.txt
                                      (README_PLAYERS_PYTHON.txt, then README_PLAYERS.txt), for players who won't run an exe

  python make_release.py

Both extract straight into the game folder. Neither holds a pak (game data): the app builds both mods from each
player's own game files. Run make_exe.py first; this refuses an exe older than the code it's built from.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import home  # noqa: E402
import make_exe  # noqa: E402

VERSION = "1.0"
GUIDE = os.path.join(home.MOD, "README_PLAYERS.txt")
PYTHON_GUIDE = os.path.join(home.MOD, "README_PLAYERS_PYTHON.txt")
RELEASE = os.path.join(home.MOD, "release")
EXE_ZIP = os.path.join(RELEASE, f"ArcadeEndless-{VERSION}.zip")
PYTHON_ZIP = os.path.join(RELEASE, f"ArcadeEndless-{VERSION}-python.zip")
BUILD_SCRIPTS = ("make_exe.py", "make_release.py")  # not part of the app


def sources():
    """{path in the zip: file} for the app's code: the .pyw, Arcade's tools and NightmarePOC's tools."""
    files = {"_ArcadeEndless/ArcadeEndless.pyw": make_exe.APP}
    for folder, prefix in ((HERE, "_ArcadeEndless/tools/"), (make_exe.NIGHTMARE_TOOLS, "_NightmarePOC/tools/")):
        for n in sorted(os.listdir(folder)):
            if n.endswith(".py") and n not in BUILD_SCRIPTS:
                files[prefix + n] = os.path.join(folder, n)
    return files


def text(*paths):
    """The files' text joined, with Notepad-friendly line endings."""
    out = ""
    for p in paths:
        with open(p, encoding="utf-8") as f:
            out += f.read()
    return out.replace("\r\n", "\n").replace("\n", "\r\n")


def write_zip(path, files, readme):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, src in files.items():
            z.write(src, name)
        z.writestr("_ArcadeEndless/README.txt", readme)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for i in z.infolist():
            print(f"  {i.filename:40} {i.file_size:>12,} bytes")
    print(f"Wrote {path} ({os.path.getsize(path) / 1e6:.2f} MB)\n")


def main():
    code = sources()
    newest = max(code.values(), key=os.path.getmtime)
    if not os.path.exists(make_exe.EXE) or os.path.getmtime(make_exe.EXE) < os.path.getmtime(newest):
        sys.exit(f"{make_exe.EXE} is older than {newest}: run make_exe.py first.")
    os.makedirs(RELEASE, exist_ok=True)
    write_zip(EXE_ZIP, {"_ArcadeEndless/ArcadeEndless.exe": make_exe.EXE}, text(GUIDE))
    write_zip(PYTHON_ZIP, code, text(PYTHON_GUIDE, GUIDE))


if __name__ == "__main__":
    main()

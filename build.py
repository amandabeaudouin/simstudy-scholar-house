import importlib.util
import os
import py_compile
import sys
import tempfile
import zipfile

if sys.version_info[:2] != (3, 7):
    raise RuntimeError("Requires CPython 3.7 bytecode for this experimental Sims 4 script mod.")
with tempfile.TemporaryDirectory() as folder:
    compiled = os.path.join(folder, "simstudy_sims.pyc")
    py_compile.compile("simstudy_sims.py", cfile=compiled, doraise=True)
    with zipfile.ZipFile("SimStudy_ScholarHouse_Auto.ts4script", "w") as archive:
        archive.write(compiled, arcname="simstudy_sims.pyc")
    with zipfile.ZipFile("SimStudy_ScholarHouse_Auto.ts4script") as archive:
        assert archive.read("simstudy_sims.pyc")[:4] == importlib.util.MAGIC_NUMBER
print("Compiled experimental Sims 4 package")

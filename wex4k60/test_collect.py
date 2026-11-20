#!/usr/bin/env python3
"""Native-offline test of read-only 4K60 evidence tools; no HDMI hardware required."""
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
script=HERE/"collect.sh"
source=script.read_text()
for term in ("sudo ", "nvram -", "pmset -", "kextload", "kmutil load",
             "WriteRegister32", "ioreg -w", "system_profiler -set"):
    assert term not in source, f"forbidden hardware mutation candidate: {term}"
assert "nvram boot-args" in source and "system_profiler SPDisplaysDataType" in source
assert "ioreg -p IOService -l -w0" in source
assert "N97FBGMBus" in source
for stage in ("hdmi30", "hdmi60black", "hdmi_recovered", "dock30"):
    assert stage in source

with tempfile.TemporaryDirectory(prefix="yoga-hdmi60-readonly-") as td:
    root=Path(td)
    inputs=[]
    for stage,clock,hz in (("hdmi30",297000000,"30.00"),
                           ("hdmi60black",594000000,"60.00"),
                           ("hdmi_recovered",297000000,"30.00")):
        directory=root/stage
        directory.mkdir()
        (directory/"ioreg.txt").write_text(
            f'"IOFBCurrentPixelClock" = {clock}\n'
            '"WEXYogaHDMI600Status" = 4\n'
            '"WEXYogaHDMIEDIDABApplied" = Yes\n')
        (directory/"displays.txt").write_text("Resolution: 3840 x 2160\n"
                                              f"Refresh Rate: {hz} Hz\n")
        (directory/"system_and_bootargs.txt").write_text(
            "boot-args -wex-yoga-tc5-sst -wex-yoga-hdmi600 -wex-yoga-hdmi-edid-deep8\n")
        (directory/"USER_OBSERVATION.txt").write_text("Actual picture: unknown\n")
        inputs.append(directory)
    cmd=[sys.executable,str(HERE/"compare.py"),
         str(inputs[0]),str(inputs[1]),str(inputs[2])]
    out=subprocess.check_output(cmd,text=True)
    assert "CHANGED IOFBCurrentPixelClock" in out
    assert "60Hz option with black physical output is not proof" in out
    assert "Differing published property keys: 1" in out
    archive=root/"hdmi30.zip"
    with zipfile.ZipFile(archive,"w") as z:
        for f in inputs[0].iterdir():
            z.write(f,arcname="Yoga_HDMI4K60_hdmi30_demo/"+f.name)
    outzip=subprocess.check_output([sys.executable,str(HERE/"compare.py"),
                                    str(archive),str(inputs[1])],text=True)
    assert "CHANGED IOFBCurrentPixelClock" in outzip
print("PASS read-only capture static guard and compare.py directory/ZIP fixtures")

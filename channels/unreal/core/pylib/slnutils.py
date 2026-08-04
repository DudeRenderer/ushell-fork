# Copyright Epic Games, Inc. All Rights Reserved.

import os
from pathlib import Path

#-------------------------------------------------------------------------------
def find_rider_bin():
    if os.name != "nt":
        return Path("rider64")

    root_dir = Path(os.getenv("ProgramFiles", "c:/Program Files/"))
    root_dir /= "JetBrains"
    candidates = [x for x in root_dir.glob("JetBrains Rider*") if x.is_dir()]
    if candidates:
        candidates.sort(key=lambda x: x.stat().st_mtime)
        candidate = candidates[-1] / "bin/rider64.exe"
        if candidate.is_file():
            return candidate

    return Path("rider64.exe")

def use_uproj(args):
    if args.uproj is None:
        return os.getenv("USHELL_UPROJ", "no").lower() == "yes"
    else:
        return args.uproj.lower() == "yes"

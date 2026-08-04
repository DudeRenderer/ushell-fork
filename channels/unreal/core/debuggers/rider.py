# Copyright Epic Games, Inc. All Rights Reserved.

import os
import subprocess
import slnutils
from pathlib import Path

#-------------------------------------------------------------------------------
def _select_sln_path(ue_context):
    base_dir = ue_context.get_branch() or ue_context.get_project()
    if not base_dir:
        return None
    base_dir = base_dir.get_dir()

    fallbacks = [x for x in base_dir.glob("*.sln") if x.is_file()]
    fallback = fallbacks[0] if fallbacks else base_dir

    state_dir = base_dir / ".idea"
    if not state_dir:
        return fallback

    suffix = ".idea/workspace.xml"
    sln_states = [x for x in state_dir.glob(".idea.*") if (x / suffix).is_file()]
    if not sln_states:
        return fallback

    for sln_state in sorted(sln_states, key=lambda x: (x / suffix).stat().st_mtime):
        sln_stem = sln_state.stem[6:]
        candidate = base_dir / (sln_stem + ".sln")
        if candidate.is_file():
            return candidate

    return fallback

#-------------------------------------------------------------------------------
class Debugger(object):
    def __init__(self, ue_context):
        self._ue_context = ue_context

    def debug(self, exec_context, cmd, *args):
        cmd = exec_context.create_runnable(cmd, *args)
        cmd.launch(suspended=True, new_term=True)
        pid = cmd.get_pid()

        try:
            if not self.attach(pid):
                cmd.kill()
        except:
            cmd.kill()
            raise

    def attach(self, pid, transport=None, host_ip=None):
        if transport and transport != "Default":
            print("Exotic debugger attachment isn't supported!")
            return False

        bin_path = slnutils.find_rider_bin()
        rider_args = (bin_path, "attach-to-process", str(pid))
        if sln_path := _select_sln_path(self._ue_context):
            sln_path = sln_path.absolute()
            rider_args = (*rider_args, str(sln_path))

        try:
            print("Launching Rider:", *rider_args)
            proc = subprocess.Popen(rider_args)
            return True
        except Exception as e:
            print("!! Failed launching Rider:", str(e))
            return False

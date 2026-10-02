#!/bin/bash
# Copyright Epic Games, Inc. All Rights Reserved.

self_dir=$(cygpath --windows --absolute "$(dirname "$0")")
working_dir=$(cygpath --unix "${flow_working_dir:-$LOCALAPPDATA/ushell/.working}")
working_win=$(cygpath --windows --absolute "$working_dir")

# Use the same Windows PowerShell provisioner, with no preinstalled Python.
MSYS2_ARG_CONV_EXCL='*' powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass \
    -File "$self_dir/provision.ps1" -Working "$working_win"
result=$?
if [ "$result" -ne 0 ]; then
    exit "$result"
fi

MSYS2_ARG_CONV_EXCL='*' "$working_dir/python/current/flow_python.exe" -Xutf8 -Esu \
    "$self_dir/../core/system/boot.py" "$@"
result=$?
if [ "$result" -eq 127 ]; then
    exit 0
fi
if [ "$result" -ne 0 ]; then
    echo "boot.py failed [$result]" >&2
fi
exit "$result"

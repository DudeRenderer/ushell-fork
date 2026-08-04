# Copyright Epic Games, Inc. All Rights Reserved.

import os
import tempfile
import unrealcmd
import subprocess as sp
from pathlib import Path

class Ai(unrealcmd.Cmd):
    """
    Launches an AI coding agent configured for ushell. Provides context
    about building Unreal Engine files/modules, optimized file search
    patterns using ripgrep, and modest source control.
    """

    def _add_tools(self, prompt_file):
        print("Tools")

        tools_path = Path(__file__).parent / "tools.md"
        tools_content = tools_path.read_text()

        # Search up the tree for code.rgignore and dirs.rgignore
        rg_cmd = "rg"
        for parent in Path(__file__).parents:
            code_ignore = parent / "code.rgignore"
            if code_ignore.exists():
                rg_cmd += f" --ignore-file={code_ignore}"
                dirs_ignore = parent / "dirs.rgignore"
                if dirs_ignore.exists():
                    rg_cmd += f" --ignore-file={dirs_ignore}"
                break

        tools_content = tools_content.replace("{{RG}}", rg_cmd)

        prompt_file.write(tools_content)
        prompt_file.write("\n")

    def _add_ue_build(self, prompt_file):
        print("Build")

        build_path = Path(__file__).parent / "build.md"
        build_content = build_path.read_text()
        prompt_file.write(build_content)
        prompt_file.write("\n")

    def _add_ue_context(self, prompt_file, ue_context):
        lines = []

        if project := ue_context.get_project():
            lines.append(f"- Project: {project.get_name()}")

        if branch := ue_context.get_branch():
            lines.append(f"- Branch: {branch.get_name()}")

        engine_info = ue_context.get_engine().get_info()
        if (cl := engine_info.get("Changelist", 0)) > 0:
            lines.append(f"- Changelist: {cl}")

        if lines:
            print("Project/branch")
            prompt_file.write("## Unreal Engine Context\n")
            prompt_file.write("\n".join(lines))
            prompt_file.write("\n\n")

    def _add_ue(self, prompt_file):
        try:
            ue_context = self.get_unreal_context()
        except EnvironmentError:
            return

        self._add_ue_build(prompt_file)
        self._add_ue_context(prompt_file, ue_context)

    def _add_perforce(self, prompt_file):
        if Path(".git").is_dir():
            return

        print("Perforce")
        perforce_path = Path(__file__).parent / "perforce.md"
        perforce_content = perforce_path.read_text()
        prompt_file.write(perforce_content)
        prompt_file.write("\n")

    def main(self):
        try:
            ue_context = self.get_unreal_context()
            if branch := ue_context.get_branch():
                os.chdir(branch.get_dir())
        except EnvironmentError:
            pass

        self.print_info("Building prompt")
        prompt_file = tempfile.NamedTemporaryFile(mode='w', delete=True, delete_on_close=False)

        prompt_file.write("- You are a ushell user\n\n")
        self._add_tools(prompt_file)
        self._add_ue(prompt_file)
        self._add_perforce(prompt_file)

        prompt_file.close()

        self.print_info("Launching claude")
        cmd = (
            "claude",
            "--append-system-prompt-file", prompt_file.name
        )
        env = os.environ.copy()
        env["MSYS2_ARG_CONV_EXCL"] = "*"
        sp.run(cmd, env=env)
